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
from engine.tiers import classify_percentile
from schemas import DefenseCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]

# Value-bearing WAR components, in display order. For a defenseman, any metric in
# `position_rules.defense.war_excludes` (Finishing) is pulled out of this set.
WAR_COMPONENTS = ["ev_offence", "ev_defence", "pp", "pk", "finishing", "penalties"]
# Extra descriptive metrics — never themselves the WAR verdict (PLAN section 4).
DESCRIPTIVE = ["goals", "first_assists"]
# Usage metrics — deployment, never a strength or weakness (PLAN section 5).
DEPLOYMENT = ["competition", "teammates"]

LABELS = {
    "ev_offence": "Even-strength offence",
    "ev_defence": "Even-strength defence",
    "pp": "Power play",
    "pk": "Penalty kill",
    "finishing": "Finishing",
    "penalties": "Discipline (penalties)",
    "goals": "Goals",
    "first_assists": "Primary assists",
    "competition": "Competition faced",
    "teammates": "Quality of teammates",
    "proj_war_pct": "Projected WAR",
}

# Mirror the config tier edges: Strong starts at 70, Below average ends at 44.
STRENGTH_MIN = 70
WEAKNESS_MAX = 44


class ComponentRead(BaseModel):
    """One metric placed in its tier, with any attached note."""

    metric: str
    label: str
    percentile: int
    tier: str
    note: Optional[str] = None


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
    trajectory: Optional[str] = None
    caveats: list[str]
    summary: str


def assess_player(card: SkaterLike, config: Optional[dict[str, Any]] = None) -> Assessment:
    """Assess a forward or defenseman card into structured findings."""
    cfg = config if config is not None else load_config()
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
            f"{LABELS[metric]}: {_ordinal(value)} percentile ({tier.label}). "
            "Deployment, not value — already baked into WAR."
        )

    strengths.sort(key=lambda r: r.percentile, reverse=True)
    weaknesses.sort(key=lambda r: r.percentile)

    caveats = _caveats(card, strengths, is_defense, cfg)
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


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


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
    return caveats


def _trajectory(card: SkaterLike) -> Optional[str]:
    trend = getattr(card, "war_pct_trend", None)
    if not trend or len(trend) < 2:
        return None
    first, last = trend[0].value, trend[-1].value
    delta = last - first
    if delta >= 15:
        direction = "pointing sharply up"
    elif delta >= 5:
        direction = "trending up"
    elif delta <= -15:
        direction = "falling sharply"
    elif delta <= -5:
        direction = "trending down"
    else:
        direction = "holding steady"
    return (
        f"Projected-WAR percentile {first} → {last} over {len(trend)} seasons "
        f"— {direction}."
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
        f"({_ordinal(card.proj_war_pct)} percentile projected WAR)"
    ]
    if strengths:
        parts.append("strengths: " + ", ".join(s.label.lower() for s in strengths[:3]))
    if weaknesses:
        parts.append("weaknesses: " + ", ".join(w.label.lower() for w in weaknesses[:2]))
    summary = "; ".join(parts) + "."
    if trajectory:
        summary += " " + trajectory
    return summary
