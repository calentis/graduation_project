# ============================================================
# test_slab_design.py # Unit Tests for Slab Design Program
# ============================================================
"""
Comprehensive unit tests for TS500/TBDY-2018 slab design program.
Run with: python -m pytest test_slab_design.py -v
Or: python test_slab_design.py
"""

import unittest
import math
from typing import Tuple


class TestUtils(unittest.TestCase):
    """Tests for utils.py functions"""
    
    def test_calculate_loads(self):
        """Test load calculation: pd = 1.4g + 1.6q"""
        from utils import calculate_loads
        
        # Case 1: h=120mm, g_add=1.5, q=5.0
        g_self, g_total, q, pd = calculate_loads(120.0, 1.5, 5.0)
        
        # Self-weight: 0.12m × 25 = 3.0 kN/m²
        self.assertAlmostEqual(g_self, 3.0, places=2)
        # Total dead: 3.0 + 1.5 = 4.5 kN/m²
        self.assertAlmostEqual(g_total, 4.5, places=2)
        # Factored: 1.4×4.5 + 1.6×5.0 = 6.3 + 8.0 = 14.3 kN/m²
        self.assertAlmostEqual(pd, 14.3, places=2)
    
    def test_calculate_loads_zero_live(self):
        """Test load calculation with zero live load"""
        from utils import calculate_loads
        
        g_self, g_total, q, pd = calculate_loads(150.0, 2.0, 0.0)
        
        # Self-weight: 0.15m × 25 = 3.75 kN/m²
        self.assertAlmostEqual(g_self, 3.75, places=2)
        # Factored: 1.4×5.75 + 1.6×0 = 8.05 kN/m²
        self.assertAlmostEqual(pd, 1.4 * 5.75, places=2)
    
    def test_calculate_net_span(self):
        """Test net span calculation: Lsn = L - w_left/2 - w_right/2"""
        from utils import calculate_net_span
        
        # Case 1: L=5m, beams 300mm each
        Lsn = calculate_net_span(5.0, 300.0, 300.0)
        # 5.0 - 0.15 - 0.15 = 4.7m
        self.assertAlmostEqual(Lsn, 4.7, places=2)
        
        # Case 2: L=6m, beams 250mm and 350mm
        Lsn = calculate_net_span(6.0, 250.0, 350.0)
        # 6.0 - 0.125 - 0.175 = 5.7m
        self.assertAlmostEqual(Lsn, 5.7, places=2)
    
    def test_calculate_net_span_minimum(self):
        """Test net span has minimum of 0.1m"""
        from utils import calculate_net_span
        
        # Small span with large beams
        Lsn = calculate_net_span(0.5, 500.0, 500.0)
        self.assertGreaterEqual(Lsn, 0.1)
    
    def test_validate_concrete_grade_valid(self):
        """Test concrete grade validation - valid cases"""
        from utils import validate_concrete_grade
        
        for grade in ["C25", "C30", "C35", "C40", "C45", "C50"]:
            ok, msg = validate_concrete_grade(grade)
            self.assertTrue(ok, f"{grade} should be valid")
    
    def test_validate_concrete_grade_invalid(self):
        """Test concrete grade validation - invalid C20"""
        from utils import validate_concrete_grade
        
        ok, msg = validate_concrete_grade("C20")
        self.assertFalse(ok)
        self.assertIn("C20", msg)
        self.assertIn("C25", msg)
    
    def test_validate_beam_width_valid(self):
        """Test beam width validation - valid cases"""
        from utils import validate_beam_width
        
        for width in [250, 300, 400, 500]:
            ok, msg = validate_beam_width(width)
            self.assertTrue(ok, f"{width}mm should be valid")
    
    def test_validate_beam_width_invalid(self):
        """Test beam width validation - invalid cases"""
        from utils import validate_beam_width
        
        for width in [200, 240, 100]:
            ok, msg = validate_beam_width(width)
            self.assertFalse(ok, f"{width}mm should be invalid")
    
    def test_validate_coefficient_method_applicable(self):
        """Test coefficient method applicability check"""
        from utils import validate_coefficient_method_applicability
        
        # Valid case: q/g < 2 and Lmin/Lmax > 0.8
        ok, msg, details = validate_coefficient_method_applicability(
            q=5.0, g=4.0, L_min=4.5, L_max=5.0
        )
        # q/g = 1.25, Lmin/Lmax = 0.9
        self.assertTrue(ok)
    
    def test_validate_coefficient_method_qg_exceeds(self):
        """Test coefficient method when q/g > 2"""
        from utils import validate_coefficient_method_applicability
        
        ok, msg, details = validate_coefficient_method_applicability(
            q=10.0, g=4.0, L_min=4.5, L_max=5.0
        )
        # q/g = 2.5 > 2
        self.assertFalse(ok)
        self.assertIn("q/g", msg)
    
    def test_validate_coefficient_method_span_ratio_low(self):
        """Test coefficient method when Lmin/Lmax <= 0.8"""
        from utils import validate_coefficient_method_applicability
        
        ok, msg, details = validate_coefficient_method_applicability(
            q=5.0, g=4.0, L_min=3.0, L_max=5.0
        )
        # Lmin/Lmax = 0.6 <= 0.8
        self.assertFalse(ok)
        self.assertIn("Lmin/Lmax", msg)
    
    def test_parse_concrete(self):
        """Test concrete grade parsing"""
        from utils import parse_concrete
        
        self.assertEqual(parse_concrete("C30"), 30.0)
        self.assertEqual(parse_concrete("C25"), 25.0)
        self.assertEqual(parse_concrete("c35"), 35.0)  # lowercase
    
    def test_rho_min_oneway(self):
        """Test minimum reinforcement ratio for one-way slabs"""
        from utils import rho_min_oneway
        
        self.assertEqual(rho_min_oneway("S420"), 0.002)
        self.assertEqual(rho_min_oneway("S220"), 0.003)
        self.assertEqual(rho_min_oneway("B500C"), 0.002)

    def test_rho_min_twoway_dir(self):
        """Test minimum reinforcement ratio per direction for two-way slabs"""
        from utils import rho_min_twoway_dir

        self.assertEqual(rho_min_twoway_dir("S420"), 0.0015)
        self.assertEqual(rho_min_twoway_dir("B500C"), 0.0015)
        self.assertEqual(rho_min_twoway_dir("S220"), 0.002)


