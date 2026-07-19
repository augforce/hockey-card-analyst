"""Trajectory bounciness (post-v1): a non-monotonic interior season is named.

The endpoint read stays the spine; when an interior season breaks past BOTH
endpoints and deviates from the straight endpoint-to-endpoint line by more
than `trajectory.bounce_margin` (config), the string appends the shape
("with a peak season (97th) in between" / "with a down year (…) in between").
Monotonic and flat series are unchanged - Thompson's 38→90→99 stays clean.
Articulation only: no tier or verdict changes.
"""
import copy
import json
from pathlib import Path

import pytest

from config import load_config
from engine.assess import assess_player
from schemas import GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def _skater(trend):
    """Minimal inline skater with a given war_pct_trend."""
    return SkaterCard(
        name="Trend Case (synthetic)", team="TEST", position="C", age=27,
        ev_offense=60, ev_defense=55, pp=None, pk=None, finishing=58,
        penalties=50, proj_war_pct=trend[-1][1],
        war_pct_trend=[{"season": s, "value": v} for s, v in trend],
    )


# --- The Hughes case: a peak season hidden by the endpoint read ---------------


def test_hughes_peak_season_is_named():
    a = assess_player(SkaterCard(**_load("hughes.json")))
    assert "93 → 92" in a.trajectory                       # endpoint spine unchanged
    assert "holding steady at a high level" in a.trajectory
    assert "with a peak season (97th) in between" in a.trajectory


def test_hughes_verdict_and_tier_unchanged_by_bounce():
    a = assess_player(SkaterCard(**_load("hughes.json")))
    assert a.overall_tier == "Elite" and a.overall_percentile == 98


# --- A dip case ----------------------------------------------------------------


def test_dip_in_the_middle_is_named():
    a = assess_player(_skater([("23-24", 80), ("24-25", 45), ("25-26", 82)]))
    assert "with a down year (45th) in between" in a.trajectory
    assert "peak season" not in a.trajectory


# --- Monotonic risers stay clean (Thompson) --------------------------------------


def test_monotonic_riser_gets_no_bounce_note():
    a = assess_player(GoalieCard(**_load("thompson.json")))
    assert "in between" not in a.trajectory                # 38→91→100 is just a rise
    assert "pointing sharply up" in a.trajectory           # spine unchanged


def test_monotonic_skater_riser_stays_clean():
    a = assess_player(_skater([("23-24", 40), ("24-25", 62), ("25-26", 78)]))
    assert "in between" not in a.trajectory


# --- Flat series stay clean ------------------------------------------------------


def test_flat_series_unchanged():
    a = assess_player(_skater([("23-24", 55), ("24-25", 56), ("25-26", 55)]))
    assert a.trajectory.endswith("- holding steady.")      # no note, no level tag
    assert "in between" not in a.trajectory


def test_high_flat_series_gets_level_tag_but_no_note():
    a = assess_player(_skater([("23-24", 88), ("24-25", 89), ("25-26", 88)]))
    assert "holding steady at a high level" in a.trajectory
    assert "in between" not in a.trajectory


# --- Goalie dip (same helper, goalie trend) --------------------------------------


def test_goalie_dip_is_named():
    card = _load("thompson.json")
    card["war_per60_trend"] = [
        {"season": "23-24", "value": 90},
        {"season": "24-25", "value": 40},
        {"season": "25-26", "value": 92},
    ]
    a = assess_player(GoalieCard(**card))
    assert "with a down year (40th) in between" in a.trajectory


# --- The margin is config, not code ----------------------------------------------


def test_bounce_margin_is_config_tunable():
    cfg = copy.deepcopy(load_config())
    cfg["trajectory"]["bounce_margin"] = 30                # huge → nothing bounces
    a = assess_player(SkaterCard(**_load("hughes.json")), config=cfg)
    assert "in between" not in a.trajectory


def test_default_margin_ignores_chart_noise():
    # 2-point wiggle is chart-reading noise, not a peak
    a = assess_player(_skater([("23-24", 70), ("24-25", 73), ("25-26", 71)]))
    assert "in between" not in a.trajectory


# --- Two-point trends unchanged ---------------------------------------------------


def test_two_point_trend_unchanged():
    a = assess_player(SkaterCard(**_load("celebrini.json")))
    assert a.trajectory == (
        "Projected-WAR percentile 78 → 97 over 2 seasons - pointing sharply up."
    )
