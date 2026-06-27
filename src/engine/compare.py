"""compare_players for skaters (PLAN sections 5, 6).

Order of operations:
1. Position-compatibility check FIRST. Percentiles are ranked within a position
   pool, so forward-vs-forward and D-vs-D are fair; forward-vs-D or skater-vs-
   goalie is not, and is refused (never a clean winner across pools).
2. Component-by-component, each with both values and the gap.
3. Overall edge — but it REFUSES to crown a single winner when the components
   genuinely split (A ahead on offence while B is ahead on defence). It only
   calls an edge when one player leads broadly or decisively on projected WAR.
   Same discipline as adjudicate's half-right read.
4. Durability flag: an edge built mainly on finishing is less durable than one
   built on play-driving (finishing volatility from config).

`focus` narrows to offence / defence / overall / a role.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel

from config import load_config
from engine.common import LABELS, ordinal
from schemas import DefenseCard, GoalieCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]

# A gap below this is effectively a tie on a component or an area.
MARGIN = 5
# A projected-WAR gap this large can carry an overall edge on its own.
PROJ_DECISIVE = 10

WAR_COMPONENTS = ["ev_offence", "ev_defence", "pp", "pk", "finishing", "penalties"]
OFFENCE_METRICS = ["ev_offence", "pp", "finishing"]
DEFENCE_METRICS = ["ev_defence", "pk"]
ROLE_TO_METRIC = {
    "pp": "pp",
    "power play": "pp",
    "powerplay": "pp",
    "pk": "pk",
    "penalty kill": "pk",
    "penaltykill": "pk",
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
        reason = (
            f"{card_a.name} is a {pool_a} and {card_b.name} is a {pool_b}; their "
            "percentiles are ranked in different position pools, so the two are not "
            "apples-to-apples and the card cannot crown a winner across them."
        )
        return Comparison(
            compatible=False,
            a_name=card_a.name,
            b_name=card_b.name,
            focus=norm_focus,
            edge_kind="incompatible",
            overall="Different position pools — comparison refused.",
            caveats=[cfg["caveats"]["within_position_only"]],
            reason=reason,
        )

    pool = pool_a
    excluded = set()
    if pool == "defense":
        excluded = set(cfg.get("position_rules", {}).get("defense", {}).get("war_excludes", []))

    metrics = _focus_metrics(norm_focus, excluded)
    components = [_compare_component(m, card_a, card_b) for m in metrics]

    edge, kind, durability, caveats, overall = _decide(
        card_a, card_b, norm_focus, excluded, cfg
    )

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
    return {"offense": "offence", "defense": "defence"}.get(f, f)


def _focus_metrics(focus: Optional[str], excluded: set) -> list[str]:
    base = [m for m in WAR_COMPONENTS if m not in excluded]
    if focus in (None, "overall"):
        return base
    if focus == "offence":
        return [m for m in OFFENCE_METRICS if m not in excluded]
    if focus == "defence":
        return [m for m in DEFENCE_METRICS if m not in excluded]
    metric = ROLE_TO_METRIC.get(focus, focus if focus in base else None)
    return [metric] if metric in base else base


def _compare_component(metric: str, a, b) -> ComponentComparison:
    av = getattr(a, metric, None)
    bv = getattr(b, metric, None)
    label = LABELS.get(metric, metric)
    if av is None or bv is None:
        return ComponentComparison(
            metric=metric, label=label, a_value=av, b_value=bv,
            leader=None, note="NA for one or both players — not comparable.",
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


def _decide(a, b, focus, excluded, cfg):
    """Return (overall_edge, edge_kind, durability, caveats, overall_text)."""
    proj_gap = a.proj_war_pct - b.proj_war_pct

    # --- Focused comparisons crown within the narrowed scope ---
    if focus == "offence" or focus == "defence":
        metrics = _focus_metrics(focus, excluded)
        leader, a_avg, b_avg = _area_leader(metrics, a, b)
        edge = leader if leader in ("A", "B") else None
        if edge:
            text = (
                f"Focused on {focus}: {_name(edge, a, b)} leads "
                f"({a_avg:.0f} vs {b_avg:.0f} average percentile)."
            )
        else:
            text = f"Focused on {focus}: even ({a_avg:.0f} vs {b_avg:.0f} average percentile)."
        return edge, "focus", _durability(edge, a, b, excluded, cfg)[0], _caveats(edge, a, b, excluded, cfg), text

    if focus not in (None, "overall"):
        # A single role/metric.
        metrics = _focus_metrics(focus, excluded)
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
    offence_in = [m for m in OFFENCE_METRICS if m not in excluded]
    defence_in = [m for m in DEFENCE_METRICS if m not in excluded]
    off_leader, _, _ = _area_leader(offence_in, a, b)
    def_leader, _, _ = _area_leader(defence_in, a, b)

    genuine_split = (
        off_leader in ("A", "B") and def_leader in ("A", "B") and off_leader != def_leader
    )

    if genuine_split:
        off_name = _name(off_leader, a, b)
        def_name = _name(def_leader, a, b)
        if abs(proj_gap) >= PROJ_DECISIVE:
            edge = "A" if proj_gap > 0 else "B"
            text = (
                f"{off_name} leads on offence and {def_name} leads on defence — a genuine "
                f"split — but {_name(edge, a, b)}'s projected WAR is clearly higher "
                f"({a.proj_war_pct} vs {b.proj_war_pct}), so the overall edge goes to "
                f"{_name(edge, a, b)} with that tradeoff noted."
            )
            return edge, "proj_war", _durability(edge, a, b, excluded, cfg)[0], _caveats(edge, a, b, excluded, cfg), text
        text = (
            f"Better at what, not better overall. {off_name} leads on offence, "
            f"{def_name} leads on defence; projected WAR is level "
            f"({a.proj_war_pct} vs {b.proj_war_pct}). No single winner — it's a tradeoff."
        )
        return None, "split", None, [], text

    # Not a split: one player leads the areas, or it comes down to projected WAR.
    area_leaders = [l for l in (off_leader, def_leader) if l in ("A", "B")]
    if area_leaders and all(l == area_leaders[0] for l in area_leaders):
        edge = area_leaders[0]
        kind = "broad"
    elif abs(proj_gap) >= MARGIN:
        edge = "A" if proj_gap > 0 else "B"
        kind = "proj_war"
    else:
        edge = None
        kind = "even"

    durability, _ = _durability(edge, a, b, excluded, cfg)
    caveats = _caveats(edge, a, b, excluded, cfg)

    if edge is None:
        text = (
            f"Too close to call — {a.name} and {b.name} are within a hair across the "
            f"board (projected WAR {a.proj_war_pct} vs {b.proj_war_pct})."
        )
    else:
        text = (
            f"{_name(edge, a, b)} has the overall edge (projected WAR "
            f"{a.proj_war_pct} vs {b.proj_war_pct})."
        )
        if durability:
            text += " " + durability
    return edge, kind, durability, caveats, text


def _durability(edge: Optional[str], a, b, excluded: set, cfg):
    """Return (durability_text, attach_finishing_caveat)."""
    if edge not in ("A", "B"):
        return None, False
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
    play_driving = max(lead_gaps.get("ev_offence", 0), lead_gaps.get("ev_defence", 0))
    if finishing_gap is not None and finishing_gap > play_driving:
        return (
            "Less durable — this edge leans on finishing, which swings year to year; "
            "a play-driving edge would be steadier.",
            True,
        )
    return ("Durable — built mainly on play-driving (the repeatable RAPM components).", False)


def _caveats(edge: Optional[str], a, b, excluded: set, cfg) -> list[str]:
    _, attach_finishing = _durability(edge, a, b, excluded, cfg)
    if attach_finishing:
        return [cfg["caveats"]["finishing_volatility"]]
    return []
