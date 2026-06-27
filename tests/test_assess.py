"""Tests for assess_player on skaters (PLAN sections 5, 6, 12).

Forward behaviour is checked against the verified Celebrini fixture; the
defenseman finishing-exclusion path is checked against a synthetic D fixture.
"""
import json
from pathlib import Path

import pytest

from config import load_config
from engine.assess import Assessment, assess_player
from schemas import DefenseCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def celebrini():
    return SkaterCard(**_load("celebrini.json"))


@pytest.fixture
def dman():
    return DefenseCard(**_load("synthetic_dman.json"))


def _metrics(reads):
    return {r.metric for r in reads}


# --- Forward (Celebrini) ---------------------------------------------------


def test_overall_tier_from_proj_war(celebrini):
    a = assess_player(celebrini)
    assert isinstance(a, Assessment)
    assert a.overall_percentile == 94
    assert a.overall_tier == "Excellent"


def test_offence_and_finishing_are_strengths(celebrini):
    a = assess_player(celebrini)
    metrics = _metrics(a.strengths)
    assert "ev_offence" in metrics
    assert "finishing" in metrics
    assert "penalties" in metrics  # 95th = elite discipline


def test_ev_defence_is_a_weakness(celebrini):
    a = assess_player(celebrini)
    weak = {r.metric: r for r in a.weaknesses}
    assert "ev_defence" in weak
    assert weak["ev_defence"].percentile == 33
    assert weak["ev_defence"].tier == "Below average"


def test_na_pk_is_deployment_not_a_weakness(celebrini):
    a = assess_player(celebrini)
    # PK is NA — must not surface as a weakness or as a zero.
    assert "pk" not in _metrics(a.weaknesses)
    assert "pk" not in _metrics(a.strengths)
    assert any("penalty kill" in note.lower() for note in a.deployment)


def test_deployment_not_counted_as_value(celebrini):
    a = assess_player(celebrini)
    assert "competition" not in _metrics(a.strengths) | _metrics(a.weaknesses)
    assert "teammates" not in _metrics(a.strengths) | _metrics(a.weaknesses)
    assert load_config()["caveats"]["deployment_not_value"] in a.caveats


def test_finishing_volatility_caveat_for_forward(celebrini):
    a = assess_player(celebrini)
    assert load_config()["caveats"]["finishing_volatility"] in a.caveats


def test_trajectory_reads_as_rising(celebrini):
    a = assess_player(celebrini)
    assert a.trajectory is not None
    assert "up" in a.trajectory.lower()


def test_summary_is_nonempty_and_names_player(celebrini):
    a = assess_player(celebrini)
    assert a.summary
    assert "Celebrini" in a.summary


# --- Defenseman finishing-exclusion ---------------------------------------


def test_defenseman_overall_not_lifted_by_finishing(dman):
    a = assess_player(dman)
    # proj WAR is 57 (Above average); finishing is 95 but excluded.
    assert a.overall_percentile == 57
    assert a.overall_tier == "Above average"


def test_defenseman_finishing_excluded_from_strengths(dman):
    a = assess_player(dman)
    assert "finishing" not in _metrics(a.strengths)


def test_defenseman_finishing_mentioned_descriptively_with_note(dman):
    a = assess_player(dman)
    desc = {r.metric: r for r in a.descriptive}
    assert "finishing" in desc
    assert desc["finishing"].percentile == 95
    assert desc["finishing"].note is not None
    assert "exclud" in desc["finishing"].note.lower()


def test_defenseman_no_finishing_volatility_caveat(dman):
    a = assess_player(dman)
    # The verdict is not built on finishing, so that caveat must not fire.
    assert load_config()["caveats"]["finishing_volatility"] not in a.caveats
