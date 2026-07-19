"""Expected-goals substrate anchors (HockeyStats xG rebuild write-up, 2026-07-18).

The card percentiles ride on the site's expected-goals model, and the rebuild
write-up establishes three reading rules the config now encodes:
- The tracking substrate has drifted across recent seasons and the model is
  recalibrated per season - cross-season level shifts in the Save% vs Expected
  Save% gap deserve slack (part of a move can be model/tracking drift, not the
  goalie).
- Penalty-kill save performance is measured against power-play shots, where
  the xG model is at its weakest - the noisiest goalie read.
- A skater's PK defense inherits the same weakness for the same reason.

All articulation-only; nothing moves a tier or verdict.
"""
import json
from pathlib import Path

from config import load_config
from engine.assess import assess_player
from engine.glossary import explain_metric
from schemas import GoalieCard

FIXTURES = Path(__file__).parent / "fixtures"


def test_goalie_pk_caveat_flags_the_pp_xg_weakness():
    caveat = explain_metric("penalty_kill").caveat.lower()
    assert "power-play shots" in caveat or "power play shots" in caveat
    assert "weakest" in caveat
    # The original isolates-the-goalie's-part wording must survive.
    assert "isolat" in caveat


def test_skater_pk_caveat_inherits_the_same_weakness():
    caveat = explain_metric("pk").caveat.lower()
    assert "weakest" in caveat
    # The load-bearing NA-role wording must survive the enrichment.
    assert "na" in caveat


def test_save_lines_rule_carries_the_drift_slack():
    rule = load_config()["goalie_rules"]["save_lines"].lower()
    assert "drift" in rule
    assert "recalibrated" in rule or "season by season" in rule


def test_drift_slack_reaches_a_goalie_assessment_with_the_trend():
    # Thompson's fixture carries sv_vs_xsv_trend, so the save-lines rule (and
    # with it the drift slack) attaches automatically.
    card = GoalieCard(**json.loads((FIXTURES / "thompson.json").read_text(encoding="utf-8")))
    caveats = " ".join(assess_player(card).caveats).lower()
    assert "drift" in caveats
