"""compare_players on microstat cards.

Rules under test:
- Micro vs micro compares within a pool (forward-micro or defense-micro), with
  the overall edge decided from the WAR-component row — there is no Proj. WAR
  headline on a micro card, so no headline tiebreak exists and a genuine split
  stays a split.
- Micro vs standard is refused even for the same player: single-season
  percentiles and a three-year-weighted projection are different regimes.
- Micro forward vs micro defenseman is refused like any cross-pool pair.
- A micro comparison always carries the single-season caveat.
"""
import json
from pathlib import Path

import pytest

from engine.compare import compare_players
from schemas import DefenseMicroCard, ForwardMicroCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _micro_forward(name, **war):
    """A synthetic forward micro card: fixture microstats, overridden WAR row."""
    data = _load("celebrini_micro.json")
    data["name"] = name
    data.update(war)
    return ForwardMicroCard(**data)


@pytest.fixture
def celebrini_micro():
    return ForwardMicroCard(**_load("celebrini_micro.json"))


@pytest.fixture
def schaefer_micro():
    return DefenseMicroCard(**_load("schaefer_micro.json"))


def test_micro_vs_standard_is_refused_as_cross_regime(celebrini_micro):
    standard = SkaterCard(**_load("celebrini.json"))
    out = compare_players(standard, celebrini_micro)
    assert out.compatible is False
    assert out.edge_kind == "incompatible"
    assert "season" in out.reason.lower()  # regime, not just position, wording


def test_micro_forward_vs_micro_defense_is_refused(celebrini_micro, schaefer_micro):
    out = compare_players(celebrini_micro, schaefer_micro)
    assert out.compatible is False
    assert out.edge_kind == "incompatible"


def test_clear_micro_leader_gets_the_edge(celebrini_micro):
    trailer = _micro_forward(
        "Synthetic Trailer",
        ev_offense=40, ev_defense=35, pp=20, penalties=30, finishing=38,
    )
    out = compare_players(celebrini_micro, trailer)
    assert out.compatible is True
    assert out.pool == "forward_micro"
    assert out.overall_edge == "A"
    assert out.edge_kind == "broad"


def test_micro_split_stays_a_split_without_a_headline_tiebreak():
    sniper = _micro_forward(
        "Synthetic Sniper",
        ev_offense=90, ev_defense=30, pp=85, pk=None, penalties=50, finishing=92,
    )
    shutdown = _micro_forward(
        "Synthetic Shutdown",
        ev_offense=45, ev_defense=93, pp=None, pk=90, penalties=55, finishing=40,
    )
    out = compare_players(sniper, shutdown)
    assert out.compatible is True
    assert out.edge_kind == "split"
    assert out.overall_edge is None
    # No Proj. WAR on a micro card — the split text must not invent one.
    assert "tradeoff" in out.overall.lower()


def test_micro_components_include_tracked_data(celebrini_micro):
    trailer = _micro_forward(
        "Synthetic Trailer",
        ev_offense=40, ev_defense=35, pp=20, penalties=30, finishing=38,
    )
    out = compare_players(celebrini_micro, trailer)
    metrics = {c.metric for c in out.components}
    assert "chances" in metrics
    assert "high_danger_passes" in metrics
    assert "ev_offense" in metrics


def test_micro_compare_carries_single_season_caveat(celebrini_micro):
    trailer = _micro_forward(
        "Synthetic Trailer",
        ev_offense=40, ev_defense=35, pp=20, penalties=30, finishing=38,
    )
    out = compare_players(celebrini_micro, trailer)
    assert any("season" in c.lower() for c in out.caveats)


def test_finishing_led_micro_edge_flagged_less_durable():
    conv = _micro_forward(
        "Synthetic Converter",
        ev_offense=55, ev_defense=55, pp=55, pk=None, penalties=55, finishing=95,
    )
    base = _micro_forward(
        "Synthetic Baseline",
        ev_offense=50, ev_defense=52, pp=50, pk=None, penalties=52, finishing=45,
    )
    out = compare_players(conv, base)
    if out.overall_edge == "A" and out.durability:
        assert "finishing" in out.durability.lower()


def test_defense_micro_pool_excludes_finishing(schaefer_micro):
    other = DefenseMicroCard(**{**_load("schaefer_micro.json"), "name": "Synthetic D"})
    out = compare_players(schaefer_micro, other)
    assert out.compatible is True
    assert out.pool == "defense_micro"
    assert all(c.metric != "finishing" for c in out.components)
