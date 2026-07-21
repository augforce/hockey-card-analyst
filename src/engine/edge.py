"""NHL Edge vetting - an articulation-only cross-check of a card's verdicts
against nhl.com/nhl-edge league tracking (assess_player's optional edge_card).

Edge data is never assessed on its own: it rides alongside the card being
assessed and vets that card's existing verdicts. The signal hierarchy (config
`edge_rules`, decided 2026-07-21):

- a RATE with a printed comparison average drives a corroborate/contradict
  call when |value - avg| clears the config threshold, with the exact
  percentile cited as color when NHL.com gives one (51st+);
- a rate with NO printed average can drive a call off its exact percentile
  when one is given;
- "<50th" (percentile None) with no average is direction-only - below the
  league median - and stays descriptive, never a magnitude;
- raw COUNTS never drive a call at any percentile: they accumulate with games
  played (the Vanecek finding - a tiny workload dresses a count up as a 99th),
  so they ride in `descriptive` with games played named.

Never moves a tier, a strength, or a weakness - asserted by test.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from engine.common import STRENGTH_MIN, WEAKNESS_MAX, ordinal
from schemas import (
    DefenseCard,
    DefenseMicroCard,
    EdgeMetric,
    ForwardMicroCard,
    GoalieCard,
    GoalieEdgeCard,
    SkaterEdgeCard,
)


class EdgeVetting(BaseModel):
    """Articulation-only Edge cross-check attached to an assessment. The
    corroboration/contradiction lists cite the page's numbers as receipts;
    `descriptive` holds the style and count color that never drives a call."""

    season: str
    corroborations: list[str]
    contradictions: list[str]
    descriptive: list[str]
    caveats: list[str]
    note: str


# --- signal helpers ---------------------------------------------------------


def _direction(em: EdgeMetric, gap_min: float) -> Optional[bool]:
    """True = meaningfully above the comparison, False = meaningfully below,
    None = no usable signal. Average-gap first; exact percentile (51st+) when
    no average is printed; the "<50th" bucket alone is never a call."""
    if em.avg is not None:
        gap = em.value - em.avg
        if abs(gap) < gap_min:
            return None
        return gap > 0
    if em.percentile is not None and em.percentile >= STRENGTH_MIN:
        return True
    return None


def _color(em: EdgeMetric) -> str:
    """The exact percentile as supporting color, only when the page gives one."""
    if em.percentile is None:
        return ""
    return f" (NHL lists it {ordinal(em.percentile)} percentile)"


def _sv(v: float) -> str:
    """Save percentages the way the page prints them: .921, not 0.921."""
    return f"{v:.3f}".lstrip("0") or "0"


# --- goalie path ------------------------------------------------------------


def _vet_goalie(card: GoalieCard, edge: GoalieEdgeCard, cfg: dict[str, Any]) -> EdgeVetting:
    rules = cfg["edge_rules"]
    sv_gap = rules["save_pct_gap"]
    corr: list[str] = []
    cont: list[str] = []
    desc: list[str] = []

    def rate_call(verdict_pct: int, em: EdgeMetric, card_side: str, edge_side: str, value_text: str):
        strong = verdict_pct >= STRENGTH_MIN
        weak = verdict_pct <= WEAKNESS_MAX
        if not (strong or weak):
            return
        above = _direction(em, sv_gap)
        if above is None:
            return
        agrees = above if strong else not above
        if agrees:
            corr.append(
                f"The card's {card_side} ({ordinal(verdict_pct)}) is backed on the "
                f"Edge page: {edge_side} {value_text}{_color(em)}."
            )
        else:
            cont.append(
                f"A tension worth naming: the card reads {card_side} at the "
                f"{ordinal(verdict_pct)}, while the Edge page shows {edge_side} "
                f"{value_text}{_color(em)} - the two sources honestly disagree here."
            )

    m = edge.save_pct_all
    if m.avg is not None:
        rate_call(
            card.proj_war_pct, m, "overall verdict", "all-locations save percentage",
            f"{_sv(m.value)} against a {_sv(m.avg)} league average",
        )
    m = edge.save_pct_high_danger
    if m.avg is not None:
        rate_call(
            card.high_danger, m, "high-danger stopping",
            "a distance-based high-danger save percentage of",
            f"{_sv(m.value)} against a {_sv(m.avg)} league average",
        )
    # Start quality: the card's floor read against the raw .900 cut. Prefer
    # quality starts when it carries a verdict; fall back to bad starts.
    floor_pct = card.quality_starts
    if not (floor_pct >= STRENGTH_MIN or floor_pct <= WEAKNESS_MAX):
        floor_pct = card.bad_starts
    m = edge.pct_starts_over_900
    rate_call(
        floor_pct, m, "start-quality floor", "starts above a .900 save percentage in",
        f"{m.value:.1f}% of his games",
    )
    if m.percentile is None and m.avg is None:
        desc.append(
            f"Starts above a .900 save percentage sit below the league median "
            f"({m.value:.1f}% of his games) - direction only, the page prints no "
            "exact percentile below the 50th."
        )

    # Mid/long-range gaps are color, not vetting - no card box maps to them.
    for label, m in (("mid-range", edge.save_pct_mid_range), ("long-range", edge.save_pct_long_range)):
        if m.avg is not None and abs(m.value - m.avg) >= sv_gap:
            side = "above" if m.value > m.avg else "below"
            desc.append(
                f"Beyond the vetted boxes: {label} save percentage {_sv(m.value)} sits "
                f"{side} the {_sv(m.avg)} league average{_color(m)}."
            )

    # Counts are workload context only - games played named, percentiles never
    # cited (a count's percentile is contaminated by workload by construction).
    sa, ga = edge.shots_against, edge.goals_against
    avg_txt = f" (league average {int(sa.avg)})" if sa.avg is not None else ""
    desc.append(
        f"Workload context: {int(sa.value)} shots against over {edge.gp} games{avg_txt}. "
        "Counts accumulate with games played, so they stay descriptive - "
        f"his {int(ga.value)} goals against carries no verdict weight on its own."
    )

    caveats = [
        cfg["caveats"]["edge_single_season"],
        cfg["caveats"]["edge_different_source"],
        cfg["caveats"]["edge_counts_workload"],
    ]
    return EdgeVetting(
        season=edge.season, corroborations=corr, contradictions=cont,
        descriptive=desc, caveats=caveats, note=rules["note"],
    )


# --- skater path ------------------------------------------------------------


def _vet_skater(primary, edge: SkaterEdgeCard, cfg: dict[str, Any], micro_companion) -> EdgeVetting:
    rules = cfg["edge_rules"]
    zt_gap = rules["zone_time_gap"]
    corr: list[str] = []
    cont: list[str] = []
    desc: list[str] = []
    zone_call_fired = False

    def zone_call(verdict_pct: int, em: EdgeMetric, favorable: Optional[bool],
                  card_side: str, tilt_good: str, tilt_bad: str):
        nonlocal zone_call_fired
        strong = verdict_pct >= STRENGTH_MIN
        weak = verdict_pct <= WEAKNESS_MAX
        if not (strong or weak) or favorable is None:
            return
        numbers = f"{em.value:.1f}% against a {em.avg:.1f}% league average{_color(em)}"
        if strong and favorable:
            corr.append(
                f"The {card_side} strength ({ordinal(verdict_pct)}) shows up "
                f"territorially: {tilt_good} - {numbers}. Territorial share is "
                "on-ice and usage-shaped, not an isolated impact."
            )
            zone_call_fired = True
        elif weak and not favorable:
            corr.append(
                f"The {card_side} weakness ({ordinal(verdict_pct)}) shows up "
                f"territorially too: {tilt_bad} - {numbers}."
            )
            zone_call_fired = True
        else:
            direction = tilt_good if favorable else tilt_bad
            cont.append(
                f"A tension worth naming: the card reads {card_side} at the "
                f"{ordinal(verdict_pct)}, yet {direction} - {numbers}. Territorial "
                "share and isolated impact can honestly disagree; the deployment "
                "caveat applies."
            )
            zone_call_fired = True

    # Offensive tilt vets EV offense; defensive-zone share vets EV defense.
    zo = edge.zone_time_offensive
    fav_o = None
    if zo.avg is not None and abs(zo.value - zo.avg) >= zt_gap:
        fav_o = zo.value > zo.avg
    zone_call(
        primary.ev_offense, zo, fav_o, "EV-offense",
        "the puck lives in the attacking zone more than average with him out there",
        "the attacking-zone share runs under the average with him out there",
    )
    zd = edge.zone_time_defensive
    fav_d = None
    if zd.avg is not None and abs(zd.value - zd.avg) >= zt_gap:
        fav_d = zd.value < zd.avg  # less time hemmed in the D-zone is favorable
    zone_call(
        primary.ev_defense, zd, fav_d, "EV-defense",
        "he sees less defensive-zone time than average",
        "he spends more time hemmed in the defensive zone than average",
    )

    # Tools are style color only, never a call (the Makar/Miller finding).
    def tool_color(em: EdgeMetric) -> str:
        return _color(em) if em.percentile is not None else " (below the league median)"

    hs, ms, mi = edge.hardest_shot, edge.max_skating_speed, edge.most_miles_per_game
    desc.append(
        f"Tools, style color only: hardest shot {hs.value:.2f} mph{tool_color(hs)}, "
        f"max skating speed {ms.value:.2f} mph{tool_color(ms)}, most miles skated "
        f"in a game {mi.value:.2f}{tool_color(mi)}."
    )

    # Shot-location volume is a count - workload context, never a call.
    sog = edge.sog_all
    avg_txt = f" (position average {int(sog.avg)})" if sog.avg is not None else ""
    desc.append(
        f"Shot-location volume: {int(sog.value)} shots on goal over {edge.gp} "
        f"games{avg_txt}; high-danger {int(edge.sog_high_danger.value)}, mid-range "
        f"{int(edge.sog_mid_range.value)}, long-range {int(edge.sog_long_range.value)}. "
        "Counts accumulate with games played, so they stay descriptive."
    )

    # A forward micro card's Skating Speed box is itself NHL Edge data.
    micro_in_play = micro_companion if micro_companion is not None else primary
    if isinstance(micro_in_play, ForwardMicroCard):
        desc.append(
            "Note: the micro card's Skating Speed box is itself built from NHL "
            "Edge tracking, so the Edge speed numbers here are the same source, "
            "not independent corroboration."
        )

    caveats = [
        cfg["caveats"]["edge_single_season"],
        cfg["caveats"]["edge_different_source"],
        cfg["caveats"]["edge_counts_workload"],
        cfg["caveats"]["edge_tools_not_value"],
    ]
    if zone_call_fired:
        # Zone time is a territorial/usage read - the SAME point the existing
        # deployment caveat makes, reused from its one canonical home.
        caveats.append(cfg["caveats"]["deployment_not_value"])

    return EdgeVetting(
        season=edge.season, corroborations=corr, contradictions=cont,
        descriptive=desc, caveats=caveats, note=rules["note"],
    )


# --- entry point ------------------------------------------------------------


def vet_edge(primary, edge, cfg: dict[str, Any], micro_companion=None) -> EdgeVetting:
    """Vet an assessed card's verdicts against the player's NHL Edge page.

    `primary` is the card being assessed (standard skater, goalie, or micro);
    `micro_companion` is the micro card when both cards ride with a standard
    assessment. Guards mirror the micro synthesis: same player, same pool.
    """
    if not isinstance(edge, (GoalieEdgeCard, SkaterEdgeCard)):
        raise ValueError("`edge_card` must be an NHL Edge page (card_kind 'edge').")
    if primary.name.strip().casefold() != edge.name.strip().casefold():
        raise ValueError(
            f"the two cards name different players ({primary.name!r} vs {edge.name!r}) - "
            "Edge vetting needs the same player's page."
        )
    if isinstance(primary, GoalieCard):
        if not isinstance(edge, GoalieEdgeCard):
            raise ValueError(
                "a goalie's card takes a goalie Edge page - skater Edge data "
                "cannot vet a goalie assessment."
            )
        return _vet_goalie(primary, edge, cfg)
    if not isinstance(edge, SkaterEdgeCard):
        raise ValueError(
            "a skater's card takes a skater Edge page - goalie Edge data "
            "cannot vet a skater assessment."
        )
    primary_is_d = isinstance(primary, (DefenseCard, DefenseMicroCard))
    edge_is_d = edge.position == "D"
    if primary_is_d != edge_is_d:
        raise ValueError(
            "the card and the Edge page are from different position pools - the "
            "Edge shots-on-goal baseline splits forwards from defensemen, so the "
            "pools must match."
        )
    return _vet_skater(primary, edge, cfg, micro_companion)
