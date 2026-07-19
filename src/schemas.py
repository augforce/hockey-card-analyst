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
