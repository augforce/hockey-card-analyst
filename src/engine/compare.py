"""compare_players for skaters (PLAN sections 5, 6).

Order of operations:
1. Position-compatibility check FIRST. Percentiles are ranked within a position
   pool, so forward-vs-forward and D-vs-D are fair; forward-vs-D or skater-vs-
   goalie is not, and is refused (never a clean winner across pools).
2. Component-by-component, each with both values and the gap.
3. Overall edge - but it REFUSES to crown a single winner when the components
   genuinely split (A ahead on offense while B is ahead on defense). It only
   calls an edge when one player leads broadly or decisively on projected WAR.
   Same discipline as adjudicate's half-right read.
4. Durability flag: an edge built mainly on finishing is less durable than one
   built on play-driving (finishing volatility from config).

`focus` narrows to offense / defense / overall / a role.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel

from config import load_config
from engine.assess import (
    D_MICRO_METRICS,
    D_STYLE_METRICS,
    F_MICRO_METRICS,
    F_STYLE_METRICS,
)
from engine.common import LABELS, WEAKNESS_MAX, ordinal
from schemas import DefenseCard, DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]

# A gap below this is effectively a tie on a component or an area.
MARGIN = 5
# A projected-WAR gap this large can carry an overall edge on its own.
PROJ_DECISIVE = 10

# Skater components and the two areas that can split (offense vs defense).
WAR_COMPONENTS = ["ev_offense", "ev_defense", "pp", "pk", "finishing", "penalties"]
OFFENSE_METRICS = ["ev_offense", "pp", "finishing"]
DEFENSE_METRICS = ["ev_defense", "pk"]
# Goalie components and the two areas that can split: ceiling (game-stealing) vs
# floor (reliability) - the floor-vs-ceiling reading rule (PLAN section 5).
GOALIE_COMPONENTS = [
    "even_strength", "penalty_kill", "high_danger", "med_danger", "low_danger",
    "quality_starts", "excellent_starts", "bad_starts", "rebound_control",
]
GOALIE_CEILING = ["excellent_starts", "high_danger"]
GOALIE_FLOOR = ["quality_starts", "low_danger", "bad_starts"]
ROLE_TO_METRIC = {
    "pp": "pp",
    "power play": "pp",
    "powerplay": "pp",
    "pk": "pk",
    "penalty kill": "pk",
    "penaltykill": "pk",
}


def _spec(pool: str) -> dict:
    """Component list and the two split-areas for a pool. Same machinery, different
    axes: forwards/D split offense-vs-defense, goalies split ceiling-vs-floor.

    Micro pools: the tracked columns join the component display, but the edge
    logic (the `areas`) stays on the WAR-component row - microstats are
    descriptive, never the value verdict."""
    if pool == "goalie":
        return {
            "components": GOALIE_COMPONENTS,
            "areas": [("ceiling", GOALIE_CEILING), ("floor", GOALIE_FLOOR)],
        }
    if pool == "forward_micro":
        return {
            "components": WAR_COMPONENTS + F_MICRO_METRICS + F_STYLE_METRICS,
            "areas": [("offense", OFFENSE_METRICS), ("defense", DEFENSE_METRICS)],
        }
    if pool == "defense_micro":
        return {
            "components": WAR_COMPONENTS + D_MICRO_METRICS + D_STYLE_METRICS,
            "areas": [("offense", OFFENSE_METRICS), ("defense", DEFENSE_METRICS)],
        }
    return {
        "components": WAR_COMPONENTS,
        "areas": [("offense", OFFENSE_METRICS), ("defense", DEFENSE_METRICS)],
    }


class ComponentComparison(BaseModel):
    """One metric, both players' values, and who leads."""

    metric: str
    label: str
    a_value: Optional[int] = None
    b_value: Optional[int] = None
    gap: Optional[int] = None         # a - b (None if either is NA)
    leader: Optional[str] = None      # "A" / "B" / "tie" / None (NA)
    note: Optional[str] = None


