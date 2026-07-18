"""assess_player on microstat cards, plus the both-cards synthesis.

Design rules under test:
- The WAR-component row is the value read (same thresholds as the standard
  card, D finishing excluded); the microstat columns are descriptive detail —
  they explain HOW, never the value verdict.
- Hits / Skating Speed / Forecheck Involvement are style reads, never value
  strengths or weaknesses, whatever the percentile.
- Paired profiles (shot selectivity, passing quality, attack style, D rush
  defense) are articulation only.
- A micro card has no Proj. WAR headline — the assessment says so instead of
  inventing an overall tier.
- With BOTH cards supplied for the same player, the standard assessment gains
  articulation-only synthesis (insights + season-vs-projection divergences);
  the tier and verdict must not move.
"""
import json
from pathlib import Path

import pytest

from engine.assess import MicroAssessment, assess_player
from schemas import DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

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


# --- Forward micro assessment ----------------------------------------------


def test_micro_card_dispatches_to_micro_assessment(celebrini_micro):
    out = assess_player(celebrini_micro)
    assert isinstance(out, MicroAssessment)
    assert out.season == "2025-26"


def test_value_reads_come_from_the_war_row_only(celebrini_micro):
    out = assess_player(celebrini_micro)
    strength_metrics = {s.metric for s in out.strengths}
    # WAR row highs: ev_offense 89, pp 75, penalties 93, finishing 91.
    assert strength_metrics == {"ev_offense", "pp", "penalties", "finishing"}
    # Microstats never appear as value strengths, however elite (chance
    # contributions is 99th here).
    assert "chance_contributions" not in strength_metrics
    assert out.weaknesses == []  # ev_defense 67 is neutral


def test_na_pk_is_deployment_not_weakness(celebrini_micro):
    out = assess_player(celebrini_micro)
    assert any("penalty kill" in d.lower() and "na" in d.lower() for d in out.deployment)
    assert all(w.metric != "pk" for w in out.weaknesses)


def test_no_overall_tier_is_invented(celebrini_micro):
    out = assess_player(celebrini_micro)
    assert "proj" in out.overall_note.lower() or "war" in out.overall_note.lower()
    assert "standard card" in out.overall_note.lower()


def test_attack_style_profile_reads_rush_led(celebrini_micro):
    out = assess_player(celebrini_micro)
    profiles = {p.family: p for p in out.profiles}
    assert "attack_style" in profiles
    p = profiles["attack_style"]
    assert p.shape == "rush_led"
    values = {r.metric: r.percentile for r in p.reads}
    assert values == {"rush_offense": 96, "in_zone_offense": 64}


def test_no_profile_forced_when_gap_is_too_small(celebrini_micro):
    # chances 91 vs shots 79 (gap 12 < 15) — no selectivity story is told.
    out = assess_player(celebrini_micro)
    assert "shot_selectivity" not in {p.family for p in out.profiles}


def test_style_metrics_are_style_reads_not_weaknesses(celebrini_micro):
    out = assess_player(celebrini_micro)
    assert {r.metric for r in out.style_reads} == {"skating_speed", "forecheck_involvement", "hits"}
    # Hits 27th must NOT appear in the lows — it's a style fact.
    assert all(r.metric != "hits" for r in out.micro_lows)
    hits = next(r for r in out.style_reads if r.metric == "hits")
    assert hits.percentile == 27
    assert hits.note and "style" in hits.note.lower()


def test_micro_highs_are_descriptive_standouts(celebrini_micro):
    out = assess_player(celebrini_micro)
    highs = {r.metric for r in out.micro_highs}
    assert "chance_contributions" in highs
    assert "zone_entries" in highs
    # Style trio excluded even when high (skating_speed 84).
    assert "skating_speed" not in highs


def test_micro_caveats_present(celebrini_micro):
    out = assess_player(celebrini_micro)
    joined = " ".join(out.caveats).lower()
    assert "one season" in joined or "single season" in joined or "smaller" in joined
    assert "not adjusted" in joined or "raw tracked" in joined
    # Finishing (91st) is a WAR-row strength -> volatility caveat still fires.
    assert "finishing" in joined
    # Hits 27th (a low style read) -> style-not-value caveat fires.
    assert "style" in joined


def test_summary_names_the_season(celebrini_micro):
    out = assess_player(celebrini_micro)
    assert "2025-26" in out.summary
    assert "Celebrini" in out.summary


# --- Defense micro assessment ----------------------------------------------


