"""WAR-methodology reading anchors (TopDownHockey write-up, distilled 2026-07-18).

Four things the source methodology states that the config now encodes:
- Replacement level (0 WAR) sits at ~the 37th percentile - a projection at or
  below it reads as replacement-level-or-worse, not merely "below average."
- The model overweights shooting and understates play-driving (ridge shrinkage
  + replacement-level shooting), by the author's own account.
- The expected-goal model is weakest on the power play - PP is the noisiest of
  the six components.
- WAR is a point estimate of value added, not ability; EV excludes empty-net
  play; a penalty minute prices at ~0.11 goals.

All articulation-only: no tier, threshold, or verdict moves.
"""
import json
from pathlib import Path

from engine.assess import assess_player
from engine.glossary import explain_metric
from schemas import SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _skater(proj):
    return SkaterCard(
        name="Synthetic Replacement", position="C",
        ev_offense=40, ev_defense=40, finishing=40, penalties=40,
        proj_war_pct=proj,
    )


def _caveats(card):
    return " ".join(assess_player(card).caveats).lower()


# --- Replacement-level anchor ------------------------------------------------


def test_replacement_note_fires_at_or_below_37():
    assert "replacement" in _caveats(_skater(37))
    assert "replacement" in _caveats(_skater(20))


def test_replacement_note_silent_above_37():
    assert "replacement" not in _caveats(_skater(38))
    celebrini = SkaterCard(**json.loads((FIXTURES / "celebrini.json").read_text(encoding="utf-8")))
    assert "replacement" not in _caveats(celebrini)


def test_replacement_note_does_not_move_the_tier():
    # Articulation only: 37 stays in its configured band.
    a = assess_player(_skater(37))
    assert a.overall_percentile == 37
    assert a.overall_tier == "Below average"


# --- Model-weighting honesty -------------------------------------------------


def test_finishing_caveat_carries_the_weighting_admission():
    caveat = explain_metric("finishing").caveat.lower()
    assert "play-driving" in caveat
    assert "overstate" in caveat or "overweight" in caveat


def test_pp_caveat_flags_the_noisiest_component():
    caveat = explain_metric("pp").caveat.lower()
    assert "power play" in caveat
    assert "noisiest" in caveat or "weakest" in caveat
    # The load-bearing NA-role wording must survive the enrichment.
    assert "na" in caveat


# --- Point-estimate framing and factual enrichments --------------------------


def test_proj_war_caveat_is_the_point_estimate_framing():
    caveat = explain_metric("proj_war_pct").caveat.lower()
    assert "point estimate" in caveat
    assert "starting point" in caveat


def test_ev_definitions_note_the_empty_net_exclusion():
    assert "empty" in explain_metric("ev_offense").definition.lower()
    assert "empty" in explain_metric("ev_defense").definition.lower()


def test_penalties_definition_prices_the_minute():
    assert "0.11" in explain_metric("penalties").definition