class Comparison(BaseModel):
    """The full head-to-head read."""

    compatible: bool
    a_name: str
    b_name: str
    pool: Optional[str] = None
    focus: Optional[str] = None
    components: list[ComponentComparison] = []
    overall_edge: Optional[str] = None   # "A" / "B" / None (split, even, or refused)
    edge_kind: str = "even"              # broad / proj_war / split / even / focus / incompatible
    overall: str = ""
    durability: Optional[str] = None
    caveats: list[str] = []
    reason: Optional[str] = None         # populated when incompatible


def compare_players(
    card_a,
    card_b,
    focus: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
) -> Comparison:
    cfg = config if config is not None else load_config()
    norm_focus = _norm_focus(focus)
    pool_a, pool_b = _pool(card_a), _pool(card_b)

    # 1. Position-compatibility check FIRST.
    if pool_a != pool_b:
        # Same position but different card regimes (standard vs micro) gets its
        # own honest refusal: single-season tracked percentiles and a
        # three-year-weighted projection are not the same pool.
        if {pool_a, pool_b} in ({"forward", "forward_micro"}, {"defense", "defense_micro"}):
            reason = (
                f"{card_a.name}'s card and {card_b.name}'s card are different regimes - "
                "one is a standard card (three-year-weighted projections), the other a "
                "microstat card (this season's 5v5 per-60 percentiles). "
                + cfg["micro_rules"]["war_row"]
            )
            overall_text = "Different card regimes (standard vs microstat) - comparison refused."
            refusal_caveats = [cfg["caveats"]["micro_single_season"]]
        else:
            reason = (
                f"{card_a.name} is a {pool_a} and {card_b.name} is a {pool_b}; their "
                "percentiles are ranked in different position pools, so the two are not "
                "apples-to-apples and the card cannot crown a winner across them."
            )
            overall_text = "Different position pools - comparison refused."
            refusal_caveats = [cfg["caveats"]["within_position_only"]]
        return Comparison(
            compatible=False,
            a_name=card_a.name,
            b_name=card_b.name,
            focus=norm_focus,
            edge_kind="incompatible",
            overall=overall_text,
            caveats=refusal_caveats,
            reason=reason,
        )

    pool = pool_a
    excluded = set()
    if pool in ("defense", "defense_micro"):
        excluded = set(cfg.get("position_rules", {}).get("defense", {}).get("war_excludes", []))

    spec = _spec(pool)
    metrics = _focus_metrics(norm_focus, spec, excluded)
    components = [_compare_component(m, card_a, card_b) for m in metrics]

    edge, kind, durability, caveats, overall = _decide(
        card_a, card_b, norm_focus, spec, excluded, cfg, pool
    )

    # Every micro comparison rides on one season of tracked data - say so.
    if pool in ("forward_micro", "defense_micro"):
        caveats = [cfg["caveats"]["micro_single_season"]] + caveats

    return Comparison(
        compatible=True,
        a_name=card_a.name,
        b_name=card_b.name,
        pool=pool,
        focus=norm_focus,
        components=components,
        overall_edge=edge,
        edge_kind=kind,
        overall=overall,
        durability=durability,
        caveats=caveats,
    )


def _pool(card) -> str:
    if isinstance(card, DefenseMicroCard):
        return "defense_micro"
    if isinstance(card, ForwardMicroCard):
        return "forward_micro"
    if isinstance(card, DefenseCard):
        return "defense"
    if isinstance(card, SkaterCard):
        return "forward"
    if isinstance(card, GoalieCard):
        return "goalie"
    return "unknown"


def _norm_focus(focus: Optional[str]) -> Optional[str]:
    if focus is None:
        return None
    f = focus.strip().lower()
    # Canonical focus values are American; accept British spellings as aliases.
    return {"offence": "offense", "defence": "defense"}.get(f, f)


def _focus_metrics(focus: Optional[str], spec: dict, excluded: set) -> list[str]:
    base = [m for m in spec["components"] if m not in excluded]
    if focus in (None, "overall"):
        return base
    for label, metrics in spec["areas"]:
        if focus == label:
            return [m for m in metrics if m not in excluded]
    metric = ROLE_TO_METRIC.get(focus, focus if focus in base else None)
    return [metric] if metric in base else base


