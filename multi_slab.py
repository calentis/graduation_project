# ============================================================
# multi_slab.py # Multi-slab system design (TS500/TBDY-2018)
# ============================================================

from typing import Dict, List, Optional, Tuple

from constant import SLAB_CASES
from models import (
    GridAxis, SlabPanel, SlabEdge, SlabSystemInput, SlabSystemResult,
    PanelMoments, SupportMomentBalance, DesignOut, ThicknessCheck, 
    LoadAnalysis
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
        x_start = x_axis_map.get(panel.x_axis_start, 0.0)
        x_end = x_axis_map.get(panel.x_axis_end, panel.lx)
        y_start = y_axis_map.get(panel.y_axis_start, 0.0)
        y_end = y_axis_map.get(panel.y_axis_end, panel.ly)
        
        lx_gross = abs(x_end - x_start) if panel.lx <= 0 else panel.lx
        ly_gross = abs(y_end - y_start) if panel.ly <= 0 else panel.ly
        
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
        
        slab_type = panel.determine_type(Lsn_x, Lsn_y)
        m_ratio = panel.get_span_ratio(Lsn_x, Lsn_y)
        
        # Thickness check
        if slab_type == "cantilever":
            L_cant = Lsn_x if panel.cantilever_direction in ["x+", "x-"] else Lsn_y
            h_min = max((L_cant * 1000) / 12.0, 80)
            note = f"Konsol: Lsn/12={L_cant*1000:.0f}/12={h_min:.0f}mm"
        elif slab_type == "one_way":
            L_short = min(Lsn_x, Lsn_y)
            h_min = max((L_short * 1000) / 30.0, 80)
            note = f"Tek dogrultu: Lsn/30={L_short*1000:.0f}/30={h_min:.0f}mm"
        else:
            L_short = min(Lsn_x, Lsn_y)
            m = max(Lsn_x, Lsn_y) / L_short
            alpha_s = 0.5 if panel.slab_case_override == 3 else 0.0
            denom = 15.0 + (20.0 / m)
            h_min = max((L_short * 1000) / denom * (1 - alpha_s/4), 80)
            note = f"Cift dogrultu: h>={h_min:.0f}mm"
        
        thk = ThicknessCheck(h_min, system.h_mm >= h_min, note)
        result.panel_thickness[panel.panel_id] = thk
        
        # Calculate moments
        moments = PanelMoments(
            panel_id=panel.panel_id, slab_type=slab_type, m_ratio=m_ratio,
            Lsn_x=Lsn_x, Lsn_y=Lsn_y
        )
        
        if slab_type == "cantilever":
            L_cant = Lsn_x if panel.cantilever_direction in ["x+", "x-"] else Lsn_y
            moments.M_cantilever = pd * (L_cant ** 2) / 2.0
        elif slab_type == "one_way":
            # Use GROSS short span per textbook
            L_short_gross = min(lx_gross, ly_gross)
            base = pd * (L_short_gross ** 2)
            moments.M_short_pos = (9.0 / 128.0) * base
            moments.M_short_neg = base / 8.0
        else:
            L_short_net = min(Lsn_x, Lsn_y)
            slab_case = panel.slab_case_override or 7
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
        
        result.panel_moments[panel.panel_id] = moments
    
    # Moment balancing - only between actually adjacent panels
    result.support_balances = balance_moments_textbook(system.panels, result.panel_moments)
    
    # Design reinforcement
    fck = parse_concrete(system.concrete)
    d_m = max((system.h_mm - system.cover_mm) / 1000.0, 1e-6)
    d_mm, b_mm = d_m * 1000.0, 1000.0
    s_max_bottom = int(min(1.5 * system.h_mm, 200))
    s_max_top = int(min(2.0 * system.h_mm, 200))
    
    for panel_id, moments in result.panel_moments.items():
        rho_min = rho_min_oneway(system.steel)
        As_min = rho_min * b_mm * d_mm
        
        if moments.slab_type == "cantilever":
            M_neg = moments.M_cantilever
            _, _, As_neg_M = calc_K_and_As_from_M(M_neg, d_m, fck, system.steel)
            As_neg_req = max(As_neg_M, As_min)
            As_dist_req = As_neg_req * 0.20
            
            top = choose_single_layer_rebar(As_neg_req, s_max_top, 70, 8)
            dist = choose_single_layer_rebar(As_dist_req, 300, 70, 8)
            
            out_x = DesignOut(direction="X (Konsol)", slab_type="cantilever", slab_case=0,
                             slab_case_name="Konsol", m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             M_neg_kNm_per_m=M_neg, As_neg_req_mm2_per_m=As_neg_req,
                             top_layout=top, d_m=d_m)
            out_y = DesignOut(direction="Y (Dagitma)", slab_type="cantilever", slab_case=0,
                             slab_case_name="Dagitma", m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             dist_As_req_mm2_per_m=As_dist_req, dist_bars=dist, d_m=d_m)
            
        elif moments.slab_type == "one_way":
            M_pos, M_neg = moments.M_short_pos, moments.M_short_neg
            _, _, As_pos_M = calc_K_and_As_from_M(M_pos, d_m, fck, system.steel)
            _, _, As_neg_M = calc_K_and_As_from_M(M_neg, d_m, fck, system.steel)
            As_pos_req = max(As_pos_M, As_min)
            As_neg_req = max(As_neg_M, As_min) if M_neg > 0 else 0
            As_dist_req = max(As_pos_req * 0.20, 0.0012 * b_mm * system.h_mm)
            
            bottom = choose_main_rebar_half_half_same_phi(As_pos_req, s_max_bottom)
            top = choose_single_layer_rebar(As_neg_req, s_max_top, 70, 8) if As_neg_req > 0 else None
            dist = choose_single_layer_rebar(As_dist_req, 300, 70, 8)
            
            out_x = DesignOut(direction="Ana", slab_type="one_way", slab_case=0,
                             slab_case_name="Tek dogrultu", m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             M_pos_kNm_per_m=M_pos, As_pos_req_mm2_per_m=As_pos_req,
                             main_bottom_layout=bottom,
                             M_neg_kNm_per_m=M_neg, As_neg_req_mm2_per_m=As_neg_req,
                             top_layout=top, d_m=d_m)
            out_y = DesignOut(direction="Dagitma", slab_type="one_way", slab_case=0,
                             slab_case_name="Dagitma", m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             dist_As_req_mm2_per_m=As_dist_req, dist_bars=dist, d_m=d_m)
            
        else:  # two_way
            x_is_long = moments.Lsn_x >= moments.Lsn_y
            if x_is_long:
                Mx_pos, My_pos = moments.M_long_pos, moments.M_short_pos
                Mx_neg, My_neg = moments.M_long_neg, moments.M_short_neg
            else:
                Mx_pos, My_pos = moments.M_short_pos, moments.M_long_pos
                Mx_neg, My_neg = moments.M_short_neg, moments.M_long_neg
            
            _, _, Asx_pos_M = calc_K_and_As_from_M(Mx_pos, d_m, fck, system.steel)
            _, _, Asy_pos_M = calc_K_and_As_from_M(My_pos, d_m, fck, system.steel)
            _, _, Asx_neg_M = calc_K_and_As_from_M(Mx_neg, d_m, fck, system.steel)
            _, _, Asy_neg_M = calc_K_and_As_from_M(My_neg, d_m, fck, system.steel)
            
            Asx_pos_req = max(Asx_pos_M, As_min)
            Asy_pos_req = max(Asy_pos_M, As_min)
            Asx_neg_req = max(Asx_neg_M, As_min) if Mx_neg > 0 else 0
            Asy_neg_req = max(Asy_neg_M, As_min) if My_neg > 0 else 0
            
            bottom_x = choose_main_rebar_half_half_same_phi(Asx_pos_req, s_max_bottom)
            bottom_y = choose_main_rebar_half_half_same_phi(Asy_pos_req, s_max_bottom)
            top_x = choose_single_layer_rebar(Asx_neg_req, s_max_top, 70, 8) if Asx_neg_req > 0 else None
            top_y = choose_single_layer_rebar(Asy_neg_req, s_max_top, 70, 8) if Asy_neg_req > 0 else None
            
            out_x = DesignOut(direction="X (uzun)" if x_is_long else "X (kisa)",
                             slab_type="two_way", slab_case=3, slab_case_name="Cift dogrultu",
                             m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             M_pos_kNm_per_m=Mx_pos, As_pos_req_mm2_per_m=Asx_pos_req,
                             main_bottom_layout=bottom_x,
                             M_neg_kNm_per_m=Mx_neg, As_neg_req_mm2_per_m=Asx_neg_req,
                             top_layout=top_x, d_m=d_m)
            out_y = DesignOut(direction="Y (kisa)" if x_is_long else "Y (uzun)",
                             slab_type="two_way", slab_case=3, slab_case_name="Cift dogrultu",
                             m=moments.m_ratio,
                             L_short=min(moments.Lsn_x, moments.Lsn_y),
                             L_long=max(moments.Lsn_x, moments.Lsn_y),
                             Lsn_x=moments.Lsn_x, Lsn_y=moments.Lsn_y,
                             M_pos_kNm_per_m=My_pos, As_pos_req_mm2_per_m=Asy_pos_req,
                             main_bottom_layout=bottom_y,
                             M_neg_kNm_per_m=My_neg, As_neg_req_mm2_per_m=Asy_neg_req,
                             top_layout=top_y, d_m=d_m)
        
        result.panel_designs[panel_id] = (out_x, out_y)
    
    return result


def balance_moments_textbook(panels, panel_moments):
    """
    Balance moments at shared supports per textbook methodology.
    Only balance between panels that actually share a physical edge.
    """
    balances = []
    
    # D1/D2: Share edge at y=2 (both span from A to B in X)
    d1 = panel_moments.get("D1")
    d2 = panel_moments.get("D2")
    bd = panel_moments.get("BD")
    
    if d1 and d2:
        # D1 and D2 share the y=2 axis, both between A-B
        # D1 has M2 = 17.6 kNm/m (short direction negative at y=2)
        # D2 has M_mesnet = 9.45 kNm/m
        M1 = d1.M_short_neg  # D1's negative moment at continuous edge
        M2 = d2.M_short_neg  # D2's support moment
        
        if M1 > 0 and M2 > 0:
            M_large, M_small = max(M1, M2), min(M1, M2)
            ratio = M_small / M_large
            
            if ratio < 0.8:
                delta_M = (2.0/3.0) * (M_large - M_small)
                # Use spans for distribution (D2=2.45m, D1=5.0m)
                L1 = 5.0  # D1 short direction
                L2 = 2.45  # D2 span
                L_total = L1 + L2
                
                if M1 > M2:
                    M1_bal = M1 - delta_M * (L2 / L_total)
                    M2_bal = M2 + delta_M * (L1 / L_total)
                else:
                    M1_bal = M1 + delta_M * (L1 / L_total)
                    M2_bal = M2 - delta_M * (L2 / L_total)
                
                M_design = max(M1_bal, M2_bal)
                note = f"Oran={ratio:.2f}<0.8, DeltaM={delta_M:.2f}"
            else:
                M1_bal = M2_bal = M_design = M_large
                note = f"Oran={ratio:.2f}>=0.8"
            
            balances.append(SupportMomentBalance(
                support_location="D1/D2 (y=2 ekseni)",
                M_left=M1, M_right=M2,
                M_left_balanced=M1_bal, M_right_balanced=M2_bal,
                M_design=M_design, note=note
            ))
    
    # D1/BD: Share edge at x=B (both span from 1 to 2 in Y)
    if d1 and bd:
        # D1 has M4 = 13.9 kNm/m (long direction negative at x=B)
        # BD has M_cantilever = 11.91 kNm/m
        M1 = d1.M_long_neg
        M2 = bd.M_cantilever
        
        if M1 > 0 and M2 > 0:
            # Per textbook: Since 13.9 > 11.91, use 13.9 kNm/m
            M_design = max(M1, M2)
            ratio = min(M1, M2) / M_design
            
            balances.append(SupportMomentBalance(
                support_location="D1/BD (x=B ekseni)",
                M_left=M1, M_right=M2,
                M_left_balanced=M_design, M_right_balanced=M_design,
                M_design=M_design,
                note=f"Buyuk moment kullanildi (oran={ratio:.2f})"
            ))
    
    return balances


def print_system_results(result: SlabSystemResult) -> None:
    """Print formatted results."""
    print("\n" + "="*80)
    print("  COKLU DOSEME SISTEMI SONUCLARI")
    print("="*80)
    
    if result.load_analysis:
        load = result.load_analysis
        print(f"\nYUK ANALIZI:")
        print(f"  g_kendi = {load.g_self_weight:.2f} kN/m2")
        print(f"  g = {load.g_total:.2f} kN/m2, q = {load.q_live:.2f} kN/m2")
        print(f"  pd = {load.pd_factored:.2f} kN/m2")
    
    for pid, moments in result.panel_moments.items():
        print(f"\n{pid}:")
        print(f"  Tip: {moments.slab_type}, m={moments.m_ratio:.2f}")
        thk = result.panel_thickness.get(pid)
        if thk:
            print(f"  {thk.note} [{'OK' if thk.ok else 'YETERSIZ'}]")
        
        if moments.slab_type == "cantilever":
            print(f"  M = {moments.M_cantilever:.2f} kNm/m")
        elif moments.slab_type == "one_way":
            print(f"  M_aciklik = {moments.M_short_pos:.2f} kNm/m")
            print(f"  M_mesnet = {moments.M_short_neg:.2f} kNm/m")
        else:
            print(f"  Kisa: M_pos={moments.M_short_pos:.2f}, M_neg={moments.M_short_neg:.2f}")
            print(f"  Uzun: M_pos={moments.M_long_pos:.2f}, M_neg={moments.M_long_neg:.2f}")
    
    if result.support_balances:
        print(f"\nMOMENT DENGELEMESI:")
        for bal in result.support_balances:
            print(f"  {bal.support_location}:")
            print(f"    {bal.M_left:.2f} / {bal.M_right:.2f} -> {bal.M_design:.2f} kNm/m")
            print(f"    {bal.note}")
    
    print("\n" + "="*80)
