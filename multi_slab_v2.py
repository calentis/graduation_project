# ============================================================
# multi_slab.py # Multi-slab system design (TS500/TBDY-2018)
# Fixed version matching textbook methodology
# ============================================================

from typing import Dict, List, Optional, Tuple

from constant import SLAB_CASES, ONEWAY_COEFFICIENTS
from models import (
    GridAxis, SlabPanel, SlabEdge, SlabSystemInput, SlabSystemResult,
    PanelMoments, SupportMomentBalance, DesignOut, ThicknessCheck, 
    LoadAnalysis, BarChoice, MainRebarLayout
)
from core import calc_K_and_As_from_M, choose_main_rebar_half_half_same_phi, choose_single_layer_rebar
from utils import interp_piecewise, parse_concrete, rho_min_oneway, calculate_loads


def compute_multi_slab_system(system: SlabSystemInput) -> SlabSystemResult:
    """Main function to design a multi-slab floor system."""
    x_axis_map = {ax.name: ax.position for ax in system.x_axes}
    y_axis_map = {ax.name: ax.position for ax in system.y_axes}
    
    g_self, g_total, q_live, pd = calculate_loads(
        system.h_mm, system.g_additional, system.q_live
    )
    load_analysis = LoadAnalysis(
        g_self_weight=g_self, g_additional=system.g_additional,
        g_total=g_total, q_live=q_live, pd_factored=pd
    )
    
    result = SlabSystemResult(
        h_mm=system.h_mm, pd_factored=pd, load_analysis=load_analysis
    )
    
    for panel in system.panels:
        # Calculate gross spans from axis positions
        x_start = x_axis_map.get(panel.x_axis_start, 0.0)
        x_end = x_axis_map.get(panel.x_axis_end, panel.lx)
        y_start = y_axis_map.get(panel.y_axis_start, 0.0)
        y_end = y_axis_map.get(panel.y_axis_end, panel.ly)
        
        lx_gross = abs(x_end - x_start) if panel.lx <= 0 else panel.lx
        ly_gross = abs(y_end - y_start) if panel.ly <= 0 else panel.ly
        
        # Calculate net spans (for thickness and two-way calcs)
        beam_deduction = system.beam_width_mm / 1000.0
        
        if panel.cantilever_direction:
            if panel.cantilever_direction in ["x+", "x-"]:
                Lsn_x = lx_gross - beam_deduction / 2
                Lsn_y = ly_gross - beam_deduction
            else:
                Lsn_x = lx_gross - beam_deduction
                Lsn_y = ly_gross - beam_deduction / 2
        else:
            Lsn_x = lx_gross - beam_deduction
            Lsn_y = ly_gross - beam_deduction
        
        Lsn_x, Lsn_y = max(Lsn_x, 0.1), max(Lsn_y, 0.1)
        
        # Determine slab type
        slab_type = panel.determine_type(Lsn_x, Lsn_y)
        m_ratio = panel.get_span_ratio(Lsn_x, Lsn_y)
        
        # Thickness check - FIXED
        if slab_type == "cantilever":
            L_cant = Lsn_x if panel.cantilever_direction in ["x+", "x-"] else Lsn_y
            thk = thickness_check_cantilever(L_cant, system.h_mm)
        elif slab_type == "one_way":
            # ONE-WAY: Use SHORT span / 30 (not long span!)
            L_short_net = min(Lsn_x, Lsn_y)
            thk = thickness_check_oneway(L_short_net, system.h_mm)
        else:
            # TWO-WAY: Use formula with alpha_s
            L_short_net = min(Lsn_x, Lsn_y)
            L_long_net = max(Lsn_x, Lsn_y)
            m = L_long_net / L_short_net
            # alpha_s depends on edge conditions (0 to 1)
            # For Type 3 (2 adjacent edges discontinuous): alpha_s ≈ 0.5
            alpha_s = 0.5 if panel.slab_case_override == 3 else 0.0
            thk = thickness_check_twoway(L_short_net, m, alpha_s, system.h_mm)
        
        result.panel_thickness[panel.panel_id] = thk
        
        # Calculate moments - pass gross spans for one-way
        moments = calculate_panel_moments(
            panel, Lsn_x, Lsn_y, lx_gross, ly_gross, pd, slab_type, m_ratio
        )
        result.panel_moments[panel.panel_id] = moments
    
    # Moment balancing
    result.support_balances = balance_support_moments(system.panels, result.panel_moments)
    apply_balanced_moments(result.panel_moments, result.support_balances)
    
    # Design reinforcement
    fck = parse_concrete(system.concrete)
    d_m = max((system.h_mm - system.cover_mm) / 1000.0, 1e-6)
    d_mm, b_mm = d_m * 1000.0, 1000.0
    s_max_bottom = int(min(1.5 * system.h_mm, 200))
    s_max_top = int(min(2.0 * system.h_mm, 200))
    
    for panel_id, moments in result.panel_moments.items():
        out_x, out_y = design_panel_reinforcement(
            panel_id, moments, d_m, d_mm, b_mm, fck, system.steel,
            system.h_mm, s_max_bottom, s_max_top
        )
        result.panel_designs[panel_id] = (out_x, out_y)
    
    return result