def _compare_component(metric: str, a, b) -> ComponentComparison:
    av = getattr(a, metric, None)
    bv = getattr(b, metric, None)
    label = LABELS.get(metric, metric)
    if av is None or bv is None:
        return ComponentComparison(
            metric=metric, label=label, a_value=av, b_value=bv,
            leader=None, note="NA for one or both players - not comparable.",
        )
    gap = av - bv
    if abs(gap) < MARGIN:
        leader = "tie"
    else:
        leader = "A" if gap > 0 else "B"
    return ComponentComparison(metric=metric, label=label, a_value=av, b_value=bv, gap=gap, leader=leader)


def _area_leader(metrics: list[str], a, b):
    """Return (leader, a_avg, b_avg) for an area; leader is 'A'/'B'/'tie'/None."""
    avs = [getattr(a, m) for m in metrics if getattr(a, m, None) is not None]
    bvs = [getattr(b, m) for m in metrics if getattr(b, m, None) is not None]
    if not avs or not bvs:
        return None, None, None
    a_avg, b_avg = sum(avs) / len(avs), sum(bvs) / len(bvs)
    diff = a_avg - b_avg
    if abs(diff) < MARGIN:
        return "tie", a_avg, b_avg
    return ("A" if diff > 0 else "B"), a_avg, b_avg


def _name(edge: str, a, b) -> str:
    return a.name if edge == "A" else b.name


def _decide(a, b, focus, spec, excluded, cfg, pool):
    """Return (overall_edge, edge_kind, durability, caveats, overall_text).

    Micro cards carry no Proj. WAR headline, so `proj_gap` is None there: no
    headline tiebreak exists, a genuine split stays a split, and edge text is
    phrased off the WAR components instead of a projected-WAR number."""
    a_proj = getattr(a, "proj_war_pct", None)
    b_proj = getattr(b, "proj_war_pct", None)
    proj_gap = (a_proj - b_proj) if (a_proj is not None and b_proj is not None) else None
    area_labels = [label for label, _ in spec["areas"]]

    # --- Focused on one of the split-areas ---
    if focus in area_labels:
        metrics = _focus_metrics(focus, spec, excluded)
        leader, a_avg, b_avg = _area_leader(metrics, a, b)
        edge = leader if leader in ("A", "B") else None
        if edge:
            text = (
                f"Focused on {focus}: {_name(edge, a, b)} leads "
                f"({a_avg:.0f} vs {b_avg:.0f} average percentile)."
            )
        else:
            text = f"Focused on {focus}: even ({a_avg:.0f} vs {b_avg:.0f} average percentile)."
        dur, _ = _durability(edge, a, b, spec, excluded, cfg, pool)
        return edge, "focus", dur, _caveats(edge, a, b, spec, excluded, cfg, pool), text

    # --- Focused on a single role/metric ---
    if focus not in (None, "overall"):
        metrics = _focus_metrics(focus, spec, excluded)
        if len(metrics) == 1:
            comp = _compare_component(metrics[0], a, b)
            edge = comp.leader if comp.leader in ("A", "B") else None
            if edge:
                text = (
                    f"Focused on {comp.label}: {_name(edge, a, b)} leads "
                    f"({comp.a_value} vs {comp.b_value})."
                )
            else:
                text = f"Focused on {comp.label}: even ({comp.a_value} vs {comp.b_value})."
            return edge, "focus", None, [], text

    # --- Full / overall comparison ---
    (a_label, a_metrics), (b_label, b_metrics) = spec["areas"][0], spec["areas"][1]
    a_in = [m for m in a_metrics if m not in excluded]
    b_in = [m for m in b_metrics if m not in excluded]
    a_lead, _, _ = _area_leader(a_in, a, b)
    b_lead, _, _ = _area_leader(b_in, a, b)

    genuine_split = a_lead in ("A", "B") and b_lead in ("A", "B") and a_lead != b_lead

    if genuine_split:
        a_area_name = _name(a_lead, a, b)
        b_area_name = _name(b_lead, a, b)
        if proj_gap is not None and abs(proj_gap) >= PROJ_DECISIVE:
            edge = "A" if proj_gap > 0 else "B"
            text = (
                f"{a_area_name} leads on {a_label} and {b_area_name} leads on {b_label} - a "
                f"genuine split - but {_name(edge, a, b)}'s projected WAR is clearly higher "
                f"({a_proj} vs {b_proj}), so the overall edge goes to "
                f"{_name(edge, a, b)} with that tradeoff noted."
            )
            dur, _ = _durability(edge, a, b, spec, excluded, cfg, pool)
            return edge, "proj_war", dur, _caveats(edge, a, b, spec, excluded, cfg, pool), text
        if proj_gap is None:
            text = (
                f"Better at what, not better overall. {a_area_name} leads on {a_label}, "
                f"{b_area_name} leads on {b_label}; a micro card has no overall WAR "
                f"headline to break the tie. No single winner - it's a tradeoff."
            )
        else:
            text = (
                f"Better at what, not better overall. {a_area_name} leads on {a_label}, "
                f"{b_area_name} leads on {b_label}; projected WAR is level "
                f"({a_proj} vs {b_proj}). No single winner - it's a tradeoff."
            )
        return None, "split", None, [], text

    # Not a split: one player leads the areas, or it comes down to projected WAR.
    area_leaders = [l for l in (a_lead, b_lead) if l in ("A", "B")]
    if area_leaders and all(l == area_leaders[0] for l in area_leaders):
        edge = area_leaders[0]
        kind = "broad"
    elif proj_gap is not None and abs(proj_gap) >= MARGIN:
        edge = "A" if proj_gap > 0 else "B"
        kind = "proj_war"
    else:
        edge = None
        kind = "even"

    durability, _ = _durability(edge, a, b, spec, excluded, cfg, pool)
    caveats = _caveats(edge, a, b, spec, excluded, cfg, pool)

    if proj_gap is not None:
        proj_note = f"(projected WAR {a_proj} vs {b_proj})"
    else:
        proj_note = "(WAR-component row, this season only - no overall headline on a micro card)"
    if edge is None:
        text = (
            f"Too close to call - {a.name} and {b.name} are within a hair across the "
            f"board {proj_note}."
        )
    else:
        text = f"{_name(edge, a, b)} has the overall edge {proj_note}."
        if durability:
            text += " " + durability
    return edge, kind, durability, caveats, text


