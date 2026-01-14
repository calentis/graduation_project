# ============================================
# design.py # Tasarım ana modülü (TS500/TBDY-2018)
# ============================================
from typing import Tuple
from constant import SLAB_CASES, ONEWAY_COEFFICIENTS
from models import DesignOut, InputData, ThicknessCheck, LoadAnalysis
from core import calc_K_and_As_from_M, choose_distribution_rebar, choose_main_rebar_half_half_same_phi, choose_single_layer_rebar
from utils import (
    edge_continuity_note_for_case, interp_piecewise, parse_concrete, rho_min_oneway,
    calculate_net_span, calculate_loads, validate_coefficient_method_applicability
)


def compute(data: InputData) -> Tuple[DesignOut, DesignOut, ThicknessCheck, LoadAnalysis]:
    """
    Main computation function for slab design.
    Returns (design_x, design_y, thickness_check, load_analysis)
    """
    # ========================================================
    # STEP 1: NET SPANS (Lsn = L - w_left/2 - w_right/2)
    # ========================================================
    Lsn_x = calculate_net_span(data.lx, data.beam_w_left_x, data.beam_w_right_x)
    Lsn_y = calculate_net_span(data.ly, data.beam_w_left_y, data.beam_w_right_y)
    
    L_short_net = min(Lsn_x, Lsn_y)
    L_long_net = max(Lsn_x, Lsn_y)
    
    # Also track gross spans for reference
    L_short = min(data.lx, data.ly)
    L_long = max(data.lx, data.ly)
    
    # ========================================================
    # STEP 2: SLAB TYPE DETERMINATION (m = Llong_net / Lshort_net)
    # ========================================================
    m = L_long_net / L_short_net if L_short_net > 0.01 else 1.0
    if data.slab_case == 8:
        slab_type = "one_way"
    else:
        slab_type = "one_way" if m > 2.0 else "two_way"
    
    # ========================================================
    # STEP 3: LOAD ANALYSIS (pd = 1.4g + 1.6q)
    # ========================================================
    g_self, g_total, q_live, pd = calculate_loads(data.h_mm, data.g_additional, data.q_live)
    load_analysis = LoadAnalysis(
        g_self_weight=g_self,
        g_additional=data.g_additional,
        g_total=g_total,
        q_live=q_live,
        pd_factored=pd
    )
    
    # Coefficient method applicability check
    coef_applicable, coef_msg, coef_details = validate_coefficient_method_applicability(
        q_live, g_total, L_short_net, L_long_net
    )
    
    # ========================================================
    # STEP 4: THICKNESS CHECK
    # ========================================================
    if slab_type == "one_way":
        thk = thickness_check_oneway(Lsn=L_long_net, h_mm=data.h_mm)
    else:
        thk = thickness_check_twoway(
            Lsn_short=L_short_net, Lsn_long=L_long_net, 
            h_mm=data.h_mm, alpha_s=0.0
        )
    
    # ========================================================
    # STEP 5: EFFECTIVE DEPTH AND MATERIAL
    # ========================================================
    d_m = max((data.h_mm - data.cover_mm) / 1000.0, 1e-6)
    d_mm = d_m * 1000.0
    b_mm = 1000.0
    fck = parse_concrete(data.concrete)
    
    # Spacing limits
    s_max_bottom = int(min(1.5 * data.h_mm, 200))  # TS500: min(1.5h, 200mm)
    s_max_top = int(min(2.0 * data.h_mm, 200))
    
    # X is long direction?
    x_is_long = data.lx >= data.ly
    
    # ========================================================
    # ONE-WAY SLAB DESIGN
    # ========================================================
    if slab_type == "one_way":
        out_x, out_y = compute_oneway(
            data=data, pd=pd, 
            Lsn_x=Lsn_x, Lsn_y=Lsn_y, 
            L_short=L_short, L_long=L_long,
            L_short_net=L_short_net, L_long_net=L_long_net,
            m=m, d_m=d_m, d_mm=d_mm, b_mm=b_mm, fck=fck,
            s_max_bottom=s_max_bottom, s_max_top=s_max_top,
            x_is_long=x_is_long, coef_msg=coef_msg
        )
        return out_x, out_y, thk, load_analysis
    
    # ========================================================
    # TWO-WAY SLAB DESIGN
    # ========================================================
    out_x, out_y = compute_twoway(
        data=data, pd=pd,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y,
        L_short=L_short, L_long=L_long,
        L_short_net=L_short_net, L_long_net=L_long_net,
        m=m, d_m=d_m, d_mm=d_mm, b_mm=b_mm, fck=fck,
        s_max_bottom=s_max_bottom, s_max_top=s_max_top,
        x_is_long=x_is_long
    )
    return out_x, out_y, thk, load_analysis


