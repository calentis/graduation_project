"""
system_solver.py
Compute textbook-style multi-panel slab systems (D1/D2/BD) including:
- thickness selection (choose common h = max of panel h_min)
- panel moments (two-way / one-way / cantilever)
- shared-support balancing and enveloping
- rebar selection using existing core routines
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Dict, Iterable, Tuple

from core import (
    calc_K_and_As_from_M,
    choose_distribution_rebar,
    choose_main_rebar_half_half_same_phi,
    choose_single_layer_rebar,
)
from design import thickness_check_oneway, thickness_check_twoway
from models import BarChoice, DesignOut, PanelSpec, SlabSystemInput, SupportBalanceLink, SupportEnvelopeLink
from system_design import (
    PanelMoments,
    balance_support_moments,
    moments_cantilever,
    moments_one_way,
    moments_two_way,
)
from utils import calculate_loads, calculate_net_span, parse_concrete, rho_min_oneway, rho_min_twoway_dir


@dataclass(frozen=True)
class PanelSystemResult:
    panel: PanelSpec
    h_mm: float
    cover_mm: float
    pd: float
    Lsn_x: float
    Lsn_y: float
    moments_raw: PanelMoments
    moments_design: PanelMoments
    design_x: DesignOut
    design_y: DesignOut


@dataclass(frozen=True)
class SupportExtraResult:
    name: str
    M_kNm_per_m: float
    As_req_mm2_per_m: float
    As_existing_mm2_per_m: float
    As_extra_req_mm2_per_m: float
    extra_bars: "BarChoice"


def support_extra_bars(
    *,
    name: str,
    M_kNm_per_m: float,
    d_m: float,
    fck: float,
    steel: str,
    existing_bars: Iterable["BarChoice"],
    s_max_mm: int = 300,
    phi_min: int = 8,
    preferred_s_cm: list[float] | None = None,
) -> SupportExtraResult:
    """
    Compute required extra top bars at a support, considering existing "pilye" bars.
    Returns an extra bar choice sized only for the deficit.
    """
    _, _, As_req = calc_K_and_As_from_M(M_kNm_per_m, d_m, fck, steel)
    As_exist = sum((b.As_prov_mm2_per_m for b in existing_bars if b and b.phi > 0), 0.0)
    As_extra = max(0.0, As_req - As_exist)
    if preferred_s_cm is None:
        preferred_s_cm = [20.0, 25.0, 30.0]
    extra = (
        choose_single_layer_rebar(As_extra, s_max_mm=s_max_mm, s_min_mm=70, phi_min=phi_min, preferred_s_cm=preferred_s_cm)
        if As_extra > 1e-9
        else choose_single_layer_rebar(0.0, s_max_mm=s_max_mm)
    )
    return SupportExtraResult(
        name=name,
        M_kNm_per_m=M_kNm_per_m,
        As_req_mm2_per_m=As_req,
        As_existing_mm2_per_m=As_exist,
        As_extra_req_mm2_per_m=As_extra,
        extra_bars=extra,
    )


def two_way_edge_line_load_points(*, w_area: float, a_perp: float, b_along: float) -> list[tuple[float, float]]:
    """
    45-degree (triangle+trapezoid) load transfer from a two-way slab to a supporting beam edge.

    Inputs:
    - w_area: area load (kN/m^2)
    - a_perp: slab dimension perpendicular to the beam (m)
    - b_along: slab dimension along the beam (m)

    Output: key points (y, w_line) along the beam in meters and kN/m.
    """
    a = float(a_perp)
    b = float(b_along)
    if b <= 1e-9 or a <= 1e-9:
        return [(0.0, 0.0), (b, 0.0)]

    if b <= a:
        # purely triangular (peak at midspan)
        wmax = w_area * (b / 2.0)
        return [(0.0, 0.0), (b / 2.0, wmax), (b, 0.0)]

    # trapezoid: rise over a/2, plateau b-a, fall over a/2
    wmax = w_area * (a / 2.0)
    y1 = a / 2.0
    y2 = b - a / 2.0
    return [(0.0, 0.0), (y1, wmax), (y2, wmax), (b, 0.0)]


def sum_line_loads_at_points(point_sets: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    """Sum multiple piecewise-linear line loads at the union of breakpoints."""
    ys = sorted({y for pts in point_sets for (y, _) in pts})

    def interp(pts: list[tuple[float, float]], y: float) -> float:
        if y <= pts[0][0]:
            return float(pts[0][1])
        if y >= pts[-1][0]:
            return float(pts[-1][1])
        for i in range(1, len(pts)):
            y2, w2 = pts[i]
            y1, w1 = pts[i - 1]
            if y <= y2 + 1e-12:
                t = (y - y1) / (y2 - y1) if abs(y2 - y1) > 1e-12 else 0.0
                return float(w1 + (w2 - w1) * t)
        return float(pts[-1][1])

    summed: list[tuple[float, float]] = []
    for y in ys:
        w = sum(interp(pts, y) for pts in point_sets)
        summed.append((y, w))
    return summed


def _make_design_out(
    *,
    direction: str,
    slab_type: str,
    slab_case: int,
    slab_case_name: str,
    m: float,
    L_short: float,
    L_long: float,
    Lsn_x: float,
    Lsn_y: float,
    d_m: float,
    fck: float,
    steel: str,
    M_pos: float,
    M_neg: float,
    As_pos_req: float,
    As_neg_req: float,
    s_max_bottom_mm: int,
    s_max_top_mm: int,
    note: str = "",
    preferred_s_cm_main: list[float] | None = None,
) -> DesignOut:
    Kp, ksp, _ = calc_K_and_As_from_M(M_pos, d_m, fck, steel)
    Kn, ksn, _ = calc_K_and_As_from_M(M_neg, d_m, fck, steel)

    bottom_layout = choose_main_rebar_half_half_same_phi(
        As_req_mm2_per_m=As_pos_req,
        # s_max_bottom_mm applies to the combined (straight+pilye) spacing effect.
        s_max_main_mm=s_max_bottom_mm,
        s_min_main_mm=70,
        phi_min_main=8,
        preferred_s_cm=preferred_s_cm_main,
    )
    top_layout = choose_single_layer_rebar(
        As_req_mm2_per_m=As_neg_req,
        s_max_mm=s_max_top_mm,
        s_min_mm=70,
        phi_min=8,
    )

    return DesignOut(
        direction=direction,
        slab_type=slab_type,
        slab_case=slab_case,
        slab_case_name=slab_case_name,
        m=m,
        L_short=L_short,
        L_long=L_long,
        Lsn_x=Lsn_x,
        Lsn_y=Lsn_y,
        a_pos_used=0.0,
        M_pos_kNm_per_m=M_pos,
        Kcalc_pos_x1e5=Kp,
        ks_pos=ksp,
        As_pos_req_mm2_per_m=As_pos_req,
        main_bottom_layout=bottom_layout,
        a_neg_used=0.0,
        M_neg_kNm_per_m=M_neg,
        Kcalc_neg_x1e5=Kn,
        ks_neg=ksn,
        As_neg_req_mm2_per_m=As_neg_req,
        top_layout=top_layout,
        d_m=d_m,
        note_min=note,
        note_spacing=f"Alt s_max={s_max_bottom_mm}mm | Üst s_max={s_max_top_mm}mm",
        edges_continuity_note="(sistem hesabı)",
    )


def choose_common_thickness_mm(system: SlabSystemInput, *, h_min_floor_mm: float = 80.0) -> Tuple[float, Dict[str, float]]:
    """Return (h_common_mm_rounded_to_10, {panel_name: h_min_mm})."""
    hmins: Dict[str, float] = {}
    h_max = h_min_floor_mm
    for p in system.panels:
        if p.panel_type == "two_way":
            Lsn_x = calculate_net_span(p.lx, p.beam_w_left_x, p.beam_w_right_x)
            Lsn_y = calculate_net_span(p.ly, p.beam_w_left_y, p.beam_w_right_y)
            thk = thickness_check_twoway(
                Lsn_short=min(Lsn_x, Lsn_y),
                Lsn_long=max(Lsn_x, Lsn_y),
                h_mm=h_min_floor_mm,
                alpha_s=p.alpha_s_thickness,
            )
            hmin = thk.h_min_mm
        elif p.panel_type == "one_way":
            L = float(p.thickness_span_override_m) if p.thickness_span_override_m is not None else (p.lx if p.span_dir == "x" else p.ly)
            thk = thickness_check_oneway(Lsn=L, h_mm=h_min_floor_mm)
            hmin = thk.h_min_mm
        else:
            L = float(p.thickness_span_override_m) if p.thickness_span_override_m is not None else (p.lx if p.span_dir == "x" else p.ly)
            hmin = max((L * 1000.0) / 12.0, h_min_floor_mm)

        hmins[p.name] = float(hmin)
        h_max = max(h_max, hmin)

    h_common = (int(h_max + 9) // 10) * 10
    if system.h_override_mm is not None:
        h_common = max(h_common, float(system.h_override_mm))
    return float(h_common), hmins


def _panel_moments(pd: float, p: PanelSpec) -> PanelMoments:
    Lsn_x = calculate_net_span(p.lx, p.beam_w_left_x, p.beam_w_right_x)
    Lsn_y = calculate_net_span(p.ly, p.beam_w_left_y, p.beam_w_right_y)
    x_is_long = p.lx >= p.ly

    if p.panel_type == "two_way":
        # Textbooks often round m to 2 decimals for coefficient lookup.
        m_override = round(max(max(p.lx, p.ly) / max(min(p.lx, p.ly), 1e-9), 1.0), 2)
        m, _ = moments_two_way(
            pd=pd,
            Lsn_short=min(Lsn_x, Lsn_y),
            Lsn_long=max(Lsn_x, Lsn_y),
            slab_case=p.slab_case,
            x_is_long=x_is_long,
            m_override=m_override,
        )
        # apply optional masks
        if not p.include_Mx_neg:
            m = PanelMoments(**{**m.__dict__, "Mx_neg": 0.0})
        if not p.include_My_neg:
            m = PanelMoments(**{**m.__dict__, "My_neg": 0.0})
        return m

    if p.panel_type == "one_way":
        L = p.lx if p.span_dir == "x" else p.ly
        Mpos, Mneg, _ = moments_one_way(pd=pd, L=L, coeff_type=p.oneway_coeff_type)
        return PanelMoments(Mx_pos=Mpos, Mx_neg=Mneg) if p.span_dir == "x" else PanelMoments(My_pos=Mpos, My_neg=Mneg)

    L0 = p.lx if p.span_dir == "x" else p.ly
    L = float(p.moment_span_override_m) if p.moment_span_override_m is not None else L0
    return PanelMoments(Mcant_neg=moments_cantilever(pd=pd, L=L))


def _get(m: PanelMoments, key: str) -> float:
    return float(getattr(m, key))


def _set(m: PanelMoments, key: str, v: float) -> PanelMoments:
    return PanelMoments(**{**m.__dict__, key: float(v)})


def compute_system(
    *,
    system: SlabSystemInput,
    concrete: str = "C25",
    steel: str = "S420",
    cover_mm: float = 20.0,
    d_y_reduction_mm: float = 10.0,
    g_additional: float = 1.5,
    q_live: float = 3.5,
) -> Tuple[float, Dict[str, PanelSystemResult], Dict[str, float], float]:
    """
    Returns:
    - h_mm (common)
    - per-panel results (moments + chosen rebar in X/Y)
    - hmins (per panel)
    - pd (factored load)
    """
    h_mm, hmins = choose_common_thickness_mm(system)
    _, _, _, pd = calculate_loads(h_mm, g_additional, q_live)

    fck = parse_concrete(concrete)
    d_m_x = max((h_mm - cover_mm) / 1000.0, 1e-6)
    d_m_y = max((h_mm - cover_mm - d_y_reduction_mm) / 1000.0, 1e-6)
    d_mm_x = d_m_x * 1000.0
    d_mm_y = d_m_y * 1000.0
    b_mm = 1000.0

    s_max_bottom_short = int(min(1.5 * h_mm, 200))
    s_max_bottom_long = int(min(1.5 * h_mm, 250))
    s_max_top = int(min(2.0 * h_mm, 200))

    # raw panel moments (as computed from coefficients)
    mom_raw: Dict[str, PanelMoments] = {p.name: _panel_moments(pd, p) for p in system.panels}

    # support-level moment rules are applied per-link (without mutating other supports)
    # - envelope: take max (does not reduce)
    # - balance: may reduce, so it must OVERRIDE raw at that support
    support_envelope: Dict[Tuple[str, str], float] = {}
    support_override: Dict[Tuple[str, str], float] = {}

    # envelope (max) computed from RAW moments
    for link in system.envelope_links:
        env = max(_get(mom_raw[link.panel_a], link.moment_key_a), _get(mom_raw[link.panel_b], link.moment_key_b))
        support_envelope[(link.panel_a, link.moment_key_a)] = max(support_envelope.get((link.panel_a, link.moment_key_a), 0.0), env)
        support_envelope[(link.panel_b, link.moment_key_b)] = max(support_envelope.get((link.panel_b, link.moment_key_b), 0.0), env)

    # balance computed from RAW moments
    for link in system.balance_links:
        ma = _get(mom_raw[link.panel_a], link.moment_key_a)
        mb = _get(mom_raw[link.panel_b], link.moment_key_b)
        ma2, mb2, _ = balance_support_moments(
            M_a=ma,
            M_b=mb,
            span_perp_a=link.span_perp_a,
            span_perp_b=link.span_perp_b,
        )
        # override raw (take max if multiple balancing ops target same key)
        support_override[(link.panel_a, link.moment_key_a)] = max(support_override.get((link.panel_a, link.moment_key_a), 0.0), ma2)
        support_override[(link.panel_b, link.moment_key_b)] = max(support_override.get((link.panel_b, link.moment_key_b), 0.0), mb2)

    # build "design moments" by taking max(raw, support_design)
    mom_design: Dict[str, PanelMoments] = {}
    for name, m0 in mom_raw.items():
        md = m0
        for key in ("Mx_neg", "My_neg", "Mcant_neg"):
            if (name, key) in support_override:
                md = _set(md, key, float(support_override[(name, key)]))
            if (name, key) in support_envelope:
                md = _set(md, key, max(_get(md, key), float(support_envelope[(name, key)])))
        mom_design[name] = md

    # build rebar designs
    results: Dict[str, PanelSystemResult] = {}
    for p in system.panels:
        Lsn_x = calculate_net_span(p.lx, p.beam_w_left_x, p.beam_w_right_x)
        Lsn_y = calculate_net_span(p.ly, p.beam_w_left_y, p.beam_w_right_y)
        L_short = min(p.lx, p.ly)
        L_long = max(p.lx, p.ly)
        m_ratio = L_long / max(L_short, 1e-9)

        m0 = mom_raw[p.name]
        m = mom_design[p.name]

        # direction-specific spacing limits (short vs long span)
        x_is_short = p.lx <= p.ly
        smax_x = s_max_bottom_short if x_is_short else s_max_bottom_long
        smax_y = s_max_bottom_long if x_is_short else s_max_bottom_short

        if p.panel_type == "two_way":
            rho_dir = rho_min_twoway_dir(steel)
            As_min_dir_x = rho_dir * b_mm * d_mm_x
            As_min_dir_y = rho_dir * b_mm * d_mm_y
            As_min_total = 0.0035 * b_mm * min(d_mm_x, d_mm_y)

            _, _, Asx_pos = calc_K_and_As_from_M(m.Mx_pos, d_m_x, fck, steel)
            _, _, Asy_pos = calc_K_and_As_from_M(m.My_pos, d_m_y, fck, steel)
            Asx_pos = max(Asx_pos, As_min_dir_x) if m.Mx_pos > 1e-12 else 0.0
            Asy_pos = max(Asy_pos, As_min_dir_y) if m.My_pos > 1e-12 else 0.0
            ssum = Asx_pos + Asy_pos
            if ssum > 1e-12 and ssum < As_min_total:
                scale = As_min_total / ssum
                Asx_pos *= scale
                Asy_pos *= scale

            _, _, Asx_neg = calc_K_and_As_from_M(m.Mx_neg, d_m_x, fck, steel)
            _, _, Asy_neg = calc_K_and_As_from_M(m.My_neg, d_m_y, fck, steel)
            Asx_neg = max(Asx_neg, 0.002 * b_mm * d_mm_x) if m.Mx_neg > 1e-12 else 0.0
            Asy_neg = max(Asy_neg, 0.002 * b_mm * d_mm_y) if m.My_neg > 1e-12 else 0.0

            dx = _make_design_out(
                direction="X",
                slab_type="two_way",
                slab_case=p.slab_case,
                slab_case_name=p.name,
                m=m_ratio,
                L_short=L_short,
                L_long=L_long,
                Lsn_x=Lsn_x,
                Lsn_y=Lsn_y,
                d_m=d_m_x,
                fck=fck,
                steel=steel,
                M_pos=m.Mx_pos,
                M_neg=m.Mx_neg,
                As_pos_req=Asx_pos,
                As_neg_req=Asx_neg,
                s_max_bottom_mm=smax_x,
                s_max_top_mm=s_max_top,
                note="system/two-way",
                preferred_s_cm_main=p.preferred_s_cm_x,
            )
            dy = _make_design_out(
                direction="Y",
                slab_type="two_way",
                slab_case=p.slab_case,
                slab_case_name=p.name,
                m=m_ratio,
                L_short=L_short,
                L_long=L_long,
                Lsn_x=Lsn_x,
                Lsn_y=Lsn_y,
                d_m=d_m_y,
                fck=fck,
                steel=steel,
                M_pos=m.My_pos,
                M_neg=m.My_neg,
                As_pos_req=Asy_pos,
                As_neg_req=Asy_neg,
                s_max_bottom_mm=smax_y,
                s_max_top_mm=s_max_top,
                note="system/two-way",
                preferred_s_cm_main=p.preferred_s_cm_y,
            )

        elif p.panel_type == "one_way":
            rho = rho_min_oneway(steel)
            As_min = rho * b_mm * d_mm_x

            if p.span_dir == "y":
                _, _, As_pos = calc_K_and_As_from_M(m.My_pos, d_m_y, fck, steel)
                _, _, As_neg = calc_K_and_As_from_M(m.My_neg, d_m_y, fck, steel)
                As_pos = max(As_pos, As_min) if m.My_pos > 1e-12 else 0.0
                As_neg = max(As_neg, As_min) if m.My_neg > 1e-12 else 0.0

                dy = _make_design_out(
                    direction="Y",
                    slab_type="one_way",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_y,
                    fck=fck,
                    steel=steel,
                    M_pos=m.My_pos,
                    M_neg=m.My_neg,
                    As_pos_req=As_pos,
                    As_neg_req=As_neg,
                    s_max_bottom_mm=smax_y,
                    s_max_top_mm=s_max_top,
                    note="system/one-way(main)",
                    preferred_s_cm_main=p.preferred_s_cm_y,
                )
                dx = _make_design_out(
                    direction="X",
                    slab_type="one_way",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=0.0,
                    As_pos_req=0.0,
                    As_neg_req=0.0,
                    s_max_bottom_mm=smax_x,
                    s_max_top_mm=s_max_top,
                    note="system/one-way(dist)",
                )
                As_d = max(0.20 * As_pos, 0.0012 * b_mm * h_mm)
                dx.dist_As_req_mm2_per_m = As_d
                dx.dist_bars = choose_distribution_rebar(As_d)
            else:
                _, _, As_pos = calc_K_and_As_from_M(m.Mx_pos, d_m_x, fck, steel)
                _, _, As_neg = calc_K_and_As_from_M(m.Mx_neg, d_m_x, fck, steel)
                As_pos = max(As_pos, As_min) if m.Mx_pos > 1e-12 else 0.0
                As_neg = max(As_neg, As_min) if m.Mx_neg > 1e-12 else 0.0

                dx = _make_design_out(
                    direction="X",
                    slab_type="one_way",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    M_pos=m.Mx_pos,
                    M_neg=m.Mx_neg,
                    As_pos_req=As_pos,
                    As_neg_req=As_neg,
                    s_max_bottom_mm=smax_x,
                    s_max_top_mm=s_max_top,
                    note="system/one-way(main)",
                    preferred_s_cm_main=p.preferred_s_cm_x,
                )
                dy = _make_design_out(
                    direction="Y",
                    slab_type="one_way",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_y,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=0.0,
                    As_pos_req=0.0,
                    As_neg_req=0.0,
                    s_max_bottom_mm=smax_y,
                    s_max_top_mm=s_max_top,
                    note="system/one-way(dist)",
                )
                As_d = max(0.20 * As_pos, 0.0012 * b_mm * h_mm)
                dy.dist_As_req_mm2_per_m = As_d
                dy.dist_bars = choose_distribution_rebar(As_d)

        else:
            # cantilever: negative moment only in span_dir
            rho = rho_min_oneway(steel)
            As_min = rho * b_mm * d_mm_x
            _, _, As_neg = calc_K_and_As_from_M(m.Mcant_neg, d_m_x, fck, steel)
            As_neg = max(As_neg, As_min) if m.Mcant_neg > 1e-12 else 0.0

            if p.span_dir == "x":
                dx = _make_design_out(
                    direction="X",
                    slab_type="cantilever",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=m.Mcant_neg,
                    As_pos_req=0.0,
                    As_neg_req=As_neg,
                    s_max_bottom_mm=smax_x,
                    s_max_top_mm=s_max_top,
                    note="system/cantilever",
                    preferred_s_cm_main=p.preferred_s_cm_x,
                )
                dy = _make_design_out(
                    direction="Y",
                    slab_type="cantilever",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_y,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=0.0,
                    As_pos_req=0.0,
                    As_neg_req=0.0,
                    s_max_bottom_mm=smax_y,
                    s_max_top_mm=s_max_top,
                    note="system/cantilever",
                    preferred_s_cm_main=p.preferred_s_cm_y,
                )
            else:
                dy = _make_design_out(
                    direction="Y",
                    slab_type="cantilever",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_y,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=m.Mcant_neg,
                    As_pos_req=0.0,
                    As_neg_req=As_neg,
                    s_max_bottom_mm=smax_y,
                    s_max_top_mm=s_max_top,
                    note="system/cantilever",
                    preferred_s_cm_main=p.preferred_s_cm_y,
                )
                dx = _make_design_out(
                    direction="X",
                    slab_type="cantilever",
                    slab_case=7,
                    slab_case_name=p.name,
                    m=m_ratio,
                    L_short=L_short,
                    L_long=L_long,
                    Lsn_x=Lsn_x,
                    Lsn_y=Lsn_y,
                    d_m=d_m_x,
                    fck=fck,
                    steel=steel,
                    M_pos=0.0,
                    M_neg=0.0,
                    As_pos_req=0.0,
                    As_neg_req=0.0,
                    s_max_bottom_mm=smax_x,
                    s_max_top_mm=s_max_top,
                    note="system/cantilever",
                    preferred_s_cm_main=p.preferred_s_cm_x,
                )

        results[p.name] = PanelSystemResult(
            panel=p,
            h_mm=h_mm,
            cover_mm=cover_mm,
            pd=pd,
            Lsn_x=Lsn_x,
            Lsn_y=Lsn_y,
            moments_raw=m0,
            moments_design=m,
            design_x=dx,
            design_y=dy,
        )

    return h_mm, results, hmins, pd


def example_8_2_system() -> SlabSystemInput:
    """Build Example 8-2 system (D1 + D2 + balcony BD)."""
    d1 = PanelSpec(
        name="D1",
        panel_type="two_way",
        lx=6.0,
        ly=5.0,
        beam_w_left_x=250,
        beam_w_right_x=250,
        beam_w_left_y=250,
        beam_w_right_y=250,
        slab_case=3,
        alpha_s_thickness=0.5,
    )
    d2 = PanelSpec(
        name="D2",
        panel_type="one_way",
        lx=6.0,
        ly=2.45,
        beam_w_left_x=250,
        beam_w_right_x=250,
        beam_w_left_y=250,
        beam_w_right_y=250,
        span_dir="y",
        oneway_coeff_type="fixed_pinned",
    )
    bd = PanelSpec(
        name="BD",
        panel_type="cantilever",
        lx=1.375,
        ly=6.0,
        span_dir="x",
    )

    return SlabSystemInput(
        panels=[d1, d2, bd],
        h_override_mm=140.0,
        balance_links=[
            SupportBalanceLink(
                panel_a="D1",
                panel_b="D2",
                moment_key_a="My_neg",
                moment_key_b="My_neg",
                span_perp_a=5.0,
                span_perp_b=2.45,
            )
        ],
        envelope_links=[
            SupportEnvelopeLink(
                panel_a="D1",
                panel_b="BD",
                moment_key_a="Mx_neg",
                moment_key_b="Mcant_neg",
            )
        ],
    )


def example_8_1_system() -> SlabSystemInput:
    """
    Build Example 8-1 system from the photos:
    - D1: 4.25 x 5.30 two-way, "üç kenar süreksiz" -> case 6
      (book uses only short-direction negative; long-direction negative ignored)
    - D2: 4.40 x 5.30 two-way, coefficients match case 4
    - BD: balcony cantilever; book uses moment L=1.375m but thickness L=1.25m
    - Shared supports:
      - D1/D2: ratio>0.8 => use max (envelope) => Md = 14.92
      - D2/BD: envelope => Md = max(14.11, 11.91) = 14.11
    """
    d1 = PanelSpec(
        name="D1",
        panel_type="two_way",
        lx=4.25,
        ly=5.30,
        beam_w_left_x=250,
        beam_w_right_x=250,
        beam_w_left_y=250,
        beam_w_right_y=250,
        slab_case=6,
        alpha_s_thickness=0.28,
        include_My_neg=False,
    )
    d2 = PanelSpec(
        name="D2",
        panel_type="two_way",
        lx=4.40,
        ly=5.30,
        beam_w_left_x=250,
        beam_w_right_x=250,
        beam_w_left_y=250,
        beam_w_right_y=250,
        slab_case=4,
        alpha_s_thickness=0.55,
        include_My_neg=False,
        preferred_s_cm_x=[38.0],
        preferred_s_cm_y=[38.0],
    )
    bd = PanelSpec(
        name="BD",
        panel_type="cantilever",
        lx=1.50,  # geometric projection
        ly=5.30,
        span_dir="x",
        thickness_span_override_m=1.25,  # 1.5 - 0.25
        moment_span_override_m=1.375,    # 1.5 - 0.25/2
    )

    return SlabSystemInput(
        panels=[d1, d2, bd],
        h_override_mm=140.0,
        envelope_links=[
            # D1/D2 shared support moment (short direction = X for both)
            SupportEnvelopeLink(panel_a="D1", panel_b="D2", moment_key_a="Mx_neg", moment_key_b="Mx_neg"),
            # D2/BD support moment (use max between D2 support and balcony cantilever)
            SupportEnvelopeLink(panel_a="D2", panel_b="BD", moment_key_a="Mx_neg", moment_key_b="Mcant_neg"),
        ],
    )

