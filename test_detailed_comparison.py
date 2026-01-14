#!/usr/bin/env python3
"""
Detailed comparison of program output vs textbook Örnek 8-2 values.
"""

from models import GridAxis, SlabPanel, SlabEdge, SlabSystemInput
from multi_slab import compute_multi_slab_system

def create_ornek_8_2():
    """Create exact system from textbook."""
    x_axes = [
        GridAxis("A", 0.0),
        GridAxis("B", 6.0),
        GridAxis("C", 7.5),
    ]
    y_axes = [
        GridAxis("1", 0.0),
        GridAxis("2", 5.0),
        GridAxis("3", 7.45),
    ]
    
    # D1: Two-way slab, Type 3 (iki komşu kenar süreksiz)
    d1 = SlabPanel(
        panel_id="D1",
        x_axis_start="A", x_axis_end="B",
        y_axis_start="1", y_axis_end="2",
        lx=6.0, ly=5.0,
        slab_case_override=3,
        edge_x_left=SlabEdge(is_fixed=True),
        edge_x_right=SlabEdge(is_continuous=True, adjacent_slab_id="BD"),
        edge_y_bottom=SlabEdge(is_fixed=True),
        edge_y_top=SlabEdge(is_continuous=True, adjacent_slab_id="D2"),
    )
    
    # D2: One-way slab
    d2 = SlabPanel(
        panel_id="D2",
        x_axis_start="A", x_axis_end="B",
        y_axis_start="2", y_axis_end="3",
        lx=6.0, ly=2.45,
        slab_type="one_way",
        edge_x_left=SlabEdge(is_fixed=True),
        edge_x_right=SlabEdge(is_fixed=True),
        edge_y_bottom=SlabEdge(is_continuous=True, adjacent_slab_id="D1"),
        edge_y_top=SlabEdge(is_fixed=True),
    )
    
    # BD: Cantilever (balcony)
    bd = SlabPanel(
        panel_id="BD",
        x_axis_start="B", x_axis_end="C",
        y_axis_start="1", y_axis_end="2",
        lx=1.5, ly=5.0,
        slab_type="cantilever",
        cantilever_direction="x+",
        edge_x_left=SlabEdge(is_continuous=True, adjacent_slab_id="D1"),
        edge_x_right=SlabEdge(is_free=True),
    )
    
    return SlabSystemInput(
        x_axes=x_axes, y_axes=y_axes,
        panels=[d1, d2, bd],
        h_mm=140.0, cover_mm=20.0,
        concrete="C25", steel="S420",
        beam_width_mm=250.0,
        g_additional=1.5, q_live=3.5,
    )


def compare(name, calculated, expected, tolerance=0.1):
    """Compare values and return status."""
    diff = abs(calculated - expected)
    pct = (diff / expected * 100) if expected != 0 else 0
    status = "OK" if diff <= tolerance * expected or diff < 0.5 else "DIFF"
    return f"{name}: {calculated:.2f} (beklenen: {expected:.2f}) [{status}, fark: {pct:.1f}%]"