def compute_oneway(
    data: InputData, pd: float,
    Lsn_x: float, Lsn_y: float,
    L_short: float, L_long: float,
    L_short_net: float, L_long_net: float,
    m: float, d_m: float, d_mm: float, b_mm: float, fck: float,
    s_max_bottom: int, s_max_top: int,
    x_is_long: bool, coef_msg: str
) -> Tuple[DesignOut, DesignOut]:
    """One-way slab design using coefficient method per TS500"""
    
    # Determine span type for coefficients
    slab_case = data.slab_case
    if slab_case == 8:  # 4 edges discontinuous = simple span
        coef_type = "cantilever"
    elif slab_case == 7:  # 4 edges discontinuous = simple span
        coef_type = "simple"
    elif slab_case == 1:  # 4 edges continuous = both ends continuous
        coef_type = "both_ends_continuous"
    elif slab_case in [2, 3, 4, 5, 6]:  # One end continuous
        coef_type = "one_end_continuous"
    else:
        coef_type = "simple"
    
    coefs = ONEWAY_COEFFICIENTS.get(coef_type, ONEWAY_COEFFICIENTS["simple"])
    
    # Calculate moments using coefficient method
    # One-way slabs span in the SHORT direction (standard assumption).
    # Cantilevers span in the direction of the overhang (usually Short).
    # So we use L_short_net for the moment calculation.
    
    # Note: If a slab is supported on SHORT edges, it would span LONG.
    # But TS500 definition of one-way (m>2) implies support on long edges -> spans short.
    # We proceed with L_short_net.
    
    span_len = L_short_net
    base = pd * (span_len ** 2)
    
    M_pos = coefs.get("pos", 1/8) * base
    M_neg = coefs.get("neg", 0.0) * base
    if "neg_cont" in coefs:
        M_neg = coefs["neg_cont"] * base
    
    # Assign moments based on SPAN direction.
    # If x_is_long (Lx >= Ly), the Short direction is Y.
    # So the slab spans in Y. My gets the moments.
    if x_is_long:
        Mx_pos, My_pos = 0.0, M_pos
        Mx_neg, My_neg = 0.0, M_neg
    else:
        # Lx < Ly. Short direction is X. Spans in X.
        Mx_pos, My_pos = M_pos, 0.0
        Mx_neg, My_neg = M_neg, 0.0
    
    # Minimum reinforcement: Asmin = ρ_min * b * d
    rho_min = rho_min_oneway(data.steel)
    Asmin_main = rho_min * b_mm * d_mm
    
    # Calculate As from moment
    _, _, Asx_M = calc_K_and_As_from_M(Mx_pos, d_m, fck, data.steel)
    _, _, Asy_M = calc_K_and_As_from_M(My_pos, d_m, fck, data.steel)
    _, _, Asx_neg_M = calc_K_and_As_from_M(Mx_neg, d_m, fck, data.steel)
    _, _, Asy_neg_M = calc_K_and_As_from_M(My_neg, d_m, fck, data.steel)
    
    # Apply minimum reinforcement
    note_x = ""
    note_y = ""
    
    if Mx_pos > 1e-9:
        Asx_req = max(Asx_M, Asmin_main)
        note_x = f"ρ_min={rho_min:.4f}, Asmin={Asmin_main:.0f}mm²/m"
    else:
        Asx_req = 0.0
        
    if My_pos > 1e-9:
        Asy_req = max(Asy_M, Asmin_main)
        note_y = f"ρ_min={rho_min:.4f}, Asmin={Asmin_main:.0f}mm²/m"
    else:
        Asy_req = 0.0
    
    # Negative moment reinforcement
    Asx_neg_req = max(Asx_neg_M, Asmin_main) if Mx_neg > 1e-9 else 0.0
    Asy_neg_req = max(Asy_neg_M, Asmin_main) if My_neg > 1e-9 else 0.0
    
    case_name = SLAB_CASES.get(data.slab_case, SLAB_CASES[7])["name"]
    edges_note = f"Tek doğrultu: {coef_type} kabulü. {coef_msg}"
    
    # Build design outputs
    out_x = build_design(
        direction="X", slab_type="one_way",
        slab_case=data.slab_case, slab_case_name=case_name,
        m=m, L_short=L_short, L_long=L_long,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y,
        d_m=d_m, fck=fck, steel=data.steel,
        a_pos=coefs.get("pos", 1/8) if Mx_pos > 1e-9 else 0.0, 
        M_pos=Mx_pos, As_pos_req=Asx_req,        
        a_neg=coefs.get("neg", 0.0), M_neg=Mx_neg, As_neg_req=Asx_neg_req,
        s_max_bottom_mm=s_max_bottom, s_max_top_mm=s_max_top,
        note_min=note_x, edges_note=edges_note
    )
    out_y = build_design(
        direction="Y", slab_type="one_way",
        slab_case=data.slab_case, slab_case_name=case_name,
        m=m, L_short=L_short, L_long=L_long,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y,
        d_m=d_m, fck=fck, steel=data.steel,
        a_pos=coefs.get("pos", 1/8) if My_pos > 1e-9 else 0.0, 
        M_pos=My_pos, As_pos_req=Asy_req,
        a_neg=coefs.get("neg", 0.0), M_neg=My_neg, As_neg_req=Asy_neg_req,
        s_max_bottom_mm=s_max_bottom, s_max_top_mm=s_max_top,
        note_min=note_y, edges_note=edges_note
    )
    
    # Distribution reinforcement (As_main / 5) per TS500
    main = out_x if out_x.M_pos_kNm_per_m > 0 else out_y
    dist = out_y if main.direction == "X" else out_x
    
    if main.As_pos_req_mm2_per_m > 0:
        As_dagitma_min1 = main.As_pos_req_mm2_per_m * 0.20  # 20% of main
        As_dagitma_min2 = 0.0012 * b_mm * data.h_mm  # 0.12% of gross section
        dist.dist_As_req_mm2_per_m = max(As_dagitma_min1, As_dagitma_min2)
        dist.dist_bars = choose_distribution_rebar(dist.dist_As_req_mm2_per_m)
        dist.note_min = f"Dağıtma: max(As_main×0.20, 0.0012×b×h)={dist.dist_As_req_mm2_per_m:.0f}mm²/m"
    
    return out_x, out_y


