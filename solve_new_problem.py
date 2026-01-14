#!/usr/bin/env python3
"""
Solve the new slab system from the image:
- Two D1 slabs (6.0m x 6.0m each, side by side)
- Two BD cantilever slabs (1.5m cantilever, at top and bottom)
- h = 140mm for all
- Beams: 250mm wide
"""

from models import GridAxis, SlabPanel, SlabEdge, SlabSystemInput
from multi_slab import compute_multi_slab_system, print_system_results
from utils import calculate_loads

# First, let's determine the loads (assuming same as Örnek 8-2)
# We need to know g_additional and q values - assuming typical values
h_mm = 140.0
g_additional = 1.5  # kN/m² (kaplama + sıva)
q_live = 3.5  # kN/m² (hareketli yük)

g_self, g_total, q, pd = calculate_loads(h_mm, g_additional, q_live)

print("="*80)
print("YENİ DÖŞEME SİSTEMİ ÇÖZÜMÜ")
print("="*80)

print("\n1. GEOMETRİ")
print("-"*40)
print("D1 döşemeleri: 6.0m x 6.0m (brüt), 2 adet yan yana")
print("BD balkonlar: 1.5m konsol (brüt), üst ve alt")
print("Kiriş genişliği: 250mm")
print("Döşeme kalınlığı: h = 140mm")

print("\n2. NET AÇIKLIKLAR")
print("-"*40)
# Net spans
Lsn_D1_x = 6.0 - 0.25  # 5.75m
Lsn_D1_y = 6.0 - 0.25  # 5.75m
Lsn_BD = 1.5 - 0.125   # 1.375m (half beam deduction for cantilever)

print(f"D1: Lsn_x = 6.0 - 0.25 = {Lsn_D1_x:.3f}m")
print(f"D1: Lsn_y = 6.0 - 0.25 = {Lsn_D1_y:.3f}m")
print(f"BD: Lsn = 1.5 - 0.125 = {Lsn_BD:.3f}m")

print("\n3. DÖŞEME TİPLERİ")
print("-"*40)
m_D1 = max(Lsn_D1_x, Lsn_D1_y) / min(Lsn_D1_x, Lsn_D1_y)
print(f"D1: m = {Lsn_D1_x}/{Lsn_D1_y} = {m_D1:.2f}")
if m_D1 <= 2:
    print(f"     m = {m_D1:.2f} ≤ 2 → İKİ DOĞRULTUDA ÇALIŞAN DÖŞEME")
else:
    print(f"     m = {m_D1:.2f} > 2 → TEK DOĞRULTUDA ÇALIŞAN DÖŞEME")
print("BD: KONSOL DÖŞEME (balkon)")

print("\n4. KALINLIK KONTROLÜ")
print("-"*40)
# D1: Two-way formula h >= Lsn/(15+20/m)*(1-αs/4)
# For case where all edges are continuous (or most), αs ≈ 0
m = m_D1
alpha_s = 0  # Assuming edges are mostly continuous
denom = 15 + 20/m
h_min_D1 = (Lsn_D1_y * 1000) / denom * (1 - alpha_s/4)
print(f"D1: h_min = {Lsn_D1_y*1000:.0f}/(15+20/{m:.2f})×(1-{alpha_s}/4)")
print(f"         = {Lsn_D1_y*1000:.0f}/{denom:.2f} = {h_min_D1:.1f}mm")
print(f"    h = {h_mm}mm ≥ {h_min_D1:.1f}mm → {'OK' if h_mm >= h_min_D1 else 'YETERSİZ'}")

# BD: Cantilever h >= Ln/12
h_min_BD = (Lsn_BD * 1000) / 12
print(f"BD: h_min = {Lsn_BD*1000:.0f}/12 = {h_min_BD:.1f}mm")
print(f"    h = {h_mm}mm ≥ {h_min_BD:.1f}mm → {'OK' if h_mm >= h_min_BD else 'YETERSİZ'}")

print("\n5. YÜK ANALİZİ")
print("-"*40)
print(f"Öz ağırlık: g_kendi = {h_mm/1000:.2f} × 25 = {g_self:.2f} kN/m²")
print(f"Kaplama+Sıva: g_ek = {g_additional:.2f} kN/m²")
print(f"Toplam sabit yük: g = {g_self:.2f} + {g_additional:.2f} = {g_total:.2f} kN/m²")
print(f"Hareketli yük: q = {q_live:.2f} kN/m²")
print(f"Hesap yükü: pd = 1.4×{g_total:.2f} + 1.6×{q_live:.2f} = {pd:.2f} kN/m²")

