"""Tests for adjudicate_claim on skaters (PLAN sections 3, 6, 7).

The server does NOT parse language: it receives assertions already decomposed
into {dimension, direction} and grades each against the card. The headline test
is the section 3 four-part claim run on Celebrini, which must surface all four
grades - including the unverifiable ones.
"""
import json
from pathlib import Path

import pytest

from engine.adjudicate import Adjudication, Assertion, adjudicate_claim
from schemas import SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def celebrini():
    return SkaterCard(**json.loads((FIXTURES / "celebrini.json").read_text()))


# The section 3 four-part claim, decomposed the way Claude Desktop would.
# "asked to do more" maps to BOTH playmaking and defense (section 3), so it
# yields two assertions - and they disagree, which is the point.
FOUR_PART = [
    {"dimension": "finishing", "direction": "high", "text": "scores goals"},
    {"dimension": "playmaking", "direction": "low", "text": "limited if asked to do more"},
    {"dimension": "two_way", "direction": "low", "text": "limited if asked to do more (defense)"},
    {"dimension": "net_front", "direction": "high", "text": "sits in front of the net"},
    {"dimension": "team_leading_scorer", "direction": "high", "text": "leading scorer next season"},
]


def _by_dim(adj):
    return {v.dimension: v for v in adj.verdicts}


def test_four_part_claim_surfaces_all_four_grades(celebrini):
    adj = adjudicate_claim(celebrini, FOUR_PART)
    assert isinstance(adj, Adjudication)
    assert {v.grade for v in adj.verdicts} == {
        "supported",
        "partial",
        "not_supported",
        "unverifiable",
    }


def test_four_part_individual_grades(celebrini):
    v = _by_dim(adjudicate_claim(celebrini, FOUR_PART))
    assert v["finishing"].grade == "supported"          # finishing 92nd
    assert v["playmaking"].grade == "not_supported"     # claim low, but 95th
    assert v["two_way"].grade == "supported"            # ev_defense 33rd, low
    assert v["net_front"].grade == "unverifiable"       # not on the card
    assert v["team_leading_scorer"].grade == "partial"  # needs team context


def test_verdicts_cite_the_metric_value(celebrini):
    v = _by_dim(adjudicate_claim(celebrini, FOUR_PART))
    assert v["finishing"].value == 92
    assert v["playmaking"].value == 95   # the receipt for the contradiction
    assert v["two_way"].value == 33
    assert v["net_front"].value is None  # nothing to cite


def test_contradicting_direction_is_not_supported_with_receipt(celebrini):
    # Claim says playmaking is LOW; card says 95th. Number is the receipt.
    v = _by_dim(adjudicate_claim(celebrini, FOUR_PART))["playmaking"]
    assert v.grade == "not_supported"
    assert "95" in v.reason


def test_not_answerable_returns_unverifiable_from_config_note(celebrini):
    v = adjudicate_claim(celebrini, [{"dimension": "net_front", "direction": "high"}]).verdicts[0]
    assert v.grade == "unverifiable"
    assert v.value is None
    assert "microstat" in v.reason.lower()  # net_front note points to microstat card


def test_skater_style_claim_is_unverifiable_with_note(celebrini):
    # "physical, north-south power forward" is playing-style, not on a standard card.
    v = adjudicate_claim(
        celebrini, [{"dimension": "skater_style", "direction": "high", "text": "he's a physical, north-south power forward"}]
    ).verdicts[0]
    assert v.grade == "unverifiable"
    assert v.value is None
    assert "playing-style" in v.reason.lower() or "playing style" in v.reason.lower()


def test_team_context_is_partial(celebrini):
    v = adjudicate_claim(
        celebrini, [{"dimension": "team_leading_scorer", "direction": "high"}]
    ).verdicts[0]
    assert v.grade == "partial"
    assert v.value == 94  # proj_war_pct receipt


def test_na_role_claim_is_unverifiable_not_a_guess(celebrini):
    # Celebrini has no PK role (pk = NA); "great penalty killer" can't be graded.
    v = adjudicate_claim(
        celebrini, [{"dimension": "penalty_kill", "direction": "high"}]
    ).verdicts[0]
    assert v.grade == "unverifiable"
    assert v.value is None
    assert "na" in v.reason.lower()


def test_unknown_dimension_is_unverifiable(celebrini):
    v = adjudicate_claim(celebrini, [{"dimension": "vibes", "direction": "high"}]).verdicts[0]
    assert v.grade == "unverifiable"


def test_finishing_support_carries_volatility_caveat(celebrini):
    v = adjudicate_claim(celebrini, [{"dimension": "finishing", "direction": "high"}]).verdicts[0]
    assert v.grade == "supported"
    assert v.caveat is not None
    assert "finishing" in v.caveat.lower()


def test_overall_read_is_present_and_names_the_split(celebrini):
    adj = adjudicate_claim(celebrini, FOUR_PART)
    assert adj.overall
    # Must not paper over a mix: both a supported and an unverifiable show up.
    assert "support" in adj.overall.lower()
    assert "unverifiable" in adj.overall.lower()


def test_accepts_assertion_objects_not_just_dicts(celebrini):
    adj = adjudicate_claim(celebrini, [Assertion(dimension="finishing", direction="high")])
    assert adj.verdicts[0].grade == "supported"