def test_defense_finishing_excluded_from_micro_value(schaefer_micro):
    out = assess_player(schaefer_micro)
    strength_metrics = {s.metric for s in out.strengths}
    # ev_offense 96, penalties 99 — but NOT finishing 95 (excluded for a D).
    assert "ev_offense" in strength_metrics
    assert "penalties" in strength_metrics
    assert "finishing" not in strength_metrics
    desc = next(d for d in out.descriptive if d.metric == "finishing")
    assert "excluded" in (desc.note or "").lower()


def test_defense_war_row_weaknesses(schaefer_micro):
    out = assess_player(schaefer_micro)
    weak_metrics = {w.metric for w in out.weaknesses}
    assert weak_metrics == {"pp", "pk"}  # 12 and 27


def test_rush_defense_profile_present_for_d(schaefer_micro):
    out = assess_player(schaefer_micro)
    profiles = {p.family: p for p in out.profiles}
    assert "rush_defense" in profiles
    p = profiles["rush_defense"]
    assert p.shape in ("lockdown", "tight_gap_walked", "soft_gap_slot", "leaky")
    # ECP 81 with a strong front (78/63 avg 70.5) reads as the full package.
    assert p.shape == "lockdown"
    metrics = {r.metric for r in p.reads}
    assert metrics == {"entry_chance_prevention", "poss_entry_prevention", "entry_denial_rate"}


def test_passing_quality_reads_dangerous_for_schaefer(schaefer_micro):
    # Chance assists 77 vs primary shot assists 51 — the dangerous-passer shape.
    out = assess_player(schaefer_micro)
    profiles = {p.family: p for p in out.profiles}
    assert profiles["passing_quality"].shape == "dangerous"


def test_d_style_reads_are_hits_only(schaefer_micro):
    out = assess_player(schaefer_micro)
    assert {r.metric for r in out.style_reads} == {"hits"}


def test_d_micro_lows_include_real_tracked_softspots(schaefer_micro):
    out = assess_player(schaefer_micro)
    lows = {r.metric for r in out.micro_lows}
    assert "dz_shot_assists" in lows       # 1st
    assert "exit_possession_rate" in lows  # 30th
    assert "in_zone_offense" in lows       # 25th
    assert "hits" not in lows              # style, not value


# --- Both-cards synthesis ---------------------------------------------------


def test_synthesis_attaches_without_moving_the_verdict(celebrini_standard, celebrini_micro):
    plain = assess_player(celebrini_standard)
    combined = assess_player(celebrini_standard, micro_card=celebrini_micro)
    # Articulation only: tier, strengths, weaknesses identical.
    assert combined.overall_tier == plain.overall_tier
    assert combined.overall_percentile == plain.overall_percentile
    assert [s.metric for s in combined.strengths] == [s.metric for s in plain.strengths]
    assert [w.metric for w in combined.weaknesses] == [w.metric for w in plain.weaknesses]
    # And the synthesis is present.
    assert combined.micro_insights is not None
    assert combined.micro_insights.season == "2025-26"
    assert plain.micro_insights is None


def test_synthesis_flags_season_vs_projection_divergence(celebrini_standard, celebrini_micro):
    # Standard ev_defense 33 (3yr projection) vs micro 67 (this season): >= 15
    # apart -> a divergence note; nearby components (finishing 92 vs 91) do not fire.
    syn = assess_player(celebrini_standard, micro_card=celebrini_micro).micro_insights
    joined = " ".join(syn.divergences).lower()
    assert "defense" in joined
    assert all("finishing" not in d.lower() for d in syn.divergences)


def test_synthesis_backs_finishing_with_chance_volume(celebrini_standard, celebrini_micro):
    syn = assess_player(celebrini_standard, micro_card=celebrini_micro).micro_insights
    joined = " ".join(syn.insights).lower()
    # Finishing 92 (standard) + chances 91 (micro): conversion backed by volume.
    assert "chance" in joined
    # First assists 95 + HD passes 93: the dangerous-passer evidence.
    assert "danger" in joined


def test_synthesis_carries_the_cross_regime_note(celebrini_standard, celebrini_micro):
    syn = assess_player(celebrini_standard, micro_card=celebrini_micro).micro_insights
    assert "season" in syn.note.lower()


def test_synthesis_refuses_mismatched_player_names(celebrini_standard, schaefer_micro):
    with pytest.raises(ValueError):
        assess_player(celebrini_standard, micro_card=schaefer_micro)


def test_synthesis_refuses_goalie_plus_micro(celebrini_micro):
    goalie = GoalieCard(**_load("thompson.json"))
    with pytest.raises(ValueError):
        assess_player(goalie, micro_card=celebrini_micro)
