"""Phase 5 - goalies through all three tools (PLAN sections 5, 6, 12).

Reuses the same engine (tiers, four grades, split refusal, position guard) over
the goalie schema and the goalie reading rules. The headline is the Thompson
assessment, which must hold the 96th-WAR / 23rd-consistency tension together.
"""
import json
from pathlib import Path

import pytest

from config import load_config
from engine.adjudicate import adjudicate_claim
from engine.assess import GoalieAssessment, assess_player
from engine.compare import compare_players
from schemas import GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _goalie(name):
    return GoalieCard(**json.loads((FIXTURES / name).read_text()))


def _skater(name):
    return SkaterCard(**json.loads((FIXTURES / name).read_text()))


@pytest.fixture
def thompson():
    return _goalie("thompson.json")


# --- assess_player (goalie) ------------------------------------------------


def test_goalie_overall_tier(thompson):
    a = assess_player(thompson)
    assert isinstance(a, GoalieAssessment)
    assert a.overall_percentile == 96
    assert a.overall_tier == "Elite"


def test_danger_split_is_a_profile_shape(thompson):
    a = assess_player(thompson)
    assert {r.metric for r in a.danger_profile.reads} == {
        "high_danger",
        "med_danger",
        "low_danger",
    }
    shape = a.danger_profile.shape.lower()
    # Thompson 99 high vs 56 low: hard saves yes, routine shots ordinary.
    assert "hard saves" in shape or "high-danger" in shape
    assert "routine" in shape or "low-danger" in shape


def test_start_quality_is_a_floor_ceiling_profile(thompson):
    a = assess_player(thompson)
    assert {r.metric for r in a.start_quality_profile.reads} == {
        "quality_starts",
        "excellent_starts",
        "bad_starts",
    }
    shape = a.start_quality_profile.shape.lower()
    # quality 99 / excellent 53: reliable, not a game-stealer.
    assert "reliab" in shape or "game-steal" in shape


def test_consistency_is_a_volatility_flag_not_a_weakness(thompson):
    a = assess_player(thompson)
    assert a.consistency.percentile == 23
    assert "volatil" in a.consistency.note.lower()
    # Never listed as a plain strength/weakness.
    assert "consistency" not in {w.metric for w in a.weaknesses}
    assert "consistency" not in {s.metric for s in a.strengths}


def test_rebound_control_is_a_called_out_weakness(thompson):
    a = assess_player(thompson)
    assert "rebound_control" in {w.metric for w in a.weaknesses}


def test_trajectory_reads_war_percentile_and_save_gap(thompson):
    a = assess_player(thompson)
    t = a.trajectory.lower()
    assert "war" in t           # WAR-per-60 standing climb
    assert "expect" in t        # save% vs expected read as a gap


def test_summary_holds_the_tension(thompson):
    a = assess_player(thompson)
    s = a.summary
    assert "96" in s            # the strong half
    assert "23" in s            # the volatility half
    assert "starter" in s.lower()


# --- adjudicate_claim (goalie) ---------------------------------------------


def test_goalie_claim_mixes_supported_refuted_unverifiable(thompson):
    assertions = [
        {"dimension": "reliability", "direction": "high", "text": "gives you a chance every night"},
        {"dimension": "goalie_rebounds", "direction": "high", "text": "controls his rebounds"},
        {"dimension": "goalie_style", "direction": "high", "text": "plays deep in his net"},
    ]
    g = {v.dimension: v for v in adjudicate_claim(thompson, assertions).verdicts}
    assert g["reliability"].grade == "supported"          # quality starts 99
    assert g["goalie_rebounds"].grade == "not_supported"  # rebound control 35
    assert g["goalie_style"].grade == "unverifiable"      # style claim


def test_goalie_supported_cites_value(thompson):
    v = adjudicate_claim(thompson, [{"dimension": "reliability", "direction": "high"}]).verdicts[0]
    assert v.value == 99


# --- compare_players (goalie) ----------------------------------------------


def test_goalie_vs_goalie_split_refuses_a_winner():
    cmp = compare_players(
        _goalie("compare_goalie_peak.json"), _goalie("compare_goalie_floor.json")
    )
    assert cmp.compatible is True
    assert cmp.pool == "goalie"
    assert cmp.overall_edge is None
    assert cmp.edge_kind == "split"


def test_goalie_vs_skater_trips_the_position_guard(thompson):
    cmp = compare_players(thompson, _skater("celebrini.json"))
    assert cmp.compatible is False
    assert cmp.edge_kind == "incompatible"
    assert load_config()["caveats"]["within_position_only"] in cmp.caveats
