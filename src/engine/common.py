"""Shared scale helpers used across the engine (assess, adjudicate, compare).

Kept in one place so the ordinal formatting and the strength/weakness cutoffs
have a single source of truth (and a single test).
"""
from __future__ import annotations

# Strength/weakness cutoffs mirror the config tier edges: Strong starts at 70,
# Below average ends at 44. The 45-69 middle is neutral / "partial" territory.
STRENGTH_MIN = 70
WEAKNESS_MAX = 44


def ordinal(n: int) -> str:
    """Render an integer with its English ordinal suffix (1 -> '1st', 72 -> '72nd')."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# Human display labels for card metrics, shared by assess / adjudicate / compare.
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
