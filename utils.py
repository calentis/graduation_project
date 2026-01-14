# ============================================================
# utils.py # Yardımcı fonksiyonlar
# ============================================================

import math
from typing import Dict, List, Optional, Tuple
from constant import CONC_NODES, K_TABLE_ROWS, M_NODES, PHI_GRID, S_GRID, MIN_CONCRETE_GRADE, MIN_BEAM_WIDTH_MM
from models import BarChoice

# ============================================================
# VALIDATION FUNCTIONS (TS500/TBDY-2018)
# ============================================================

def validate_concrete_grade(concrete: str) -> Tuple[bool, str]:
    """
    Check fck >= 25 (minimum C25 per Turkish code)
    Returns (is_valid, message)
    """
    try:
        fck = parse_concrete(concrete)
        if fck < MIN_CONCRETE_GRADE:
            return False, f"Beton sınıfı C{int(fck)} < C{MIN_CONCRETE_GRADE} (minimum). C{MIN_CONCRETE_GRADE} veya üzeri kullanın."
        return True, f"Beton sınıfı C{int(fck)} ✓ (≥ C{MIN_CONCRETE_GRADE})"
    except ValueError as e:
        return False, str(e)


def validate_beam_width(width_mm: float, direction: str = "") -> Tuple[bool, str]:
    """
    Check beam width >= 250mm per TS500
    Returns (is_valid, message)
    """
    if width_mm < MIN_BEAM_WIDTH_MM:
        return False, f"Kiriş genişliği {direction}{width_mm:.0f}mm < {MIN_BEAM_WIDTH_MM}mm (minimum)"
    return True, f"Kiriş genişliği {direction}{width_mm:.0f}mm ✓ (≥ {MIN_BEAM_WIDTH_MM}mm)"


def validate_coefficient_method_applicability(q: float, g: float, L_min: float, L_max: float) -> Tuple[bool, str, List[str]]:
    """
    Check coefficient method applicability per TS500:
    - q/g <= 2
    - Lmin/Lmax > 0.8
    Returns (is_applicable, summary_message, detail_messages)
    """
    issues = []
    details = []
    
    # Check q/g ratio
    if g > 0:
        qg_ratio = q / g
        if qg_ratio > 2.0:
            issues.append(f"q/g = {qg_ratio:.2f} > 2.0")
            details.append(f"q/g = {qg_ratio:.2f} > 2.0 → Katsayı yöntemi UYGULANAMAZ")
        else:
            details.append(f"q/g = {qg_ratio:.2f} ≤ 2.0 ✓")
    else:
        issues.append("g = 0, q/g hesaplanamaz")
        details.append("g = 0, q/g hesaplanamaz")
    
    # Check span ratio
    if L_max > 0:
        span_ratio = L_min / L_max
        if span_ratio <= 0.8:
            issues.append(f"Lmin/Lmax = {span_ratio:.2f} ≤ 0.8")
            details.append(f"Lmin/Lmax = {span_ratio:.2f} ≤ 0.8 → Katsayı yöntemi UYGULANAMAZ")
        else:
            details.append(f"Lmin/Lmax = {span_ratio:.2f} > 0.8 ✓")
    else:
        issues.append("L_max = 0, oran hesaplanamaz")
        details.append("L_max = 0, oran hesaplanamaz")
    
    is_applicable = len(issues) == 0
    summary = "Katsayı yöntemi uygulanabilir ✓" if is_applicable else f"UYARI: {'; '.join(issues)}"
    return is_applicable, summary, details


def calculate_net_span(L_gross: float, beam_w_left_mm: float, beam_w_right_mm: float) -> float:
    """
    Calculate net span: Lsn = L - w_left/2 - w_right/2
    L_gross in meters, beam widths in mm
    Returns net span in meters
    """
    deduction = (beam_w_left_mm + beam_w_right_mm) / 2000.0  # Convert mm to m
    return max(L_gross - deduction, 0.1)  # Minimum 0.1m


def calculate_loads(h_mm: float, g_additional: float, q_live: float) -> Tuple[float, float, float, float]:
    """
    Calculate loads per TS500:
    - g_self_weight = (h_mm/1000) * 25 kN/m³
    - g_total = g_self_weight + g_additional
    - pd = 1.4*g_total + 1.6*q_live
    
    Returns (g_self_weight, g_total, q_live, pd_factored)
    """
    g_self_weight = (h_mm / 1000.0) * 25.0  # kN/m²
    g_total = g_self_weight + g_additional
    pd_factored = 1.4 * g_total + 1.6 * q_live
    return g_self_weight, g_total, q_live, pd_factored