def main():
    print("="*80)
    print("ÖRNEK 8-2 - DETAYLI KARŞILAŞTIRMA")
    print("="*80)
    
    system = create_ornek_8_2()
    result = compute_multi_slab_system(system)
    
    load = result.load_analysis
    
    # 1. YÜK ANALİZİ
    print("\n1. YÜK ANALİZİ")
    print("-" * 40)
    print(compare("g_kendi (öz ağırlık)", load.g_self_weight, 3.5))
    print(compare("g (toplam sabit)", load.g_total, 5.0))
    print(compare("q (hareketli)", load.q_live, 3.5))
    print(compare("pd (hesap yükü)", load.pd_factored, 12.6))
    
    # 2. DÖŞEME TİPLERİ
    print("\n2. DÖŞEME TİPLERİ")
    print("-" * 40)
    d1 = result.panel_moments["D1"]
    d2 = result.panel_moments["D2"]
    bd = result.panel_moments["BD"]
    
    print(f"D1: m={d1.m_ratio:.2f} → {d1.slab_type} (beklenen: m=1.2, two_way)")
    print(f"D2: m={d2.m_ratio:.2f} → {d2.slab_type} (beklenen: m=2.45, one_way)")
    print(f"BD: {bd.slab_type} (beklenen: cantilever)")
    
    # 3. NET AÇIKLIKLAR
    print("\n3. NET AÇIKLIKLAR")
    print("-" * 40)
    # Textbook: D1 Lsn = 4.75m (short direction)
    # D1: 6.0m x 5.0m, beams 250mm → Lsn_x = 6.0-0.25 = 5.75m, Lsn_y = 5.0-0.25 = 4.75m
    print(f"D1 Lsn_x: {d1.Lsn_x:.3f}m (beklenen: ~5.75m)")
    print(f"D1 Lsn_y: {d1.Lsn_y:.3f}m (beklenen: 4.75m)")
    print(f"D2 Lsn_y: {d2.Lsn_y:.3f}m (beklenen: 2.20m)")
    print(f"BD Lsn_x: {bd.Lsn_x:.3f}m (beklenen: 1.375m)")
    
    # 4. KALINLIK KONTROLÜ
    print("\n4. KALINLIK KONTROLÜ")
    print("-" * 40)
    for pid in ["D1", "D2", "BD"]:
        thk = result.panel_thickness[pid]
        status = "OK" if thk.ok else "FAIL"
        print(f"{pid}: h_min={thk.h_min_mm:.1f}mm, h=140mm [{status}]")
    print("Ders kitabı: D1→130mm, D2→73mm, BD→104mm (hepsi 140mm ile OK)")
    
    # 5. BALKON MOMENTİ
    print("\n5. BALKON MOMENTİ (BD)")
    print("-" * 40)
    # Textbook: M = 12.6 × 1.375² / 2 = 11.91 kNm/m
    print(compare("M_konsol", bd.M_cantilever, 11.91))
    
    # 6. D1 MOMENTLERİ (İki doğrultulu - Tip 3)
    print("\n6. D1 MOMENTLERİ (İki doğrultuda çalışan döşeme)")
    print("-" * 40)
    # Textbook uses Lsn = 4.75m (short span) for all calculations
    # Short direction (Y in our case since Ly < Lx):
    #   M1 (açıklık) = 0.047 × 12.6 × 4.75² = 13.4 kNm/m
    #   M2 (sürekli kenar) = 0.062 × 12.6 × 4.75² = 17.6 kNm/m
    # Long direction (X):
    #   M3 (açıklık) = 0.037 × 12.6 × 4.75² = 10.5 kNm/m
    #   M4 (sürekli kenar) = 0.049 × 12.6 × 4.75² = 13.9 kNm/m
    
    print("Kısa doğrultu (Y - 5.0m):")
    print(compare("  M1 açıklık (pos)", d1.M_short_pos, 13.4))
    print(compare("  M2 sürekli kenar (neg)", d1.M_short_neg, 17.6))
    print("Uzun doğrultu (X - 6.0m):")
    print(compare("  M3 açıklık (pos)", d1.M_long_pos, 10.5))
    print(compare("  M4 sürekli kenar (neg)", d1.M_long_neg, 13.9))
    
    # 7. D2 MOMENTLERİ (Tek doğrultulu)
    print("\n7. D2 MOMENTLERİ (Tek doğrultuda çalışan döşeme)")
    print("-" * 40)
    # Textbook: Uses gross span 2.45m
    # M_açıklık = 9 × 12.6 × 2.45² / 128 = 5.32 kNm/m
    # M_mesnet = 12.6 × 2.45² / 8 = 9.45 kNm/m
    M_d2_pos = d2.M_short_pos if d2.M_short_pos > 0 else d2.M_long_pos
    M_d2_neg = d2.M_short_neg if d2.M_short_neg > 0 else d2.M_long_neg
    
    # Recalculate expected with net span (2.20m)
    expected_pos_net = 9 * 12.6 * 2.20**2 / 128  # 4.29
    expected_neg_net = 12.6 * 2.20**2 / 8  # 7.62
    expected_pos_gross = 9 * 12.6 * 2.45**2 / 128  # 5.32
    expected_neg_gross = 12.6 * 2.45**2 / 8  # 9.45
    
    print(compare("  M_açıklık (net span 2.2m)", M_d2_pos, expected_pos_net))
    print(f"     Ders kitabı (gross span 2.45m): {expected_pos_gross:.2f} kNm/m")
    print(compare("  M_mesnet (net span 2.2m)", M_d2_neg, expected_neg_net))
    print(f"     Ders kitabı (gross span 2.45m): {expected_neg_gross:.2f} kNm/m")
    
    # 8. MOMENT DENGELEMESİ
    print("\n8. MOMENT DENGELEMESİ")
    print("-" * 40)
    for bal in result.support_balances:
        print(f"{bal.support_location}:")
        print(f"  Sol: {bal.M_left:.2f} → {bal.M_left_balanced:.2f} kNm/m")
        print(f"  Sağ: {bal.M_right:.2f} → {bal.M_right_balanced:.2f} kNm/m")
        print(f"  Tasarım: {bal.M_design:.2f} kNm/m")
    
    print("\nDers kitabı D1/D2 dengelemesi:")
    print("  9.45/17.6 = 0.54 < 0.8 → dağıtım yapılır")
    print("  ΔM = (2/3)(17.6-9.45) = 5.43 kNm/m")
    print("  D1: 17.6 - (2.45/7.45)×5.43 = 15.8 kNm/m")
    print("  D2: 9.45 + (5/7.45)×5.43 = 13.1 kNm/m")
    
    # 9. DONATILAMA
    print("\n9. DONATILAMA ÖZETİ")
    print("-" * 40)
    for pid, (out_x, out_y) in result.panel_designs.items():
        print(f"\n{pid}:")
        if out_x.main_bottom_layout and out_x.main_bottom_layout.straight.phi > 0:
            s = out_x.main_bottom_layout.straight
            total = out_x.main_bottom_layout.As_total_prov_mm2_per_m
            print(f"  {out_x.direction} Alt: Ø{s.phi}/{s.s_cm:.0f}cm (As={total:.0f}mm²/m)")
        if out_x.top_layout and out_x.top_layout.phi > 0:
            t = out_x.top_layout
            print(f"  {out_x.direction} Üst: Ø{t.phi}/{t.s_cm:.0f}cm (As={t.As_prov_mm2_per_m:.0f}mm²/m)")
        if out_y.main_bottom_layout and out_y.main_bottom_layout.straight.phi > 0:
            s = out_y.main_bottom_layout.straight
            total = out_y.main_bottom_layout.As_total_prov_mm2_per_m
            print(f"  {out_y.direction} Alt: Ø{s.phi}/{s.s_cm:.0f}cm (As={total:.0f}mm²/m)")
        if out_y.dist_bars and out_y.dist_bars.phi > 0:
            d = out_y.dist_bars
            print(f"  {out_y.direction} Dağıtma: Ø{d.phi}/{d.s_cm:.0f}cm (As={d.As_prov_mm2_per_m:.0f}mm²/m)")
    
    print("\n" + "="*80)
    print("SONUÇ")
    print("="*80)


if __name__ == "__main__":
    main()
