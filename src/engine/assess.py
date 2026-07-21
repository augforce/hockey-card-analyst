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
from engine.edge import EdgeVetting, vet_edge
from engine.tiers import classify_percentile
from schemas import DefenseCard, DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]
MicroLike = Union[ForwardMicroCard, DefenseMicroCard]

# Goalie metric groupings (PLAN sections 4, 5).
GOALIE_SKILLS = ["even_strength", "penalty_kill", "rebound_control"]
GOALIE_DANGER = ["high_danger", "med_danger", "low_danger"]
GOALIE_START_QUALITY = ["quality_starts", "excellent_starts", "bad_starts"]

# Value-bearing WAR components, in display order. For a defenseman, any metric in
# `position_rules.defense.war_excludes` (Finishing) is pulled out of this set.
WAR_COMPONENTS = ["ev_offense", "ev_defense", "pp", "pk", "finishing", "penalties"]
# Extra descriptive metrics - never themselves the WAR verdict (PLAN section 4).
DESCRIPTIVE = ["goals", "first_assists"]
# Usage metrics - deployment, never a strength or weakness (PLAN section 5).
DEPLOYMENT = ["competition", "teammates"]

# Microstat card metric groupings. The WAR-component row is the value read; the
# tracked columns are descriptive detail. The style trio (hits, skating speed,
# forecheck involvement) is reported separately and is NEVER a value strength
# or weakness, whatever the percentile.
F_MICRO_METRICS = [
    "goals", "chances", "shots", "in_zone_shots", "rush_shots",
    "shots_off_hd_passes", "zone_entries", "entries_w_possession",
    "primary_assists", "chance_assists", "primary_shot_assists",
    "in_zone_shot_assists", "rush_shot_assists", "high_danger_passes",
    "zone_exits", "exits_w_possession", "chance_contributions",
    "shot_contributions", "in_zone_offense", "rush_offense",
    "d_zone_puck_touches",
]
F_STYLE_METRICS = ["skating_speed", "forecheck_involvement", "hits"]
D_MICRO_METRICS = [
    "goals", "chances", "shots", "primary_assists", "chance_assists",
    "primary_shot_assists", "nz_shot_assists", "dz_shot_assists", "passes",
    "entries", "entry_possession_rate", "exits", "exit_possession_rate",
    "exit_success_rate", "pass_exits", "carry_exits", "d_zone_retrievals",
    "retrieval_success", "chance_contributions", "shot_contributions",
    "in_zone_offense", "rush_offense", "success_per_poss_play",
    "entry_denial_rate", "poss_entry_prevention", "entry_chance_prevention",
]
D_STYLE_METRICS = ["hits"]
# A season-vs-projection gap this large on a WAR component is worth naming when
# both cards for a player are supplied.
DIVERGENCE_MIN = 15

class ComponentRead(BaseModel):
    """One metric placed in its tier, with any attached note."""

    metric: str
    label: str
    percentile: int
    tier: str
    note: Optional[str] = None


class ScoringProfileRead(BaseModel):
    """EV offense (play-driving) read against finishing (conversion).

    Articulation only - never moves the tier or the WAR verdict. `shape` is one
    of both_high / positive_regression / negative_regression; the two percentiles
    it weighs are carried alongside the note so a narrator can cite them.
    """

    shape: str
    label: str
    ev_offense: int
    finishing: int
    note: str


class MicroProfileRead(BaseModel):
    """One paired microstat read (shot selectivity, passing quality, attack
    style, D rush defense). Articulation only - never a tier or verdict; the
    reads carry the numbers so a narrator can cite them."""

    family: str
    shape: str
    label: str
    note: str
    reads: list[ComponentRead]


class MicroSynthesis(BaseModel):
    """Articulation-only cross-card insights when BOTH the standard and the
    microstat card for a player are supplied. Never moves the tier."""

    season: str
    insights: list[str]
    divergences: list[str]
    note: str  # the cross-regime (single-season vs 3-year) framing