# ============================================================
# INTERPOLATION AND HELPER FUNCTIONS
# ============================================================

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def best_spacing_for_phi(
    As_req_mm2_per_m: float,
    phi: int,
    s_max_mm: int,
    s_min_mm: int = 70,
    preferred_s_cm: Optional[List[float]] = None,
) -> Optional[BarChoice]:
    if As_req_mm2_per_m <= 1e-12:
        return BarChoice(phi, 0.0, 0.0, 0.0, 0.0)
    if phi not in PHI_GRID:
        return None

    As_req_cm2 = As_req_mm2_per_m / 100.0
    s_max_cm = s_max_mm / 10.0
    s_min_cm = s_min_mm / 10.0

    pj = PHI_GRID.index(phi)
    best: Optional[BarChoice] = None

    if preferred_s_cm:
        for s in preferred_s_cm:
            if s < s_min_cm or s > s_max_cm:
                continue
            As_cm2 = as_cm2_per_m(phi, s)
            if As_cm2 + 1e-12 < As_req_cm2:
                continue
            ratio = As_cm2 / As_req_cm2
            cand = BarChoice(phi, s, As_cm2 * 100.0, As_cm2, ratio)
            if best is None or cand.ratio < best.ratio:
                best = cand
        return best

    for si, s in enumerate(S_GRID):
        if s < s_min_cm or s > s_max_cm:
            continue
        As_cm2 = AS_GRID[si][pj]
        if As_cm2 + 1e-12 < As_req_cm2:
            continue
        ratio = As_cm2 / As_req_cm2
        cand = BarChoice(phi, s, As_cm2 * 100.0, As_cm2, ratio)
        if best is None or cand.ratio < best.ratio:
            best = cand
    return best

def interp_piecewise(points: Dict[float, float], x: float) -> float:
    xs = sorted(points.keys())
    if x <= xs[0]:
        return points[xs[0]]
    if x >= xs[-1]:
        return points[xs[-1]]
    hi = next(i for i in range(1, len(xs)) if xs[i] >= x)
    lo = hi - 1
    x1, x2 = xs[lo], xs[hi]
    t = (x - x1) / (x2 - x1)
    return lerp(points[x1], points[x2], t)


def parse_concrete(name: str) -> float:
    name = name.strip().upper()
    if not name.startswith("C"):
        raise ValueError("Beton sınıfı C30 gibi olmalı.")
    return float(name[1:])


def steel_group(name: str) -> str:
    s = name.strip().upper()
    return "B500" if "500" in s else "S420"


def rho_min_oneway(steel: str) -> float:
    s = steel.strip().upper()
    if "220" in s:
        return 0.003
    return 0.002  # S420 ve S500/B500 için


def rho_min_twoway_dir(steel: str) -> float:
    """
    Minimum reinforcement ratio per direction for two-way slabs.

    Many Turkish RC textbooks use:
    - S420/S500/B500: ρ_min,x = ρ_min,y = 0.0015
    - Lower grade steels may require higher minimum ratios.

    Note: total minimum is checked separately (e.g., ρx + ρy ≥ 0.0035).
    """
    s = steel.strip().upper()
    if "220" in s:
        return 0.002
    return 0.0015


def K_row_concrete_value(row: Tuple, fck: float) -> float:
    K_map = {
        25.0: row[1], 30.0: row[2], 35.0: row[3],
        40.0: row[4], 45.0: row[5], 50.0: row[6],
    }
    if fck <= 25.0:
        return K_map[25.0]
    if fck >= 50.0:
        return K_map[50.0]
    hi = next(i for i in range(1, len(CONC_NODES)) if CONC_NODES[i] >= fck)
    lo = hi - 1
    f1, f2 = CONC_NODES[lo], CONC_NODES[hi]
    t = (fck - f1) / (f2 - f1)
    return lerp(K_map[f1], K_map[f2], t)