def compute_twoway(
    data: InputData, pd: float,
    Lsn_x: float, Lsn_y: float,
    L_short: float, L_long: float,
    L_short_net: float, L_long_net: float,
    m: float, d_m: float, d_mm: float, b_mm: float, fck: float,
    s_max_bottom: int, s_max_top: int,
    x_is_long: bool
) -> Tuple[DesignOut, DesignOut]:
    """Two-way slab design using ABAK coefficient method"""
    
    case = SLAB_CASES.get(data.slab_case, SLAB_CASES[7])
    case_name = case["name"]
    
    # Get coefficients from ABAK tables
    aS_pos = interp_piecewise(case["short_pos"], m)
    aS_neg = interp_piecewise(case["short_neg"], m) if case["short_neg"] else 0.0
    aL_pos = float(case["long_pos"])
    aL_neg = float(case["long_neg"])
    
    # Calculate moments: M = α × pd × Lsn²
    # Use net span of short direction per TS500
    base = pd * (L_short_net ** 2)
    
    M_short_pos = aS_pos * base
    M_short_neg = aS_neg * base
    M_long_pos = aL_pos * base
    M_long_neg = aL_neg * base
    
    # Assign to X/Y based on which is long
    if x_is_long:
        Mx_pos, My_pos = M_long_pos, M_short_pos
        Mx_neg, My_neg = M_long_neg, M_short_neg
        ax_pos, ay_pos = aL_pos, aS_pos
        ax_neg, ay_neg = aL_neg, aS_neg
    else:
        Mx_pos, My_pos = M_short_pos, M_long_pos
        Mx_neg, My_neg = M_short_neg, M_long_neg
        ax_pos, ay_pos = aS_pos, aL_pos
        ax_neg, ay_neg = aS_neg, aL_neg
    
    # Calculate As from moments
    _, _, Asx_pos_M = calc_K_and_As_from_M(Mx_pos, d_m, fck, data.steel)
    _, _, Asy_pos_M = calc_K_and_As_from_M(My_pos, d_m, fck, data.steel)
    _, _, Asx_neg_M = calc_K_and_As_from_M(Mx_neg, d_m, fck, data.steel)
    _, _, Asy_neg_M = calc_K_and_As_from_M(My_neg, d_m, fck, data.steel)
    
    # Minimum reinforcement checks
    # 1. Each direction: ρ >= 0.002
    rho_min_single = rho_min_oneway(data.steel)
    As_min_single = rho_min_single * b_mm * d_mm
    
    Asx_pos_req = max(Asx_pos_M, As_min_single)
    Asy_pos_req = max(Asy_pos_M, As_min_single)
    
    # 2. Total: ρx + ρy >= 0.0035
    As_min_total = 0.0035 * b_mm * d_mm
    As_sum = Asx_pos_req + Asy_pos_req
    
    if As_sum < As_min_total and As_sum > 1e-12:
        scale = As_min_total / As_sum
        Asx_pos_req *= scale
        Asy_pos_req *= scale
        note_total = f"ρx+ρy<0.0035 → ölçeklendi (×{scale:.2f})"
    else:
        note_total = f"ρx+ρy={As_sum/(b_mm*d_mm):.4f}≥0.0035 ✓"
    
    # Negative moment reinforcement
    As_top_min = 0.002 * b_mm * d_mm
    Asx_neg_req = max(Asx_neg_M, As_top_min) if Mx_neg > 1e-12 else 0.0
    Asy_neg_req = max(Asy_neg_M, As_top_min) if My_neg > 1e-12 else 0.0
    
    edges_note = edge_continuity_note_for_case(data.slab_case, data.lx, data.ly)
    
    out_x = build_design(
        direction="X", slab_type="two_way",
        slab_case=data.slab_case, slab_case_name=case_name,
        m=m, L_short=L_short, L_long=L_long,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y,
        d_m=d_m, fck=fck, steel=data.steel,
        a_pos=ax_pos, M_pos=Mx_pos, As_pos_req=Asx_pos_req,
        a_neg=ax_neg, M_neg=Mx_neg, As_neg_req=Asx_neg_req,
        s_max_bottom_mm=s_max_bottom, s_max_top_mm=s_max_top,
        note_min=note_total, edges_note=edges_note
    )
    out_y = build_design(
        direction="Y", slab_type="two_way",
        slab_case=data.slab_case, slab_case_name=case_name,
        m=m, L_short=L_short, L_long=L_long,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y,
        d_m=d_m, fck=fck, steel=data.steel,
        a_pos=ay_pos, M_pos=My_pos, As_pos_req=Asy_pos_req,
        a_neg=ay_neg, M_neg=My_neg, As_neg_req=Asy_neg_req,
        s_max_bottom_mm=s_max_bottom, s_max_top_mm=s_max_top,
        note_min=note_total, edges_note=edges_note
    )
    
    return out_x, out_y