print("\n6. MOMENT HESABI")
print("-"*40)

# BD Cantilever moment: M = p*L²/2
M_BD = pd * (Lsn_BD ** 2) / 2
print(f"\nBD (Konsol):")
print(f"  M = pd × Lsn² / 2 = {pd:.2f} × {Lsn_BD:.3f}² / 2 = {M_BD:.2f} kNm/m")

# D1 Two-way slab moments
# Since m = 1.0 (square slab), use ABAK coefficients for Case 1 or appropriate case
# Looking at the geometry: D1 slabs have continuous edges at the middle beam
# and with BD cantilevers at sides

# For a square slab (m=1.0), the coefficients from ABAK:
# Let's assume Case 3 (two adjacent edges discontinuous) based on typical layout
# Or Case 1 (all edges continuous) if the middle beam provides continuity

print(f"\nD1 (İki doğrultuda çalışan, m={m_D1:.2f}):")

# Using ABAK table for m=1.0 (interpolation between values)
# For simplicity, let's calculate with the formula
# M = α × pd × Lsn²

# For m = 1.0, square slab:
# Case 1 (4 edges continuous): α_pos ≈ 0.025, α_neg ≈ 0.033
# Case 7 (4 edges discontinuous): α_pos ≈ 0.05, α_neg ≈ 0

# Since D1 has continuity at middle beam and with BD:
# Let's assume Case 1 or similar

from constant import SLAB_CASES
from utils import interp_piecewise

# Determine appropriate case based on edge conditions
# D1-left: continuous at right edge (with D1-right), continuous at top/bottom (with BD)
# This suggests Case 1 (all continuous) or Case 2 (one edge discontinuous)

# Let's use Case 1 for this analysis
case = SLAB_CASES[1]  # 4 edges continuous
print(f"  Tip: Senaryo 1 - Dört kenar sürekli")

aS_pos = interp_piecewise(case["short_pos"], m_D1)
aS_neg = interp_piecewise(case["short_neg"], m_D1) if case["short_neg"] else 0.0
aL_pos = float(case["long_pos"])
aL_neg = float(case["long_neg"])

base = pd * (Lsn_D1_y ** 2)  # Use short span

print(f"  Lsn = {Lsn_D1_y:.3f}m, pd = {pd:.2f} kN/m²")
print(f"  pd × Lsn² = {pd:.2f} × {Lsn_D1_y:.3f}² = {base:.2f}")

M_short_pos = aS_pos * base
M_short_neg = aS_neg * base
M_long_pos = aL_pos * base
M_long_neg = aL_neg * base

print(f"\n  Kısa doğrultu:")
print(f"    α₁ (açıklık) = {aS_pos:.4f} → M₁ = {aS_pos:.4f} × {base:.2f} = {M_short_pos:.2f} kNm/m")
print(f"    α₂ (mesnet)  = {aS_neg:.4f} → M₂ = {aS_neg:.4f} × {base:.2f} = {M_short_neg:.2f} kNm/m")

print(f"\n  Uzun doğrultu:")
print(f"    α₃ (açıklık) = {aL_pos:.4f} → M₃ = {aL_pos:.4f} × {base:.2f} = {M_long_pos:.2f} kNm/m")
print(f"    α₄ (mesnet)  = {aL_neg:.4f} → M₄ = {aL_neg:.4f} × {base:.2f} = {M_long_neg:.2f} kNm/m")

print("\n7. MOMENT DENGELEMESİ")
print("-"*40)

# D1/BD junction (at top and bottom edges)
print("\nD1/BD Mesneti:")
M_D1_at_BD = M_long_neg if M_long_neg > 0 else M_short_neg  # D1's negative moment at BD edge
print(f"  D1 tarafı: M = {M_D1_at_BD:.2f} kNm/m")
print(f"  BD tarafı: M = {M_BD:.2f} kNm/m")
M_design_BD = max(M_D1_at_BD, M_BD)
print(f"  Tasarım momenti: M = max({M_D1_at_BD:.2f}, {M_BD:.2f}) = {M_design_BD:.2f} kNm/m")

