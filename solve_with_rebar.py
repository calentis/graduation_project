#!/usr/bin/env python3
"""
Complete solution with rebar selection matching textbook format.
Using Case 3 (two adjacent edges discontinuous) as per the answer key.
"""

import math
from constant import SLAB_CASES
from utils import interp_piecewise, calculate_loads, ks_from_Kcalc

# =============================================================================
# INPUT DATA
# =============================================================================
h_mm = 140.0
cover_mm = 20.0
g_additional = 1.5  # kN/m²
q_live = 3.5  # kN/m²
concrete = "C25"
fck = 25.0

# Net spans
Lsn_D1 = 5.75  # m (both directions, square slab)
Lsn_BD = 1.375  # m (cantilever)

# Effective depths
d_x = h_mm - cover_mm  # 120mm (bottom layer)
d_y = h_mm - cover_mm - 10  # 110mm (top layer, assuming Ø10 bars)

print("="*80)
print("DÖŞEME TASARIMI - TAM ÇÖZÜM")
print("="*80)

# =============================================================================
# 1. LOAD ANALYSIS
# =============================================================================
g_self, g_total, q, pd = calculate_loads(h_mm, g_additional, q_live)
print(f"\n1. YÜK ANALİZİ")
print("-"*40)
print(f"g_kendi = {g_self:.2f} kN/m²")
print(f"g = {g_total:.2f} kN/m²")
print(f"q = {q_live:.2f} kN/m²")
print(f"pd = 1.4×{g_total:.1f} + 1.6×{q_live:.1f} = {pd:.2f} kN/m²")

# =============================================================================
# 2. BALKON MOMENT
# =============================================================================
print(f"\n2. BALKON (BD)")
print("-"*40)
M_BD = pd * (Lsn_BD ** 2) / 2
print(f"M = pd×L²/2 = {pd:.2f}×{Lsn_BD:.3f}²/2 = {M_BD:.2f} kNm/m")

# =============================================================================
# 3. D1 MOMENTS (Case 3 - Two adjacent edges discontinuous)
# =============================================================================
print(f"\n3. D1 AÇIKLIK MOMENTLERİ (Tip 3 - İki komşu kenar süreksiz)")
print("-"*40)

m = 1.0  # Square slab
case = SLAB_CASES[3]  # Case 3

# Get coefficients for m=1.0
aS_pos = interp_piecewise(case["short_pos"], m)  # 0.037
aS_neg = interp_piecewise(case["short_neg"], m)  # 0.049
aL_pos = float(case["long_pos"])  # 0.037
aL_neg = float(case["long_neg"])  # 0.049

base = pd * (Lsn_D1 ** 2)
print(f"m = {m:.2f}, Lsn = {Lsn_D1:.2f}m")
print(f"pd×Lsn² = {pd:.2f}×{Lsn_D1:.2f}² = {base:.2f}")

M_pos = aS_pos * base  # Same for both directions (square)
M_neg = aS_neg * base

print(f"\nKatsayılar (m=1.0):")
print(f"  α_açıklık = {aS_pos:.3f}")
print(f"  α_mesnet = {aS_neg:.3f}")
print(f"\nMomentler:")
print(f"  M_açıklık = {aS_pos:.3f}×{base:.2f} = {M_pos:.2f} kNm/m")
print(f"  M_mesnet = {aS_neg:.3f}×{base:.2f} = {M_neg:.2f} kNm/m")

# =============================================================================
# 4. REBAR CALCULATION FUNCTION
# =============================================================================
def calc_rebar(Md, d_mm, fck, label):
    """Calculate K, ks, As for a given moment."""
    b = 1000  # mm (unit width)
    d_m = d_mm / 1000
    M_Nmm = Md * 1e6  # Convert kNm/m to Nmm/m
    
    # K = b×d²/M × 10⁵ (formula from ABAK)
    K_x1e5 = (b * d_mm**2 / M_Nmm) * 1e2
    
    # Get ks from table
    ks = ks_from_Kcalc(K_x1e5, fck, "S420")
    
    # As = ks × M / d (mm²/m)
    As = (ks / 1000) * (M_Nmm / d_mm)
    
    return K_x1e5, ks, As

