"""Config coverage for the microstat card: glossary, caveats, dimensions.

The methodology-lives-in-config rule extends to the micro card: every metric box
on the two micro card variants must have a glossary entry (definition + caveat),
the micro caveats must exist as single-source sentences, and the dimension
dictionary must make style claims answerable against a micro card while the
standard-card entries stay honest about what a standard card cannot see.
"""
import pytest

from config import load_config, load_glossary
from engine.glossary import explain_metric
from schemas import DefenseMicroCard, ForwardMicroCard

# Context fields that are not percentile metric boxes.
_NON_METRIC = {"card_kind", "name", "team", "season", "position"}
# Micro field names that resolve to an existing standard-card glossary entry
# (same underlying stat, different schema spelling on the micro card).
_RESOLVES_TO = {"primary_assists": "first_assists"}

FORWARD_MICRO_METRICS = sorted(set(ForwardMicroCard.model_fields) - _NON_METRIC)
DEFENSE_MICRO_METRICS = sorted(set(DefenseMicroCard.model_fields) - _NON_METRIC)


@pytest.mark.parametrize("metric", sorted(set(FORWARD_MICRO_METRICS) | set(DEFENSE_MICRO_METRICS)))
def test_every_micro_metric_has_a_glossary_entry(metric):
    out = explain_metric(metric)
    assert out.found is True, f"no glossary entry resolves '{metric}'"
    assert out.definition and out.caveat
    expected = _RESOLVES_TO.get(metric, metric)
    assert out.metric == expected


def test_inferred_entries_disclose_the_inference():
    """Six micro metrics have no published definition anywhere (checked
    2026-07-18) — the glossary reads are inferred from the documented tracking
    conventions, and each caveat must keep saying so."""
    gloss = load_glossary()["metrics"]
    for metric in ("entries_w_possession", "exits_w_possession",
                   "d_zone_puck_touches", "entry_possession_rate",
                   "pass_exits", "carry_exits"):
        caveat = gloss[metric]["caveat"].lower()
        assert "inferred" in caveat, metric
        assert "no official definition" in caveat, metric


def test_micro_caveats_exist_as_single_source_sentences():
    cav = load_config()["caveats"]
    for key in ("micro_single_season", "micro_unadjusted", "micro_style_not_value"):
        assert cav.get(key), key


def test_micro_rules_carry_the_cross_regime_war_row_note():
    rules = load_config().get("micro_rules") or {}
    note = rules.get("war_row", "")
    assert "season" in note.lower()
    assert "three-year" in note.lower() or "3-year" in note.lower()


def test_micro_profiles_are_configured():
    prof = load_config().get("micro_profiles") or {}
    assert "high_min" in prof and "gap" in prof
    for family in ("shot_selectivity", "passing_quality", "attack_style", "rush_defense"):
        assert family in prof, family
    # The D rush-defense shapes the source methodology scripts explicitly.
    for shape in ("lockdown", "tight_gap_walked", "soft_gap_slot", "leaky"):
        assert shape in prof["rush_defense"], shape


def _dims():
    return {d["id"]: d for d in load_config()["dimensions"]}


def test_micro_style_dimensions_are_answerable():
    dims = _dims()
    expected = {
        "skating": "skating_speed",
        "physicality": "hits",
        "forechecking": "forecheck_involvement",
        "rush_attack": "rush_offense",
        "cycle_game": "in_zone_offense",
        "rush_defense": "entry_chance_prevention",
        "puck_management": "success_per_poss_play",
        "retrievals": "d_zone_retrievals",
    }
    for dim_id, primary in expected.items():
        entry = dims.get(dim_id)
        assert entry is not None, dim_id
        assert entry["applies_to"] == "micro"
        assert entry.get("answerability", "answerable") == "answerable"
        assert entry["metrics"][0] == primary, dim_id


def test_style_not_value_dimensions_carry_the_caveat():
    dims = _dims()
    for dim_id in ("skating", "physicality", "forechecking"):
        assert dims[dim_id].get("caveat") == "micro_style_not_value", dim_id


def test_playmaking_resolves_on_both_card_kinds():
    # Standard card has first_assists; micro card spells it primary_assists.
    metrics = _dims()["playmaking"]["metrics"]
    assert "first_assists" in metrics
    assert "primary_assists" in metrics


def test_standard_card_style_notes_updated_but_still_honest():
    dims = _dims()
    style_note = dims["skater_style"]["note"]
    # Still unverifiable on a standard card...
    assert dims["skater_style"]["answerability"] == "not_answerable"
    # ...but the note now says the microstat card measures several style traits
    # (the old note wrongly claimed skating and physicality weren't measured there).
    assert "microstat" in style_note.lower()
    assert "skating" in style_note.lower()
    net_front_note = dims["net_front"]["note"]
    assert dims["net_front"]["answerability"] == "not_answerable"
    assert "microstat" in net_front_note.lower()
