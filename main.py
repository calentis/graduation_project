# =================================================
# main.py # Giriş ve Raporlama (TS500/TBDY-2018)
# =================================================
from constant import SLAB_CASES
from design import compute
from models import BarChoice, DesignOut, InputData, ThicknessCheck, LoadAnalysis
from utils import validate_concrete_grade, validate_beam_width, calculate_loads
from system_solver import compute_system, example_8_1_system, example_8_2_system, support_extra_bars, sum_line_loads_at_points, two_way_edge_line_load_points


def print_choice(prefix: str, c: BarChoice):
    if c is None or c.phi <= 0:
        print(f"{prefix}: seçilemedi / gerek yok")
        return
    print(f"{prefix}: Ø{c.phi} / {c.s_cm:.1f} cm  (As={c.As_prov_cm2_per_m:.2f} cm²/m, oran={c.ratio:.3f})")


def format_rebar(c: BarChoice) -> str:
    """Format rebar choice as string e.g., 'Ø10/13'"""
    if c is None or c.phi <= 0:
        return "-"
    return f"Ø{c.phi}/{c.s_cm:.0f}"


def print_load_analysis(load: LoadAnalysis, h_mm: float):
    print("\n--- Yük Analizi (TS500) ---")
    print(f"Öz ağırlık (g_sw): {h_mm/1000:.3f}m × 25 kN/m³ = {load.g_self_weight:.2f} kN/m²")
    print(f"Ek sabit yük (g_add): {load.g_additional:.2f} kN/m²")
    print(f"Toplam sabit yük (g): {load.g_total:.2f} kN/m²")
    print(f"Hareketli yük (q): {load.q_live:.2f} kN/m²")
    print(f"Hesap yükü (pd): 1.4×{load.g_total:.2f} + 1.6×{load.q_live:.2f} = {load.pd_factored:.2f} kN/m²")


def print_design(o: DesignOut):
    print(f"\n--- {o.direction} doğrultusu ---")
    print(f"Tip: {o.slab_type} | Senaryo {o.slab_case}: {o.slab_case_name} | m={o.m:.3f}")
    print(f"Net açıklık: Lsn_x={o.Lsn_x:.3f}m, Lsn_y={o.Lsn_y:.3f}m")
    if o.edges_continuity_note:
        print(o.edges_continuity_note)

    print(f"d = {o.d_m:.4f} m (= {o.d_m*1000:.1f} mm)")
    if o.note_min:
        print(f"Min kontrol: {o.note_min}")
    if o.note_spacing:
        print(f"Aralık kısıtı: {o.note_spacing}")

    # Alt (pozitif)
    if o.M_pos_kNm_per_m > 1e-12:
        print("\nAlt donatı (pozitif moment, açıklık ortası):")
        print(f"  α_pos = {o.a_pos_used:.4f}")
        print(f"  M_pos = {o.M_pos_kNm_per_m:.3f} kNm/m")
        print(f"  K_calc (x10^5) = {o.Kcalc_pos_x1e5:.1f} | ks = {o.ks_pos:.3f}")
        print(f"  As_req = {o.As_pos_req_mm2_per_m:.0f} mm²/m ({o.As_pos_req_mm2_per_m/100:.2f} cm²/m)")

        ml = o.main_bottom_layout
        if ml is None or ml.straight.phi == 0:
            print("  Ana alt donatı seçilemedi (yük çok büyük veya grid dışında).")
        else:
            print("  Ana alt donatı (%50 düz + %50 pilye) [AYNI ÇAP]:")
            print_choice("    Düz", ml.straight)
            print_choice("    Pilye", ml.pilye)
            print(f"    Toplam As_prov = {ml.As_total_prov_mm2_per_m:.0f} mm²/m ({ml.As_total_prov_mm2_per_m/100:.2f} cm²/m) | oran={ml.ratio:.3f}")
    else:
        if o.dist_bars and o.dist_bars.phi > 0:
            print("\nBu doğrultuda pozitif moment yok → dağıtma donatısı:")
            print(f"  As_dist_req = {o.dist_As_req_mm2_per_m:.0f} mm²/m ({o.dist_As_req_mm2_per_m/100:.2f} cm²/m)")
            print_choice("  Dağıtma", o.dist_bars)
        else:
            print("\nBu doğrultuda pozitif moment yok.")

    # Üst (negatif)
    if o.M_neg_kNm_per_m > 1e-12 and o.As_neg_req_mm2_per_m > 1e-12:
        print("\nÜst donatı (negatif moment, sürekli kenar bölgesi):")
        print(f"  α_neg = {o.a_neg_used:.4f}")
        print(f"  M_neg = {o.M_neg_kNm_per_m:.3f} kNm/m")
        print(f"  K_calc (x10^5) = {o.Kcalc_neg_x1e5:.1f} | ks = {o.ks_neg:.3f}")
        print(f"  As_req = {o.As_neg_req_mm2_per_m:.0f} mm²/m ({o.As_neg_req_mm2_per_m/100:.2f} cm²/m)")
        print_choice("  Seçilen üst donatı", o.top_layout)
    else:
        print("\nÜst donatı: negatif moment yok / abakta yok (bu senaryo/kenar süreksizliği için).")