class TestDesign(unittest.TestCase):
    """Tests for design.py functions"""
    
    def test_thickness_check_oneway(self):
        """Test one-way slab thickness check: h >= Ln/30"""
        from design import thickness_check_oneway
        
        # Case: Ln = 6m => h_min = 6000/30 = 200mm
        thk = thickness_check_oneway(Lsn=6.0, h_mm=200.0)
        self.assertTrue(thk.ok)
        self.assertAlmostEqual(thk.h_min_mm, 200.0, places=1)
        
        # Case: h < h_min
        thk = thickness_check_oneway(Lsn=6.0, h_mm=150.0)
        self.assertFalse(thk.ok)
    
    def test_thickness_check_twoway(self):
        """Test two-way slab thickness check with D0U2 formula"""
        from design import thickness_check_twoway
        
        # Case: Lsn_short=4m, Lsn_long=5m, m=1.25
        # denom = 15 + 20/1.25 = 15 + 16 = 31
        # h_min = 4000/31 ≈ 129mm
        thk = thickness_check_twoway(Lsn_short=4.0, Lsn_long=5.0, h_mm=130.0)
        self.assertTrue(thk.ok)
        
        # With αs = 0, h_min should be around 129mm
        self.assertLess(thk.h_min_mm, 135)
        self.assertGreater(thk.h_min_mm, 120)
    
    def test_compute_oneway_slab(self):
        """Test one-way slab design (m > 2)"""
        from models import InputData
        from design import compute
        
        data = InputData(
            lx=3.0, ly=8.0,  # m = 8/3 ≈ 2.67 > 2 => one-way
            beam_w_left_x=300, beam_w_right_x=300,
            beam_w_left_y=300, beam_w_right_y=300,
            h_mm=150, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=7
        )
        
        out_x, out_y, thk, load = compute(data)
        
        self.assertEqual(out_x.slab_type, "one_way")
        self.assertGreater(out_x.m, 2.0)
        # One direction should have main reinforcement
        self.assertTrue(
            out_x.M_pos_kNm_per_m > 0 or out_y.M_pos_kNm_per_m > 0
        )
    
    def test_compute_twoway_slab(self):
        """Test two-way slab design (m <= 2)"""
        from models import InputData
        from design import compute
        
        data = InputData(
            lx=5.0, ly=6.0,  # m = 6/5 = 1.2 <= 2 => two-way
            beam_w_left_x=300, beam_w_right_x=300,
            beam_w_left_y=300, beam_w_right_y=300,
            h_mm=150, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=1
        )
        
        out_x, out_y, thk, load = compute(data)
        
        self.assertEqual(out_x.slab_type, "two_way")
        self.assertLessEqual(out_x.m, 2.0)
        # Both directions should have moments
        self.assertGreater(out_x.M_pos_kNm_per_m, 0)
        self.assertGreater(out_y.M_pos_kNm_per_m, 0)
    
    def test_load_analysis_in_compute(self):
        """Test that compute returns correct load analysis"""
        from models import InputData
        from design import compute
        
        data = InputData(
            lx=5.0, ly=6.0,
            h_mm=120, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=7
        )
        
        _, _, _, load = compute(data)
        
        # g_self = 0.12 * 25 = 3.0
        self.assertAlmostEqual(load.g_self_weight, 3.0, places=2)
        # g_total = 3.0 + 1.5 = 4.5
        self.assertAlmostEqual(load.g_total, 4.5, places=2)
        # pd = 1.4*4.5 + 1.6*5.0 = 14.3
        self.assertAlmostEqual(load.pd_factored, 14.3, places=2)
    
    def test_net_spans_in_compute(self):
        """Test that compute uses net spans correctly"""
        from models import InputData
        from design import compute
        
        data = InputData(
            lx=5.0, ly=6.0,
            beam_w_left_x=300, beam_w_right_x=300,
            beam_w_left_y=400, beam_w_right_y=400,
            h_mm=150, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=7
        )
        
        out_x, out_y, _, _ = compute(data)
        
        # Lsn_x = 5.0 - 0.15 - 0.15 = 4.7
        self.assertAlmostEqual(out_x.Lsn_x, 4.7, places=2)
        # Lsn_y = 6.0 - 0.2 - 0.2 = 5.6
        self.assertAlmostEqual(out_x.Lsn_y, 5.6, places=2)


