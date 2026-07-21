"""Pydantic card schemas (PLAN section 4).

Claude Desktop reads the card image and extracts these structured fields; the
server never does vision. Strict validation (extra fields forbidden, percentiles
bounded 0-100) makes a bad extraction fail loudly rather than silently produce a
wrong verdict.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# A card percentile: an integer 0-100. Every percentile box on a HockeyStats
# card is already oriented so that higher is better (PLAN section 4, goalie
# direction note) - do not invert any of them.
Percentile = Annotated[int, Field(ge=0, le=100)]

# Forward positions as shown on the card. DefenseCard is fixed to "D"; goalies
# carry no position field.
ForwardPosition = Literal["C", "LW", "RW", "L", "R", "F"]


class _StrictModel(BaseModel):
    """Reject unknown fields so a mis-extracted card fails loudly."""

    model_config = ConfigDict(extra="forbid")


# --- Skaters (forward and defenseman) -------------------------------------


class SkaterTrendPoint(_StrictModel):
    """One season of the projected-WAR percentile trend."""

    season: str
    value: Percentile


class _SkaterBase(_StrictModel):
    # Context (does not affect value). Age may be missing from the card itself
    # (e.g. a UFA card with a blank Age line); absence is unknown context,
    # never a value signal. `team` is accepted for compatibility but IGNORED -
    # the logo/team on a card goes stale with trades, so team affiliation is
    # never read, echoed, or reported (2026-07-19).
    name: str
    team: Optional[str] = None  # accepted but ignored - never surfaced
    age: Optional[int] = Field(default=None, ge=15, le=60)
    toi_role: Optional[str] = None
    cap: Optional[str] = None
    competition: Optional[Percentile] = None  # deployment, not value
    teammates: Optional[Percentile] = None     # deployment, not value

    # WAR components (percentiles)
    ev_offense: Percentile
    ev_defense: Percentile
    pp: Optional[Percentile] = None  # NA when the player has no PP role
    pk: Optional[Percentile] = None  # NA when the player has no PK role
    finishing: Percentile
    penalties: Percentile

    # Headline
    proj_war_pct: Percentile

    # Extra descriptive
    goals: Optional[Percentile] = None
    first_assists: Optional[Percentile] = None

    # Trends (optional)
    war_pct_trend: Optional[list[SkaterTrendPoint]] = None


class SkaterCard(_SkaterBase):
    """A forward's standard card."""

    position: ForwardPosition


class DefenseCard(_SkaterBase):
    """A defenseman's standard card.

    Structurally identical to a forward, but Finishing - though it may appear on
    the card - is excluded from projected WAR (PLAN section 4). That exclusion is
    enforced in the engine via `position_rules.defense.war_excludes` in the
    config, not in this schema.
    """

    position: Literal["D"] = "D"


# --- Microstat cards (the $10-tier card; skaters only) ---------------------
#
# A different data regime from the standard card: single-season percentiles at
# 5v5 per 60 (microstats tracked by AllThreeZones; WAR components from
# TopDownHockey), no Proj. WAR headline, no age/TOI/cap/competition/teammates,
# and no trend charts. Forwards and defensemen carry different microstat sets;
# there is no goalie microstat card. `card_kind: "micro"` is an explicit
# discriminator so a mis-extracted card fails loudly rather than validating as
# the wrong type; `season` is required because the single-season sample is
# load-bearing context for every verdict.


class _MicroBase(_StrictModel):
    """Fields shared by the forward and defense microstat cards."""

    card_kind: Literal["micro"]
    name: str
    team: Optional[str] = None  # accepted but ignored - never surfaced (see _SkaterBase)
    season: str

    # WAR-component row (single-season). Same orientation and NA rules as the
    # standard card: PP/PK are None when the player has no such role.
    ev_offense: Percentile
    ev_defense: Percentile
    pp: Optional[Percentile] = None
    pk: Optional[Percentile] = None
    penalties: Percentile
    finishing: Percentile

    # Microstats present on both position variants.
    goals: Percentile
    chances: Percentile
    shots: Percentile
    primary_assists: Percentile
    chance_assists: Percentile
    primary_shot_assists: Percentile
    chance_contributions: Percentile
    shot_contributions: Percentile
    in_zone_offense: Percentile
    rush_offense: Percentile
    hits: Percentile


class ForwardMicroCard(_MicroBase):
    """A forward's microstat card (verified against the real Celebrini card).

    The card itself shows no position box - the footer says "percentile ranks
    among forwards"; extraction passes position "F" (or C/LW/RW if known).
    """

    position: ForwardPosition = "F"

    # Shooting column.
    in_zone_shots: Percentile
    rush_shots: Percentile
    shots_off_hd_passes: Percentile
    zone_entries: Percentile
    entries_w_possession: Percentile

    # Passing column.
    in_zone_shot_assists: Percentile
    rush_shot_assists: Percentile
    high_danger_passes: Percentile
    zone_exits: Percentile
    exits_w_possession: Percentile

    # Composite / style column. Skating Speed is NHL Edge tracking, not
    # AllThreeZones, and appears only on the forward card.
    skating_speed: Percentile
    forecheck_involvement: Percentile
    d_zone_puck_touches: Percentile


