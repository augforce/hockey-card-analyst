"""adjudicate_claim against microstat cards.

The point of the micro card in the claim pipeline: style claims that are
honestly unverifiable on a standard card (skating, physicality, forechecking,
rush-vs-cycle) become answerable - with a number as the receipt - when the
micro card is supplied. The same aliases still land on `skater_style`
(unverifiable) for a standard card; the pool preference in `_resolve` routes
them to the micro dimensions for a micro card.
"""
import json
from pathlib import Path

import pytest

from engine.adjudicate import adjudicate_claim
from schemas import DefenseMicroCard, ForwardMicroCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def celebrini_micro():
    return ForwardMicroCard(**_load("celebrini_micro.json"))


@pytest.fixture
def schaefer_micro():
    return DefenseMicroCard(**_load("schaefer_micro.json"))


@pytest.fixture
def celebrini_standard():
    return SkaterCard(**_load("celebrini.json"))


def _one(card, dimension, direction="high", text=None):
    return adjudicate_claim(card, [{"dimension": dimension, "direction": direction, "text": text}]).verdicts[0]


# --- Style claims become answerable on a micro card -------------------------


def test_physical_claim_refuted_with_receipt_and_style_caveat(celebrini_micro):
    v = _one(celebrini_micro, "physical", "high", "he's a physical player")
    assert v.grade == "not_supported"
    assert v.metric == "hits"
    assert v.value == 27
    # The style caveat must ride along even on a refutation - a low Hits number
    # is a style fact, not a value weakness, and the narrator needs that.
    assert v.caveat is not None
    assert "style" in v.caveat.lower()


def test_great_skater_claim_supported(celebrini_micro):
    v = _one(celebrini_micro, "great skater")
    assert v.grade == "supported"
    assert v.metric == "skating_speed"
    assert v.value == 84


def test_forechecker_claim_is_partial_at_57(celebrini_micro):
    v = _one(celebrini_micro, "forechecker")
    assert v.grade == "partial"
    assert v.value == 57


def test_rush_player_claim_supported(celebrini_micro):
    v = _one(celebrini_micro, "rush player")
    assert v.grade == "supported"
    assert v.metric == "rush_offense"
    assert v.value == 96


def test_same_style_claims_stay_unverifiable_on_standard_card(celebrini_standard):
    for phrase in ("physical", "great skater", "rush player"):
        v = _one(celebrini_standard, phrase)
        assert v.grade == "unverifiable", phrase
        assert "microstat" in v.reason.lower(), phrase


# --- Defense micro claims ----------------------------------------------------


def test_defends_the_rush_supported_for_schaefer(schaefer_micro):
    v = _one(schaefer_micro, "defends the rush")
    assert v.grade == "supported"
    assert v.metric == "entry_chance_prevention"
    assert v.value == 81


def test_turnover_prone_claim_refuted(schaefer_micro):
    # "turnover-prone" claims LOW puck management; Schaefer sits 85th.
    v = _one(schaefer_micro, "turnover-prone", "low")
    assert v.grade == "not_supported"
    assert v.value == 85


def test_power_play_weakness_supported_on_micro_war_row(schaefer_micro):
    v = _one(schaefer_micro, "power_play", "low")
    assert v.grade == "supported"
    assert v.value == 12


# --- Honest gaps -------------------------------------------------------------


def test_overall_claim_needs_the_standard_card(celebrini_micro):
    # "he's elite" -> overall_skater -> proj_war_pct, which a micro card
    # doesn't carry. Must be unverifiable and point at the standard card -
    # NOT the misleading "no role (NA)" wording.
    v = _one(celebrini_micro, "overall_skater", "high", "he's elite")
    assert v.grade == "unverifiable"
    assert "standard card" in v.reason.lower()
    assert "role" not in v.reason.lower()


def test_na_role_on_micro_still_reads_as_na(celebrini_micro):
    # Celebrini's micro card has PK = NA - role absence wording is right here.
    v = _one(celebrini_micro, "penalty_kill")
    assert v.grade == "unverifiable"
    assert "na" in v.reason.lower()


def test_playmaking_resolves_to_primary_assists_on_micro(celebrini_micro):
    # The playmaking dimension lists first_assists (standard) then
    # primary_assists (micro spelling) - the micro card must resolve.
    v = _one(celebrini_micro, "playmaking")
    assert v.grade == "supported"
    assert v.metric == "primary_assists"
    assert v.value == 96


def test_micro_overall_read_flags_the_single_season(celebrini_micro):
    adj = adjudicate_claim(celebrini_micro, [{"dimension": "rush player", "direction": "high"}])
    assert "season" in adj.overall.lower()
