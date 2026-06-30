"""assess_player for skaters (PLAN sections 5, 6, 12).

Turns a validated skater card into structured findings: overall tier, top
strengths and weaknesses (from the value-bearing WAR components), deployment
context, trajectory from the trend, the caveats the verdict leans on, and a
one-line summary. The server returns this structure; Claude Desktop narrates it.

Two rules from the plan are load-bearing here:
- An NA component (pp/pk = None) is the absence of a role, not a weakness. It is
  reported as deployment context and never read as a zero.
- A defenseman's Finishing appears on the card but is excluded from his WAR
  (config `position_rules.defense.war_excludes`); it is reported descriptively
  and never credited to his value.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel

from config import load_config
from engine.common import LABELS, STRENGTH_MIN, WEAKNESS_MAX, ordinal
from engine.tiers import classify_percentile
from schemas import DefenseCard, GoalieCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]

# Goalie metric groupings (PLAN sections 4, 5).
GOALIE_SKILLS = ["even_strength", "penalty_kill", "rebound_control"]
GOALIE_DANGER = ["high_danger", "med_danger", "low_danger"]
GOALIE_START_QUALITY = ["quality_starts", "excellent_starts", "bad_starts"]

# Value-bearing WAR components, in display order. For a defenseman, any metric in
# `position_rules.defense.war_excludes` (Finishing) is pulled out of this set.
WAR_COMPONENTS = ["ev_offense", "ev_defense", "pp", "pk", "finishing", "penalties"]
# Extra descriptive metrics — never themselves the WAR verdict (PLAN section 4).
DESCRIPTIVE = ["goals", "first_assists"]
# Usage metrics — deployment, never a strength or weakness (PLAN section 5).
DEPLOYMENT = ["competition", "teammates"]

class ComponentRead(BaseModel):
    """One metric placed in its tier, with any attached note."""

    metric: str
    label: str
    percentile: int
    tier: str
    note: Optional[str] = None


class ScoringProfileRead(BaseModel):
    """EV offense (play-driving) read against finishing (conversion).

    Articulation only — never moves the tier or the WAR verdict. `shape` is one
    of both_high / positive_regression / negative_regression; the two percentiles
    it weighs are carried alongside the note so a narrator can cite them.
    """

    shape: str
    label: str
    ev_offense: int
    finishing: int
    note: str


class Assessment(BaseModel):
    """Structured assessment of a single skater (the server's return shape)."""

    name: str
    team: str
    position: str
    overall_tier: str
    overall_percentile: int
    overall_note: Optional[str] = None
    strengths: list[ComponentRead]
    weaknesses: list[ComponentRead]
    descriptive: list[ComponentRead]
    deployment: list[str]
    scoring_profile: Optional[ScoringProfileRead] = None
    trajectory: Optional[str] = None
    caveats: list[str]
    summary: str


class Profile(BaseModel):
    """A cluster of metrics read as one shape (danger split, start quality)."""

    label: str
    reads: list[ComponentRead]
    shape: str


class ConsistencyRead(BaseModel):
    """Consistency reported as a volatility flag, not a skill (PLAN section 5)."""

    percentile: int
    tier: str
    note: str


class GoalieAssessment(BaseModel):
    """Structured assessment of a goalie (the server's goalie return shape)."""

    name: str
    team: str
    role: str
    overall_tier: str
    overall_percentile: int
    overall_note: Optional[str] = None
    danger_profile: Profile
    start_quality_profile: Profile
    strengths: list[ComponentRead]
    weaknesses: list[ComponentRead]
    consistency: ConsistencyRead
    workload: str
    trajectory: Optional[str] = None
    caveats: list[str]
    summary: str


def assess_player(card, config: Optional[dict[str, Any]] = None):
    """Assess a card into structured findings; dispatches on card type.

    Returns an Assessment for skaters, or a GoalieAssessment for goalies (goalies
    run different reading rules over the same tier/threshold machinery).
    """
    cfg = config if config is not None else load_config()
    if isinstance(card, GoalieCard):
        return assess_goalie(card, cfg)
    is_defense = isinstance(card, DefenseCard)
    excluded = set()
    if is_defense:
        excluded = set(cfg.get("position_rules", {}).get("defense", {}).get("war_excludes", []))

    overall = classify_percentile(card.proj_war_pct, cfg)

    strengths: list[ComponentRead] = []
    weaknesses: list[ComponentRead] = []
    descriptive: list[ComponentRead] = []
    deployment: list[str] = []

    # Value-bearing WAR components (excluding any position-excluded metric).
    for metric in WAR_COMPONENTS:
        if metric in excluded:
            continue
        value = getattr(card, metric)
        if value is None:  # NA — absence of a role, not a weakness.
            deployment.append(_na_note(metric))
            continue
        read = _read(metric, value, cfg)
        if read.percentile >= STRENGTH_MIN:
            strengths.append(read)
        elif read.percentile <= WEAKNESS_MAX:
            weaknesses.append(read)

    # Descriptive metrics — supporting colour, never the WAR verdict.
    for metric in DESCRIPTIVE:
        value = getattr(card, metric, None)
        if value is not None:
            descriptive.append(_read(metric, value, cfg))

    # Position-excluded metrics (defenseman Finishing) — descriptive only.
    for metric in excluded:
        value = getattr(card, metric, None)
        if value is None:
            continue
        read = _read(metric, value, cfg)
        descriptive.append(
            read.model_copy(
                update={
                    "note": (
                        f"{LABELS.get(metric, metric)} is shown on the card but is excluded "
                        "from a defenseman's projected WAR — descriptive only, not credited "
                        "to his value."
                    )
                }
            )
        )

    # Deployment context.
    for metric in DEPLOYMENT:
        value = getattr(card, metric, None)
        if value is None:
            continue
        tier = classify_percentile(value, cfg)
        deployment.append(
            f"{LABELS[metric]}: {ordinal(value)} percentile ({tier.label}). "
            "Deployment, not value — already baked into WAR."
        )

    strengths.sort(key=lambda r: r.percentile, reverse=True)
    weaknesses.sort(key=lambda r: r.percentile)

    caveats = _caveats(card, strengths, is_defense, cfg)
    scoring_profile = _scoring_profile(card, is_defense, cfg)
    trajectory = _trajectory(card)
    summary = _summary(card, overall, strengths, weaknesses, trajectory, is_defense)

    return Assessment(
        name=card.name,
        team=card.team,
        position=card.position,
        overall_tier=overall.label,
        overall_percentile=card.proj_war_pct,
        overall_note=overall.note,
        strengths=strengths,
        weaknesses=weaknesses,
        descriptive=descriptive,
        deployment=deployment,
        scoring_profile=scoring_profile,
        trajectory=trajectory,
        caveats=caveats,
        summary=summary,
    )


def _read(metric: str, value: int, cfg: dict[str, Any]) -> ComponentRead:
    tier = classify_percentile(value, cfg)
    return ComponentRead(
        metric=metric,
        label=LABELS.get(metric, metric),
        percentile=value,
        tier=tier.label,
        note=tier.note,
    )


def _na_note(metric: str) -> str:
    return (
        f"No {LABELS[metric].lower()} role (NA) — an absence of usage, not a weakness."
    )


def _caveats(
    card: SkaterLike,
    strengths: list[ComponentRead],
    is_defense: bool,
    cfg: dict[str, Any],
) -> list[str]:
    caveats: list[str] = []
    cav = cfg["caveats"]
    # Finishing volatility: only when a forward's verdict leans on finishing.
    if not is_defense and any(s.metric == "finishing" for s in strengths):
        caveats.append(cav["finishing_volatility"])
    # Deployment is not value: whenever competition/teammates are present.
    if any(getattr(card, m, None) is not None for m in DEPLOYMENT):
        caveats.append(cav["deployment_not_value"])
    # Dangerous passing is underrated: forwards with borderline playmaking.
    fa = getattr(card, "first_assists", None)
    if not is_defense and fa is not None and STRENGTH_MIN > fa > WEAKNESS_MAX:
        caveats.append(cav["dangerous_passing"])
    # Young-sample uncertainty: the card is a 3-year weighted average, so a young
    # skater's number rests on a short, recent, still-developing sample. Pair it
    # with the trajectory when the trend points up. Position-agnostic.
    if card.age <= cfg["age_uncertainty"]["max_age"]:
        note = cav["young_sample"]
        if _trend_is_up(card):
            note = note + " " + cav["young_sample_rising"]
        caveats.append(note)
    return caveats


def _scoring_profile(
    card: SkaterLike, is_defense: bool, cfg: dict[str, Any]
) -> Optional[ScoringProfileRead]:
    """Read EV offense (play-driving, repeatable) against finishing (conversion,
    volatile). Articulation only — it never feeds the tier or the WAR verdict.

    Forwards only: a defenseman's finishing is excluded from his value, so a
    scoring read off it would contradict that exclusion. Returns None when
    neither dimension is high enough (by `gap`) to tell a story.
    """
    if is_defense:
        return None
    spec = cfg.get("scoring_profile")
    if not spec:
        return None
    evo, fin = card.ev_offense, card.finishing
    high, gap = spec["high_min"], spec["gap"]
    if evo >= high and fin >= high:
        shape = "both_high"
    elif evo >= high and evo - fin >= gap:
        shape = "positive_regression"
    elif fin >= high and fin - evo >= gap:
        shape = "negative_regression"
    else:
        return None
    band = spec["shapes"][shape]
    return ScoringProfileRead(
        shape=shape,
        label=band["label"],
        ev_offense=evo,
        finishing=fin,
        note=band["note"],
    )


def _trend_direction(delta: float) -> str:
    if delta >= 15:
        return "pointing sharply up"
    if delta >= 5:
        return "trending up"
    if delta <= -15:
        return "falling sharply"
    if delta <= -5:
        return "trending down"
    return "holding steady"


def _trend_is_up(card: SkaterLike) -> bool:
    """True when the projected-WAR trend rises by the margin `_trajectory` reads
    as 'up' (>= 5 over the span). Used to pair the young-sample caveat with a
    rising trajectory."""
    trend = getattr(card, "war_pct_trend", None)
    if not trend or len(trend) < 2:
        return False
    return trend[-1].value - trend[0].value >= 5


def _trajectory(card: SkaterLike) -> Optional[str]:
    trend = getattr(card, "war_pct_trend", None)
    if not trend or len(trend) < 2:
        return None
    first, last = trend[0].value, trend[-1].value
    return (
        f"Projected-WAR percentile {first} → {last} over {len(trend)} seasons "
        f"— {_trend_direction(last - first)}."
    )


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _summary(
    card: SkaterLike,
    overall,
    strengths: list[ComponentRead],
    weaknesses: list[ComponentRead],
    trajectory: Optional[str],
    is_defense: bool,
) -> str:
    position = "defenseman" if is_defense else "forward"
    parts = [
        f"{card.name} grades as {_article(overall.label)} {overall.label} {position} "
        f"({ordinal(card.proj_war_pct)} percentile projected WAR)"
    ]
    if strengths:
        parts.append("strengths: " + ", ".join(s.label.lower() for s in strengths[:3]))
    if weaknesses:
        parts.append("weaknesses: " + ", ".join(w.label.lower() for w in weaknesses[:2]))
    summary = "; ".join(parts) + "."
    if trajectory:
        summary += " " + trajectory
    return summary


# --- Goalie assessment (PLAN section 5 goalie rules) -----------------------


def assess_goalie(card: GoalieCard, cfg: dict[str, Any]) -> GoalieAssessment:
    """Assess a goalie: danger split + start-quality profiles, consistency as a
    volatility flag, rebound control called out, trajectory from the two trends."""
    overall = classify_percentile(card.proj_war_pct, cfg)

    # Discrete skills -> strengths/weaknesses (rebound control is called out here,
    # never folded into the danger numbers).
    strengths: list[ComponentRead] = []
    weaknesses: list[ComponentRead] = []
    for metric in GOALIE_SKILLS:
        read = _read(metric, getattr(card, metric), cfg)
        if read.percentile >= STRENGTH_MIN:
            strengths.append(read)
        elif read.percentile <= WEAKNESS_MAX:
            weaknesses.append(read)
    strengths.sort(key=lambda r: r.percentile, reverse=True)
    weaknesses.sort(key=lambda r: r.percentile)

    danger_profile = Profile(
        label="Danger split",
        reads=[_read(m, getattr(card, m), cfg) for m in GOALIE_DANGER],
        shape=_danger_shape(card.high_danger, card.med_danger, card.low_danger, cfg),
    )
    start_quality_profile = Profile(
        label="Start quality",
        reads=[_read(m, getattr(card, m), cfg) for m in GOALIE_START_QUALITY],
        shape=_start_quality_shape(card.quality_starts, card.excellent_starts, card.bad_starts, cfg),
    )

    ctier = classify_percentile(card.consistency, cfg)
    consistency = ConsistencyRead(
        percentile=card.consistency,
        tier=ctier.label,
        note=_consistency_note(card.consistency, ctier.label, _is_climbing(card.war_per60_trend)),
    )

    caveats = [cfg["goalie_rules"]["consistency_volatility"]]
    if card.sv_vs_xsv_trend:
        caveats.append(cfg["goalie_rules"]["save_lines"])

    return GoalieAssessment(
        name=card.name,
        team=card.team,
        role=card.role,
        overall_tier=overall.label,
        overall_percentile=card.proj_war_pct,
        overall_note=overall.note,
        danger_profile=danger_profile,
        start_quality_profile=start_quality_profile,
        strengths=strengths,
        weaknesses=weaknesses,
        consistency=consistency,
        workload=_workload_note(card, cfg),
        trajectory=_goalie_trajectory(card),
        caveats=caveats,
        summary=_goalie_summary(card, overall, strengths, weaknesses, consistency),
    )


def _danger_shape(high: int, med: int, low: int, cfg: dict[str, Any]) -> str:
    ht = classify_percentile(high, cfg).label
    lt = classify_percentile(low, cfg).label
    if high >= STRENGTH_MIN and high - low >= 20:
        shape = (
            f"Makes the hard saves (high-danger {ordinal(high)}, {ht}) but is more "
            f"ordinary on routine shots (low-danger {ordinal(low)}, {lt})."
        )
    elif high >= STRENGTH_MIN and low >= STRENGTH_MIN:
        shape = (
            f"Strong across danger levels — high-danger {ordinal(high)} and low-danger "
            f"{ordinal(low)} both hold up."
        )
    elif low <= WEAKNESS_MAX:
        shape = (
            f"Weak on routine low-danger shots ({ordinal(low)}, {lt}) — a "
            f"leaking-soft-goals flag; high-danger sits at {ordinal(high)}."
        )
    else:
        shape = (
            f"High-danger {ordinal(high)}, mid {ordinal(med)}, low-danger {ordinal(low)} "
            f"— read where the value comes from."
        )
    if low <= WEAKNESS_MAX and "leaking" not in shape:
        shape += " Low-danger is a soft spot — a leaking-soft-goals risk."
    return shape


def _start_quality_shape(quality: int, excellent: int, bad: int, cfg: dict[str, Any]) -> str:
    qt = classify_percentile(quality, cfg).label
    et = classify_percentile(excellent, cfg).label
    bt = classify_percentile(bad, cfg).label
    parts = []
    if quality >= STRENGTH_MIN:
        parts.append(f"High floor — gives his team a chance most nights (quality starts {ordinal(quality)}, {qt}).")
    elif quality <= WEAKNESS_MAX:
        parts.append(f"Low floor (quality starts {ordinal(quality)}, {qt}).")
    else:
        parts.append(f"Average floor (quality starts {ordinal(quality)}, {qt}).")
    if excellent >= STRENGTH_MIN:
        parts.append(f"Real ceiling — can steal games (excellent starts {ordinal(excellent)}, {et}).")
    else:
        parts.append(f"Modest ceiling — not a game-stealer (excellent starts {ordinal(excellent)}, {et}).")
    if bad >= STRENGTH_MIN:
        parts.append(f"Rarely a disaster (bad starts {ordinal(bad)}, {bt}).")
    elif bad <= WEAKNESS_MAX:
        parts.append(f"Prone to disaster nights (bad starts {ordinal(bad)}, {bt}).")
    if quality >= STRENGTH_MIN and excellent < STRENGTH_MIN:
        parts.append("Reliability over game-stealing.")
    return " ".join(parts)


def _consistency_note(value: int, tier: str, climbing: bool) -> str:
    base = f"Consistency is {ordinal(value)} ({tier}) — a volatility flag, not a skill."
    if value <= WEAKNESS_MAX and climbing:
        return base + (
            " Paired with a steep recent WAR climb, the projection may be riding a "
            "recent spike rather than a settled level."
        )
    if value <= WEAKNESS_MAX:
        return base + " A low mark means year-to-year results are unpredictable."
    return base


def _is_climbing(trend) -> bool:
    if not trend or len(trend) < 2:
        return False
    return trend[-1].value - trend[0].value >= 15


def _workload_note(card: GoalieCard, cfg: dict[str, Any]) -> str:
    parts = [f"Role: {card.role}."]
    if card.gp_pct is not None:
        gt = classify_percentile(card.gp_pct, cfg).label
        parts.append(f"Games played {ordinal(card.gp_pct)} ({gt}) — workload/deployment, not value.")
    return " ".join(parts)


def _goalie_trajectory(card: GoalieCard) -> Optional[str]:
    parts = []
    trend = card.war_per60_trend
    if trend and len(trend) >= 2:
        first, last = int(round(trend[0].value)), int(round(trend[-1].value))
        parts.append(
            f"WAR-per-60 standing {ordinal(first)} → {ordinal(last)} over {len(trend)} "
            f"seasons — {_trend_direction(last - first)} (a percentile rank, so read it as "
            f"rising standing, not a raw rate)."
        )
    sv = card.sv_vs_xsv_trend
    if sv and len(sv) >= 2:
        first_gap = sv[0].sv - sv[0].xsv
        last_gap = sv[-1].sv - sv[-1].xsv
        if last_gap > first_gap:
            parts.append(
                f"Actual save % held ({sv[0].sv}→{sv[-1].sv}) while expected save % fell "
                f"({sv[0].xsv}→{sv[-1].xsv}) — he's beating expectation by more each year "
                f"(rising goals saved above expected), which is what drives the WAR up."
            )
        else:
            parts.append(
                f"Save % vs expected gap moved {first_gap:+.1f} → {last_gap:+.1f} points "
                f"— read the two lines together, never alone."
            )
    return " ".join(parts) if parts else None


def _goalie_summary(card, overall, strengths, weaknesses, consistency) -> str:
    strong = [f"{ordinal(card.proj_war_pct)} in projected WAR"]
    if strengths:
        strong.append(", ".join(s.label.lower() for s in strengths[:2]))
    tension = [f"consistency sits at {ordinal(consistency.percentile)}"]
    if weaknesses:
        tension.append(", ".join(f"{w.label.lower()} {ordinal(w.percentile)}" for w in weaknesses[:2]))
    return (
        f"{card.name} projects as {_article(overall.label)} {overall.label} starter — "
        f"{'; '.join(strong)}. But hold that against the volatility: {'; '.join(tension)}, "
        f"and the WAR standing climbed steeply rather than holding. The honest read: a "
        f"genuinely strong starter whose multi-year track record is short and uneven — "
        f"reliability over game-stealing, not a settled elite."
    )