def ks_from_Kcalc(Kcalc_x1e5: float, fck: float, steel: str) -> float:
    grp = steel_group(steel)
    Kvals = [K_row_concrete_value(r, fck) for r in K_TABLE_ROWS]  # azalan

    if Kcalc_x1e5 >= Kvals[0]:
        r = K_TABLE_ROWS[0]
        return r[7] if grp == "S420" else r[8]
    if Kcalc_x1e5 <= Kvals[-1]:
        r = K_TABLE_ROWS[-1]
        return r[7] if grp == "S420" else r[8]

    i2 = next(i for i in range(1, len(Kvals)) if Kvals[i] <= Kcalc_x1e5)
    i1 = i2 - 1
    K1, K2 = Kvals[i1], Kvals[i2]
    r1, r2 = K_TABLE_ROWS[i1], K_TABLE_ROWS[i2]

    ks1 = r1[7] if grp == "S420" else r1[8]
    ks2 = r2[7] if grp == "S420" else r2[8]

    t = (Kcalc_x1e5 - K1) / (K2 - K1)
    return lerp(ks1, ks2, t)

def as_cm2_per_m(phi_mm: float, s_cm: float) -> float:
    s_mm = s_cm * 10.0
    a_bar = math.pi * (phi_mm**2) / 4.0  # mm²
    as_mm2_per_m = a_bar * 1000.0 / s_mm
    return as_mm2_per_m / 100.0  # cm²/m

def _pts(vals: List[float]) -> Dict[float, float]:
    return {M_NODES[i]: vals[i] for i in range(len(M_NODES))}

def edge_continuity_note_for_case(
    case_id: int, lx: float, ly: float
) -> str:
    """
    Varsayım (geometriye bağlı):
      - Eğer lx < ly ise: kısa kenarlar y=0 & y=ly (uzunluk=lx), uzun kenarlar x=0 & x=lx (uzunluk=ly)
      - Eğer ly <= lx ise: kısa kenarlar x=0 & x=lx (uzunluk=ly), uzun kenarlar y=0 & y=ly (uzunluk=lx)

    Senaryo 2 ve 3 için "hangi kenar(lar)" bilgisini abak vermiyor.
    Bu yüzden burada sadece tipik/varsayılan bir atama yapıyoruz:
      2: bir kenar süreksiz -> uzun kenarlardan birini (top) süreksiz
      3: iki komşu süreksiz -> bir uzun + bir kısa (top + right)
      6: üç kenar süreksiz -> sadece left sürekli (örnek)
    """
    short_is_x = lx <= ly  # kısa açıklık (L_short) x yönünde mi?

    if short_is_x:
        short_edges = ["y=0", "y=ly"]   # uzunluğu lx (kısa kenar)
        long_edges = ["x=0", "x=lx"]    # uzunluğu ly (uzun kenar)
    else:
        short_edges = ["x=0", "x=lx"]
        long_edges = ["y=0", "y=ly"]

    if case_id == 1:
        cont = short_edges + long_edges
        disc: List[str] = []
    elif case_id == 7:
        cont = []
        disc = short_edges + long_edges
    elif case_id == 4:  # iki kısa kenar süreksiz
        disc = short_edges
        cont = long_edges
    elif case_id == 5:  # iki uzun kenar süreksiz
        disc = long_edges
        cont = short_edges
    elif case_id == 2:  # bir kenar süreksiz (varsayım: bir uzun kenar süreksiz)
        disc = [long_edges[1]]
        cont = [e for e in (short_edges + long_edges) if e not in disc]
    elif case_id == 3:  # iki komşu süreksiz (varsayım: bir uzun + bir kısa)
        disc = [long_edges[1], short_edges[1]]
        cont = [e for e in (short_edges + long_edges) if e not in disc]
    elif case_id == 6:  # üç kenar süreksiz (varsayım: sadece long_edges[0] sürekli)
        cont = [long_edges[0]]
        disc = [e for e in (short_edges + long_edges) if e not in cont]
    else:
        cont = []
        disc = []

    cont_s = ", ".join(cont) if cont else "yok"
    disc_s = ", ".join(disc) if disc else "yok"
    return f"Sürekli kenarlar: {cont_s} | Süreksiz kenarlar: {disc_s} (not: 2/3/6 için varsayım)"

AS_GRID = [[as_cm2_per_m(phi, s) for phi in PHI_GRID] for s in S_GRID]
