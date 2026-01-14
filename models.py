# ============================================================
# models.py # Veri modelleri
# ============================================================

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class BarChoice:
    phi: int
    s_cm: float
    As_prov_mm2_per_m: float
    As_prov_cm2_per_m: float
    ratio: float

@dataclass
class MainRebarLayout:
    straight: BarChoice
    pilye: BarChoice
    As_total_prov_mm2_per_m: float
    As_total_req_mm2_per_m: float
    ratio: float

@dataclass
class ThicknessCheck:
    h_min_mm: float
    ok: bool
    note: str

@dataclass
class InputData:
    """Enhanced input data with beam widths and separate loads per TS500/TBDY-2018"""
    # Geometry
    lx: float  # X span length (m)
    ly: float  # Y span length (m)
    
    # Beam widths (mm) - for net span calculation
    beam_w_left_x: float = 250.0   # Left beam width in X direction
    beam_w_right_x: float = 250.0  # Right beam width in X direction
    beam_w_left_y: float = 250.0   # Left beam width in Y direction
    beam_w_right_y: float = 250.0  # Right beam width in Y direction
    
    # Slab properties
    h_mm: float = 120.0       # Slab thickness (mm)
    cover_mm: float = 20.0    # Concrete cover (mm)
    
    # Materials
    concrete: str = "C30"     # Concrete grade (min C25)
    steel: str = "S420"       # Steel grade
    
    # Loads (kN/m²) - separate dead and live per README
    g_additional: float = 1.5  # Additional dead load (coating, plaster, etc.)
    q_live: float = 5.0        # Live load based on occupancy
    
    # Slab case (support conditions)
    slab_case: int = 7  # 1..7 from ABAK tables
    
    # Optional identifier for database storage
    slab_id: Optional[str] = None


@dataclass
class DesignOut:
    direction: str
    slab_type: str
    slab_case: int
    slab_case_name: str
    m: float
    L_short: float
    L_long: float
    
    # Net spans (after beam deductions)
    Lsn_x: float = 0.0
    Lsn_y: float = 0.0

    # Pozitif moment (alt donatı) için
    a_pos_used: float = 0.0
    M_pos_kNm_per_m: float = 0.0
    Kcalc_pos_x1e5: float = 0.0
    ks_pos: float = 0.0
    As_pos_req_mm2_per_m: float = 0.0
    main_bottom_layout: Optional[MainRebarLayout] = None

    # Negatif moment (üst donatı) için
    a_neg_used: float = 0.0
    M_neg_kNm_per_m: float = 0.0
    Kcalc_neg_x1e5: float = 0.0
    ks_neg: float = 0.0
    As_neg_req_mm2_per_m: float = 0.0
    top_layout: Optional[BarChoice] = None

    # Ortak
    d_m: float = 0.0
    note_min: str = ""
    note_spacing: str = ""
    edges_continuity_note: str = ""

    # Tek doğrultuda moment olmayan doğrultu için dağıtma
    dist_As_req_mm2_per_m: float = 0.0
    dist_bars: Optional[BarChoice] = None


@dataclass
class LoadAnalysis:
    """Load analysis results per TS500"""
    g_self_weight: float  # Self-weight: h × 25 kN/m³
    g_additional: float   # Additional dead load (coating, plaster)
    g_total: float        # Total dead load
    q_live: float         # Live load
    pd_factored: float    # Factored load: 1.4g + 1.6q


@dataclass
class SlabDesignResult:
    """Database storage model for slab design results"""
    slab_id: str
    
    # Input summary
    lx_m: float
    ly_m: float
    h_mm: float
    concrete: str
    steel: str
    
    # Load summary
    g_total_kN_m2: float
    q_live_kN_m2: float
    pd_factored_kN_m2: float
    
    # Slab classification
    slab_type: str  # "one_way" or "two_way"
    slab_case: int
    m_ratio: float
    
    # Net spans
    Lsn_x_m: float
    Lsn_y_m: float
    
    # Reinforcement results (string format: "Ø10/130")
    x_bottom_main: str
    x_bottom_pilye: str
    x_top: str
    y_bottom_main: str
    y_bottom_pilye: str
    y_top: str
    
    # Distribution bars (one-way only)
    distribution_bars: str = ""
    
    # Thickness check
    h_min_required_mm: float = 0.0
    thickness_ok: bool = True
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""


# ============================================================
# MULTI-SLAB SYSTEM MODELS
# ============================================================

@dataclass
class GridAxis:
    """Represents an axis in the building grid system (e.g., A, B, C or 1, 2, 3)"""
    name: str          # e.g., "A", "B", "1", "2"
    position: float    # Position in meters from origin
    
    def __repr__(self):
        return f"GridAxis({self.name}, {self.position}m)"


@dataclass
class SlabEdge:
    """Edge condition for a slab panel"""
    is_continuous: bool = False     # True if continuous with adjacent slab
    is_fixed: bool = False          # True if fixed (e.g., at beam/wall)
    is_free: bool = False           # True if free edge (cantilever tip)
    adjacent_slab_id: Optional[str] = None  # ID of adjacent slab if continuous


