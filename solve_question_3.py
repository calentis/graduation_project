
from system_solver import SlabSystem
from models import InputData
from core import choose_single_layer_rebar, calc_K_and_As_from_M
from diagrams_cad import generate_system_dxf

def run_question_3_detailed():
    print("Soru Çözümü - Detaylı Analiz")
    print("==========================================================")
    
    system = SlabSystem()
    
    h = 140.0
    cover = 20.0
    conc = "C25" 
    steel = "S420"
    g_add = 1.5
    q = 3.5
    bw = 250.0
    
    # --- SLAB DEFINITIONS (Same as before) ---
    d1_l = InputData(lx=6.0, ly=6.0, beam_w_left_x=bw, beam_w_right_x=bw, beam_w_left_y=bw, beam_w_right_y=bw, h_mm=h, cover_mm=cover, concrete=conc, steel=steel, g_additional=g_add, q_live=q, slab_case=3, slab_id="D1_Sol")
    system.add_slab("D1_Sol", d1_l)
    
    d1_r = InputData(lx=6.0, ly=6.0, beam_w_left_x=bw, beam_w_right_x=bw, beam_w_left_y=bw, beam_w_right_y=bw, h_mm=h, cover_mm=cover, concrete=conc, steel=steel, g_additional=g_add, q_live=q, slab_case=3, slab_id="D1_Sag")
    system.add_slab("D1_Sag", d1_r)
    
    bd_b = InputData(lx=6.0, ly=1.5, beam_w_left_x=bw, beam_w_right_x=bw, beam_w_left_y=bw, beam_w_right_y=0.0, h_mm=h, cover_mm=cover, concrete=conc, steel=steel, g_additional=g_add, q_live=q, slab_case=8, slab_id="BD_Alt")
    system.add_slab("BD_Alt", bd_b)
    
    bd_t = InputData(lx=6.0, ly=1.5, beam_w_left_x=bw, beam_w_right_x=bw, beam_w_left_y=0.0, beam_w_right_y=bw, h_mm=h, cover_mm=cover, concrete=conc, steel=steel, g_additional=g_add, q_live=q, slab_case=8, slab_id="BD_Ust")
    system.add_slab("BD_Ust", bd_t)
    
    # --- CONNECTIONS ---
    system.connect("D1_Sol", "right", "D1_Sag", "left")
    system.connect("D1_Sol", "bottom", "BD_Alt", "top")
    system.connect("D1_Sag", "top", "BD_Ust", "bottom")
    
    # Solve
    system.solve()
    
    # Generate DXF
    print("\n>>> Generating DXF Drawing...")
    generate_system_dxf(system, "Question3_Reinforcement.dxf")

    # --- DETAILED REPORT GENERATION ---
    print("\n=== DETAYLI DONATI RAPORU (AS KONTROLÜ) ===")
    
    def print_span_details(slab_id, direction, design):
        if design.slab_type == "one_way" and design.M_pos_kNm_per_m < 0.001:
            print(f"  {direction} Yönü: Dağıtma Donatısı")
            return

        print(f"  {direction} Yönü (Açıklık):")
        print(f"    Md = {design.M_pos_kNm_per_m:.2f} kNm")
        print(f"    d  = {design.d_m*100:.1f} cm")
        print(f"    K  = {design.Kcalc_pos_x1e5:.1f} (*10^-5)")
        print(f"    ks = {design.ks_pos:.2f}")
        print(f"    As_req = {design.As_pos_req_mm2_per_m:.1f} mm2/m")
        
        layout = design.main_bottom_layout
        if layout:
            print(f"    SEÇİLEN: Düz Ø{layout.straight.phi}/{layout.straight.s_cm:.0f} + Pilye Ø{layout.pilye.phi}/{layout.pilye.s_cm:.0f}")
            print(f"    As_prov = {layout.As_total_prov_mm2_per_m:.1f} mm2/m")
        else:
            print("    Seçim yapılamadı.")

    for slab_id in ["D1_Sol", "BD_Alt"]: # Showing Representative Slabs
        print(f"\n[{slab_id}]")
        slab = system.slabs[slab_id]
        print_span_details(slab_id, "X", slab.design_x)
        print_span_details(slab_id, "Y", slab.design_y)

    print("\n--- MESNET (SUPPORT) ANALİZİ ---")
    
    def analyze_support(name, Md, d_m, pilye_sources):
        print(f"\n[Mesnet: {name}]")
        # 1. Calculate Required As
        fck = 25
        steel_grade = "S420"
        _, _, As_req = calc_K_and_As_from_M(Md, d_m, fck, steel_grade)
        
        print(f"    Md = {Md:.2f} kNm")
        print(f"    d  = {d_m*100:.1f} cm")
        print(f"    As_req = {As_req:.1f} mm2/m")
        
        # 2. Calculate Mevcut (From Pilyes)
        As_mevcut = 0
        details = []
        for src_slab, src_dir in pilye_sources:
            design = system.slabs[src_slab].design_x if src_dir == "X" else system.slabs[src_slab].design_y
            if design.main_bottom_layout:
                pilye = design.main_bottom_layout.pilye
                if pilye.phi > 0:
                    area = pilye.As_prov_mm2_per_m / 2.0 
                    As_mevcut += pilye.As_prov_mm2_per_m
                    details.append(f"{src_slab} Pilye (Ø{pilye.phi}/{pilye.s_cm:.0f})")
            
        print(f"    Mevcut Donatı: {As_mevcut:.1f} mm2 ({' + '.join(details)})")
        
        # 3. Calculate Ek (Additional)
        As_ek_req = max(0, As_req - As_mevcut)
        print(f"    Gerekli Ek (As_ek): {As_ek_req:.1f} mm2")
        
        if As_ek_req > 0:
            ek_bar = choose_single_layer_rebar(As_ek_req, s_max_mm=300)
            print(f"    SEÇİLEN EK: Ø{ek_bar.phi}/{ek_bar.s_cm:.0f} (As={ek_bar.As_prov_mm2_per_m:.1f})")
            print(f"    TOPLAM (Mevcut+Ek): {As_mevcut + ek_bar.As_prov_mm2_per_m:.1f} mm2")
        else:
            print("    Ek donatı gerekmiyor.")

    md_d1_d1 = system.slabs["D1_Sol"].balanced_moments["right"]
    analyze_support("D1(Sol)-D1(Sağ)", md_d1_d1, 0.12, [("D1_Sol", "X"), ("D1_Sag", "X")])
    
    md_d1_bd = system.slabs["D1_Sol"].balanced_moments["bottom"]
    analyze_support("D1(Sol)-Balkon(Alt)", md_d1_bd, 0.12, [("D1_Sol", "Y")])

if __name__ == "__main__":
    run_question_3_detailed()

#  python .\solve_question_3.py