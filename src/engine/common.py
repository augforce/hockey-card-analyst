"""Shared scale helpers used across the engine (assess, adjudicate, compare).

Kept in one place so the ordinal formatting and the strength/weakness cutoffs
have a single source of truth (and a single test).
"""
from __future__ import annotations

# Strength/weakness cutoffs mirror the config tier edges: Strong starts at 70,
# Below average ends at 44. The 45-69 middle is neutral / "partial" territory.
STRENGTH_MIN = 70
WEAKNESS_MAX = 44


# No-em-dash rule (2026-07-19, user call): no output surface may contain an em
# dash - not the structured tool results, not the PDFs. Source text is written
# dash-free (guarded by tests/test_no_em_dashes.py); this scrub is the runtime
# backstop at the output boundaries. The character is spelled as an escape so
# this file itself stays clean under the source scan.
_EM_DASH = "\u2014"


def strip_em_dashes(value):
    """Recursively replace em dashes with plain hyphens in any output structure."""
    if isinstance(value, str):
        return value.replace(_EM_DASH, "-")
    if isinstance(value, dict):
        return {k: strip_em_dashes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [strip_em_dashes(v) for v in value]
    if isinstance(value, tuple):
        return tuple(strip_em_dashes(v) for v in value)
    return value


def ordinal(n: int) -> str:
    """Render an integer with its English ordinal suffix (1 -> '1st', 72 -> '72nd')."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# Human display labels for card metrics, shared by assess / adjudicate / compare.
LABELS = {
    # Skater
    "ev_offense": "Even-strength offense",
    "ev_defense": "Even-strength defense",
    "pp": "Power play",
    "pk": "Penalty kill",
    "finishing": "Finishing",
    "penalties": "Discipline (penalties)",
    "goals": "Goals",
    "first_assists": "Primary assists",
    "competition": "Competition faced",
    "teammates": "Quality of teammates",
    "proj_war_pct": "Projected WAR",
    # Goalie
    "even_strength": "Even strength",
    "penalty_kill": "Penalty kill",
    "high_danger": "High-danger saves",
    "med_danger": "Mid-danger saves",
    "low_danger": "Low-danger saves",
    "quality_starts": "Quality starts",
    "excellent_starts": "Excellent starts",
    "bad_starts": "Bad starts (avoided)",
    "rebound_control": "Rebound control",
    "consistency": "Consistency",
    "gp_pct": "Games played",
    # Microstat card - shared
    "chances": "Chances",
    "shots": "Shots",
    "primary_assists": "Primary assists",
    "chance_assists": "Chance assists",
    "primary_shot_assists": "Primary shot assists",
    "chance_contributions": "Chance contributions",
    "shot_contributions": "Shot contributions",
    "in_zone_offense": "In-zone offense",
    "rush_offense": "Rush offense",
    "hits": "Hits",
    # Microstat card - forward
    "in_zone_shots": "In-zone shots",
    "rush_shots": "Rush shots",
    "shots_off_hd_passes": "Shots off HD passes",
    "zone_entries": "Zone entries",
    "entries_w_possession": "Entries w/ possession",
    "in_zone_shot_assists": "In-zone shot assists",
    "rush_shot_assists": "Rush shot assists",
    "high_danger_passes": "High-danger passes",
    "zone_exits": "Zone exits",
    "exits_w_possession": "Exits w/ possession",
    "skating_speed": "Skating speed",
    "forecheck_involvement": "Forecheck involvement",
    "d_zone_puck_touches": "D-zone puck touches",
    # Microstat card - defenseman
    "nz_shot_assists": "NZ shot assists",
    "dz_shot_assists": "DZ shot assists",
    "passes": "Passes",
    "entries": "Entries",
    "entry_possession_rate": "Entry possession rate",
    "exits": "Exits",
    "exit_possession_rate": "Exit possession rate",
    "exit_success_rate": "Exit success rate",
    "pass_exits": "Pass exits",
    "carry_exits": "Carry exits",
    "d_zone_retrievals": "D-zone retrievals",
    "retrieval_success": "Retrieval success",
    "success_per_poss_play": "Success per possession play",
    "entry_denial_rate": "Entry denial rate",
    "poss_entry_prevention": "Poss. entry prevention",
    "entry_chance_prevention": "Entry chance prevention",
}
