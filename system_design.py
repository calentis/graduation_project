"""
system_design.py
Multi-panel slab system helper to solve textbook-style examples like "D1 + D2 + BD balcony".

This module intentionally sits *on top* of the existing single-panel machinery:
- Uses existing ABAK two-way coefficients from `constant.SLAB_CASES`
- Uses existing one-way coefficients from `constant.ONEWAY_COEFFICIENTS`

What it adds:
- Panel-by-panel moment calculation for different slab behaviours (two-way / one-way / cantilever)
- Moment balancing at shared supports (as in many Turkish RC textbooks)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from constant import ONEWAY_COEFFICIENTS, SLAB_CASES
from utils import interp_piecewise


@dataclass(frozen=True)
class PanelMoments:
    """
    Moments are per 1m strip width (kNm/m), matching the rest of the codebase.

    Naming convention:
    - x/y: geometric directions of the panel
    - pos: midspan (positive) moment
    - neg: support (negative) moment at the *critical* supported edge for that direction
    """

    # Two-way / one-way in X direction
    Mx_pos: float = 0.0
    Mx_neg: float = 0.0

    # Two-way / one-way in Y direction
    My_pos: float = 0.0
    My_neg: float = 0.0

    # Optional: cantilever fixed-end (negative) moment (kNm/m)
    Mcant_neg: float = 0.0


def moments_two_way(
    *,
    pd: float,
    Lsn_short: float,
    Lsn_long: float,
    slab_case: int,
    x_is_long: bool,
    m_override: Optional[float] = None,
) -> Tuple[PanelMoments, Dict[str, float]]:
    """
    Two-way slab moments using ABAK coefficients (Tablo 8-2 style):
      M = α * pd * Lsn_short^2

    Returns (moments, coeffs_used).
    """
    m = float(m_override) if m_override is not None else max(Lsn_long / max(Lsn_short, 1e-9), 1.0)
    case = SLAB_CASES[slab_case]

    aS_pos = interp_piecewise(case["short_pos"], m)
    aS_neg = interp_piecewise(case["short_neg"], m) if case["short_neg"] else 0.0
    aL_pos = float(case["long_pos"])
    aL_neg = float(case["long_neg"])

    base = pd * (Lsn_short**2)
    M_short_pos = aS_pos * base
    M_short_neg = aS_neg * base
    M_long_pos = aL_pos * base
    M_long_neg = aL_neg * base

    if x_is_long:
        moments = PanelMoments(
            Mx_pos=M_long_pos,
            Mx_neg=M_long_neg,
            My_pos=M_short_pos,
            My_neg=M_short_neg,
        )
    else:
        moments = PanelMoments(
            Mx_pos=M_short_pos,
            Mx_neg=M_short_neg,
            My_pos=M_long_pos,
            My_neg=M_long_neg,
        )

    return moments, {
        "m": m,
        "a_short_pos": aS_pos,
        "a_short_neg": aS_neg,
        "a_long_pos": aL_pos,
        "a_long_neg": aL_neg,
    }


def moments_one_way(
    *,
    pd: float,
    L: float,
    coeff_type: str,
) -> Tuple[float, float, Dict[str, float]]:
    """
    One-way strip moments:
      M_pos = α_pos * pd * L^2
      M_neg = α_neg * pd * L^2 (if any)

    Returns (M_pos, M_neg, coeffs_used)
    """
    coefs = ONEWAY_COEFFICIENTS[coeff_type]
    base = pd * (L**2)
    M_pos = float(coefs.get("pos", 0.0)) * base
    # negative can be under key "neg" (both ends continuous) or "neg_cont" (one end continuous)
    M_neg = float(coefs.get("neg", 0.0) or coefs.get("neg_cont", 0.0)) * base
    return M_pos, M_neg, {"coeff_type": coeff_type, "a_pos": float(coefs.get("pos", 0.0)), "a_neg": float(coefs.get("neg", 0.0) or coefs.get("neg_cont", 0.0))}


def moments_cantilever(*, pd: float, L: float) -> float:
    """Cantilever fixed-end moment: M = pd * L^2 / 2 (kNm/m)."""
    return pd * (L**2) / 2.0


def balance_support_moments(
    *,
    M_a: float,
    M_b: float,
    span_perp_a: float,
    span_perp_b: float,
    ratio_limit: float = 0.8,
    redistribution: float = 2.0 / 3.0,
) -> Tuple[float, float, Dict[str, float]]:
    """
    Moment balancing at a shared support between two slabs (a and b).

    Textbook rule used in Example 8-2:
    - If min/max < 0.8, redistribute 2/3 of the difference
    - Distribute by slab rigidities; many books approximate rigidity ~ 1/L_perp,
      which leads to weights:
        w_a = span_perp_b / (span_perp_a + span_perp_b)
        w_b = span_perp_a / (span_perp_a + span_perp_b)
      (i.e., the shorter slab gets more moment).

    Returns (M_a_bal, M_b_bal, details).
    """
    Ma = float(M_a)
    Mb = float(M_b)
    Mmax = max(Ma, Mb)
    Mmin = min(Ma, Mb)
    if Mmax <= 1e-12:
        return Ma, Mb, {"applied": False, "reason": "both ~0"}

    r = Mmin / Mmax
    if r >= ratio_limit:
        return Ma, Mb, {"applied": False, "ratio": r, "reason": f"ratio>= {ratio_limit}"}

    dM = redistribution * (Mmax - Mmin)
    denom = max(span_perp_a + span_perp_b, 1e-9)

    # weights inverse to own span (implemented as "other span / sum")
    w_a = span_perp_b / denom
    w_b = span_perp_a / denom

    if Ma >= Mb:
        Ma_bal = Ma - w_a * dM
        Mb_bal = Mb + w_b * dM
    else:
        Mb_bal = Mb - w_b * dM
        Ma_bal = Ma + w_a * dM

    return Ma_bal, Mb_bal, {
        "applied": True,
        "ratio": r,
        "redistribution": redistribution,
        "dM": dM,
        "w_a": w_a,
        "w_b": w_b,
    }