def thickness_check_cantilever(Lsn: float, h_mm: float) -> ThicknessCheck:
    """Cantilever: h >= Ln/12"""
    ln = max(Lsn, 0.10)
    h_min = max((ln * 1000) / 12.0, 80)
    ok = h_mm >= h_min
    note = f"Konsol: h_min=Lsn/12={ln*1000:.0f}/12={h_min:.0f}mm"
    return ThicknessCheck(h_min, ok, note)


def thickness_check_oneway(Lsn_short: float, h_mm: float) -> ThicknessCheck:
    """One-way: h >= Ln/30 (using SHORT span)"""
    ln = max(Lsn_short, 0.10)
    h_min = max((ln * 1000) / 30.0, 80)
    ok = h_mm >= h_min
    note = f"Tek dogrultu: h_min=Lsn/30={ln*1000:.0f}/30={h_min:.0f}mm"
    return ThicknessCheck(h_min, ok, note)


def thickness_check_twoway(Lsn_short: float, m: float, alpha_s: float, h_mm: float) -> ThicknessCheck:
    """Two-way: h >= (Lsn/(15+20/m))*(1-alpha_s/4)"""
    ln = max(Lsn_short, 0.10)
    denom = 15.0 + (20.0 / m) if m > 0 else 15.0
    factor = (1.0 - alpha_s / 4.0)
    h_min = max((ln * 1000) / denom * factor, 80)
    ok = h_mm >= h_min
    note = f"Cift dogrultu: h_min={ln*1000:.0f}/({denom:.1f})*(1-{alpha_s}/4)={h_min:.0f}mm"
    return ThicknessCheck(h_min, ok, note)


def calculate_panel_moments(panel, Lsn_x, Lsn_y, lx_gross, ly_gross, pd, slab_type, m_ratio):
    """Calculate moments for a single panel."""
    moments = PanelMoments(
        panel_id=panel.panel_id, slab_type=slab_type, m_ratio=m_ratio,
        Lsn_x=Lsn_x, Lsn_y=Lsn_y
    )
    
    if slab_type == "cantilever":
        L_cant = Lsn_x if panel.cantilever_direction in ["x+", "x-"] else Lsn_y
        moments.M_cantilever = pd * (L_cant ** 2) / 2.0
        moments.alpha_long_neg = 0.5
        
    elif slab_type == "one_way":
        # ONE-WAY: Use GROSS SHORT span for moments (per textbook)
        L_short_gross = min(lx_gross, ly_gross)
        base = pd * (L_short_gross ** 2)
        
        # Coefficients: M_pos = 9*p*L^2/128, M_neg = p*L^2/8
        M_pos = (9.0 / 128.0) * base
        M_neg = base / 8.0
        
        moments.M_short_pos = M_pos
        moments.M_short_neg = M_neg
        moments.alpha_short_pos = 9.0/128.0
        moments.alpha_short_neg = 1.0/8.0
            
    else:  # two_way
        # TWO-WAY: Use NET SHORT span for moments
        L_short_net = min(Lsn_x, Lsn_y)
        slab_case = panel.slab_case_override or determine_slab_case(panel)
        case = SLAB_CASES.get(slab_case, SLAB_CASES[7])
        
        aS_pos = interp_piecewise(case["short_pos"], m_ratio)
        aS_neg = interp_piecewise(case["short_neg"], m_ratio) if case["short_neg"] else 0.0
        aL_pos, aL_neg = float(case["long_pos"]), float(case["long_neg"])
        
        base = pd * (L_short_net ** 2)
        
        moments.M_short_pos = aS_pos * base
        moments.M_short_neg = aS_neg * base
        moments.M_long_pos = aL_pos * base
        moments.M_long_neg = aL_neg * base
        
        moments.alpha_short_pos, moments.alpha_short_neg = aS_pos, aS_neg
        moments.alpha_long_pos, moments.alpha_long_neg = aL_pos, aL_neg
    
    return moments