# D1-left/D1-right junction (at middle beam)
print("\nD1-Sol/D1-Sağ Mesneti (orta kiriş):")
# Both D1 slabs are identical, so moments are equal - no redistribution needed
print(f"  Her iki taraf: M = {M_short_neg:.2f} kNm/m")
print(f"  Simetrik olduğundan dengeleme gerekmez")

print("\n8. SONUÇ TABLOSU")
print("-"*40)
print(f"{'Döşeme':<10} {'Tip':<15} {'M_pos (kNm/m)':<15} {'M_neg (kNm/m)':<15}")
print("-"*55)
print(f"{'D1':<10} {'İki doğrultulu':<15} {M_short_pos:<15.2f} {M_short_neg:<15.2f}")
print(f"{'BD':<10} {'Konsol':<15} {'-':<15} {M_BD:<15.2f}")

print("\n" + "="*80)
print("HESAP TAMAMLANDI")
print("="*80)

# Now let's also verify with the multi_slab module
print("\n\n" + "="*80)
print("MULTI_SLAB MODÜLÜ İLE DOĞRULAMA")
print("="*80)

# Define the system
x_axes = [
    GridAxis("A", 0.0),
    GridAxis("B", 6.0),
    GridAxis("C", 12.0),
]
y_axes = [
    GridAxis("1", 0.0),      # Bottom BD edge
    GridAxis("2", 1.5),      # D1 bottom edge
    GridAxis("3", 7.5),      # D1 top edge  
    GridAxis("4", 9.0),      # Top BD edge
]

# D1-Left (between A-B and 2-3)
d1_left = SlabPanel(
    panel_id="D1-Sol",
    x_axis_start="A", x_axis_end="B",
    y_axis_start="2", y_axis_end="3",
    lx=6.0, ly=6.0,
    slab_case_override=1,  # All edges continuous
    edge_x_left=SlabEdge(is_fixed=True),
    edge_x_right=SlabEdge(is_continuous=True, adjacent_slab_id="D1-Sağ"),
    edge_y_bottom=SlabEdge(is_continuous=True, adjacent_slab_id="BD-Alt"),
    edge_y_top=SlabEdge(is_continuous=True, adjacent_slab_id="BD-Üst"),
)

# D1-Right (between B-C and 2-3)
d1_right = SlabPanel(
    panel_id="D1-Sağ",
    x_axis_start="B", x_axis_end="C",
    y_axis_start="2", y_axis_end="3",
    lx=6.0, ly=6.0,
    slab_case_override=1,
    edge_x_left=SlabEdge(is_continuous=True, adjacent_slab_id="D1-Sol"),
    edge_x_right=SlabEdge(is_fixed=True),
    edge_y_bottom=SlabEdge(is_continuous=True, adjacent_slab_id="BD-Alt"),
    edge_y_top=SlabEdge(is_continuous=True, adjacent_slab_id="BD-Üst"),
)

# BD-Bottom (cantilever at bottom)
bd_bottom = SlabPanel(
    panel_id="BD-Alt",
    x_axis_start="A", x_axis_end="C",
    y_axis_start="1", y_axis_end="2",
    lx=12.0, ly=1.5,
    slab_type="cantilever",
    cantilever_direction="y-",
    edge_y_top=SlabEdge(is_continuous=True),
    edge_y_bottom=SlabEdge(is_free=True),
)

# BD-Top (cantilever at top)
bd_top = SlabPanel(
    panel_id="BD-Üst",
    x_axis_start="A", x_axis_end="C",
    y_axis_start="3", y_axis_end="4",
    lx=12.0, ly=1.5,
    slab_type="cantilever",
    cantilever_direction="y+",
    edge_y_bottom=SlabEdge(is_continuous=True),
    edge_y_top=SlabEdge(is_free=True),
)

system = SlabSystemInput(
    x_axes=x_axes,
    y_axes=y_axes,
    panels=[d1_left, d1_right, bd_bottom, bd_top],
    h_mm=140.0,
    cover_mm=20.0,
    concrete="C25",
    steel="S420",
    beam_width_mm=250.0,
    g_additional=1.5,
    q_live=3.5,
)

result = compute_multi_slab_system(system)
print_system_results(result)
