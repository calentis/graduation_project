
import dataclasses
from typing import List, Dict, Tuple, Optional
from models import InputData, DesignOut, LoadAnalysis, BarChoice
from design import compute
from core import calc_K_and_As_from_M, choose_single_layer_rebar

@dataclasses.dataclass
class SlabNode:
    id: str
    data: InputData
    # Results
    design_x: Optional[DesignOut] = None
    design_y: Optional[DesignOut] = None
    load: Optional[LoadAnalysis] = None
    
    # Balancing results (edge -> moment)
    # Stores the FINAL balanced moment at this edge
    balanced_moments: Dict[str, float] = dataclasses.field(default_factory=dict) 
    
    # Re-designed support reinforcement based on balanced moments
    # key: edge name ("top", "bottom", "left", "right") -> BarChoice
    support_reinforcement: Dict[str, BarChoice] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class Connection:
    slab1_id: str
    edge1: str # "top", "bottom", "left", "right"
    slab2_id: str
    edge2: str

class SlabSystem:
    def __init__(self):
        self.slabs: Dict[str, SlabNode] = {}
        self.connections: List[Connection] = []
        
    def add_slab(self, id: str, data: InputData):
        self.slabs[id] = SlabNode(id=id, data=data)
        
    def connect(self, id1: str, edge1: str, id2: str, edge2: str):
        self.connections.append(Connection(id1, edge1, id2, edge2))
        
    def solve(self):
        print(">>> Sistem Çözümü Başlıyor...")
        # 1. Initial Design
        for slab in self.slabs.values():
            print(f"  - Döşeme {slab.id} hesaplanıyor...")
            dx, dy, _, load = compute(slab.data)
            slab.design_x = dx
            slab.design_y = dy
            slab.load = load
            
        # 2. Balancing
        print(">>> Moment Dengelemesi...")
        for conn in self.connections:
            self._balance_connection(conn)
            
        # 3. Final Reinforcement Selection for Supports
        print(">>> Mesnet Donatıları Belirleniyor...")
        for slab in self.slabs.values():
            self._design_supports(slab)
            
        print(">>> Çözüm Tamamlandı.")
        
    def _get_moment_and_span(self, slab: SlabNode, edge: str) -> Tuple[float, float, float]:
        """Returns (Moment_neg, Span_net, d_m) for the given edge direction"""
        if edge in ["top", "bottom"]:
            # Y direction
            # Check if Y is developed
            if slab.design_y.m > 2.0 and slab.design_y.slab_type == "one_way" and abs(slab.design_y.M_neg_kNm_per_m) < 1e-9:
                 # One way slab not spanning in Y direction (distribution direction)
                 # Moment is effectively 0 for balancing main moments of other slab?
                 # Or minimal.
                 pass
            
            return (slab.design_y.M_neg_kNm_per_m, slab.design_y.Lsn_y, slab.design_y.d_m)
        else:
            # X direction
            return (slab.design_x.M_neg_kNm_per_m, slab.design_x.Lsn_x, slab.design_x.d_m)

    def _balance_connection(self, conn: Connection):
        s1 = self.slabs[conn.slab1_id]
        s2 = self.slabs[conn.slab2_id]
        
        M1, L1, d1 = self._get_moment_and_span(s1, conn.edge1)
        M2, L2, d2 = self._get_moment_and_span(s2, conn.edge2)
        
        print(f"  * Bağlantı: {s1.id}({conn.edge1}) <-> {s2.id}({conn.edge2})")
        print(f"    M_{s1.id} = {M1:.2f}, L_{s1.id} = {L1:.2f}")
        print(f"    M_{s2.id} = {M2:.2f}, L_{s2.id} = {L2:.2f}")
        
        # Check for cantilever (if one M is huge or coef type is cantilever?)
        # Actually cantilever moment is fixed static moment. It usually dominates.
        # But TS500 allows redistribution if difference is small (<0.8 ratio).
        # For cantilever, usually we design for the cantilever moment on the back span too?
        # Example 8-2: "Balcony moment 11.91. Adjacent D1 13.9. 13.9 > 11.91 -> Use 13.9"
        # It seems they just take the max if it's a balcony connection?
        # Or maybe balancing applies?
        # The example text says: "D1/Balkon mesneti için 13.9 > 11.91 olduğundan M=13.9 kullanılır."
        # This implies simple MAX check for balcony boundary.
        
        # Heuristic: If one is cantilever, take MAX. If both are supported slabs, BALANCE.
        is_cantilever = False
        if s1.data.slab_case == 8 or s2.data.slab_case == 8:
            is_cantilever = True
            
        if is_cantilever:
            M_bal = max(M1, M2)
            print(f"    -> Konsol bağlantısı: MAX alındı = {M_bal:.2f}")
            s1.balanced_moments[conn.edge1] = M_bal
            s2.balanced_moments[conn.edge2] = M_bal
        else:
            # Balancing logic
            # Check ratio
            M_min = min(M1, M2)
            M_max = max(M1, M2)
            
            if M_max > 1e-9:
                ratio = M_min / M_max
            else:
                ratio = 1.0
                
            if ratio < 0.8:
                # Distribute 2/3 of difference
                diff = M_max - M_min
                delta = (2/3) * diff
                
                # Distribution factors based on spans (stiffness ~ 1/L)
                # DF1 = L2 / (L1 + L2)  (Factor for Slab 1)
                # DF2 = L1 / (L1 + L2)  (Factor for Slab 2)
                
                sum_L = L1 + L2
                df1 = L2 / sum_L
                df2 = L1 / sum_L
                
                # Apply signs: Add to min, subtract from max
                # But we don't know which is which yet.
                # Let's calculate target "balanced" moments for both sides
                # Actually, they converge to a common moment?
                # No, they might be different in a frame analysis, but here we want a single design moment?
                # The example calculates "Correction" and applies it.
                # "17.6 - ... = 15.8"
                # "9.45 + ... = 13.1"
                # They don't meet at the same value! 15.8 vs 13.1.
                # Then "Use larger value 15.8".
                
                # So we calculate independent corrected moments and take MAX.
                
                # If M1 is Max:
                # M1_new = M1 - delta * df1
                # M2_new = M2 + delta * df2
                
                if M1 >= M2:
                    M1_new = M1 - delta * df1
                    M2_new = M2 + delta * df2
                else:
                    M1_new = M1 + delta * df1
                    M2_new = M2 - delta * df2
                    
                print(f"    -> Dengeleme (Oran {ratio:.2f} < 0.8):")
                print(f"       Delta = {delta:.2f}")
                print(f"       {s1.id} düzeltme: {M1:.2f} -> {M1_new:.2f}")
                print(f"       {s2.id} düzeltme: {M2:.2f} -> {M2_new:.2f}")
                
                M_final = max(M1_new, M2_new)
                print(f"       Seçilen ortak moment: {M_final:.2f}")
                
                s1.balanced_moments[conn.edge1] = M_final
                s2.balanced_moments[conn.edge2] = M_final
                
            else:
                M_final = M_max
                print(f"    -> Oran {ratio:.2f} >= 0.8. Dengeleme yok. Max kullanılır: {M_final:.2f}")
                s1.balanced_moments[conn.edge1] = M_final
                s2.balanced_moments[conn.edge2] = M_final

    def _design_supports(self, slab: SlabNode):
        for edge, M_bal in slab.balanced_moments.items():
            if M_bal <= 1e-9:
                continue
                
            # Get effective depth for this edge
            _, _, d_m = self._get_moment_and_span(slab, edge)
            
            # Calculate required As
            # Use 'top' reinforcement parameters
            # Note: We need fck and steel type
            fck = 30.0 # Default fallback, should parse from InputData
            try:
                from utils import parse_concrete
                fck = parse_concrete(slab.data.concrete)
            except:
                pass
                
            _, _, As_req = calc_K_and_As_from_M(M_bal, d_m, fck, slab.data.steel)
            
            # Minimum check (0.002 * b * h)? Or top min?
            # Standard top min is 0.002 * b * d? Or 0.002 * b * h?
            # design.py uses: As_top_min = 0.002 * b_mm * d_mm
            b_mm = 1000.0
            d_mm = d_m * 1000.0
            As_min = 0.002 * b_mm * d_mm
            
            As_final = max(As_req, As_min)
            
            # Select Bars
            # Assuming s_max = 2*h or 200mm
            s_max = min(2 * slab.data.h_mm, 200)
            
            choice = choose_single_layer_rebar(As_final, int(s_max))
            
            slab.support_reinforcement[edge] = choice
     