class Assessment(BaseModel):
    """Structured assessment of a single skater (the server's return shape)."""

    name: str
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
    micro_insights: Optional[MicroSynthesis] = None
    edge_vetting: Optional[EdgeVetting] = None


class MicroAssessment(BaseModel):
    """Structured assessment of a microstat ($10-tier) card.

    Profile-first: there is no Proj. WAR headline to anchor on, so the value
    read comes from the WAR-component row and everything else is descriptive
    shape. `style_reads` (hits / skating speed / forecheck involvement) are
    style facts, never value strengths or weaknesses.
    """

    name: str
    position: str
    season: str
    card_kind: str = "micro"
    overall_note: str
    strengths: list[ComponentRead]
    weaknesses: list[ComponentRead]
    descriptive: list[ComponentRead]
    deployment: list[str]
    profiles: list[MicroProfileRead]
    micro_highs: list[ComponentRead]
    micro_lows: list[ComponentRead]
    style_reads: list[ComponentRead]
    caveats: list[str]
    summary: str
    edge_vetting: Optional[EdgeVetting] = None


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
    edge_vetting: Optional[EdgeVetting] = None


def assess_player(card, config: Optional[dict[str, Any]] = None, micro_card=None, edge_card=None):
    """Assess a card into structured findings; dispatches on card type.

    Returns an Assessment for skaters, a GoalieAssessment for goalies, or a
    MicroAssessment for a microstat card. When BOTH cards for one player are
    supplied (standard `card` + `micro_card`), the standard assessment gains an
    articulation-only `micro_insights` synthesis - the tier never moves.
    `edge_card` (optional, NHL Edge page for the same player) adds an
    articulation-only `edge_vetting` cross-check on any of the three
    assessment shapes - the tier never moves for that either.
    """
    cfg = config if config is not None else load_config()
    if isinstance(card, (ForwardMicroCard, DefenseMicroCard)):
        if micro_card is not None:
            raise ValueError(
                "pass the STANDARD card as `card` and the microstat card as "
                "`micro_card` - two micro cards can't be combined."
            )
        result = assess_micro(card, cfg)
        if edge_card is not None:
            result.edge_vetting = vet_edge(card, edge_card, cfg)
        return result
    if isinstance(card, GoalieCard):
        if micro_card is not None:
            raise ValueError(
                "there is no goalie microstat card - goalies are assessed from "
                "the standard card only."
            )
        result = assess_goalie(card, cfg)
        if edge_card is not None:
            result.edge_vetting = vet_edge(card, edge_card, cfg)
        return result
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
        if value is None:  # NA - absence of a role, not a weakness.
            deployment.append(_na_note(metric))
            continue
        read = _read(metric, value, cfg)
        if read.percentile >= STRENGTH_MIN:
            strengths.append(read)
        elif read.percentile <= WEAKNESS_MAX:
            weaknesses.append(read)

    # Descriptive metrics - supporting colour, never the WAR verdict.
    for metric in DESCRIPTIVE:
        value = getattr(card, metric, None)
        if value is not None:
            descriptive.append(_read(metric, value, cfg))

    # Position-excluded metrics (defenseman Finishing) - descriptive only.
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
                        "from a defenseman's projected WAR - descriptive only, not credited "
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
            "Deployment, not value - already baked into WAR."
        )

    strengths.sort(key=lambda r: r.percentile, reverse=True)
    weaknesses.sort(key=lambda r: r.percentile)

    caveats = _caveats(card, strengths, is_defense, cfg)
    scoring_profile = _scoring_profile(card, is_defense, cfg)
    trajectory = _trajectory(card, cfg)
    summary = _summary(card, overall, strengths, weaknesses, trajectory, is_defense)

    return Assessment(
        name=card.name,        position=card.position,
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
        micro_insights=(
            _synthesize(card, micro_card, cfg) if micro_card is not None else None
        ),
        edge_vetting=(
            vet_edge(card, edge_card, cfg, micro_companion=micro_card)
            if edge_card is not None else None
        ),
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
        f"No {LABELS[metric].lower()} role (NA) - an absence of usage, not a weakness."
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
    # Defense repeatability: a forward's defensive impact is the less
    # repeatable half of play-driving (the model's priors regress it ~2x as
    # hard toward average as offense) - attach when the verdict leans on it.
    # Forwards only: the published trend coefficients are forward-specific.
    if not is_defense and any(s.metric == "ev_defense" for s in strengths):
        caveats.append(cav["defense_repeatability"])
    # Deployment is not value: whenever competition/teammates are present.
    if any(getattr(card, m, None) is not None for m in DEPLOYMENT):
        caveats.append(cav["deployment_not_value"])
    # Dangerous passing is underrated: forwards with borderline playmaking.
    fa = getattr(card, "first_assists", None)
    if not is_defense and fa is not None and STRENGTH_MIN > fa > WEAKNESS_MAX:
        caveats.append(cav["dangerous_passing"])
    # Young-sample uncertainty: the card is a 3-year weighted average, so a young
    # skater's number rests on a short, recent, still-developing sample. Pair it
    # with the trajectory when the trend points up. Position-agnostic. An unknown
    # age (blank on the card) is not young - the caveat needs evidence to fire.
    if card.age is not None and card.age <= cfg["age_uncertainty"]["max_age"]:
        note = cav["young_sample"]
        if _trend_is_up(card):
            note = note + " " + cav["young_sample_rising"]
        caveats.append(note)
    # Replacement-level anchor (TopDownHockey): 0 WAR sits at ~the 37th
    # percentile, so a projection at or below it is replacement-level-or-worse,
    # not merely "below average." Articulation only - the tier never moves.
    war_read = cfg.get("war_reading") or {}
    rep = war_read.get("replacement_pct")
    if rep is not None and card.proj_war_pct <= rep:
        caveats.append(war_read["replacement_note"])
    return caveats


def _scoring_profile(
    card: SkaterLike, is_defense: bool, cfg: dict[str, Any]
) -> Optional[ScoringProfileRead]:
    """Read EV offense (play-driving, repeatable) against finishing (conversion,
    volatile). Articulation only - it never feeds the tier or the WAR verdict.

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


def _trend_phrase(first: float, last: float) -> str:
    """The endpoint direction word; a steady series at a strong level says so
    (steady at 92 and steady at 45 are different facts)."""
    phrase = _trend_direction(last - first)
    if phrase == "holding steady" and min(first, last) >= STRENGTH_MIN:
        phrase += " at a high level"
    return phrase


def _bounce_note(values: list[float], cfg: dict[str, Any]) -> Optional[str]:
    """Name a non-monotonic interior season the endpoint read would hide.

    An interior season counts only when it breaks past BOTH endpoints (a
    monotonic rise/fall can never trip this) and deviates from the straight
    endpoint-to-endpoint line by more than `trajectory.bounce_margin` (config)
    - so flat-series chart noise stays quiet. Articulation only: this never
    moves a tier or verdict.
    """
    if len(values) < 3:
        return None
    margin = (cfg.get("trajectory") or {}).get("bounce_margin", 4)
    first, last = values[0], values[-1]
    lo, hi = min(first, last), max(first, last)
    span = len(values) - 1
    peaks: list[float] = []
    dips: list[float] = []
    for i in range(1, span):
        value = values[i]
        line = first + (last - first) * (i / span)
        if value > hi and value - line > margin:
            peaks.append(value)
        elif value < lo and line - value > margin:
            dips.append(value)
    peak = f"a peak season ({ordinal(int(round(max(peaks))))})" if peaks else None
    dip = f"a down year ({ordinal(int(round(min(dips))))})" if dips else None
    if peak and dip:
        return f"with {peak} and {dip} in between"
    if peak or dip:
        return f"with {peak or dip} in between"
    return None


def _trajectory(card: SkaterLike, cfg: dict[str, Any]) -> Optional[str]:
    trend = getattr(card, "war_pct_trend", None)
    if not trend or len(trend) < 2:
        return None
    first, last = trend[0].value, trend[-1].value
    bounce = _bounce_note([p.value for p in trend], cfg)
    return (
        f"Projected-WAR percentile {first} → {last} over {len(trend)} seasons "
        f"- {_trend_phrase(first, last)}"
        + (f", {bounce}." if bounce else ".")
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


# --- Microstat card assessment ----------------------------------------------


def assess_micro(card: MicroLike, cfg: dict[str, Any]) -> MicroAssessment:
    """Assess a microstat card: WAR-row value reads, paired style profiles,
    tracked-data standouts and soft spots, and the style trio kept apart.

    The single-season and unadjusted caveats always attach - this card is one
    season of raw tracked rates, a different regime from the standard card.
    """
    is_defense = isinstance(card, DefenseMicroCard)
    excluded: set = set()
    if is_defense:
        excluded = set(cfg.get("position_rules", {}).get("defense", {}).get("war_excludes", []))

    strengths: list[ComponentRead] = []
    weaknesses: list[ComponentRead] = []
    descriptive: list[ComponentRead] = []
    deployment: list[str] = []

    # Value reads: the WAR-component row only (same thresholds and NA/exclusion
    # rules as the standard card).
    for metric in WAR_COMPONENTS:
        if metric in excluded:
            continue
        value = getattr(card, metric)
        if value is None:  # NA - absence of a role, not a weakness.
            deployment.append(_na_note(metric))
            continue
        read = _read(metric, value, cfg)
        if read.percentile >= STRENGTH_MIN:
            strengths.append(read)
        elif read.percentile <= WEAKNESS_MAX:
            weaknesses.append(read)

    # Position-excluded metrics (defenseman Finishing) - descriptive only.
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
                        "from a defenseman's value - descriptive only, not credited to it."
                    )
                }
            )
        )

    strengths.sort(key=lambda r: r.percentile, reverse=True)
    weaknesses.sort(key=lambda r: r.percentile)

    # Tracked-data standouts and soft spots - descriptive, never the verdict.
    metric_set = D_MICRO_METRICS if is_defense else F_MICRO_METRICS
    style_set = D_STYLE_METRICS if is_defense else F_STYLE_METRICS
    micro_highs = sorted(
        (_read(m, getattr(card, m), cfg) for m in metric_set
         if getattr(card, m) >= STRENGTH_MIN),
        key=lambda r: r.percentile, reverse=True,
    )
    micro_lows = sorted(
        (_read(m, getattr(card, m), cfg) for m in metric_set
         if getattr(card, m) <= WEAKNESS_MAX),
        key=lambda r: r.percentile,
    )
    style_note = cfg["caveats"]["micro_style_not_value"]
    style_reads = [
        _read(m, getattr(card, m), cfg).model_copy(
            update={"note": f"A style read, not value. {style_note}"}
        )
        for m in style_set
    ]

    profiles = _micro_profiles(card, is_defense, cfg)
    caveats = _micro_caveats(card, strengths, style_reads, is_defense, cfg)

    position_noun = "defenseman" if is_defense else "forward"
    overall_note = (
        "A microstat card has no Proj. WAR headline - the value read here comes "
        f"from the six WAR components, for the {card.season} season only. An "
        "overall tier needs the standard card."
    )
    summary = _micro_summary(card, position_noun, strengths, weaknesses, profiles, micro_highs)

    return MicroAssessment(
        name=card.name,        position=card.position,
        season=card.season,
        overall_note=overall_note,
        strengths=strengths,
        weaknesses=weaknesses,
        descriptive=descriptive,
        deployment=deployment,
        profiles=profiles,
        micro_highs=micro_highs,
        micro_lows=micro_lows,
        style_reads=style_reads,
        caveats=caveats,
        summary=summary,
    )


def _micro_profile(
    family: str, shape: Optional[str], metrics: list[str], card, cfg: dict[str, Any]
) -> Optional[MicroProfileRead]:
    if shape is None:
        return None
    band = cfg["micro_profiles"][family][shape]
    return MicroProfileRead(
        family=family,
        shape=shape,
        label=band["label"],
        note=band["note"],
        reads=[_read(m, getattr(card, m), cfg) for m in metrics],
    )


def _micro_profiles(card: MicroLike, is_defense: bool, cfg: dict[str, Any]) -> list[MicroProfileRead]:
    """The paired style reads the tracking methodology scripts. Articulation
    only - a family with no clear shape is simply omitted, never forced."""
    spec = cfg["micro_profiles"]
    high, gap = spec["high_min"], spec["gap"]
    profiles: list[MicroProfileRead] = []

    # Shot selectivity: chances vs shots.
    c, s = card.chances, card.shots
    shape = None
    if c >= high and c - s >= gap:
        shape = "chance_led"
    elif s >= high and s - c >= gap:
        shape = "volume_led"
    profiles.append(_micro_profile("shot_selectivity", shape, ["chances", "shots"], card, cfg))

    # Passing quality: chance assists vs primary shot assists.
    ca, psa = card.chance_assists, card.primary_shot_assists
    shape = None
    if ca >= high and ca - psa >= gap:
        shape = "dangerous"
    elif psa >= high and psa - ca >= gap:
        shape = "funneler"
    profiles.append(
        _micro_profile("passing_quality", shape, ["chance_assists", "primary_shot_assists"], card, cfg)
    )

    # Attack style: rush vs in-zone offense - style, not value.
    r, iz = card.rush_offense, card.in_zone_offense
    shape = None
    if r >= high and r - iz >= gap:
        shape = "rush_led"
    elif iz >= high and iz - r >= gap:
        shape = "cycle_led"
    elif r >= high and iz >= high and abs(r - iz) < gap:
        shape = "balanced"
    profiles.append(
        _micro_profile("attack_style", shape, ["rush_offense", "in_zone_offense"], card, cfg)
    )

    # Rush defense (D only): the three metrics read together, chance prevention
    # first - it's the bottom line of the trio.
    if is_defense:
        ecp = card.entry_chance_prevention
        front = (card.entry_denial_rate + card.poss_entry_prevention) / 2
        shape = None
        if ecp >= high and front >= high:
            shape = "lockdown"
        elif front >= high and ecp <= WEAKNESS_MAX:
            shape = "tight_gap_walked"
        elif front >= high:
            # Elite at the line, ordinary coverage after it - the entries
            # that never happen don't show up in the chance-prevention box.
            shape = "line_dominant"
        elif front <= WEAKNESS_MAX and ecp >= high:
            shape = "soft_gap_slot"
        elif ecp <= WEAKNESS_MAX and front <= WEAKNESS_MAX:
            shape = "leaky"
        profiles.append(
            _micro_profile(
                "rush_defense", shape,
                ["entry_chance_prevention", "poss_entry_prevention", "entry_denial_rate"],
                card, cfg,
            )
        )

        # Breakout style (D only): exit success against possession retention.
        # Low retention beside elite success is a working style; high
        # retention beside failing exits is ambition with a bill attached.
        es, ep = card.exit_success_rate, card.exit_possession_rate
        shape = None
        if es >= high and ep >= high:
            shape = "complete"
        elif es >= high and ep <= WEAKNESS_MAX:
            shape = "safe_and_effective"
        elif ep >= high and es <= WEAKNESS_MAX:
            shape = "ambitious_and_costly"
        elif es <= WEAKNESS_MAX and ep <= WEAKNESS_MAX:
            shape = "broken"
        profiles.append(
            _micro_profile(
                "breakout_style", shape,
                ["exit_success_rate", "exit_possession_rate", "pass_exits", "carry_exits"],
                card, cfg,
            )
        )

    return [p for p in profiles if p is not None]


def _micro_caveats(
    card: MicroLike,
    strengths: list[ComponentRead],
    style_reads: list[ComponentRead],
    is_defense: bool,
    cfg: dict[str, Any],
) -> list[str]:
    cav = cfg["caveats"]
    caveats = [cav["micro_single_season"], cav["micro_unadjusted"]]
    # A style read at either extreme is where the misread risk lives.
    if any(r.percentile <= WEAKNESS_MAX or r.percentile >= STRENGTH_MIN for r in style_reads):
        caveats.append(cav["micro_style_not_value"])
    # Finishing volatility: same rule as the standard card (forwards only).
    if not is_defense and any(s.metric == "finishing" for s in strengths):
        caveats.append(cav["finishing_volatility"])
    return caveats


def _micro_summary(
    card: MicroLike,
    position_noun: str,
    strengths: list[ComponentRead],
    weaknesses: list[ComponentRead],
    profiles: list[MicroProfileRead],
    micro_highs: list[ComponentRead],
) -> str:
    parts = [f"{card.name}'s {card.season} microstat card ({position_noun})"]
    if strengths:
        parts.append(
            "this season's value drivers: "
            + ", ".join(f"{s.label.lower()} ({ordinal(s.percentile)})" for s in strengths[:3])
        )
    if weaknesses:
        parts.append(
            "soft spots: "
            + ", ".join(f"{w.label.lower()} ({ordinal(w.percentile)})" for w in weaknesses[:2])
        )
    if profiles:
        parts.append("shape: " + "; ".join(p.label.lower() for p in profiles))
    if micro_highs:
        parts.append(
            "tracked standouts: "
            + ", ".join(f"{h.label.lower()} ({ordinal(h.percentile)})" for h in micro_highs[:3])
        )
    return "; ".join(parts) + ". One season of tracked data - shape, not a settled level."


# --- Both-cards synthesis (standard + micro, articulation only) --------------


def _synthesize(std: SkaterLike, micro, cfg: dict[str, Any]) -> MicroSynthesis:
    """Cross-card insights when both cards for one player are supplied.

    Articulation only: this NEVER feeds the tier or the strengths/weaknesses.
    Divergences name WAR components where this season's number sits far from
    the three-year projection; insights read the tracked data against the
    standard card's verdict-bearing components.
    """
    if not isinstance(micro, (ForwardMicroCard, DefenseMicroCard)):
        raise ValueError("`micro_card` must be a microstat card (card_kind 'micro').")
    if std.name.strip().casefold() != micro.name.strip().casefold():
        raise ValueError(
            f"the two cards name different players ({std.name!r} vs {micro.name!r}) - "
            "synthesis needs both cards for the SAME player."
        )
    std_is_d = isinstance(std, DefenseCard)
    if std_is_d != isinstance(micro, DefenseMicroCard):
        raise ValueError(
            "the two cards are from different position pools - a forward's and a "
            "defenseman's percentiles are not comparable."
        )

    # A D's excluded metrics (finishing) are descriptive on both cards - a
    # season-vs-projection divergence there is noise, not a value story.
    skip: set = set()
    if std_is_d:
        skip = set(cfg.get("position_rules", {}).get("defense", {}).get("war_excludes", []))

    divergences: list[str] = []
    for metric in WAR_COMPONENTS:
        if metric in skip:
            continue
        sv, mv = getattr(std, metric), getattr(micro, metric)
        if sv is None or mv is None:
            continue
        if abs(sv - mv) >= DIVERGENCE_MIN:
            direction = "above" if mv > sv else "below"
            ran = "hot" if mv > sv else "cold"
            divergences.append(
                f"This season's {LABELS[metric].lower()} ({ordinal(mv)}) sits well "
                f"{direction} the three-year projection ({ordinal(sv)}) - the season "
                f"ran {ran} there relative to the settled level."
            )

    insights: list[str] = []
    # Finishing vs chance volume (forwards; a D's finishing is excluded anyway).
    if not std_is_d and std.finishing >= STRENGTH_MIN:
        if micro.chances >= STRENGTH_MIN:
            insights.append(
                f"The finishing verdict is backed by chance volume - chances sit at "
                f"{ordinal(micro.chances)} this season, so the conversion rests on real "
                "chance generation. That tempers the finishing-volatility caveat."
            )
        elif micro.chances <= WEAKNESS_MAX:
            insights.append(
                f"The finishing verdict runs ahead of thin chance volume - chances sit at "
                f"only {ordinal(micro.chances)} this season, which sharpens the "
                "finishing-volatility caveat."
            )
    # Playmaking vs dangerous passing evidence.
    fa = getattr(std, "first_assists", None)
    hd = getattr(micro, "high_danger_passes", None)
    if fa is not None and hd is not None and hd >= STRENGTH_MIN:
        if fa >= STRENGTH_MIN:
            insights.append(
                f"The playmaking reads as the dangerous kind: high-danger passes "
                f"{ordinal(hd)} and chance assists {ordinal(micro.chance_assists)} - "
                "the passing shape this model is known to underrate, now with tracked "
                "evidence behind it."
            )
        elif fa > WEAKNESS_MAX:
            insights.append(
                f"The borderline playmaking number hides dangerous passing: high-danger "
                f"passes sit at {ordinal(hd)} - the underrated-passer caveat resolves "
                "into tracked evidence in his favor."
            )
    # Play-driving vs tracked creation.
    if std.ev_offense >= STRENGTH_MIN and micro.chance_contributions >= STRENGTH_MIN:
        insights.append(
            f"The play-driving shows up in the tracking: chance contributions at "
            f"{ordinal(micro.chance_contributions)} this season back the EV-offense impact."
        )
    # D: impact vs tracked rush defense. Corroborating evidence can live at
    # the blue line (denials + possession prevention) even when chance
    # prevention on completed entries is only ordinary - the entries that
    # never happen don't show up in that box.
    if std_is_d:
        ecp = micro.entry_chance_prevention
        edr, pep = micro.entry_denial_rate, micro.poss_entry_prevention
        front = (edr + pep) / 2
        if std.ev_defense >= STRENGTH_MIN and ecp >= STRENGTH_MIN:
            insights.append(
                f"The defensive impact is corroborated in the tracking: entry chance "
                f"prevention sits at {ordinal(ecp)}."
            )
        elif std.ev_defense >= STRENGTH_MIN and front >= STRENGTH_MIN:
            insights.append(
                f"The defensive impact is corroborated at the blue line: entry denials "
                f"{ordinal(edr)} and possession-entry prevention {ordinal(pep)} - chance "
                f"prevention on completed entries sits at {ordinal(ecp)}, but the entries "
                "he erases never reach that box."
            )
        elif std.ev_defense <= WEAKNESS_MAX and ecp >= STRENGTH_MIN:
            insights.append(
                f"A tension worth naming: the isolated defensive impact is weak "
                f"({ordinal(std.ev_defense)}), yet tracked rush defense is strong (entry "
                f"chance prevention {ordinal(ecp)}) - the leak may be in-zone coverage "
                "rather than the rush."
            )
        elif std.ev_defense <= WEAKNESS_MAX and ecp <= WEAKNESS_MAX:
            insights.append(
                f"The weak defensive impact is corroborated in the tracking (entry "
                f"chance prevention {ordinal(ecp)})."
            )

    return MicroSynthesis(
        season=micro.season,
        insights=insights,
        divergences=divergences,
        note=cfg["micro_rules"]["war_row"],
    )


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
        name=card.name,        role=card.role,
        overall_tier=overall.label,
        overall_percentile=card.proj_war_pct,
        overall_note=overall.note,
        danger_profile=danger_profile,
        start_quality_profile=start_quality_profile,
        strengths=strengths,
        weaknesses=weaknesses,
        consistency=consistency,
        workload=_workload_note(card, cfg),
        trajectory=_goalie_trajectory(card, cfg),
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
            f"Strong across danger levels - high-danger {ordinal(high)} and low-danger "
            f"{ordinal(low)} both hold up."
        )
    elif low <= WEAKNESS_MAX:
        shape = (
            f"Weak on routine low-danger shots ({ordinal(low)}, {lt}) - a "
            f"leaking-soft-goals flag; high-danger sits at {ordinal(high)}."
        )
    else:
        shape = (
            f"High-danger {ordinal(high)}, mid {ordinal(med)}, low-danger {ordinal(low)} "
            f"- read where the value comes from."
        )
    if low <= WEAKNESS_MAX and "leaking" not in shape:
        shape += " Low-danger is a soft spot - a leaking-soft-goals risk."
    return shape


def _start_quality_shape(quality: int, excellent: int, bad: int, cfg: dict[str, Any]) -> str:
    qt = classify_percentile(quality, cfg).label
    et = classify_percentile(excellent, cfg).label
    bt = classify_percentile(bad, cfg).label
    parts = []
    if quality >= STRENGTH_MIN:
        parts.append(f"High floor - gives his team a chance most nights (quality starts {ordinal(quality)}, {qt}).")
    elif quality <= WEAKNESS_MAX:
        parts.append(f"Low floor (quality starts {ordinal(quality)}, {qt}).")
    else:
        parts.append(f"Average floor (quality starts {ordinal(quality)}, {qt}).")
    if excellent >= STRENGTH_MIN:
        parts.append(f"Real ceiling - can steal games (excellent starts {ordinal(excellent)}, {et}).")
    else:
        parts.append(f"Modest ceiling - not a game-stealer (excellent starts {ordinal(excellent)}, {et}).")
    if bad >= STRENGTH_MIN:
        parts.append(f"Rarely a disaster (bad starts {ordinal(bad)}, {bt}).")
    elif bad <= WEAKNESS_MAX:
        parts.append(f"Prone to disaster nights (bad starts {ordinal(bad)}, {bt}).")
    if quality >= STRENGTH_MIN and excellent < STRENGTH_MIN:
        parts.append("Reliability over game-stealing.")
    return " ".join(parts)


def _consistency_note(value: int, tier: str, climbing: bool) -> str:
    base = f"Consistency is {ordinal(value)} ({tier}) - a volatility flag, not a skill."
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
        parts.append(f"Games played {ordinal(card.gp_pct)} ({gt}) - workload/deployment, not value.")
    return " ".join(parts)


def _goalie_trajectory(card: GoalieCard, cfg: dict[str, Any]) -> Optional[str]:
    parts = []
    trend = card.war_per60_trend
    if trend and len(trend) >= 2:
        first, last = int(round(trend[0].value)), int(round(trend[-1].value))
        bounce = _bounce_note([p.value for p in trend], cfg)
        parts.append(
            f"WAR-per-60 standing {ordinal(first)} → {ordinal(last)} over {len(trend)} "
            f"seasons - {_trend_phrase(first, last)}"
            + (f", {bounce}" if bounce else "")
            + " (a percentile rank, so read it as rising standing, not a raw rate)."
        )
    sv = card.sv_vs_xsv_trend
    if sv and len(sv) >= 2:
        first_gap = sv[0].sv - sv[0].xsv
        last_gap = sv[-1].sv - sv[-1].xsv
        if last_gap > first_gap:
            parts.append(
                f"Actual save % held ({sv[0].sv}→{sv[-1].sv}) while expected save % fell "
                f"({sv[0].xsv}→{sv[-1].xsv}) - he's beating expectation by more each year "
                f"(rising goals saved above expected), which is what drives the WAR up."
            )
        else:
            parts.append(
                f"Save % vs expected gap moved {first_gap:+.1f} → {last_gap:+.1f} points "
                f"- read the two lines together, never alone."
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
        f"{card.name} projects as {_article(overall.label)} {overall.label} starter - "
        f"{'; '.join(strong)}. But hold that against the volatility: {'; '.join(tension)}, "
        f"and the WAR standing climbed steeply rather than holding. The honest read: a "
        f"genuinely strong starter whose multi-year track record is short and uneven - "
        f"reliability over game-stealing, not a settled elite."
    )
