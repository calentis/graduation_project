# Slab Design Automation Programming: Required Steps
Below are the required steps to structure your design automation programming, incorporating the coefficient method.

1. Pre-Processing and Input Module
Define the building attributes and geometry.
• Geometric Input: Define span lengths (Lx ,Ly), beam widths, and story heights.
• Material Selection: Input material and pick characteristic strengths for concrete (fck) and steel (fyk). For Turkish design, the minimum concrete grade is C25.
• Beam Width Check: Beam width must meet the criteria of minimum 250mm: *Lbeam ≥ 250*.
• Calculate Net Spans: *Lsn = Lx,y - (w_left/2) - (w_right/2)*.
• Slab Type Determination: Calculate the ratio *m=Llong/Lshort*.
    ◦ m>2: One-way slab (Tek Doğrultulu).
    ◦ m≤2: Two-way slab (Çift Doğrultulu).

2. Geometric Verification (Thickness Control)
Before calculating loads, verify the slab thickness (h) meets code minimums to avoid deflection checks.
• Minimum Thickness: Generally *h≥80mm* (or 120 mm for trafficable areas).
• One-way Control: *h≥Ln/30*.
• Two-way Control: Based on the D0U2 formula: *h≥ (Lsn/(15+20/m))​⋅(1−αs/4)*.
​
3. Load Analysis
• Dead Loads (g): Calculate self-weight *(h×25 kN/m³)*, coating, and plaster weights *(γc = 25kN/m3)*.
• Live Loads (q): Assign based on occupancy (e.g., 5.0 kN/m² for commercial/industrial).
• Factored Load (pd): Use the Turkish standard combination: *pd=1.4g+1.6q* (Kn/m2).

4. Structural Analysis (Analysis Module)
A. Coefficient Method (DO1U/D0U2 Etudes)
• One-way: Apply coefficients (1/11,1/15,1/8, etc.) if *q/g≤2* and span ratios are within 0.8 *(Lmin/Lmax > 0.8)*.
• Two-way: Retrieve α moment coefficients from the ABAK tables based on support conditions (e.g., four edges continuous vs. one edge discontinuous).
• Formula: *Md=α⋅pd⋅Lsn^2*.

5. Reinforcement Calculation (As) using ABAK
Integrate the tables from the ABAK_TR_2022 document to automate steel selection.
• Effective Depth (d): d=h−cover (use d≈h−20mm for slabs).
• Section Constant (K): K= b⋅d^2/Md, where b=1.0 m for unit width design. *b(m), d(m), Md(Knm) x 10^5 to look up ABAK*
• Lookup (ks​): Use your code to look up the ks​ value from the ABAK table corresponding to your K and material grade (e.g., C30/S420).
• Required Area: *As​ =ks​⋅Md/d​* (mm2/m), d(m).

6. Detailing and Regulatory Checks
• Minimum Reinforcement:
    ◦ Ensure *ρ≥0.002* (for S420) in one-way slabs.
    ◦ For two-way slabs, check *min(ρx​+ρy​)=0.0035*.
• Spacing (s): Check that *s≤1.5h* and *s≤200mm* (short direction).
• Secondary Reinforcement: Include Distribution Bars (Dağıtma Donatısı) *As,d = As/5* at 1/5 the area of the main bars in one-way slabs.

7. Post-Processing (BDIM Database)
Store the final outputs in a structured format:
• Final thickness and section dimensions.
• Reinforcement diameters and spacings (e.g., ϕ10/130).
• Reinforcement Sketches: Automatically generate diagrams for straight and "pilye" (bent) bars.

---

## Multi-panel (System) problems (Examples 8-1 / 8-2)

Single-panel design is not enough for textbook questions like `D1 + D2 + BD (balcony)` because you must handle **multiple connected panels** and **shared support rules**.

Supported additions:

- **Panel types**: `two_way`, `one_way`, `cantilever`
- **Moments**:
  - two-way: ABAK coefficients (`SLAB_CASES`)
  - one-way: strip coefficients (`ONEWAY_COEFFICIENTS`) incl. **fixed–pinned** (9/128 and 1/8)
  - cantilever: \(M=p_d L^2/2\)
- **Shared supports**:
  - **moment balancing** (redistribute \(2/3\) of difference when \(\min/\max<0.8\))
  - **envelope** (take max of competing support moments)
- **Common thickness**: choose one `h` as max of each panel’s `h_min`.

### Run interactively

```bash
python3 main.py
```

Choose **Mode 2** (“Sistem (Örnek 8-2)”) to print:
- selected common thickness
- system moments per panel
- per-panel bar selections

Choose **Mode 3** (“Sistem (Örnek 8-1)”) to print:
- system moments (raw + design at supports)
- extra support bars (Ek donatı) based on existing pilye bars
- an approximate line-load diagram transferred to beam `K102` (45° method)