def thickness_check_oneway(Lsn: float, h_mm: float) -> ThicknessCheck:
    """
    One-way slab thickness check per TS500
    h >= Ln/30 (README says /30, not /25)
    """
    ln = max(Lsn, 0.10)
    h_min = max((ln * 1000) / 30.0, 80)  # Fixed: /30 per README
    ok = h_mm >= h_min
    note = f"Tek doğrultu: h_min=Lsn/30={ln:.3f}×1000/30={h_min:.1f}mm (min 80mm)"
    return ThicknessCheck(h_min, ok, note)


def thickness_check_twoway(
    Lsn_short: float, Lsn_long: float, h_mm: float, alpha_s: float = 0.0
) -> ThicknessCheck:
    """
    Two-way slab thickness check per TS500 (D0U2 formula)
    h >= (Lsn / (15 + 20/m)) × (1 - αs/4)
    """
    m = max(Lsn_long / Lsn_short, 1.0) if Lsn_short > 0.01 else 1.0
    factor = (1.0 - alpha_s / 4.0)
    denom = 15.0 + (20.0 / m)
    h_min = max((Lsn_short * 1000) / denom * factor, 80)
    ok = h_mm >= h_min
    note = f"Çift doğrultu: h_min=Lsn/(15+20/m)×(1-αs/4), m={m:.2f}, αs={alpha_s:.1f} → h_min={h_min:.1f}mm"
    return ThicknessCheck(h_min, ok, note)


