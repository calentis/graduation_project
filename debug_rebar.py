
from core import calc_K_and_As_from_M, choose_main_rebar_half_half_same_phi

def debug_selection():
    M = 15.41
    d = 0.12
    fck = 25
    steel = "S420"
    
    print(f"Debug inputs: M={M}, d={d}, fck={fck}, steel={steel}")
    
    K, ks, As_req = calc_K_and_As_from_M(M, d, fck, steel)
    print(f"Calculated: K={K:.2f}, ks={ks:.2f}, As_req={As_req:.2f}")
    
    # Try selection
    layout = choose_main_rebar_half_half_same_phi(As_req, s_max_main_mm=200)
    print(f"Selected Layout:")
    print(f"  Straight: Ø{layout.straight.phi}/{layout.straight.s_cm}")
    print(f"  Pilye:    Ø{layout.pilye.phi}/{layout.pilye.s_cm}")
    print(f"  Total As: {layout.As_total_prov_mm2_per_m}")

if __name__ == "__main__":
    debug_selection()