@dataclass
class SlabPanel:
    """
    Represents a single slab panel in a multi-slab system.
    Can be: two_way, one_way, or cantilever
    """
    panel_id: str               # e.g., "D1", "D2", "BD"
    
    # Grid position (axes)
    x_axis_start: str           # Start axis in X (e.g., "A")
    x_axis_end: str             # End axis in X (e.g., "B")
    y_axis_start: str           # Start axis in Y (e.g., "1")
    y_axis_end: str             # End axis in Y (e.g., "2")
    
    # Dimensions (meters) - gross spans
    lx: float                   # X direction span
    ly: float                   # Y direction span
    
    # Slab type: "two_way", "one_way", "cantilever"
    slab_type: str = "auto"     # "auto" = determined by m ratio
    
    # Cantilever direction (only for cantilever slabs)
    cantilever_direction: Optional[str] = None  # "x+" means cantilever in +X direction
    
    # Edge conditions (left, right, bottom, top)
    edge_x_left: SlabEdge = field(default_factory=SlabEdge)
    edge_x_right: SlabEdge = field(default_factory=SlabEdge)
    edge_y_bottom: SlabEdge = field(default_factory=SlabEdge)
    edge_y_top: SlabEdge = field(default_factory=SlabEdge)
    
    # Optional specific slab case override (1-7)
    slab_case_override: Optional[int] = None
    
    def get_span_ratio(self, Lsn_x: float, Lsn_y: float) -> float:
        """Calculate m = Llong/Lshort using net spans"""
        L_short = min(Lsn_x, Lsn_y)
        L_long = max(Lsn_x, Lsn_y)
        return L_long / L_short if L_short > 0.01 else 1.0
    
    def determine_type(self, Lsn_x: float, Lsn_y: float) -> str:
        """Determine slab type based on dimensions and configuration"""
        if self.slab_type != "auto":
            return self.slab_type
        
        # Cantilever if specified
        if self.cantilever_direction:
            return "cantilever"
        
        # Check aspect ratio
        m = self.get_span_ratio(Lsn_x, Lsn_y)
        return "one_way" if m > 2.0 else "two_way"


@dataclass
class SlabSystemInput:
    """
    Input data for a multi-slab floor system.
    Example: Örnek 8-2 with D1, D2, and BD slabs.
    """
    # Grid axes definitions
    x_axes: List[GridAxis] = field(default_factory=list)  # e.g., [A(0), B(6), C(7.5)]
    y_axes: List[GridAxis] = field(default_factory=list)  # e.g., [1(0), 2(5), 3(7.45)]
    
    # Slab panels
    panels: List[SlabPanel] = field(default_factory=list)
    
    # Common properties
    h_mm: float = 140.0         # Slab thickness (mm)
    cover_mm: float = 20.0      # Concrete cover (mm)
    concrete: str = "C25"       # Concrete grade
    steel: str = "S420"         # Steel grade
    
    # Beam dimensions (for net span calculation)
    beam_width_mm: float = 250.0   # Default beam width
    beam_depth_mm: float = 600.0   # Default beam depth
    
    # Loads (kN/m²)
    g_additional: float = 1.5      # Additional dead load (finishing, plaster)
    q_live: float = 3.5            # Live load


@dataclass
class PanelMoments:
    """Calculated moments for a slab panel"""
    panel_id: str
    slab_type: str              # "two_way", "one_way", "cantilever"
    m_ratio: float              # Llong/Lshort
    
    # Net spans
    Lsn_x: float
    Lsn_y: float
    
    # Short direction moments (kNm/m)
    M_short_pos: float = 0.0    # Positive (midspan)
    M_short_neg: float = 0.0    # Negative (support)
    
    # Long direction moments (kNm/m)
    M_long_pos: float = 0.0     # Positive (midspan)
    M_long_neg: float = 0.0     # Negative (support)
    
    # Cantilever moment (kNm/m)
    M_cantilever: float = 0.0   # At fixed end
    
    # Alpha coefficients used
    alpha_short_pos: float = 0.0
    alpha_short_neg: float = 0.0
    alpha_long_pos: float = 0.0
    alpha_long_neg: float = 0.0


@dataclass
class SupportMomentBalance:
    """Moment balancing result at a common support between slabs"""
    support_location: str       # e.g., "D1/D2 ara mesnet" or "D1/BD mesnet"
    
    # Original moments from each side
    M_left: float               # kNm/m from left/bottom slab
    M_right: float              # kNm/m from right/top slab
    
    # Balanced moments (after distribution)
    M_left_balanced: float
    M_right_balanced: float
    
    # Design moment (max used)
    M_design: float
    
    # Notes
    note: str = ""


@dataclass
class SlabSystemResult:
    """Complete design result for a multi-slab system"""
    # Common properties
    h_mm: float
    pd_factored: float
    
    # Panel results (dict keyed by panel_id)
    panel_moments: dict = field(default_factory=dict)      # panel_id -> PanelMoments
    panel_designs: dict = field(default_factory=dict)      # panel_id -> (DesignOut_x, DesignOut_y)
    panel_thickness: dict = field(default_factory=dict)    # panel_id -> ThicknessCheck
    
    # Support balancing results
    support_balances: List[SupportMomentBalance] = field(default_factory=list)
    
    # Load analysis
    load_analysis: Optional[LoadAnalysis] = None
    
    # Notes and warnings
    notes: List[str] = field(default_factory=list)