def build_design(
    direction: str,
    slab_type: str,
    slab_case: int,
    slab_case_name: str,
    m: float,
    L_short: float,
    L_long: float,
    Lsn_x: float,
    Lsn_y: float,
    d_m: float,
    fck: float,
    steel: str,
    a_pos: float,
    M_pos: float,
    As_pos_req: float,
    a_neg: float,
    M_neg: float,
    As_neg_req: float,
    s_max_bottom_mm: int,
    s_max_top_mm: int,
    note_min: str,
    edges_note: str
) -> DesignOut:
    """Build a DesignOut object with rebar selection"""
    
    # Calculate K and ks for record
    Kp, ksp, _ = calc_K_and_As_from_M(M_pos, d_m, fck, steel)
    Kn, ksn, _ = calc_K_and_As_from_M(M_neg, d_m, fck, steel)
    
    # Select bottom reinforcement (50% straight + 50% pilye)
    bottom_layout = choose_main_rebar_half_half_same_phi(
        As_req_mm2_per_m=As_pos_req,
        s_max_main_mm=s_max_bottom_mm,
        s_min_main_mm=70,
        phi_min_main=8,
    )
    
    # Select top reinforcement
    top_layout = choose_single_layer_rebar(
        As_req_mm2_per_m=As_neg_req,
        s_max_mm=s_max_top_mm,
        s_min_mm=70,
        phi_min=8
    )
    
    note_spacing = f"Alt s_max={s_max_bottom_mm}mm | Üst s_max={s_max_top_mm}mm"
    
    return DesignOut(
        direction=direction,
        slab_type=slab_type,
        slab_case=slab_case,
        slab_case_name=slab_case_name,
        m=m,
        L_short=L_short,
        L_long=L_long,
        Lsn_x=Lsn_x,
        Lsn_y=Lsn_y,
        a_pos_used=a_pos,
        M_pos_kNm_per_m=M_pos,
        Kcalc_pos_x1e5=Kp,
        ks_pos=ksp,
        As_pos_req_mm2_per_m=As_pos_req,
        main_bottom_layout=bottom_layout,
        a_neg_used=a_neg,
        M_neg_kNm_per_m=M_neg,
        Kcalc_neg_x1e5=Kn,
        ks_neg=ksn,
        As_neg_req_mm2_per_m=As_neg_req,
        top_layout=top_layout,
        d_m=d_m,
        note_min=note_min,
        note_spacing=note_spacing,
        edges_continuity_note=edges_note
    )