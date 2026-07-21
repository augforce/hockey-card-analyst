"""NHL Edge config: the vetting thresholds, the new caveats, the generalized
deployment caveat, and the glossary entries for the Edge page's terms."""
from config import load_config
from engine.glossary import explain_metric


# --- edge_rules: the signal-hierarchy thresholds ----------------------------


def test_edge_rules_exist_with_tunable_thresholds():
    rules = load_config()["edge_rules"]
    assert rules["save_pct_gap"] > 0
    assert rules["zone_time_gap"] > 0
    assert "articulation only" in rules["note"].lower()


def test_save_pct_gap_separates_the_real_sample_gaps():
    # Wedgewood's high-danger gap (+.026) and Markstrom's (-.018) are signal;
    # every long-range gap in the sample (<= .007) is noise. The threshold must
    # split them.
    gap = load_config()["edge_rules"]["save_pct_gap"]
    assert abs(0.837 - 0.811) >= gap    # Wedgewood HD fires
    assert abs(0.793 - 0.811) >= gap    # Markstrom HD fires
    assert abs(0.975 - 0.968) < gap     # Wedgewood long-range stays quiet
    assert abs(0.883 - 0.896) < gap     # the .883 twins' all-locations gap stays quiet


def test_zone_time_gap_separates_the_real_sample_gaps():
    gap = load_config()["edge_rules"]["zone_time_gap"]
    assert (45.1 - 43.1) >= gap         # Hughes offensive tilt fires
    assert (46.4 - 42.3) >= gap         # Miller offensive tilt fires
    assert abs(17.5 - 16.8) < gap       # Makar neutral-zone sliver stays quiet


# --- The four Edge caveats --------------------------------------------------


def test_edge_counts_workload_caveat_carries_the_vanecek_finding():
    cav = load_config()["caveats"]["edge_counts_workload"]
    assert "games played" in cav.lower()
    assert "count" in cav.lower()
    # The rule itself: a count never drives a verdict on its own.
    assert "never" in cav.lower()


def test_edge_tools_not_value_caveat_is_about_tools_only():
    cav = load_config()["caveats"]["edge_tools_not_value"].lower()
    assert "shot" in cav and "speed" in cav
    assert "offensive" in cav
    # It must NOT absorb the zone-time/deployment point - that one is
    # deployment_not_value's job (kept separate so neither dilutes).
    assert "zone time" not in cav
    assert "zone-time" not in cav


def test_edge_single_season_and_different_source_caveats_exist():
    cavs = load_config()["caveats"]
    assert "season" in cavs["edge_single_season"].lower()
    src = cavs["edge_different_source"].lower()
    assert "nhl" in src
    assert "<50th" in src
    assert "distance" in src   # Edge zones are distance-based, not xG danger


def test_deployment_caveat_generalizes_to_territorial_reads():
    # Zone-time vetting reuses deployment_not_value (one caveat, one place);
    # its canonical wording covers territorial share alongside comp/teammates.
    cav = load_config()["caveats"]["deployment_not_value"].lower()
    assert "zone-time" in cav or "zone time" in cav
    # The RAPM-round content survives the generalization.
    assert "zone starts" in cav and "score" in cav and "back-to-back" in cav


# --- Glossary: the Edge page's terms resolve through explain_metric ---------


def test_edge_save_pct_fields_resolve_to_one_entry():
    hd = explain_metric("save_pct_high_danger")
    assert hd.found
    assert "29" in hd.definition          # the distance bound defines the zone
    assert explain_metric("save_pct_all").metric == hd.metric


def test_edge_counts_share_the_workload_caveat():
    out = explain_metric("shots_against")
    assert out.found
    assert out.caveat == load_config()["caveats"]["edge_counts_workload"]
    assert explain_metric("goals_against").caveat == out.caveat
    assert explain_metric("sog_all").caveat == out.caveat


def test_pct_starts_over_900_is_defined():
    out = explain_metric("pct_starts_over_900")
    assert out.found
    assert ".900" in out.definition


def test_tools_share_the_tools_caveat():
    tools_cav = load_config()["caveats"]["edge_tools_not_value"]
    assert explain_metric("hardest_shot").caveat == tools_cav
    assert explain_metric("max_skating_speed").caveat == tools_cav
    assert explain_metric("most_miles_per_game").caveat == tools_cav


def test_zone_time_reuses_the_deployment_caveat():
    out = explain_metric("zone_time_offensive")
    assert out.found
    assert out.caveat == load_config()["caveats"]["deployment_not_value"]


def test_documented_but_unsampled_terms_are_defined():
    # These NHL Edge boxes are documented but not yet seen on a sampled page,
    # so they get glossary entries only - no schema field this round.
    for term in ["avg_shot_speed", "zone_starts", "skating_speed_bursts"]:
        assert explain_metric(term).found, term


def test_micro_skating_speed_still_resolves_to_the_micro_entry():
    # The new Edge aliases must not shadow the micro card's skating_speed box.
    assert explain_metric("skating_speed").metric == "skating_speed"