def select_rebar(As_req, s_max=200, phi_options=[8, 10, 12]):
    """Select rebar diameter and spacing."""
    for phi in phi_options:
        A_bar = math.pi * phi**2 / 4  # mm²
        # s = 1000 × A_bar / As_req
        s_calc = 1000 * A_bar / As_req
        
        # Round down to nearest 10mm
        s = int(s_calc / 10) * 10
        
        if s >= 70 and s <= s_max:  # Min 70mm, max s_max
            As_prov = 1000 * A_bar / s
            return phi, s, As_prov
    
    # If no single layer works, return best option
    phi = phi_options[-1]
    A_bar = math.pi * phi**2 / 4
    s = max(70, int(1000 * A_bar / As_req / 10) * 10)
    As_prov = 1000 * A_bar / s
    return phi, s, As_prov

# =============================================================================
# 5. AÇIKLIK (SPAN) REINFORCEMENT
# =============================================================================
print(f"\n4. AÇIKLIK DONATISI (50% düz + 50% pilye)")
print("-"*40)
print(f"{'Yer':<8} {'Md':<8} {'d':<6} {'K×10⁻⁵':<10} {'ks':<6} {'As':<8} {'Seçilen':<20}")
print("-"*70)

# D1-X direction (d = 120mm)
K_x, ks_x, As_x = calc_rebar(M_pos, d_x, fck, "D1-X")
phi_x, s_x, As_prov_x = select_rebar(As_x/2, s_max=200)  # Half for düz
print(f"{'D1-X':<8} {M_pos:<8.2f} {d_x/1000:<6.2f} {K_x:<10.0f} {ks_x:<6.2f} {As_x:<8.0f} Ø{phi_x}/{s_x}+Ø{phi_x}/{s_x}")

# D1-Y direction (d = 110mm)
K_y, ks_y, As_y = calc_rebar(M_pos, d_y, fck, "D1-Y")
phi_y, s_y, As_prov_y = select_rebar(As_y/2, s_max=200)
print(f"{'D1-Y':<8} {M_pos:<8.2f} {d_y/1000:<6.2f} {K_y:<10.0f} {ks_y:<6.2f} {As_y:<8.0f} Ø{phi_y}/{s_y}+Ø{phi_y}/{s_y}")

# Minimum reinforcement check
print(f"\nMinimum Donatı Kontrolü:")
rho_min = 0.002  # For S420
As_min_x = rho_min * 1000 * d_x
As_min_y = rho_min * 1000 * d_y
print(f"  As_min_x = 0.002×1000×{d_x:.0f} = {As_min_x:.0f} mm²/m")
print(f"  As_min_y = 0.002×1000×{d_y:.0f} = {As_min_y:.0f} mm²/m")

# Total ratio check
rho_min_total = 0.0035
As_min_total = rho_min_total * 1000 * (d_x + d_y) / 2
print(f"  min(ρx+ρy) = 0.0035×1000×({d_x:.0f}+{d_y:.0f})/2 = {As_min_total:.1f} mm²/m")

# Spacing check
s_max_short = min(1.5 * h_mm, 200)
s_max_long = min(1.5 * h_mm, 250)
print(f"\nAralık Kontrolü:")
print(f"  s ≤ 1.5h = 1.5×{h_mm:.0f} = {1.5*h_mm:.0f}mm")
print(f"  s ≤ 200mm (kısa doğrultu)")
print(f"  s ≤ 250mm (uzun doğrultu)")

# =============================================================================
# 6. MESNET (SUPPORT) REINFORCEMENT
# =============================================================================
print(f"\n5. MESNET DONATISI")
print("-"*40)
print(f"{'Yer':<10} {'Md':<8} {'d':<6} {'K×10⁻⁵':<10} {'ks':<6} {'As':<8} {'Mevcut':<12} {'Ek':<12}")
print("-"*80)