def determine_slab_case(panel):
    """Determine ABAK slab case (1-7) from edge conditions."""
    cont_count = sum([
        panel.edge_x_left.is_continuous or panel.edge_x_left.is_fixed,
        panel.edge_x_right.is_continuous or panel.edge_x_right.is_fixed,
        panel.edge_y_bottom.is_continuous or panel.edge_y_bottom.is_fixed,
        panel.edge_y_top.is_continuous or panel.edge_y_top.is_fixed,
    ])
    
    if cont_count == 4: return 1
    if cont_count == 3: return 2
    if cont_count == 2:
        x_cont = (panel.edge_x_left.is_continuous or panel.edge_x_left.is_fixed) and \
                 (panel.edge_x_right.is_continuous or panel.edge_x_right.is_fixed)
        y_cont = (panel.edge_y_bottom.is_continuous or panel.edge_y_bottom.is_fixed) and \
                 (panel.edge_y_top.is_continuous or panel.edge_y_top.is_fixed)
        if x_cont: return 4
        if y_cont: return 5
        return 3
    if cont_count == 1: return 6
    return 7


def balance_support_moments(panels, panel_moments):
    """Balance moments at common supports per textbook methodology."""
    balances = []
    processed_pairs = set()
    
    for i, panel1 in enumerate(panels):
        for j, panel2 in enumerate(panels):
            if i >= j: continue
            
            pair_key = tuple(sorted([panel1.panel_id, panel2.panel_id]))
            if pair_key in processed_pairs: continue
            
            shared = find_shared_support(panel1, panel2)
            if not shared: continue
            
            processed_pairs.add(pair_key)
            
            moments1 = panel_moments.get(panel1.panel_id)
            moments2 = panel_moments.get(panel2.panel_id)
            if not moments1 or not moments2: continue
            
            M1 = get_support_moment(moments1, shared, panel1)
            M2 = get_support_moment(moments2, shared, panel2)
            if M1 < 1e-6 and M2 < 1e-6: continue
            
            M_large, M_small = max(M1, M2), min(M1, M2)
            if M_large < 1e-6: continue
            
            ratio = M_small / M_large
            
            if ratio < 0.8:
                # Distribute 2/3 of difference proportionally to span
                delta_M = (2.0 / 3.0) * (M_large - M_small)
                L1 = moments1.Lsn_y if "y=" in shared else moments1.Lsn_x
                L2 = moments2.Lsn_y if "y=" in shared else moments2.Lsn_x
                L_total = L1 + L2
                
                if M1 > M2:
                    M1_bal = M1 - delta_M * (L1 / L_total)
                    M2_bal = M2 + delta_M * (L2 / L_total)
                else:
                    M1_bal = M1 + delta_M * (L1 / L_total)
                    M2_bal = M2 - delta_M * (L2 / L_total)
                
                M_design = max(M1_bal, M2_bal)
                note = f"Oran={ratio:.2f}<0.8, DeltaM={delta_M:.2f}"
            else:
                M1_bal = M2_bal = M_design = M_large
                note = f"Oran={ratio:.2f}>=0.8, buyuk moment"
            
            balances.append(SupportMomentBalance(
                support_location=f"{panel1.panel_id}/{panel2.panel_id}",
                M_left=M1, M_right=M2,
                M_left_balanced=M1_bal, M_right_balanced=M2_bal,
                M_design=M_design, note=note
            ))
    
    return balances


def find_shared_support(panel1, panel2):
    """Find shared support between panels."""
    if panel1.x_axis_end == panel2.x_axis_start: return f"x={panel1.x_axis_end}"
    if panel2.x_axis_end == panel1.x_axis_start: return f"x={panel2.x_axis_end}"
    if panel1.y_axis_end == panel2.y_axis_start: return f"y={panel1.y_axis_end}"
    if panel2.y_axis_end == panel1.y_axis_start: return f"y={panel2.y_axis_end}"
    return None


def get_support_moment(moments, support, panel):
    """Get negative moment at a support."""
    if moments.slab_type == "cantilever": return moments.M_cantilever
    
    # For D1/D2 junction (y=2), use short direction negative moment
    if moments.slab_type == "two_way":
        # D1 short direction neg moment is at the continuous edges
        return moments.M_short_neg if moments.M_short_neg > 0 else moments.M_long_neg
    
    # For one-way slab
    return moments.M_short_neg if moments.M_short_neg > 0 else moments.M_long_neg


