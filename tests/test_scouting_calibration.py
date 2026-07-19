"""Calibration from the scouting-report comparison (2026-07-18).

Comparing an engine-narrated Celebrini read against the site's prose scouting
report exposed two generalizable gaps:

1. Motor/compete claims are broader than Forecheck Involvement. That metric
   tracks only offensive-zone recoveries and exit pressures - wall battles,
   stick checks, and all-ice pursuit are invisible to it, so a "high motor"
   claim must grade as PARTIAL (with the number as a partial receipt), never
   as settled by the one box.
2. Forwards have no puck-security metric on either card (D cards have
   Success per Poss. Play). The missing-metric message must not claim the
   other card carries a metric it doesn't - "turnover-prone" about a forward
   is honestly untracked anywhere.
"""
import json
from pathlib import Path

from engine.adjudicate import adjudicate_claim
from engine.glossary import explain_metric
from schemas import ForwardMicroCard, GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _one(card, dimension, direction="high"):
    return adjudicate_claim(card, [{"dimension": dimension, "direction": direction}]).verdicts[0]


# --- Motor is only partially tracked -----------------------------------------


def test_high_motor_claim_is_partial_not_settled():
    v = _one(ForwardMicroCard(**_load("celebrini_micro.json")), "high motor")
    assert v.grade == "partial"
    assert v.metric == "forecheck_involvement"
    assert v.value == 57  # the partial receipt
    assert "wall battles" in v.reason.lower() or "stick" in v.reason.lower()


def test_forechecker_claim_still_answerable():
    # A specifically-forechecking claim IS what the box measures - unchanged.
    v = _one(ForwardMicroCard(**_load("celebrini_micro.json")), "forechecker")
    assert v.grade == "partial"  # 57th is middling for a 'high' claim
    assert v.metric == "forecheck_involvement"


def test_forecheck_glossary_caveat_scopes_the_metric():
    caveat = explain_metric("forecheck_involvement").caveat.lower()
    assert "offensive-zone" in caveat or "offensive zone" in caveat
    assert "wall" in caveat or "stick" in caveat


def test_motor_claim_on_defenseman_cites_retrieval_workload():
    """A D micro card has no forecheck box, but it does carry one slice of
    motor - D-zone retrieval workload. The claim stays partial, with that
    number as the receipt (never 'not tracked at all')."""
    from schemas import DefenseMicroCard

    v = _one(DefenseMicroCard(**_load("schaefer_micro.json")), "high motor")
    assert v.grade == "partial"
    assert v.metric == "d_zone_retrievals"
    assert v.value == 71


def test_skating_claim_on_defenseman_is_honestly_untracked():
    """Skating Speed is a forward-card-only box (NHL Edge); a D micro card
    must say the position isn't tracked rather than point at another card."""
    from schemas import DefenseMicroCard

    v = _one(DefenseMicroCard(**_load("schaefer_micro.json")), "great skater")
    assert v.grade == "unverifiable"
    assert "carries it" not in v.reason.lower()


# --- Net-front presence: the proxy is used, partially (Cuylle round) ---------
# The Cuylle comparison validated Shots off HD Passes as the net-front proxy:
# a scouted net-front winger posted a 96th there against low marks in every
# other shooting box. A net-front claim on a micro card now grades PARTIAL
# with that number as the receipt; on a standard card it stays unverifiable.


def test_net_front_claim_on_micro_is_partial_with_proxy_receipt():
    v = _one(ForwardMicroCard(**_load("cuylle_micro.json")), "net-front")
    assert v.grade == "partial"
    assert v.metric == "shots_off_hd_passes"
    assert v.value == 96
    assert "proxy" in v.reason.lower()
    assert "location" in v.reason.lower()  # still honest about what isn't tracked


def test_net_front_claim_on_standard_card_stays_unverifiable():
    v = _one(SkaterCard(**_load("celebrini.json")), "net-front")
    assert v.grade == "unverifiable"


# --- Passer claims grade on process, not assist outcomes (Cuylle round) ------
# Cuylle: primary assists 66th (outcomes, linemate-dependent) against 36th
# chance assists / 9th shot assists / 18th HD passes (process). "Not much of
# a passer" must grade on the process metrics - the scout was right.


def test_passer_claim_on_micro_grades_on_chance_assists():
    v = _one(ForwardMicroCard(**_load("cuylle_micro.json")), "passer", "low")
    assert v.grade == "supported"
    assert v.metric == "chance_assists"
    assert v.value == 36


