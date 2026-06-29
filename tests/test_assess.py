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
def dorofeyev():
    return SkaterCard(**_load("dorofeyev.json"))


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


# --- Scoring profile: EV offence (play-driving) vs finishing (conversion) ---


def test_dorofeyev_scoring_profile_is_negative_regression(dorofeyev):
    a = assess_player(dorofeyev)
    sp = a.scoring_profile
    assert sp is not None
    assert sp.shape == "negative_regression"
    # The read carries the two card numbers it weighs, unchanged.
    assert sp.ev_offence == 61
    assert sp.finishing == 97


def test_scoring_profile_does_not_change_tier_or_war(dorofeyev):
    # Articulation only: the read must not move the tier or the WAR verdict.
    a = assess_player(dorofeyev)
    assert a.overall_percentile == 94
    assert a.overall_tier == "Excellent"
    # finishing is still a genuine strength on the card; the read doesn't demote it.
    assert "finishing" in _metrics(a.strengths)


def test_negative_regression_reinforces_finishing_volatility(dorofeyev):
    a = assess_player(dorofeyev)
    cfg = load_config()
    # The verdict leans on finishing, so the existing caveat still fires...
    assert cfg["caveats"]["finishing_volatility"] in a.caveats
    # ...and the scoring profile is worded to reinforce it, not contradict it.
    assert "finishing-volatility" in a.scoring_profile.note.lower()


def test_celebrini_scoring_profile_is_both_high(celebrini):
    a = assess_player(celebrini)
    sp = a.scoring_profile
    assert sp is not None
    assert sp.shape == "both_high"
    assert sp.ev_offence == 91
    assert sp.finishing == 92


def test_both_high_tempers_finishing_volatility(celebrini):
    a = assess_player(celebrini)
    cfg = load_config()
    # finishing is a strength, so the caveat still fires...
    assert cfg["caveats"]["finishing_volatility"] in a.caveats
    # ...but the both-high read tempers it (scoring is well-supported).
    assert "temper" in a.scoring_profile.note.lower()


def test_positive_regression_when_ev_offence_leads_finishing():
    # High play-driving, finishing lagging — generates chances he isn't converting.
    card = SkaterCard(
        name="Synthetic PR (test fixture, not a real player)",
        team="TEST",
        position="C",
        age=24,
        ev_offence=88,
        ev_defence=60,
        finishing=60,
        penalties=50,
        proj_war_pct=75,
    )
    a = assess_player(card)
    assert a.scoring_profile is not None
    assert a.scoring_profile.shape == "positive_regression"


def test_no_scoring_profile_when_neither_dimension_is_high():
    card = SkaterCard(
        name="Synthetic mid (test fixture, not a real player)",
        team="TEST",
        position="C",
        age=24,
        ev_offence=55,
        ev_defence=58,
        finishing=58,
        penalties=50,
        proj_war_pct=52,
    )
    a = assess_player(card)
    assert a.scoring_profile is None


def test_defenseman_has_no_scoring_profile(dman):
    # Finishing is excluded from a D's value, so the scoring read must not fire
    # even though the synthetic D shows finishing 95 over ev_offence 48.
    a = assess_player(dman)
    assert a.scoring_profile is None


# --- Young-sample uncertainty (the card is a 3-year weighted average) -------


def test_young_player_gets_uncertainty_caveat(celebrini):
    # Celebrini is 20 — under the threshold, so the thin-sample caveat fires.
    a = assess_player(celebrini)
    base = load_config()["caveats"]["young_sample"]
    assert any(base in c for c in a.caveats)


def test_young_sample_caveat_pairs_with_rising_trend(celebrini):
    # Celebrini's WAR trend points up (78 -> 97), so the caveat is paired with it.
    a = assess_player(celebrini)
    rising = load_config()["caveats"]["young_sample_rising"]
    assert any(rising in c for c in a.caveats)


def test_uncertainty_caveat_does_not_change_tier_or_verdict(celebrini):
    # Articulation only — the caveat must not move the tier or the WAR verdict.
    a = assess_player(celebrini)
    assert a.overall_percentile == 94
    assert a.overall_tier == "Excellent"


def test_older_player_gets_no_uncertainty_caveat():
    card = SkaterCard(
        name="Synthetic vet (test fixture, not a real player)",
        team="TEST",
        position="C",
        age=28,
        ev_offence=70,
        ev_defence=60,
        finishing=55,
        penalties=50,
        proj_war_pct=72,
        war_pct_trend=[
            {"season": "24-25", "value": 60},
            {"season": "25-26", "value": 80},
        ],
    )
    a = assess_player(card)
    base = load_config()["caveats"]["young_sample"]
    assert not any(base in c for c in a.caveats)


def test_young_without_rising_trend_omits_the_pairing():
    # Young, but no upward trend — the base caveat fires without the paired clause.
    card = SkaterCard(
        name="Synthetic kid (test fixture, not a real player)",
        team="TEST",
        position="C",
        age=21,
        ev_offence=60,
        ev_defence=58,
        finishing=55,
        penalties=50,
        proj_war_pct=55,
    )
    a = assess_player(card)
    cfg = load_config()
    assert any(cfg["caveats"]["young_sample"] in c for c in a.caveats)
    assert not any(cfg["caveats"]["young_sample_rising"] in c for c in a.caveats)