def apply_balanced_moments(panel_moments, balances):
    """Apply balanced moments to panels."""
    for balance in balances:
        parts = balance.support_location.split("/")
        if len(parts) < 2: continue
        
        panel1_id = parts[0].strip()
        if panel1_id in panel_moments:
            m = panel_moments[panel1_id]
            if m.M_long_neg > 1e-6:
                m.M_long_neg = max(m.M_long_neg, balance.M_design)
            if m.M_short_neg > 1e-6:
                m.M_short_neg = max(m.M_short_neg, balance.M_design)


def design_panel_reinforcement(panel_id, moments, d_m, d_mm, b_mm, fck, steel, h_mm, s_max_bottom, s_max_top):
    """Design reinforcement for a panel."""
    rho_min = rho_min_oneway(steel)
    As_min = rho_min * b_mm * d_mm
    
    if moments.slab_type == "cantilever":
        M_neg = moments.M_cantilever
        _, _, As_neg_M = calc_K_and_As_from_M(M_neg, d_m, fck, steel)
        As_neg_req = max(As_neg_M, As_min)
        As_dist_req = As_neg_req * 0.20
        
        out_x = create_design("X (Konsol)", "cantilever", moments, d_m, fck, steel,
                              0, 0, 0, M_neg, As_neg_req, 0.5, s_max_bottom, s_max_top)
        out_y = create_dist_design("Y (Dagitma)", moments, d_m, As_dist_req)
        
    elif moments.slab_type == "one_way":
        M_pos = moments.M_short_pos
        M_neg = moments.M_short_neg
        
        _, _, As_pos_M = calc_K_and_As_from_M(M_pos, d_m, fck, steel)
        _, _, As_neg_M = calc_K_and_As_from_M(M_neg, d_m, fck, steel)
        As_pos_req = max(As_pos_M, As_min)
        As_neg_req = max(As_neg_M, As_min) if M_neg > 1e-6 else 0.0
        As_dist_req = max(As_pos_req * 0.20, 0.0012 * b_mm * h_mm)
        
        out_x = create_design("Ana", "one_way", moments, d_m, fck, steel,
                              M_pos, As_pos_req, 9.0/128.0, M_neg, As_neg_req, 1.0/8.0, s_max_bottom, s_max_top)
        out_y = create_dist_design("Dagitma", moments, d_m, As_dist_req)
        
    else:  # two_way
        x_is_long = moments.Lsn_x >= moments.Lsn_y
        if x_is_long:
            Mx_pos, My_pos = moments.M_long_pos, moments.M_short_pos
            Mx_neg, My_neg = moments.M_long_neg, moments.M_short_neg
            ax_pos, ay_pos = moments.alpha_long_pos, moments.alpha_short_pos
            ax_neg, ay_neg = moments.alpha_long_neg, moments.alpha_short_neg
        else:
            Mx_pos, My_pos = moments.M_short_pos, moments.M_long_pos
            Mx_neg, My_neg = moments.M_short_neg, moments.M_long_neg
            ax_pos, ay_pos = moments.alpha_short_pos, moments.alpha_long_pos
            ax_neg, ay_neg = moments.alpha_short_neg, moments.alpha_long_neg
        
        _, _, Asx_pos_M = calc_K_and_As_from_M(Mx_pos, d_m, fck, steel)
        _, _, Asy_pos_M = calc_K_and_As_from_M(My_pos, d_m, fck, steel)
        _, _, Asx_neg_M = calc_K_and_As_from_M(Mx_neg, d_m, fck, steel)
        _, _, Asy_neg_M = calc_K_and_As_from_M(My_neg, d_m, fck, steel)
        
        Asx_pos_req = max(Asx_pos_M, As_min)
        Asy_pos_req = max(Asy_pos_M, As_min)
        Asx_neg_req = max(Asx_neg_M, As_min) if Mx_neg > 1e-6 else 0.0
        Asy_neg_req = max(Asy_neg_M, As_min) if My_neg > 1e-6 else 0.0
        
        # Check total ratio
        As_min_total = 0.0035 * b_mm * d_mm
        if Asx_pos_req + Asy_pos_req < As_min_total and Asx_pos_req + Asy_pos_req > 1e-12:
            scale = As_min_total / (Asx_pos_req + Asy_pos_req)
            Asx_pos_req *= scale
            Asy_pos_req *= scale
        
        out_x = create_design("X (uzun)", "two_way", moments, d_m, fck, steel,
                              Mx_pos, Asx_pos_req, ax_pos, Mx_neg, Asx_neg_req, ax_neg, s_max_bottom, s_max_top)
        out_y = create_design("Y (kisa)", "two_way", moments, d_m, fck, steel,
                              My_pos, Asy_pos_req, ay_pos, My_neg, Asy_neg_req, ay_neg, s_max_bottom, s_max_top)
    
    return out_x, out_y