class TestCore(unittest.TestCase):
    """Tests for core.py functions"""
    
    def test_calc_K_and_As_from_M_zero(self):
        """Test K calculation with zero moment"""
        from core import calc_K_and_As_from_M
        
        K, ks, As = calc_K_and_As_from_M(0.0, 0.1, 30.0, "S420")
        self.assertEqual(K, 0.0)
        self.assertEqual(ks, 0.0)
        self.assertEqual(As, 0.0)
    
    def test_calc_K_and_As_from_M_positive(self):
        """Test K calculation with positive moment"""
        from core import calc_K_and_As_from_M
        
        # M = 20 kNm/m, d = 0.1m, C30, S420
        K, ks, As = calc_K_and_As_from_M(20.0, 0.1, 30.0, "S420")
        
        self.assertGreater(K, 0)
        self.assertGreater(ks, 0)
        self.assertGreater(As, 0)
    
    def test_choose_single_layer_rebar(self):
        """Test single layer rebar selection"""
        from core import choose_single_layer_rebar
        
        # Need 400 mm²/m
        result = choose_single_layer_rebar(400.0, s_max_mm=200, s_min_mm=70, phi_min=8)
        
        self.assertGreater(result.phi, 0)
        self.assertGreater(result.As_prov_mm2_per_m, 400)
        self.assertGreaterEqual(result.ratio, 1.0)
    
    def test_choose_main_rebar_half_half(self):
        """Test main rebar selection with 50% straight + 50% pilye"""
        from core import choose_main_rebar_half_half_same_phi
        
        # Need 800 mm²/m total
        layout = choose_main_rebar_half_half_same_phi(800.0, s_max_main_mm=200)
        
        self.assertIsNotNone(layout)
        self.assertGreater(layout.straight.phi, 0)
        self.assertEqual(layout.straight.phi, layout.pilye.phi)  # Same diameter
        self.assertGreater(layout.As_total_prov_mm2_per_m, 800)


