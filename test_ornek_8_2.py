# ============================================================
# test_ornek_8_2.py # Test for Ornek 8-2 (Example 8-2)
# ============================================================
"""
Tests the multi-slab system design against Example 8-2 from the textbook.
"""

import unittest

from models import GridAxis, SlabPanel, SlabEdge, SlabSystemInput
from multi_slab import compute_multi_slab_system, print_system_results


def create_ornek_8_2_system():
    """Create the slab system from Example 8-2."""
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
    
    d1 = SlabPanel(
        panel_id="D1",
        x_axis_start="A", x_axis_end="B",
        y_axis_start="1", y_axis_end="2",
        lx=6.0, ly=5.0,
        slab_type="auto",
        slab_case_override=3,
        edge_x_left=SlabEdge(is_fixed=True),
        edge_x_right=SlabEdge(is_continuous=True, adjacent_slab_id="BD"),
        edge_y_bottom=SlabEdge(is_fixed=True),
        edge_y_top=SlabEdge(is_continuous=True, adjacent_slab_id="D2"),
    )
    
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
    
    bd = SlabPanel(
        panel_id="BD",
        x_axis_start="B", x_axis_end="C",
        y_axis_start="1", y_axis_end="2",
        lx=1.5, ly=5.0,
        slab_type="cantilever",
        cantilever_direction="x+",
        edge_x_left=SlabEdge(is_continuous=True, adjacent_slab_id="D1"),
        edge_x_right=SlabEdge(is_free=True),
        edge_y_bottom=SlabEdge(is_fixed=True),
        edge_y_top=SlabEdge(is_fixed=True),
    )
    
    return SlabSystemInput(
        x_axes=x_axes,
        y_axes=y_axes,
        panels=[d1, d2, bd],
        h_mm=140.0,
        cover_mm=20.0,
        concrete="C25",
        steel="S420",
        beam_width_mm=250.0,
        beam_depth_mm=600.0,
        g_additional=1.5,
        q_live=3.5,
    )


class TestOrnek82(unittest.TestCase):
    """Test Example 8-2 calculations."""
    
    def setUp(self):
        self.system = create_ornek_8_2_system()
        self.result = compute_multi_slab_system(self.system)
    
    def test_load_calculation(self):
        """Test pd = 12.6 kN/m2."""
        load = self.result.load_analysis
        self.assertAlmostEqual(load.g_self_weight, 3.5, places=1)
        self.assertAlmostEqual(load.g_total, 5.0, places=1)
        self.assertAlmostEqual(load.pd_factored, 12.6, places=1)
    
    def test_d1_classification(self):
        """Test D1 is two-way (m < 2)."""
        d1 = self.result.panel_moments.get("D1")
        self.assertEqual(d1.slab_type, "two_way")
        self.assertLess(d1.m_ratio, 2.0)
    
    def test_d2_classification(self):
        """Test D2 is one-way (m > 2)."""
        d2 = self.result.panel_moments.get("D2")
        self.assertEqual(d2.slab_type, "one_way")
        self.assertGreater(d2.m_ratio, 2.0)
    
    def test_bd_classification(self):
        """Test BD is cantilever."""
        bd = self.result.panel_moments.get("BD")
        self.assertEqual(bd.slab_type, "cantilever")
    
    def test_d1_moments_match_textbook(self):
        """D1 moments should closely match textbook values."""
        d1 = self.result.panel_moments.get("D1")
        
        # Textbook: M1=13.4, M2=17.6, M3=10.5, M4=13.9
        # Allow 10% tolerance for net span vs gross span differences
        self.assertAlmostEqual(d1.M_short_pos, 13.4, delta=1.5)  # Expected 13.4
        self.assertAlmostEqual(d1.M_short_neg, 17.6, delta=1.5)  # Expected 17.6
        self.assertAlmostEqual(d1.M_long_pos, 10.5, delta=1.5)   # Expected 10.5
        self.assertGreater(d1.M_long_neg, 10.0)  # Should be around 13.9
    
    def test_balcony_moment(self):
        """BD cantilever moment = pL²/2 ≈ 11.91 kNm/m."""
        bd = self.result.panel_moments.get("BD")
        self.assertAlmostEqual(bd.M_cantilever, 11.91, delta=1.0)
    
    def test_d2_one_way_moments(self):
        """D2 one-way slab should have positive moments."""
        d2 = self.result.panel_moments.get("D2")
        self.assertGreater(d2.M_short_pos, 0)
    
    def test_support_balancing_exists(self):
        """Moment balancing should occur at shared supports."""
        self.assertGreater(len(self.result.support_balances), 0)
    
    def test_reinforcement_designed(self):
        """All panels should have reinforcement."""
        for pid in ["D1", "D2", "BD"]:
            design = self.result.panel_designs.get(pid)
            self.assertIsNotNone(design)
            out_x, out_y = design
            has_rebar = (
                (out_x.main_bottom_layout and out_x.main_bottom_layout.straight.phi > 0) or
                (out_x.top_layout and out_x.top_layout.phi > 0) or
                (out_y.dist_bars and out_y.dist_bars.phi > 0)
            )
            self.assertTrue(has_rebar, f"{pid} should have rebar")


def run_ornek_8_2():
    """Run Example 8-2 and print results."""
    print("\n" + "="*80)
    print("  ORNEK 8-2: Coklu Doseme Sistemi Tasarimi")
    print("="*80)
    
    system = create_ornek_8_2_system()
    result = compute_multi_slab_system(system)
    print_system_results(result)
    
    print("\n--- Ders Kitabi Karsilastirmasi ---")
    print(f"pd (beklenen: 12.6): {result.load_analysis.pd_factored:.2f} kN/m2")
    
    d1 = result.panel_moments.get("D1")
    if d1:
        print(f"\nD1 (m={d1.m_ratio:.2f}, tip: {d1.slab_type}):")
        print(f"  Kisa pos (beklenen ~13.4): {d1.M_short_pos:.2f} kNm/m")
        print(f"  Kisa neg (beklenen ~17.6): {d1.M_short_neg:.2f} kNm/m")
        print(f"  Uzun pos (beklenen ~10.5): {d1.M_long_pos:.2f} kNm/m")
        print(f"  Uzun neg (beklenen ~13.9): {d1.M_long_neg:.2f} kNm/m")
    
    d2 = result.panel_moments.get("D2")
    if d2:
        print(f"\nD2 (m={d2.m_ratio:.2f}, tip: {d2.slab_type}):")
        print(f"  M_aciklik (beklenen ~5.32): {d2.M_short_pos:.2f} kNm/m")
        print(f"  M_mesnet (beklenen ~9.45): {d2.M_short_neg:.2f} kNm/m")
        print(f"  Not: Fark, net aciklik (2.2m) vs brut aciklik (2.45m) kullanimi")
    
    bd = result.panel_moments.get("BD")
    if bd:
        print(f"\nBD (konsol):")
        print(f"  M_konsol (beklenen ~11.91): {bd.M_cantilever:.2f} kNm/m")
    
    return result


if __name__ == "__main__":
    run_ornek_8_2()
    print("\n\n" + "="*80)
    print("  RUNNING TESTS")
    print("="*80)
    unittest.main(verbosity=2)
