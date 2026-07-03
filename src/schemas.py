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
# direction note) — do not invert any of them.
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
    # Context (does not affect value). Team and age may be missing from the
    # card itself (e.g. a UFA card with a blank Age line and no team shown);
    # absence is unknown context, never a value signal.
    name: str
    team: Optional[str] = None
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

    Structurally identical to a forward, but Finishing — though it may appear on
    the card — is excluded from projected WAR (PLAN section 4). That exclusion is
    enforced in the engine via `position_rules.defense.war_excludes` in the
    config, not in this schema.
    """

    position: Literal["D"] = "D"


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
    already oriented so higher is better — including Bad Starts (higher = better
    at avoiding them) and Consistency. Do not invert any of them.
    """

    # Context (team/age may be missing from the card itself — see _SkaterBase)
    name: str
    team: Optional[str] = None
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