class TestModels(unittest.TestCase):
    """Tests for models.py dataclasses"""
    
    def test_input_data_defaults(self):
        """Test InputData default values"""
        from models import InputData
        
        data = InputData(lx=5.0, ly=6.0)
        
        self.assertEqual(data.beam_w_left_x, 250.0)
        self.assertEqual(data.h_mm, 120.0)
        self.assertEqual(data.concrete, "C30")
        self.assertEqual(data.steel, "S420")
        self.assertEqual(data.slab_case, 7)
    
    def test_load_analysis_creation(self):
        """Test LoadAnalysis dataclass"""
        from models import LoadAnalysis
        
        load = LoadAnalysis(
            g_self_weight=3.0,
            g_additional=1.5,
            g_total=4.5,
            q_live=5.0,
            pd_factored=14.3
        )
        
        self.assertEqual(load.g_total, 4.5)
        self.assertEqual(load.pd_factored, 14.3)
    
    def test_slab_design_result(self):
        """Test SlabDesignResult dataclass"""
        from models import SlabDesignResult
        
        result = SlabDesignResult(
            slab_id="TEST-001",
            lx_m=5.0, ly_m=6.0, h_mm=150,
            concrete="C30", steel="S420",
            g_total_kN_m2=4.5, q_live_kN_m2=5.0, pd_factored_kN_m2=14.3,
            slab_type="two_way", slab_case=1, m_ratio=1.2,
            Lsn_x_m=4.7, Lsn_y_m=5.6,
            x_bottom_main="Ø10/15", x_bottom_pilye="Ø10/15", x_top="Ø8/20",
            y_bottom_main="Ø10/15", y_bottom_pilye="Ø10/15", y_top="Ø8/20"
        )
        
        self.assertEqual(result.slab_id, "TEST-001")
        self.assertEqual(result.slab_type, "two_way")


