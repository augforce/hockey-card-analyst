"""NHL Edge card schemas: strict validation, the "<50th" rule, and the seven
real-data fixtures (2025-26 regular season, hand-transcribed from nhl.com/nhl-edge).
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas import EdgeMetric, GoalieEdgeCard, SkaterEdgeCard

FIXTURES = Path(__file__).parent / "fixtures"

GOALIE_EDGE_FIXTURES = ["wedgewood_edge.json", "vanecek_edge.json", "markstrom_edge.json"]
SKATER_EDGE_FIXTURES = [
    "hughes_edge.json", "cotter_edge.json", "makar_edge.json", "miller_edge.json",
]


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# --- EdgeMetric: the one legend-table entry shape ---------------------------


def test_edge_metric_holds_value_avg_and_percentile():
    m = EdgeMetric(value=0.837, avg=0.811, percentile=81)
    assert m.value == 0.837
    assert m.avg == 0.811
    assert m.percentile == 81


def test_edge_metric_percentile_none_means_below_50th():
    # NHL Edge never prints an exact number below the 50th percentile - the
    # page shows only "<50th". None IS that bucket; nothing is ever invented.
    m = EdgeMetric(value=0.793, avg=0.811)
    assert m.percentile is None


def test_edge_metric_rejects_a_fabricated_sub_50_percentile():
    with pytest.raises(ValidationError):
        EdgeMetric(value=0.793, avg=0.811, percentile=43)


def test_edge_metric_rejects_percentile_above_100():
    with pytest.raises(ValidationError):
        EdgeMetric(value=0.9, percentile=101)


def test_edge_metric_avg_is_optional():
    # Tools rows (hardest shot, skating speed) print no comparison average.
    m = EdgeMetric(value=98.21, percentile=91)
    assert m.avg is None


def test_edge_metric_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EdgeMetric(value=0.9, median=0.8)


# --- Goalie Edge card -------------------------------------------------------


@pytest.mark.parametrize("name", GOALIE_EDGE_FIXTURES)
def test_goalie_edge_fixtures_validate(name):
    card = GoalieEdgeCard(**_load(name))
    assert card.card_kind == "edge"
    assert card.season == "2025-26"


def test_wedgewood_numbers_survive_roundtrip():
    card = GoalieEdgeCard(**_load("wedgewood_edge.json"))
    assert card.gp == 45
    assert card.save_pct_high_danger.value == 0.837
    assert card.save_pct_high_danger.avg == 0.811
    assert card.save_pct_high_danger.percentile == 81
    assert card.pct_starts_over_900.value == 74.4
    assert card.saves_mid_range.percentile is None  # the "<50th" bucket


def test_goalie_edge_requires_gp():
    data = _load("wedgewood_edge.json")
    del data["gp"]
    with pytest.raises(ValidationError):
        GoalieEdgeCard(**data)


def test_goalie_edge_requires_season():
    data = _load("wedgewood_edge.json")
    del data["season"]
    with pytest.raises(ValidationError):
        GoalieEdgeCard(**data)


def test_goalie_edge_requires_the_edge_discriminator():
    data = _load("wedgewood_edge.json")
    data["card_kind"] = "micro"
    with pytest.raises(ValidationError):
        GoalieEdgeCard(**data)


def test_goalie_edge_rejects_unknown_fields():
    data = _load("wedgewood_edge.json")
    data["five_v_five_save_pct"] = {"value": 0.9}
    with pytest.raises(ValidationError):
        GoalieEdgeCard(**data)


# --- Skater Edge card -------------------------------------------------------


@pytest.mark.parametrize("name", SKATER_EDGE_FIXTURES)
def test_skater_edge_fixtures_validate(name):
    card = SkaterEdgeCard(**_load(name))
    assert card.card_kind == "edge"


def test_skater_edge_requires_position():
    # The shots-on-goal baseline is "Avg. by Position (F/D)" - the pool must be
    # stated, never defaulted.
    data = _load("hughes_edge.json")
    del data["position"]
    with pytest.raises(ValidationError):
        SkaterEdgeCard(**data)


def test_skater_edge_rejects_a_goalie_position():
    data = _load("hughes_edge.json")
    data["position"] = "G"
    with pytest.raises(ValidationError):
        SkaterEdgeCard(**data)


def test_miller_numbers_survive_roundtrip():
    card = SkaterEdgeCard(**_load("miller_edge.json"))
    assert card.position == "D"
    assert card.gp == 72
    assert card.max_skating_speed.value == 23.22
    assert card.max_skating_speed.percentile == 96
    assert card.zone_time_offensive.value == 46.4
    assert card.zone_time_offensive.avg == 42.3


def test_cotter_sub_50_buckets_load_as_none():
    card = SkaterEdgeCard(**_load("cotter_edge.json"))
    assert card.most_miles_per_game.percentile is None
    assert card.sog_all.percentile is None
    assert card.zone_time_offensive.percentile is None