def create_design(direction, slab_type, moments, d_m, fck, steel, M_pos, As_pos_req, a_pos,
                  M_neg, As_neg_req, a_neg, s_max_bottom, s_max_top):
    """Create a DesignOut object."""
    Kp, ksp, _ = calc_K_and_As_from_M(M_pos, d_m, fck, steel) if M_pos > 0 else (0, 0, 0)
    Kn, ksn, _ = calc_K_and_As_from_M(M_neg, d_m, fck, steel) if M_neg > 0 else (0, 0, 0)
    
    bottom = choose_main_rebar_half_half_same_phi(As_pos_req, s_max_bottom) if As_pos_req > 0 else None
    top = choose_single_layer_rebar(As_neg_req, s_max_top, 70, 8) if As_neg_req > 0 else None
    
    return DesignOut(
        direction=direction, slab_type=slab_type, slab_case=3,
        slab_case_name="Multi-slab",
        m=moments.m_ratio, L_short=min(moments.Lsn_x, moments.Lsn_y),
        L_long=max(moments.Lsn_x, moments.Lsn_y),
        Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
        a_pos_used=a_pos, M_pos_kNm_per_m=M_pos, Kcalc_pos_x1e5=Kp, ks_pos=ksp,
        As_pos_req_mm2_per_m=As_pos_req, main_bottom_layout=bottom,
        a_neg_used=a_neg, M_neg_kNm_per_m=M_neg, Kcalc_neg_x1e5=Kn, ks_neg=ksn,
        As_neg_req_mm2_per_m=As_neg_req, top_layout=top,
        d_m=d_m, note_spacing=f"s_max={s_max_bottom}/{s_max_top}mm"
    )


def create_dist_design(direction, moments, d_m, As_dist_req):
    """Create distribution reinforcement design."""
    dist_bars = choose_single_layer_rebar(As_dist_req, 300, 70, 8)
    
    return DesignOut(
        direction=direction, slab_type=moments.slab_type, slab_case=0,
        slab_case_name="Dagitma", m=moments.m_ratio,
        L_short=min(moments.Lsn_x, moments.Lsn_y), L_long=max(moments.Lsn_x, moments.Lsn_y),
        Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y, d_m=d_m,
        dist_As_req_mm2_per_m=As_dist_req, dist_bars=dist_bars,
        note_min=f"Dagitma: As={As_dist_req:.0f}mm2/m"
    )


def print_system_results(result: SlabSystemResult) -> None:
    """Print formatted results."""
    print("\n" + "="*80)
    print("  COKLU DOSEME SISTEMI SONUCLARI")
    print("="*80)
    
    if result.load_analysis:
        load = result.load_analysis
        print(f"\nYUK ANALIZI:")
        print(f"  g_kendi = {load.g_self_weight:.2f} kN/m2")
        print(f"  g = {load.g_total:.2f} kN/m2")
        print(f"  q = {load.q_live:.2f} kN/m2")
        print(f"  pd = 1.4*{load.g_total:.2f} + 1.6*{load.q_live:.2f} = {load.pd_factored:.2f} kN/m2")
    
    for panel_id, moments in result.panel_moments.items():
        print(f"\n{panel_id} DOSEMESI:")
        print(f"  Tip: {moments.slab_type}, m={moments.m_ratio:.2f}")
        
        if panel_id in result.panel_thickness:
            thk = result.panel_thickness[panel_id]
            status = "OK" if thk.ok else "YETERSIZ"
            print(f"  Kalinlik: {thk.note} [{status}]")
        
        if moments.slab_type == "cantilever":
            print(f"  M_konsol = {moments.M_cantilever:.2f} kNm/m")
        elif moments.slab_type == "one_way":
            print(f"  M_aciklik = {moments.M_short_pos:.2f} kNm/m")
            print(f"  M_mesnet = {moments.M_short_neg:.2f} kNm/m")
        else:
            print(f"  Kisa: M_pos={moments.M_short_pos:.2f}, M_neg={moments.M_short_neg:.2f} kNm/m")
            print(f"  Uzun: M_pos={moments.M_long_pos:.2f}, M_neg={moments.M_long_neg:.2f} kNm/m")
    
    if result.support_balances:
        print(f"\nMOMENT DENGELEMESI:")
        for bal in result.support_balances:
            print(f"  {bal.support_location}: {bal.M_left:.2f}/{bal.M_right:.2f} -> {bal.M_design:.2f} kNm/m")
    
    print("\n" + "="*80)