class DefenseMicroCard(_MicroBase):
    """A defenseman's microstat card (verified against the real Schaefer card).

    No Skating Speed or Forecheck Involvement boxes; instead the transition and
    rush-defense sets. Finishing appears on the WAR row but remains excluded
    from a defenseman's value read (`position_rules.defense.war_excludes`),
    same as the standard card.
    """

    position: Literal["D"] = "D"

    # Production column.
    nz_shot_assists: Percentile
    dz_shot_assists: Percentile
    passes: Percentile

    # Transition column. Exit Possession Rate / Exit Success Rate are rates
    # underneath but shown as percentile ranks - same 0-100 orientation.
    entries: Percentile
    entry_possession_rate: Percentile
    exits: Percentile
    exit_possession_rate: Percentile
    exit_success_rate: Percentile
    pass_exits: Percentile
    carry_exits: Percentile
    d_zone_retrievals: Percentile
    retrieval_success: Percentile

    # Composite / rush-defense column.
    success_per_poss_play: Percentile
    entry_denial_rate: Percentile
    poss_entry_prevention: Percentile
    entry_chance_prevention: Percentile


# --- NHL Edge tracking pages (supplemental only) ----------------------------
#
# nhl.com/nhl-edge league tracking - a third, optional cross-reference source,
# unrelated to the HockeyStats/JFresh model. Edge data is NEVER assessed on its
# own: it rides alongside a card already being assessed (assess_player's
# `edge_card` param) and vets that card's verdicts, articulation only.
#
# Extraction contract: capture the legend tables (player value + printed
# comparison average + percentile), never the zone-map cell counts - those do
# not reconcile against their own stated totals. Below the 50th percentile the
# site prints only "<50th", never an exact number: that bucket is
# `percentile: null`. A sub-50 percentile must never be invented.


class EdgeMetric(_StrictModel):
    """One NHL Edge legend-table entry: the player's value as printed, the
    comparison average when the page shows one, and the exact percentile when
    NHL.com gives one (51st+). `percentile` None IS the "<50th" bucket."""

    value: float
    avg: Optional[float] = None
    percentile: Optional[int] = Field(default=None, ge=50, le=100)


class _EdgeBase(_StrictModel):
    """Fields shared by the goalie and skater Edge schemas. `gp` is required
    because raw counts accumulate with games played - the workload context is
    load-bearing for every count read."""

    card_kind: Literal["edge"]
    name: str
    season: str
    gp: int = Field(ge=1, le=82)


class GoalieEdgeCard(_EdgeBase):
    """A goalie's NHL Edge page (save-location legend tables + start quality).

    Edge zones are DISTANCE-based (high-danger: within 29 feet of the center
    of the goal bounded by the face-off dot lines; mid-range: 29-43 feet;
    long-range: beyond 43), not the card's expected-goals danger split. Counts
    (saves, shots against, goals against) are shots on goal only.
    """

    save_pct_all: EdgeMetric
    save_pct_high_danger: EdgeMetric
    save_pct_mid_range: EdgeMetric
    save_pct_long_range: EdgeMetric
    saves_all: EdgeMetric
    saves_high_danger: EdgeMetric
    saves_mid_range: EdgeMetric
    saves_long_range: EdgeMetric
    shots_against: EdgeMetric
    goals_against: EdgeMetric
    high_danger_goals_against: EdgeMetric
    pct_starts_over_900: EdgeMetric


class SkaterEdgeCard(_EdgeBase):
    """A skater's NHL Edge page (tools + shots-on-goal zones + zone time).

    `position` is required because the shots-on-goal baseline is "Avg. by
    Position (F/D)" - the pool must be stated, never defaulted. Zone-time
    percentiles are pre-oriented like everything else (less defensive-zone
    time than average ranks HIGH on the defensive row).
    """

    position: Literal["C", "LW", "RW", "L", "R", "F", "D"]
    hardest_shot: EdgeMetric
    max_skating_speed: EdgeMetric
    most_miles_per_game: EdgeMetric
    sog_all: EdgeMetric
    sog_high_danger: EdgeMetric
    sog_mid_range: EdgeMetric
    sog_long_range: EdgeMetric
    zone_time_defensive: EdgeMetric
    zone_time_neutral: EdgeMetric
    zone_time_offensive: EdgeMetric


# --- Goalie ----------------------------------------------------------------


class GoalieWarTrendPoint(_StrictModel):
    """One season of the WAR-per-60 trend (a rate, not a percentile)."""

    season: str
    value: float


class SaveTrendPoint(_StrictModel):
    """One season of actual vs expected save percentage. Read the two together."""

    season: str
    sv: float
    xsv: float


class GoalieCard(_StrictModel):
    """A goalie's standard card (PLAN section 4).

    The current HockeyStats goalie card does not split WAR into 5v5/4v5/All; it
    is a single headline plus ten percentile boxes. Every percentile here is
    already oriented so higher is better - including Bad Starts (higher = better
    at avoiding them) and Consistency. Do not invert any of them.
    """

    # Context (age may be missing from the card itself - see _SkaterBase;
    # team is accepted but ignored, same as skaters)
    name: str
    team: Optional[str] = None  # accepted but ignored - never surfaced
    age: Optional[int] = Field(default=None, ge=15, le=60)
    gp_pct: Optional[Percentile] = None  # games-played percentile (workload)
    role: Literal["Starter", "1A", "1B", "Backup"]
    cap: Optional[str] = None

    # Headline
    proj_war_pct: Percentile

    # Performance by game state
    even_strength: Percentile
    penalty_kill: Percentile

    # Performance by shot danger
    high_danger: Percentile
    med_danger: Percentile
    low_danger: Percentile

    # Start quality (built on goals saved above expected, not save %)
    quality_starts: Percentile     # saved above 0
    excellent_starts: Percentile   # saved 2+
    bad_starts: Percentile         # allowed 2+ (higher = better at avoiding)

    # Reliability and puck handling
    rebound_control: Percentile
    consistency: Percentile        # year-to-year predictability

    # Trends (optional)
    war_per60_trend: Optional[list[GoalieWarTrendPoint]] = None
    sv_vs_xsv_trend: Optional[list[SaveTrendPoint]] = None