def test_playmaker_claim_on_elite_micro_still_supported():
    v = _one(ForwardMicroCard(**_load("celebrini_micro.json")), "playmaker")
    assert v.grade == "supported"
    assert v.metric == "chance_assists"
    assert v.value == 98


# --- The shutdown-D positive case (Slavin round) -----------------------------
# The elite-shutdown archetype exposed four positive-direction gaps: no shape
# for line-dominant rush defense, no breakout-style read, a corroboration rule
# blind to blue-line evidence, and noise divergences on a D's excluded
# finishing. All four fixed; Slavin's golden fixtures pin them.


def _slavin_cards():
    from engine.assess import assess_player
    from schemas import DefenseCard, DefenseMicroCard

    std = DefenseCard(**_load("slavin.json"))
    micro = DefenseMicroCard(**_load("slavin_micro.json"))
    return assess_player(std, micro_card=micro), assess_player(micro)


def test_line_dominant_rush_defense_shape():
    _, m = _slavin_cards()
    profiles = {p.family: p for p in m.profiles}
    assert profiles["rush_defense"].shape == "line_dominant"
    # The note explains why ordinary chance prevention isn't a contradiction.
    assert "never" in profiles["rush_defense"].note.lower()


def test_breakout_style_safe_and_effective():
    _, m = _slavin_cards()
    profiles = {p.family: p for p in m.profiles}
    assert profiles["breakout_style"].shape == "safe_and_effective"
    values = {r.metric: r.percentile for r in profiles["breakout_style"].reads}
    assert values["exit_success_rate"] == 94
    assert values["exit_possession_rate"] == 21


def test_breakout_style_ambitious_pole():
    from engine.assess import assess_player
    from schemas import DefenseMicroCard

    data = _load("slavin_micro.json")
    data.update(name="Synthetic Rover", exit_possession_rate=74, exit_success_rate=19)
    m = assess_player(DefenseMicroCard(**data))
    profiles = {p.family: p for p in m.profiles}
    assert profiles["breakout_style"].shape == "ambitious_and_costly"


def test_synthesis_corroborates_at_the_blue_line():
    combined, _ = _slavin_cards()
    joined = " ".join(combined.micro_insights.insights).lower()
    assert "blue line" in joined
    assert "96" in joined  # entry denials cited


def test_no_finishing_divergence_for_a_defenseman():
    # Slavin's finishing ran 48 -> 16, a >=15 gap - but it's excluded from a
    # D's value on both cards, so flagging it is noise, not a value story.
    combined, _ = _slavin_cards()
    assert all("finishing" not in d.lower() for d in combined.micro_insights.divergences)


def test_schaefer_rush_defense_still_lockdown():
    # Regression: the new line_dominant branch must not steal lockdown cases.
    from engine.assess import assess_player
    from schemas import DefenseMicroCard

    m = assess_player(DefenseMicroCard(**_load("schaefer_micro.json")))
    profiles = {p.family: p for p in m.profiles}
    assert profiles["rush_defense"].shape == "lockdown"


# --- Missing-metric messages tell the truth about the other card -------------


def test_turnover_claim_on_forward_is_untracked_anywhere():
    v = _one(ForwardMicroCard(**_load("celebrini_micro.json")), "turnover-prone", "low")
    assert v.grade == "unverifiable"
    reason = v.reason.lower()
    assert "standard card" not in reason  # must not point at a card that lacks it
    assert "either card" in reason or "not tracked" in reason


def test_overall_claim_on_micro_still_points_at_standard_card():
    # Regression: proj_war_pct genuinely IS on the standard card - keep saying so.
    v = _one(ForwardMicroCard(**_load("celebrini_micro.json")), "overall_skater")
    assert v.grade == "unverifiable"
    assert "standard card" in v.reason.lower()


def test_micro_only_metric_on_standard_card_points_at_micro_card():
    # "Defends the rush" against a standard skater card: the rush-defense trio
    # really does live on the (defense) micro card.
    v = _one(SkaterCard(**_load("celebrini.json")), "rush player")
    assert v.grade == "unverifiable"
    assert "microstat" in v.reason.lower()


def test_goalie_missing_metric_gets_generic_honesty():
    # A skater-only metric asked of a goalie card must not claim any other
    # card carries it - goalies have no counterpart card type.
    v = _one(GoalieCard(**_load("thompson.json")), "sheltered")
    assert v.grade == "unverifiable"
    assert "microstat card carries" not in v.reason.lower()
    assert "standard card carries" not in v.reason.lower()
