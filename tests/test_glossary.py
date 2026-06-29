"""Tests for the metric glossary and explain_metric (skater + goalie).

explain_metric is a thin lookup: it DEFINES a card metric (definition + the one
key interpretive caveat). It does not reason about any player. These tests check
lookup by field name and natural alias, the honest not-found path, full coverage
of every card metric, and that caveats already attached by the engine are reused
from one source rather than duplicated.
"""
import pytest

from config import load_config
from engine.glossary import explain_metric, load_glossary

# Every percentile metric on each card (the glossary must cover all of them).
SKATER_METRICS = [
    "proj_war_pct", "competition", "teammates", "ev_offence", "ev_defence",
    "pp", "pk", "finishing", "penalties", "goals", "first_assists",
]
GOALIE_METRICS = [
    "proj_war_pct", "gp_pct", "even_strength", "penalty_kill", "high_danger",
    "med_danger", "low_danger", "quality_starts", "excellent_starts",
    "bad_starts", "rebound_control", "consistency",
]


# --- Lookup ----------------------------------------------------------------


def test_explain_by_schema_field_name():
    out = explain_metric("finishing")
    assert out.found is True
    assert out.metric == "finishing"
    assert out.definition and out.caveat


def test_explain_by_natural_alias():
    # The host can pass natural phrasing, not just the field name.
    out = explain_metric("even strength defense")
    assert out.found is True
    assert out.metric == "ev_defence"


def test_lookup_is_case_space_and_underscore_insensitive():
    for query in (" EV_Defence ", "EVEN-STRENGTH DEFENCE", "ev defence"):
        assert explain_metric(query).metric == "ev_defence"


def test_unknown_metric_is_not_found_and_does_not_guess():
    out = explain_metric("grit")
    assert out.found is False
    assert out.metric is None
    assert out.definition is None
    assert "not a card metric" in out.message.lower()


# --- Content ---------------------------------------------------------------


def test_goalie_bad_starts_caveat_states_orientation():
    out = explain_metric("bad starts")
    assert out.metric == "bad_starts"
    assert "higher" in out.caveat.lower()
    assert "invert" in out.caveat.lower()


def test_every_entry_has_a_definition_and_a_caveat():
    gloss = load_glossary()["metrics"]
    for name in gloss:
        out = explain_metric(name)
        assert out.definition, f"{name} missing definition"
        assert out.caveat, f"{name} missing caveat"


# --- Single source of truth (no duplicated caveat text) --------------------


def test_finishing_caveat_is_the_one_the_engine_attaches():
    # The glossary references the canonical sentence rather than retyping it.
    out = explain_metric("finishing")
    assert out.caveat == load_config()["caveats"]["finishing_volatility"]


def test_goalie_consistency_caveat_references_the_goalie_rule():
    out = explain_metric("consistency")
    assert out.caveat == load_config()["goalie_rules"]["consistency_volatility"]


def test_deployment_metrics_share_the_deployment_caveat():
    dep = load_config()["caveats"]["deployment_not_value"]
    assert explain_metric("competition").caveat == dep
    assert explain_metric("teammates").caveat == dep


# --- Coverage & hygiene ----------------------------------------------------


@pytest.mark.parametrize("metric", sorted(set(SKATER_METRICS) | set(GOALIE_METRICS)))
def test_every_card_metric_has_an_entry(metric):
    assert explain_metric(metric).found is True


def test_no_two_metrics_share_an_alias():
    # Data hygiene: a normalized lookup key must point at exactly one metric, or
    # explain_metric would silently pick one and mislead the host.
    from engine.glossary import _alias_index

    index = _alias_index(load_glossary())
    # _alias_index raises on collision; if it returns, every key is unambiguous.
    assert len(index) >= len(load_glossary()["metrics"])