class TestDatabase(unittest.TestCase):
    """Tests for database.py"""
    
    def setUp(self):
        """Create a test database in temp directory"""
        import os
        import uuid
        import tempfile
        self.temp_dir = tempfile.gettempdir()
        self.test_db = os.path.join(self.temp_dir, f"test_slab_{uuid.uuid4().hex[:8]}.db")
        self.db = None
    
    def tearDown(self):
        """Clean up test database"""
        import os
        import time
        # Close any open connections
        if hasattr(self, 'db') and self.db:
            self.db = None
        # Wait a bit for file handles to release (Windows issue)
        time.sleep(0.1)
        try:
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
        except PermissionError:
            pass  # Ignore on Windows
    
    def test_database_creation(self):
        """Test database initialization"""
        from database import SlabDatabase
        import os
        
        self.db = SlabDatabase(self.test_db)
        self.assertTrue(os.path.exists(self.test_db))
    
    def test_save_and_retrieve_design(self):
        """Test saving and retrieving a design"""
        from database import SlabDatabase
        from models import SlabDesignResult
        
        self.db = SlabDatabase(self.test_db)
        
        result = SlabDesignResult(
            slab_id="DB-TEST-001",
            lx_m=5.0, ly_m=6.0, h_mm=150,
            concrete="C30", steel="S420",
            g_total_kN_m2=4.5, q_live_kN_m2=5.0, pd_factored_kN_m2=14.3,
            slab_type="two_way", slab_case=1, m_ratio=1.2,
            Lsn_x_m=4.7, Lsn_y_m=5.6,
            x_bottom_main="Ø10/15", x_bottom_pilye="Ø10/15", x_top="Ø8/20",
            y_bottom_main="Ø10/15", y_bottom_pilye="Ø10/15", y_top="Ø8/20"
        )
        
        row_id = self.db.save_design(result)
        self.assertGreater(row_id, 0)
        
        retrieved = self.db.get_design("DB-TEST-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.slab_id, "DB-TEST-001")
        self.assertEqual(retrieved.lx_m, 5.0)
        self.assertEqual(retrieved.concrete, "C30")
    
    def test_list_designs(self):
        """Test listing all designs"""
        from database import SlabDatabase
        from models import SlabDesignResult
        
        self.db = SlabDatabase(self.test_db)
        
        # Save two designs
        for i in range(2):
            result = SlabDesignResult(
                slab_id=f"LIST-TEST-{i}",
                lx_m=5.0, ly_m=6.0, h_mm=150,
                concrete="C30", steel="S420",
                g_total_kN_m2=4.5, q_live_kN_m2=5.0, pd_factored_kN_m2=14.3,
                slab_type="two_way", slab_case=1, m_ratio=1.2,
                Lsn_x_m=4.7, Lsn_y_m=5.6,
                x_bottom_main="Ø10/15", x_bottom_pilye="Ø10/15", x_top="Ø8/20",
                y_bottom_main="Ø10/15", y_bottom_pilye="Ø10/15", y_top="Ø8/20"
            )
            self.db.save_design(result)
        
        designs = self.db.list_designs()
        self.assertEqual(len(designs), 2)


class TestDiagrams(unittest.TestCase):
    """Tests for diagrams.py"""
    
    def test_format_bar_str(self):
        """Test bar formatting"""
        from diagrams import format_bar_str
        from models import BarChoice
        
        bar = BarChoice(phi=10, s_cm=15.0, As_prov_mm2_per_m=524, 
                        As_prov_cm2_per_m=5.24, ratio=1.05)
        result = format_bar_str(bar)
        self.assertEqual(result, "Ø10/15cm")
        
        # None case
        self.assertEqual(format_bar_str(None), "-")
    
    def test_generate_section_text(self):
        """Test section diagram generation"""
        from diagrams import generate_section_text
        from models import DesignOut, BarChoice, MainRebarLayout
        
        # Create a mock design output
        straight = BarChoice(10, 15.0, 524, 5.24, 1.05)
        pilye = BarChoice(10, 15.0, 524, 5.24, 1.05)
        layout = MainRebarLayout(straight, pilye, 1048, 1000, 1.05)
        
        design = DesignOut(
            direction="X", slab_type="two_way",
            slab_case=1, slab_case_name="Dört kenar sürekli",
            m=1.2, L_short=5.0, L_long=6.0
        )
        design.main_bottom_layout = layout
        design.top_layout = BarChoice(8, 20.0, 251, 2.51, 1.0)
        
        text = generate_section_text(design, h_mm=150, cover_mm=20)
        
        self.assertIn("X DOĞRULTUSU", text)
        self.assertIn("Ø10", text)
    
    def test_generate_pilye_detail(self):
        """Test pilye detail generation"""
        from diagrams import generate_pilye_detail
        
        text = generate_pilye_detail(phi=10, span_m=5.0, h_mm=150, cover_mm=20)
        
        self.assertIn("PİLYE", text)
        self.assertIn("Ø10", text)
        self.assertIn("L/5", text)


class TestConstants(unittest.TestCase):
    """Tests for constant.py"""
    
    def test_oneway_coefficients_exist(self):
        """Test that one-way coefficients are defined"""
        from constant import ONEWAY_COEFFICIENTS
        
        self.assertIn("simple", ONEWAY_COEFFICIENTS)
        self.assertIn("one_end_continuous", ONEWAY_COEFFICIENTS)
        self.assertIn("both_ends_continuous", ONEWAY_COEFFICIENTS)
        
        # Check coefficient values
        self.assertAlmostEqual(ONEWAY_COEFFICIENTS["simple"]["pos"], 1/8, places=4)
        self.assertAlmostEqual(ONEWAY_COEFFICIENTS["one_end_continuous"]["pos"], 1/11, places=4)
    
    def test_min_values(self):
        """Test minimum code values"""
        from constant import MIN_CONCRETE_GRADE, MIN_BEAM_WIDTH_MM
        
        self.assertEqual(MIN_CONCRETE_GRADE, 25)
        self.assertEqual(MIN_BEAM_WIDTH_MM, 250)
    
    def test_slab_cases_complete(self):
        """Test that all 7 slab cases are defined"""
        from constant import SLAB_CASES
        
        for i in range(1, 8):
            self.assertIn(i, SLAB_CASES)
            self.assertIn("name", SLAB_CASES[i])
            self.assertIn("short_pos", SLAB_CASES[i])


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow"""
    
    def test_full_twoway_workflow(self):
        """Test complete two-way slab design workflow"""
        from models import InputData
        from design import compute
        from database import SlabDatabase, create_design_result
        import os
        
        # Create input
        data = InputData(
            lx=5.0, ly=6.0,
            beam_w_left_x=300, beam_w_right_x=300,
            beam_w_left_y=300, beam_w_right_y=300,
            h_mm=150, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=1
        )
        
        # Run design
        out_x, out_y, thk, load = compute(data)
        
        # Verify outputs
        self.assertEqual(out_x.slab_type, "two_way")
        self.assertGreater(out_x.M_pos_kNm_per_m, 0)
        self.assertGreater(out_y.M_pos_kNm_per_m, 0)
        # pd = 1.4*(3.75+1.5) + 1.6*5.0 = 1.4*5.25 + 8.0 = 7.35 + 8.0 = 15.35
        self.assertAlmostEqual(load.pd_factored, 15.35, places=1)
        
        # Save to database in temp directory
        import uuid
        import tempfile
        temp_dir = tempfile.gettempdir()
        test_db = os.path.join(temp_dir, f"integration_{uuid.uuid4().hex[:8]}.db")
        db = SlabDatabase(test_db)
        result = create_design_result(
            slab_id="INT-001",
            data=data,
            out_x=out_x, out_y=out_y,
            load=load, thk=thk
        )
        db.save_design(result)
        
        # Retrieve and verify
        retrieved = db.get_design("INT-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.slab_type, "two_way")
        
        # Note: File cleanup may fail on Windows due to file locking, which is fine
        try:
            import time
            time.sleep(0.1)
            if os.path.exists(test_db):
                os.remove(test_db)
        except PermissionError:
            pass  # Ignore on Windows
    
    def test_full_oneway_workflow(self):
        """Test complete one-way slab design workflow"""
        from models import InputData
        from design import compute
        
        # Create input for one-way slab (m > 2)
        data = InputData(
            lx=2.5, ly=6.0,  # m ≈ 2.4 > 2
            beam_w_left_x=300, beam_w_right_x=300,
            beam_w_left_y=300, beam_w_right_y=300,
            h_mm=150, cover_mm=20,
            concrete="C30", steel="S420",
            g_additional=1.5, q_live=5.0,
            slab_case=7  # Simple span
        )
        
        # Run design
        out_x, out_y, thk, load = compute(data)
        
        # Verify one-way behavior
        self.assertEqual(out_x.slab_type, "one_way")
        self.assertGreater(out_x.m, 2.0)
        
        # One direction should have main reinforcement, other should have distribution
        main_moment = max(out_x.M_pos_kNm_per_m, out_y.M_pos_kNm_per_m)
        self.assertGreater(main_moment, 0)


class TestSystemDesignExample8_2(unittest.TestCase):
    """Regression checks for textbook-style Example 8-2 moment workflow."""

    def test_example_8_2_moments(self):
        from system_design import (
            balance_support_moments,
            moments_cantilever,
            moments_one_way,
            moments_two_way,
        )

        # From the book (Example 8-2):
        # h = 140mm => g_self = 0.14*25 = 3.5; g_add = 1.5 => g=5.0
        # q = 3.5 => pd = 1.4*5.0 + 1.6*3.5 = 12.6 kN/m^2
        pd = 12.6

        # D1 panel: 6.0m x 5.0m with 250mm beams => net spans 5.75 x 4.75, m≈1.21
        # D1 is two-way, "two adjacent edges discontinuous" => slab_case=3
        d1_mom, d1_coef = moments_two_way(
            pd=pd,
            Lsn_short=4.75,
            Lsn_long=5.75,
            slab_case=3,
            x_is_long=True,  # x=6.0 is the long direction
            m_override=1.2,  # textbook uses gross ratio m=6/5
        )

        # Expected (book): M_long_pos=10.5, M_long_neg=13.9, M_short_pos=13.4, M_short_neg=17.6
        self.assertAlmostEqual(d1_mom.Mx_pos, 10.5, places=1)
        self.assertAlmostEqual(d1_mom.Mx_neg, 13.9, places=1)
        self.assertAlmostEqual(d1_mom.My_pos, 13.4, places=1)
        self.assertAlmostEqual(d1_mom.My_neg, 17.6, places=1)

        # D2 panel: one-way (m>2). Book uses L=2.45m for strip moments (fixed–pinned).
        d2_Mpos, d2_Mneg, _ = moments_one_way(pd=pd, L=2.45, coeff_type="fixed_pinned")
        self.assertAlmostEqual(d2_Mpos, 5.32, places=2)
        self.assertAlmostEqual(d2_Mneg, 9.45, places=2)

        # Balcony BD: cantilever L = 1.5 - 0.25/2 = 1.375m
        bd_Mneg = moments_cantilever(pd=pd, L=1.375)
        self.assertAlmostEqual(bd_Mneg, 11.91, places=2)

        # Moment balancing at the shared support between D1 and D2 (book uses 2/3 redistribution)
        # Use spans perpendicular to the support: D1 has 5.0m, D2 has 2.45m.
        d1_bal, d2_bal, info = balance_support_moments(
            M_a=d1_mom.My_neg,
            M_b=d2_Mneg,
            span_perp_a=5.0,
            span_perp_b=2.45,
        )
        self.assertTrue(info["applied"])
        self.assertAlmostEqual(d1_bal, 15.8, places=1)
        self.assertAlmostEqual(d2_bal, 13.1, places=1)


class TestSystemSolverExample8_2(unittest.TestCase):
    def test_example_8_2_system_thickness_and_supports(self):
        from system_solver import compute_system, example_8_2_system

        system = example_8_2_system()
        h_mm, results, hmins, pd = compute_system(
            system=system,
            concrete="C25",
            steel="S420",
            cover_mm=20.0,
            d_y_reduction_mm=10.0,
            g_additional=1.5,
            q_live=3.5,
        )

        # Book chooses h = 140mm (common).
        self.assertEqual(h_mm, 140.0)
        self.assertAlmostEqual(pd, 12.6, places=2)

        # D1/D2 balancing should reflect in the stored moments
        self.assertAlmostEqual(results["D1"].moments_design.My_neg, 15.8, places=1)
        self.assertAlmostEqual(results["D2"].moments_design.My_neg, 13.1, places=1)

        # D1/BD envelope should make both equal to the larger (D1 support)
        self.assertAlmostEqual(results["D1"].moments_design.Mx_neg, 13.9, places=1)
        self.assertAlmostEqual(results["BD"].moments_design.Mcant_neg, 13.9, places=1)


class TestSystemSolverExample8_1(unittest.TestCase):
    def test_example_8_1_moments_match_book(self):
        from system_solver import compute_system, example_8_1_system
        from system_solver import support_extra_bars

        system = example_8_1_system()
        h_mm, results, hmins, pd = compute_system(
            system=system,
            concrete="C25",
            steel="S420",
            cover_mm=20.0,
            d_y_reduction_mm=10.0,
            g_additional=1.5,
            q_live=3.5,
        )

        self.assertEqual(h_mm, 140.0)
        self.assertAlmostEqual(pd, 12.6, places=2)

        # Raw moments (before support envelope)
        d1 = results["D1"].moments_raw
        d2 = results["D2"].moments_raw
        bd = results["BD"].moments_raw

        self.assertAlmostEqual(d1.Mx_pos, 11.29, places=2)
        self.assertAlmostEqual(d1.Mx_neg, 14.92, places=2)
        self.assertAlmostEqual(d1.My_pos, 8.87, places=2)

        self.assertAlmostEqual(d2.Mx_neg, 14.11, places=2)
        self.assertAlmostEqual(d2.Mx_pos, 10.63, places=2)
        self.assertAlmostEqual(d2.My_pos, 9.55, places=2)

        self.assertAlmostEqual(bd.Mcant_neg, 11.91, places=2)

        # Design moments at supports (after envelope)
        self.assertAlmostEqual(results["D1"].moments_design.Mx_neg, 14.92, places=2)
        self.assertAlmostEqual(results["D2"].moments_design.Mx_neg, 14.92, places=2)
        self.assertAlmostEqual(results["BD"].moments_design.Mcant_neg, 14.11, places=2)

        # Bottom reinforcement selection should match the book table (phi8 with large spacings)
        d1x = results["D1"].design_x.main_bottom_layout.straight
        d1y = results["D1"].design_y.main_bottom_layout.straight
        d2x = results["D2"].design_x.main_bottom_layout.straight
        d2y = results["D2"].design_y.main_bottom_layout.straight
        self.assertEqual((d1x.phi, d1x.s_cm), (8, 36.0))
        self.assertEqual((d2x.phi, d2x.s_cm), (8, 38.0))
        self.assertEqual((d1y.phi, d1y.s_cm), (8, 40.0))
        self.assertEqual((d2y.phi, d2y.s_cm), (8, 38.0))

        # Extra top bars at shared supports (book uses Ø8/300 and Ø8/200)
        fck = 25.0
        d_m_x = 0.12  # h=140, cover=20
        # D1/D2 support: existing are pilyes from both slabs in X direction
        extra_k102 = support_extra_bars(
            name="D1/D2",
            M_kNm_per_m=14.92,
            d_m=d_m_x,
            fck=fck,
            steel="S420",
            existing_bars=[
                results["D1"].design_x.main_bottom_layout.pilye,
                results["D2"].design_x.main_bottom_layout.pilye,
            ],
            s_max_mm=300,
            phi_min=8,
        )
        self.assertEqual((extra_k102.extra_bars.phi, extra_k102.extra_bars.s_cm), (8, 30.0))

        # D2/BD support: existing is D2 pilye in X direction
        extra_bd = support_extra_bars(
            name="D2/BD",
            M_kNm_per_m=14.11,
            d_m=d_m_x,
            fck=fck,
            steel="S420",
            existing_bars=[results["D2"].design_x.main_bottom_layout.pilye],
            s_max_mm=300,
            phi_min=8,
        )
        self.assertEqual((extra_bd.extra_bars.phi, extra_bd.extra_bars.s_cm), (8, 20.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