def print_thickness(thk: ThicknessCheck, h_mm: float):
    print("\n--- Kalınlık kontrolü ---")
    print(thk.note)
    if thk.ok:
        print(f"OK: h={h_mm:.1f}mm ≥ h_min={thk.h_min_mm:.1f}mm")
    else:
        print(f"UYARI: h={h_mm:.1f}mm < h_min={thk.h_min_mm:.1f}mm (tasarım devam ediyor ama kalınlık artırılmalı)")


def get_input(msg, cast, default):
    v = input(f"{msg} [{default}]: ").strip()
    return default if v == "" else cast(v)


def main():
    print("\n" + "="*80)
    print("  DÖŞEME TASARIMI (TS500 / TBDY-2018)")
    print("  ABAK Tabloları + Net Açıklık + Yük Kombinasyonu")
    print("="*80)

    mode = get_input("\nMod seçimi: 1) Tek panel  2) Sistem (Örnek 8-2)  3) Sistem (Örnek 8-1)", int, 1)
    if mode in (2, 3):
        if mode == 2:
            print("\n--- Örnek 8-2 (D1 + D2 + BD) sistem hesabı ---")
            system = example_8_2_system()
        else:
            print("\n--- Örnek 8-1 (D1 + D2 + BD) sistem hesabı ---")
            system = example_8_1_system()

        conc = get_input("Beton sınıfı (C25..C50)", str, "C25").upper()
        conc_ok, conc_msg = validate_concrete_grade(conc)
        print(f"  {conc_msg}")
        steel = get_input("Çelik sınıfı (S420 / S220 / B500C)", str, "S420").upper()
        cover_mm = get_input("Paspayı (mm)", float, 20.0)
        g_additional = get_input("Kaplama+Sıva (kN/m²)", float, 1.5)
        q_live = get_input("Hareketli yük (kN/m²)", float, 3.5)

        h_mm, results, hmins, pd = compute_system(
            system=system,
            concrete=conc,
            steel=steel,
            cover_mm=cover_mm,
            d_y_reduction_mm=10.0,
            g_additional=g_additional,
            q_live=q_live,
        )

        print("\n--- Kalınlık seçimi (ortak) ---")
        for k, v in hmins.items():
            print(f"  {k}: h_min ≈ {v:.1f} mm")
        print(f"  Seçilen ortak kalınlık: h = {h_mm:.0f} mm")

        print("\n--- Yükler ---")
        g_self, g_total, _, _ = calculate_loads(h_mm, g_additional, q_live)
        print(f"  g_self={g_self:.2f}  g={g_total:.2f}  q={q_live:.2f}  pd={pd:.2f} kN/m²")

        print("\n--- Sistem Momentleri (kNm/m) ---")
        for name, r in results.items():
            m = r.moments_raw
            md = r.moments_design
            print(
                f"  {name}: "
                f"Mx+={m.Mx_pos:.2f}, Mx-={m.Mx_neg:.2f}, "
                f"My+={m.My_pos:.2f}, My-={m.My_neg:.2f}, "
                f"Mcant-={m.Mcant_neg:.2f} | "
                f"DESIGN: Mx-={md.Mx_neg:.2f}, My-={md.My_neg:.2f}, Mcant-={md.Mcant_neg:.2f}"
            )

        print("\n--- Donatı (panel bazında) ---")
        for name, r in results.items():
            print(f"\n[{name}]")
            print_design(r.design_x)
            print_design(r.design_y)

        if mode == 3:
            # Support extra bars as in the textbook table
            fck = 25.0 if conc.startswith("C25") else float(conc[1:])
            d_m_x = max((h_mm - cover_mm) / 1000.0, 1e-6)
            print("\n--- Mesnet Ek Donatı (Örnek 8-1 yaklaşımı) ---")
            if "D1" in results and "D2" in results:
                extra_k102 = support_extra_bars(
                    name="D1/D2",
                    M_kNm_per_m=results["D1"].moments_design.Mx_neg,
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    existing_bars=[
                        results["D1"].design_x.main_bottom_layout.pilye,
                        results["D2"].design_x.main_bottom_layout.pilye,
                    ],
                )
                print(f"  D1/D2: Md={extra_k102.M_kNm_per_m:.2f} → As_req={extra_k102.As_req_mm2_per_m:.0f}, As_var={extra_k102.As_existing_mm2_per_m:.0f}, As_ek={extra_k102.extra_bars.As_prov_mm2_per_m:.0f} → Ø{extra_k102.extra_bars.phi}/{extra_k102.extra_bars.s_cm:.0f}cm")

            if "D2" in results and "BD" in results:
                extra_bd = support_extra_bars(
                    name="D2/BD",
                    M_kNm_per_m=results["D2"].moments_raw.Mx_neg,  # raw D2 support at balcony side (before D1 envelope)
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    existing_bars=[results["D2"].design_x.main_bottom_layout.pilye],
                )
                print(f"  D2/BD: Md={extra_bd.M_kNm_per_m:.2f} → As_req={extra_bd.As_req_mm2_per_m:.0f}, As_var={extra_bd.As_existing_mm2_per_m:.0f}, As_ek={extra_bd.extra_bars.As_prov_mm2_per_m:.0f} → Ø{extra_bd.extra_bars.phi}/{extra_bd.extra_bars.s_cm:.0f}cm")

            # K102 beam load transfer (approx. 45-degree method, service load)
            g_self, g_total, _, _ = calculate_loads(h_mm, g_additional, q_live)
            w_service = g_total + q_live
            print("\n--- K102 kirişine aktarılan yük (yaklaşık, 45° yöntemi) ---")
            # D1 contributes with a=4.25, b=5.30; D2 with a=4.40, b=5.30 (beam along 5.30m)
            pts_d1 = two_way_edge_line_load_points(w_area=w_service, a_perp=4.25, b_along=5.30)
            pts_d2 = two_way_edge_line_load_points(w_area=w_service, a_perp=4.40, b_along=5.30)
            pts_sum = sum_line_loads_at_points([pts_d1, pts_d2])
            for y, w in pts_sum:
                print(f"  y={y:.3f}m : w={w:.2f} kN/m")

        return

    # Geometry inputs
    print("\n--- Geometri Girdileri ---")
    lx = get_input("X kenar uzunluğu (m)", float, 5.0)
    ly = get_input("Y kenar uzunluğu (m)", float, 6.0)
    
    # Beam width inputs (new per README)
    print("\n--- Kiriş Genişlikleri (net açıklık hesabı için) ---")
    beam_w_left_x = get_input("X sol kiriş genişliği (mm)", float, 300.0)
    beam_w_right_x = get_input("X sağ kiriş genişliği (mm)", float, 300.0)
    beam_w_left_y = get_input("Y sol kiriş genişliği (mm)", float, 300.0)
    beam_w_right_y = get_input("Y sağ kiriş genişliği (mm)", float, 300.0)
    
    # Validate beam widths
    for name, w in [("X sol", beam_w_left_x), ("X sağ", beam_w_right_x), 
                    ("Y sol", beam_w_left_y), ("Y sağ", beam_w_right_y)]:
        ok, msg = validate_beam_width(w, f"{name}: ")
        if not ok:
            print(f"  UYARI: {msg}")

    # Slab properties
    print("\n--- Döşeme Özellikleri ---")
    h_mm = get_input("Döşeme kalınlığı (mm)", float, 120.0)
    cover_mm = get_input("Paspayı (mm)", float, 20.0)

    # Materials
    print("\n--- Malzeme Seçimi ---")
    conc = get_input("Beton sınıfı (C25..C50)", str, "C30").upper()
    
    # Validate concrete grade
    conc_ok, conc_msg = validate_concrete_grade(conc)
    print(f"  {conc_msg}")
    
    steel = get_input("Çelik sınıfı (S420 / S220 / B500C)", str, "S420").upper()

    # Load inputs (separate dead and live per README)
    print("\n--- Yük Girdileri (TBDY-2018) ---")
    g_additional = get_input("Ek sabit yük -kaplama, sıva vb.- (kN/m²)", float, 1.5)
    q_live = get_input("Hareketli yük (kN/m²)", float, 5.0)
    
    # Show calculated loads
    g_self, g_total, _, pd = calculate_loads(h_mm, g_additional, q_live)
    print(f"\n  Hesaplanan yükler:")
    print(f"    Öz ağırlık: {g_self:.2f} kN/m² (h×25)")
    print(f"    Toplam sabit yük (g): {g_total:.2f} kN/m²")
    print(f"    Hesap yükü (pd): 1.4×{g_total:.2f} + 1.6×{q_live:.2f} = {pd:.2f} kN/m²")

    # Slab case selection
    print("\n--- Mesnet Senaryosu ---")
    for k in range(1, 8):
        print(f"  {k}) {SLAB_CASES[k]['name']}")
    slab_case = get_input("Döşeme mesnet senaryosu (1..7)", int, 7)

    # Create input data
    data = InputData(
        lx=lx, 
        ly=ly,
        beam_w_left_x=beam_w_left_x,
        beam_w_right_x=beam_w_right_x,
        beam_w_left_y=beam_w_left_y,
        beam_w_right_y=beam_w_right_y,
        h_mm=h_mm, 
        cover_mm=cover_mm,
        concrete=conc, 
        steel=steel,
        g_additional=g_additional,
        q_live=q_live,
        slab_case=slab_case
    )

    # Run computation
    out_x, out_y, thk, load_analysis = compute(data)

    # Print results
    print("\n" + "="*100)
    print("  SONUÇLAR")
    print("="*100)
    print(f"Brüt açıklık: Lx={lx:.3f}m, Ly={ly:.3f}m")
    print(f"Net açıklık: Lsn_x={out_x.Lsn_x:.3f}m, Lsn_y={out_x.Lsn_y:.3f}m")
    print(f"Kısa={min(lx, ly):.3f}m, Uzun={max(lx, ly):.3f}m")
    print(f"m (net) = {out_x.m:.3f} => {out_x.slab_type}")
    print(f"Senaryo {slab_case}: {SLAB_CASES.get(slab_case, SLAB_CASES[7])['name']}")

    print_load_analysis(load_analysis, h_mm)
    print_thickness(thk, h_mm)
    print_design(out_x)
    print_design(out_y)
    
    # Summary table
    print("\n" + "="*100)
    print("  DONATILAMA ÖZETİ")
    print("="*100)
    
    # X direction
    if out_x.main_bottom_layout and out_x.main_bottom_layout.straight.phi > 0:
        x_bottom = format_rebar(out_x.main_bottom_layout.straight)
        x_pilye = format_rebar(out_x.main_bottom_layout.pilye)
    else:
        x_bottom = "-"
        x_pilye = "-"
    x_top = format_rebar(out_x.top_layout) if out_x.top_layout else "-"
    
    # Y direction
    if out_y.main_bottom_layout and out_y.main_bottom_layout.straight.phi > 0:
        y_bottom = format_rebar(out_y.main_bottom_layout.straight)
        y_pilye = format_rebar(out_y.main_bottom_layout.pilye)
    else:
        y_bottom = "-"
        y_pilye = "-"
    y_top = format_rebar(out_y.top_layout) if out_y.top_layout else "-"
    
    # Distribution bars
    dist = "-"
    if out_x.dist_bars and out_x.dist_bars.phi > 0:
        dist = format_rebar(out_x.dist_bars)
    elif out_y.dist_bars and out_y.dist_bars.phi > 0:
        dist = format_rebar(out_y.dist_bars)
    
    print(f"  X Doğrultu Alt (düz): {x_bottom}")
    print(f"  X Doğrultu Alt (pilye): {x_pilye}")
    print(f"  X Doğrultu Üst: {x_top}")
    print(f"  Y Doğrultu Alt (düz): {y_bottom}")
    print(f"  Y Doğrultu Alt (pilye): {y_pilye}")
    print(f"  Y Doğrultu Üst: {y_top}")
    if out_x.slab_type == "one_way":
        print(f"  Dağıtma Donatısı: {dist}")
    
    print("\n" + "="*100)
    
    # === DXF EXPORT ===
    export_dxf = get_input("\nDXF çizim dosyası oluşturulsun mu? (e/h)", str, "e").lower()
    
    if export_dxf in ["e", "evet", "y", "yes"]:
        from diagrams_cad import generate_slab_drawing
        
        filename = get_input("DXF dosya adı", str, "slab_reinforcement.dxf")
        if not filename.endswith(".dxf"):
            filename += ".dxf"
        
        output_file = generate_slab_drawing(
            design_x=out_x, design_y=out_y,
            lx=lx, ly=ly,
            h_mm=h_mm, cover_mm=cover_mm,
            output_file=filename
        )
        print(f"\n✓ DXF dosyası oluşturuldu: {output_file}")
        print("  Bu dosyayı AutoCAD, BricsCAD, LibreCAD gibi programlarda açabilirsiniz.")
    
    print("\n" + "="*100)
    print("  Program tamamlandı.")
    print("="*100)


if __name__ == "__main__":
    main()