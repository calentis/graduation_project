from system_solver import SlabSystem
from models import InputData
 
def solve_my_system():
    # 1. Start the system
    system = SlabSystem()
    
    # Constants for your project
    h = 140.0        # Slab thickness (mm)
    cover = 20.0     # Concrete cover (mm)
    conc = "C25"     # Concrete Grade
    steel = "S420"   # Steel Grade
    g_add = 1.5      # Additional Dead Load (kN/m2)
    q = 3.5          # Live Load (kN/m2)
    bw = 250.0       # Beam Width (mm)
 
    # 2. Define Slabs (Example: 2 Slabs side-by-side)
    
    # Slab 1 (Left)
    d1 = InputData(
        lx=6.0, ly=5.0,        # Dimensions
        beam_w_left_x=bw, beam_w_right_x=bw, # Beam widths (Left/Right)
        beam_w_left_y=bw, beam_w_right_y=bw, # Beam widths (Top/Bottom)
        h_mm=h, cover_mm=cover, concrete=conc, steel=steel,
        g_additional=g_add, q_live=q,
        slab_case=3,           # <--- CHANGE THIS based on continuity
        slab_id="D1"
    )
    system.add_slab("D1", d1)
 
    # Slab 2 (Right)
    d2 = InputData(
        lx=6.0, ly=5.0,
        beam_w_left_x=bw, beam_w_right_x=bw,
        beam_w_left_y=bw, beam_w_right_y=bw,
        h_mm=h, cover_mm=cover, concrete=conc, steel=steel,
        g_additional=g_add, q_live=q,
        slab_case=3,           # <--- CHANGE THIS
        slab_id="D2"
    )
    system.add_slab("D2", d2)
    
    # 3. Connect Slabs
    # "D1's Right edge connects to D2's Left edge"
    system.connect("D1", "right", "D2", "left")
    
    # 4. Run Solver
    system.solve()
    
    # 5. Print Results
    # You can access specific results like this:
    print(f"D1 Span Moment X: {system.slabs['D1'].design_x.M_pos_kNm_per_m:.2f}")
    
    # Or check connection moments
    connection_moment = system.slabs['D1'].balanced_moments['right']
    print(f"Support Moment (D1-D2): {connection_moment:.2f}")
 
if __name__ == "__main__":
    solve_my_system()