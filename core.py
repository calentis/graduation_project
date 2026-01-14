# ============================================================
# core.py # Donatı seçimi ve moment-As dönüşümü
# ============================================================
from typing import Optional, Tuple
from constant import PHI_GRID
from models import BarChoice, MainRebarLayout, MainRebarLayout
from utils import best_spacing_for_phi, ks_from_Kcalc

def calc_K_and_As_from_M(
    M_kNm_per_m: float,
    d_m: float,
    fck: float,
    steel: str
) -> Tuple[float, float, float]:
    """
    K hesabı:
      K (x10^5) = (b*d^2/M) * 1e5
    As:
      As (mm²/m) = (ks/1000) * (M/d)
    """
    if abs(M_kNm_per_m) <= 1e-12:
        return 0.0, 0.0, 0.0

    b_mm = 1000.0
    d_mm = d_m * 1000.0
    M_Nmm = abs(M_kNm_per_m) * 1e6  # kNm/m -> Nmm/m

    K_x1e5 = (b_mm * d_mm**2 / M_Nmm) * 1e2
    ks = ks_from_Kcalc(K_x1e5, fck, steel)
    As = (ks / 1000.0) * (M_Nmm / d_mm)
    return K_x1e5, ks, As

def choose_main_rebar_half_half_same_phi(
    As_req_mm2_per_m: float,
    s_max_main_mm: int,
    s_min_main_mm: int = 70,
    phi_min_main: int = 8,
) -> MainRebarLayout:
    z = BarChoice(0, 0.0, 0.0, 0.0, 0.0)
    if As_req_mm2_per_m <= 1e-12:
        return MainRebarLayout(z, z, 0.0, 0.0, 0.0)

    As_half = As_req_mm2_per_m / 2.0
    best_layout: Optional[MainRebarLayout] = None

    for phi in PHI_GRID:
        if phi < phi_min_main:
            continue

        straight = best_spacing_for_phi(As_half, phi, s_max_main_mm, s_min_main_mm)
        pilye = best_spacing_for_phi(As_half, phi, s_max_main_mm, s_min_main_mm)
        if straight is None or pilye is None:
            continue

        As_prov = straight.As_prov_mm2_per_m + pilye.As_prov_mm2_per_m
        ratio = As_prov / As_req_mm2_per_m
        cand = MainRebarLayout(straight, pilye, As_prov, As_req_mm2_per_m, ratio)

        if best_layout is None or cand.ratio < best_layout.ratio:
            best_layout = cand

    return best_layout if best_layout else MainRebarLayout(z, z, 0.0, As_req_mm2_per_m, 0.0)

def choose_single_layer_rebar(
    As_req_mm2_per_m: float,
    s_max_mm: int,
    s_min_mm: int = 70,
    phi_min: int = 8,
) -> BarChoice:
    if As_req_mm2_per_m <= 1e-12:
        return BarChoice(0, 0.0, 0.0, 0.0, 0.0)

    best: Optional[BarChoice] = None
    for phi in PHI_GRID:
        if phi < phi_min:
            continue
        cand = best_spacing_for_phi(As_req_mm2_per_m, phi, s_max_mm, s_min_mm)
        if cand is None:
            continue
        if best is None or cand.ratio < best.ratio:
            best = cand
    return best if best else BarChoice(0, 0.0, 0.0, 0.0, 0.0)


def choose_distribution_rebar(As_req_mm2_per_m: float) -> BarChoice:
    s_max = 300
    s_min = 70
    phi_min = 6
    return choose_single_layer_rebar(As_req_mm2_per_m, s_max, s_min, phi_min)
