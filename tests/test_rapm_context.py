"""RAPM-methodology anchors (the isolating-impact write-up, 2026-07-18).

Three reading rules the source establishes:
- The impact components adjust for far more context than teammates/competition:
  zone starts, score state, home ice, back-to-backs, and power-play-expiry
  shifts — so "his numbers are a deployment artifact" claims are largely
  priced in already.
- A forward's defensive impact is the less repeatable half of play-driving
  (the model's own priors regress past defense roughly twice as hard toward
  average as past offense) — verdicts leaning on a forward's EV defense carry
  that caveat.
- "Sheltered" / "easy minutes" claims route to the deployment machinery.

All articulation-only; no tier, threshold, or verdict moves.
"""
import json
from pathlib import Path

from config import load_config
from engine.adjudicate import adjudicate_claim
from engine.assess import assess_player
from engine.glossary import explain_metric
from schemas import DefenseCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _forward(**over):
    base = dict(
        name="Synthetic Two-Way", position="C",
        ev_offense=50, ev_defense=80, finishing=50, penalties=50,
        proj_war_pct=60,
    )
    base.update(over)
    return SkaterCard(**base)


# --- Deployment context is broader than teammates/competition ----------------


def test_deployment_caveat_names_the_adjusted_context():
    caveat = load_config()["caveats"]["deployment_not_value"].lower()
    assert "zone starts" in caveat
    assert "score" in caveat
    assert "back-to-back" in caveat


def test_sheltered_claim_routes_to_deployment():
    dims = {d["id"]: d for d in load_config()["dimensions"]}
    aliases = [a.lower() for a in dims["competition"]["aliases"]]
    assert "sheltered" in aliases
    assert "easy minutes" in aliases
    v = adjudicate_claim(
        SkaterCard(**_load("celebrini.json")),
        [{"dimension": "sheltered", "direction": "high"}],
    ).verdicts[0]
    assert v.metric == "competition"
    assert v.caveat is not None and "deployment" in v.caveat.lower()


# --- Forward defensive impact is the less repeatable half --------------------


def test_ev_defense_caveat_carries_both_identity_and_repeatability():
    caveat = explain_metric("ev_defense").caveat.lower()
    assert "hits" in caveat          # impact-not-hits identity preserved
    assert "repeat" in caveat        # ...plus the repeatability asymmetry


def test_forward_ev_defense_strength_attaches_repeatability_caveat():
    caveats = " ".join(assess_player(_forward()).caveats).lower()
    assert "repeat" in caveats


def test_no_repeatability_caveat_when_defense_is_not_a_strength():
    celebrini = SkaterCard(**_load("celebrini.json"))  # ev_defense 33
    caveats = " ".join(assess_player(celebrini).caveats).lower()
    assert "less repeatable half" not in caveats


def test_defenseman_ev_defense_strength_does_not_attach_it():
    # The published trend coefficients are for forwards; a D's defensive
    # verdict does not get the forward asymmetry caveat.
    dman = DefenseCard(
        name="Synthetic Shutdown D", ev_offense=40, ev_defense=85,
        finishing=30, penalties=50, proj_war_pct=70,
    )
    caveats = " ".join(assess_player(dman).caveats).lower()
    assert "less repeatable half" not in caveats


def test_two_way_claim_carries_the_repeatability_caveat():
    v = adjudicate_claim(
        _forward(), [{"dimension": "two_way", "direction": "high", "text": "a real two-way center"}]
    ).verdicts[0]
    assert v.grade == "supported"
    assert v.caveat is not None
    assert "repeat" in v.caveat.lower()


# --- Definitions name the fuller adjustment list -----------------------------


def test_ev_definitions_name_the_richer_adjustments():
    for metric in ("ev_offense", "ev_defense"):
        definition = explain_metric(metric).definition.lower()
        assert "zone starts" in definition, metric