# D1|D1 support (middle beam) - use d_x = 120mm
K_neg, ks_neg, As_neg = calc_rebar(M_neg, d_x, fck, "D1|D1")
phi_neg, s_neg, As_prov_neg = select_rebar(As_neg, s_max=200)
# Mevcut = existing from span pilye, Ek = additional
print(f"{'D1|D1':<10} {M_neg:<8.2f} {d_x/1000:<6.2f} {K_neg:<10.0f} {ks_neg:<6.2f} {As_neg:<8.0f} Ø{phi_x}/{s_x:<10} Ø{phi_neg}/{s_neg}")

# D1|BD support (balcony edge)
M_design_BD = max(M_neg, M_BD)
K_bd, ks_bd, As_bd = calc_rebar(M_BD, d_x, fck, "Balkon")
phi_bd, s_bd, As_prov_bd = select_rebar(As_bd, s_max=250)
print(f"{'Balkon':<10} {M_BD:<8.2f} {d_x/1000:<6.2f} {K_bd:<10.0f} {ks_bd:<6.2f} {As_bd:<8.0f} Ø{phi_y}/{s_y:<10} Ø{phi_bd}/{s_bd}")

# =============================================================================
# 7. BALKON DAĞITMA DONATISI
# =============================================================================
print(f"\n6. BALKON DAĞITMA DONATISI")
print("-"*40)
As_dist = As_bd / 5  # Distribution = 1/5 of main
print(f"As_dağıtma = As/5 = {As_bd:.0f}/5 = {As_dist:.1f} mm²/m")
phi_dist, s_dist, As_prov_dist = select_rebar(As_dist, s_max=300, phi_options=[6, 8])
print(f"Seçilen: Ø{phi_dist}/{s_dist} (As = {As_prov_dist:.0f} mm²/m)")

# =============================================================================
# 8. SUMMARY TABLE
# =============================================================================
print(f"\n" + "="*80)
print("SONUÇ TABLOSU")
print("="*80)

print(f"\n{'Yer':<15} {'Moment':<12} {'d (m)':<8} {'K×10⁻⁵':<10} {'ks':<8} {'As (mm²/m)':<12} {'Seçilen':<20}")
print("-"*95)
print(f"{'D1-X açıklık':<15} {M_pos:<12.2f} {d_x/1000:<8.2f} {K_x:<10.0f} {ks_x:<8.2f} {As_x:<12.0f} {'Ø'+str(phi_x)+'/'+str(s_x)+'+Ø'+str(phi_x)+'/'+str(s_x):<20}")
print(f"{'D1-Y açıklık':<15} {M_pos:<12.2f} {d_y/1000:<8.2f} {K_y:<10.0f} {ks_y:<8.2f} {As_y:<12.0f} {'Ø'+str(phi_y)+'/'+str(s_y)+'+Ø'+str(phi_y)+'/'+str(s_y):<20}")
print(f"{'D1|D1 mesnet':<15} {M_neg:<12.2f} {d_x/1000:<8.2f} {K_neg:<10.0f} {ks_neg:<8.2f} {As_neg:<12.0f} {'Ø'+str(phi_neg)+'/'+str(s_neg)+' (ek)':<20}")
print(f"{'Balkon':<15} {M_BD:<12.2f} {d_x/1000:<8.2f} {K_bd:<10.0f} {ks_bd:<8.2f} {As_bd:<12.0f} {'Ø'+str(phi_bd)+'/'+str(s_bd):<20}")
print(f"{'Balkon dağıtma':<15} {'-':<12} {'-':<8} {'-':<10} {'-':<8} {As_dist:<12.1f} {'Ø'+str(phi_dist)+'/'+str(s_dist):<20}")

print("\n" + "="*80)
