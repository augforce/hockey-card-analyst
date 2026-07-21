"""NHL Edge vetting on assess_player: articulation-only cross-checks of the
card's verdicts against nhl.com/nhl-edge tracking.

Validation is internal consistency against the seven real 2025-26 Edge pages
(no scouting-prose calibration source exists for Edge): the Vanecek/Markstrom
workload finding (identical .883 rates, opposite count percentiles) and the
Makar/Miller tools finding (near-identical tools, opposite offensive value)
must both read honestly. Standard-card partners for the Edge fixtures are
synthetic inline cards except Hughes, the real+real golden pair.
"""
import json
from pathlib import Path

import pytest

from engine.assess import assess_player
from schemas import (
    DefenseCard,
    DefenseMicroCard,
    ForwardMicroCard,
    GoalieCard,
    GoalieEdgeCard,
    SkaterCard,
    SkaterEdgeCard,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _goalie(name: str, **over) -> GoalieCard:
    """Synthetic standard goalie card to partner a real Edge fixture."""
    base = dict(
        name=name, age=30, role="Starter", proj_war_pct=70, even_strength=70,
        penalty_kill=60, high_danger=70, med_danger=60, low_danger=60,
        quality_starts=70, excellent_starts=60, bad_starts=60,
        rebound_control=55, consistency=55,
    )
    base.update(over)
    return GoalieCard(**base)


def _dman(name: str, **over) -> DefenseCard:
    """Synthetic standard defenseman card to partner a real Edge fixture."""
    base = dict(
        name=name, position="D", age=27, ev_offense=55, ev_defense=55,
        pp=None, pk=55, finishing=40, penalties=55, proj_war_pct=60,
    )
    base.update(over)
    return DefenseCard(**base)


def _celebrini_edge(**over) -> dict:
    """Synthetic skater Edge dict for Celebrini (no real page sampled)."""
    m = lambda v, avg=None, pct=None: {"value": v, "avg": avg, "percentile": pct}
    base = dict(
        card_kind="edge", name="Macklin Celebrini", season="2025-26",
        position="F", gp=70,
        hardest_shot=m(88.0, None, 70), max_skating_speed=m(22.8, None, 80),
        most_miles_per_game=m(4.1, None, 90),
        sog_all=m(200, 86, 95), sog_high_danger=m(60, 32, 90),
        sog_mid_range=m(80, 27, 92), sog_long_range=m(12, 8, 70),
        zone_time_defensive=m(37.0, 40.1, 90), zone_time_neutral=m(17.0, 16.8, None),
        zone_time_offensive=m(46.0, 43.1, 90),
    )
    base.update(over)
    return base


# --- Wiring and guards ------------------------------------------------------


def test_no_edge_card_means_no_edge_vetting():
    a = assess_player(SkaterCard(**_load("hughes.json")))
    assert a.edge_vetting is None


def test_edge_vetting_never_moves_the_verdict():
    card = SkaterCard(**_load("hughes.json"))
    edge = SkaterEdgeCard(**_load("hughes_edge.json"))
    plain = assess_player(card).model_dump(exclude={"edge_vetting"})
    vetted = assess_player(card, edge_card=edge).model_dump(exclude={"edge_vetting"})
    assert plain == vetted


def test_name_mismatch_is_refused():
    card = SkaterCard(**_load("hughes.json"))
    edge = SkaterEdgeCard(**_load("cotter_edge.json"))
    with pytest.raises(ValueError, match="different players"):
        assess_player(card, edge_card=edge)


def test_goalie_card_with_skater_edge_is_refused():
    card = _goalie("Jack Hughes")
    edge = SkaterEdgeCard(**_load("hughes_edge.json"))
    with pytest.raises(ValueError, match="[Ee]dge"):
        assess_player(card, edge_card=edge)


def test_skater_card_with_goalie_edge_is_refused():
    card = SkaterCard(**_load("hughes.json"))
    edge = GoalieEdgeCard(**{**_load("wedgewood_edge.json"), "name": "Jack Hughes"})
    with pytest.raises(ValueError, match="[Ee]dge"):
        assess_player(card, edge_card=edge)


def test_position_pool_mismatch_is_refused():
    # A forward's card with a defenseman's Edge page: different baselines.
    card = SkaterCard(**{**_load("hughes.json"), "name": "Cale Makar"})
    edge = SkaterEdgeCard(**_load("makar_edge.json"))
    with pytest.raises(ValueError, match="position"):
        assess_player(card, edge_card=edge)


def test_base_caveats_always_attach():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["edge_single_season"] in a.edge_vetting.caveats
    assert cfg_cavs["edge_different_source"] in a.edge_vetting.caveats
    assert a.edge_vetting.season == "2025-26"


# --- Goalies: rates drive calls, counts never do ----------------------------


def test_wedgewood_strong_verdicts_are_corroborated():
    a = assess_player(
        _goalie("Scott Wedgewood", proj_war_pct=88, high_danger=85, quality_starts=90),
        edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json")),
    )
    joined = " ".join(a.edge_vetting.corroborations)
    assert ".837" in joined and ".811" in joined   # HD save% gap, both numbers cited
    assert ".921" in joined and ".896" in joined   # all-locations gap
    assert "74.4" in joined                        # starts over .900 (99th, exact pct)
    assert a.edge_vetting.contradictions == []


def test_markstrom_weak_hd_verdict_is_corroborated_by_the_gap():
    # .793 vs .811 clears the threshold even though the page shows only
    # "<50th" - the raw-vs-average rule recovers the sub-50 signal honestly.
    a = assess_player(
        _goalie("Jacob Markstrom", proj_war_pct=40, high_danger=30, quality_starts=35),
        edge_card=GoalieEdgeCard(**_load("markstrom_edge.json")),
    )
    joined = " ".join(a.edge_vetting.corroborations)
    assert ".793" in joined and ".811" in joined


def test_markstrom_strong_hd_verdict_is_contradicted():
    a = assess_player(
        _goalie("Jacob Markstrom", high_danger=80),
        edge_card=GoalieEdgeCard(**_load("markstrom_edge.json")),
    )
    joined = " ".join(a.edge_vetting.contradictions)
    assert ".793" in joined and ".811" in joined


def test_vanecek_false_99th_never_becomes_a_corroboration():
    # Vanecek's goals-against counts read 99th percentile ONLY because his
    # workload was tiny (22 GP). The load-bearing internal-consistency test:
    # that number must never surface as a corroboration of anything.
    a = assess_player(
        _goalie("Vitek Vanecek", proj_war_pct=30, high_danger=40, quality_starts=30),
        edge_card=GoalieEdgeCard(**_load("vanecek_edge.json")),
    )
    calls = " ".join(a.edge_vetting.corroborations + a.edge_vetting.contradictions)
    assert "99th" not in calls
    assert "goals against" not in calls.lower()
    # His rate gaps are all inside the noise threshold, so nothing fires.
    assert a.edge_vetting.corroborations == []
    assert a.edge_vetting.contradictions == []
    # Workload rides in descriptive with games played named, plus the caveat.
    desc = " ".join(a.edge_vetting.descriptive)
    assert "22 games" in desc
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["edge_counts_workload"] in a.edge_vetting.caveats


def test_identical_rates_read_the_same_through_the_rate_lens():
    # Vanecek and Markstrom post the same .883: neither gets an all-locations
    # call (the gap to .896 is inside the threshold) despite count percentiles
    # sitting at opposite extremes.
    for name, fixture in [
        ("Vitek Vanecek", "vanecek_edge.json"),
        ("Jacob Markstrom", "markstrom_edge.json"),
    ]:
        a = assess_player(
            _goalie(name, proj_war_pct=30, high_danger=60, quality_starts=60),
            edge_card=GoalieEdgeCard(**_load(fixture)),
        )
        calls = " ".join(a.edge_vetting.corroborations + a.edge_vetting.contradictions)
        assert ".883" not in calls


def test_count_percentiles_are_never_cited():
    # Wedgewood's counts carry real percentiles (56th saves, 76th goals
    # against, 54th shots against) - none may appear anywhere in the vetting.
    a = assess_player(
        _goalie("Scott Wedgewood", proj_war_pct=88, high_danger=85, quality_starts=90),
        edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json")),
    )
    v = a.edge_vetting
    everything = " ".join(v.corroborations + v.contradictions + v.descriptive)
    for pct in ["54th", "56th", "58th", "61st", "63rd", "76th"]:
        assert pct not in everything, pct


# --- Skaters: zone time vets, tools and counts stay descriptive -------------


def test_hughes_golden_pair_offense_corroborated_defense_contradicted():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    v = a.edge_vetting
    # EV offense 98 (strength) + offensive-zone tilt 45.1% vs 43.1% avg.
    corr = " ".join(v.corroborations)
    assert "45.1" in corr and "43.1" in corr
    # EV defense 34 (weakness) yet LESS defensive-zone time than average
    # (36.3% vs 40.1%) - an honest tension, surfaced as a contradiction.
    cont = " ".join(v.contradictions)
    assert "36.3" in cont and "40.1" in cont


def test_zone_time_calls_carry_the_deployment_caveat():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["deployment_not_value"] in a.edge_vetting.caveats


def test_goalie_vetting_never_carries_the_deployment_caveat():
    a = assess_player(
        _goalie("Scott Wedgewood", proj_war_pct=88, high_danger=85),
        edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json")),
    )
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["deployment_not_value"] not in a.edge_vetting.caveats


def test_tools_are_descriptive_only_with_their_caveat():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    v = a.edge_vetting
    desc = " ".join(v.descriptive)
    assert "22.49" in desc          # max skating speed rides in descriptive
    assert "4.60" in desc           # miles skated too
    calls = " ".join(v.corroborations + v.contradictions)
    assert "22.49" not in calls and "4.60" not in calls
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["edge_tools_not_value"] in v.caveats


def test_sub_50_tools_read_as_below_the_league_median():
    # Cotter's miles/game shows "<50th" and no average - direction only,
    # never a magnitude, never an invented number.
    card = SkaterCard(**{**_load("hughes.json"), "name": "Paul Cotter"})
    a = assess_player(card, edge_card=SkaterEdgeCard(**_load("cotter_edge.json")))
    desc = " ".join(a.edge_vetting.descriptive)
    assert "below the league median" in desc


def test_miller_tools_never_generate_an_offense_call():
    # Miller's tools read nearly identical to Makar's; his offense doesn't.
    # With an ordinary EV offense (55), NOTHING may fire an offense call -
    # not the 96th-percentile speed, not the offense-tilted zone time.
    a = assess_player(
        _dman("K'Andre Miller", ev_offense=55, ev_defense=75),
        edge_card=SkaterEdgeCard(**_load("miller_edge.json")),
    )
    v = a.edge_vetting
    calls = " ".join(v.corroborations + v.contradictions)
    assert "23.22" not in calls           # speed never enters a call
    assert "offens" not in calls.lower() or "46.4" not in calls
    # His EV-defense strength IS corroborated territorially (35.0% vs 40.9%).
    corr = " ".join(v.corroborations)
    assert "35.0" in corr and "40.9" in corr


def test_makar_strong_offense_is_corroborated():
    a = assess_player(
        _dman("Cale Makar", ev_offense=97, ev_defense=80, proj_war_pct=99),
        edge_card=SkaterEdgeCard(**_load("makar_edge.json")),
    )
    corr = " ".join(a.edge_vetting.corroborations)
    assert "45.3" in corr and "42.3" in corr


def test_skater_counts_stay_descriptive_with_games_played():
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    v = a.edge_vetting
    desc = " ".join(v.descriptive)
    assert "228" in desc and "61 games" in desc
    assert "228" not in " ".join(v.corroborations + v.contradictions)
    cfg_cavs = __import__("config").load_config()["caveats"]
    assert cfg_cavs["edge_counts_workload"] in v.caveats


# --- Micro primary and the three-source stack -------------------------------


def test_micro_primary_gains_edge_vetting():
    micro = ForwardMicroCard(**_load("celebrini_micro.json"))
    a = assess_player(micro, edge_card=SkaterEdgeCard(**_celebrini_edge()))
    v = a.edge_vetting
    assert v is not None
    # Micro WAR-row EV offense (89, strength) + offensive tilt 46.0 vs 43.1.
    corr = " ".join(v.corroborations)
    assert "46.0" in corr


def test_micro_skating_speed_is_flagged_as_same_source():
    # The micro card's Skating Speed box is itself NHL Edge data - the Edge
    # speed numbers must not be presented as independent corroboration.
    micro = ForwardMicroCard(**_load("celebrini_micro.json"))
    a = assess_player(micro, edge_card=SkaterEdgeCard(**_celebrini_edge()))
    desc = " ".join(a.edge_vetting.descriptive)
    assert "same source" in desc.lower()


def test_all_three_sources_stack():
    card = SkaterCard(**_load("celebrini.json"))
    micro = ForwardMicroCard(**_load("celebrini_micro.json"))
    a = assess_player(card, micro_card=micro, edge_card=SkaterEdgeCard(**_celebrini_edge()))
    assert a.micro_insights is not None
    assert a.edge_vetting is not None


def test_goalie_edge_vetting_rides_on_goalie_assessment():
    a = assess_player(
        _goalie("Scott Wedgewood", proj_war_pct=88, high_danger=85),
        edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json")),
    )
    # Goalie assessment shape is otherwise untouched.
    assert a.danger_profile is not None
    assert a.edge_vetting.note != ""