def _durability(edge: Optional[str], a, b, spec: dict, excluded: set, cfg, pool: str):
    """Return (durability_text, attach_caveat). Skaters: finishing-driven edges
    are less durable. Goalies: an edge resting on a low-consistency goalie is."""
    if edge not in ("A", "B"):
        return None, False
    if pool == "goalie":
        return _durability_goalie(edge, a, b)
    return _durability_skater(edge, a, b, excluded)


def _durability_skater(edge: str, a, b, excluded: set):
    winner, loser = (a, b) if edge == "A" else (b, a)
    lead_gaps = {}
    for m in [c for c in WAR_COMPONENTS if c not in excluded]:
        wv, lv = getattr(winner, m, None), getattr(loser, m, None)
        if wv is None or lv is None:
            continue
        gap = wv - lv
        if gap >= MARGIN:
            lead_gaps[m] = gap
    finishing_gap = lead_gaps.get("finishing")
    play_driving = max(lead_gaps.get("ev_offense", 0), lead_gaps.get("ev_defense", 0))
    if finishing_gap is not None and finishing_gap > play_driving:
        return (
            "Less durable - this edge leans on finishing, which swings year to year; "
            "a play-driving edge would be steadier.",
            True,
        )
    return ("Durable - built mainly on play-driving (the repeatable RAPM components).", False)


def _durability_goalie(edge: str, a, b):
    winner = a if edge == "A" else b
    if winner.consistency <= WEAKNESS_MAX:
        return (
            f"Less durable - the edge rests on a goalie whose consistency is "
            f"{ordinal(winner.consistency)}, and goalie performance is the least stable "
            f"thing in the model.",
            True,
        )
    return (
        "Durable enough - the leader's consistency holds up, though goalie projections "
        "are always the model's least stable.",
        False,
    )


def _caveats(edge: Optional[str], a, b, spec: dict, excluded: set, cfg, pool: str) -> list[str]:
    _, attach = _durability(edge, a, b, spec, excluded, cfg, pool)
    if not attach:
        return []
    if pool == "goalie":
        return [cfg["goalie_rules"]["consistency_volatility"]]
    return [cfg["caveats"]["finishing_volatility"]]
