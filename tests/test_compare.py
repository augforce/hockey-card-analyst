"""Tests for compare_players on skaters (PLAN sections 5, 6).

The headline discipline (carried over from adjudicate's half-right read): when
components genuinely split, compare must NOT crown a single winner. Three cases:
a clear winner, a genuine split, and a cross-position pair that trips the
position-compatibility guard.
"""
import json
from pathlib import Path

import pytest

from config import load_config
from engine.compare import Comparison, compare_players
from schemas import DefenseCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _skater(name):
    return SkaterCard(**json.loads((FIXTURES / name).read_text()))


def _defense(name):
    return DefenseCard(**json.loads((FIXTURES / name).read_text()))


def _components(cmp):
    return {c.metric: c for c in cmp.components}


# --- Clear winner ----------------------------------------------------------


def test_clear_winner_is_crowned():
    cmp = compare_players(
        _skater("compare_clear_leader.json"), _skater("compare_clear_trailer.json")
    )
    assert isinstance(cmp, Comparison)
    assert cmp.compatible is True
    assert cmp.pool == "forward"
    assert cmp.overall_edge == "A"
    assert cmp.edge_kind in ("broad", "proj_war")


def test_components_carry_both_values_and_gap():
    cmp = compare_players(
        _skater("compare_clear_leader.json"), _skater("compare_clear_trailer.json")
    )
    evo = _components(cmp)["ev_offense"]
    assert evo.a_value == 90
    assert evo.b_value == 55
    assert evo.gap == 35
    assert evo.leader == "A"


# --- Genuine split (the case to read) --------------------------------------


def test_genuine_split_refuses_to_crown_a_winner():
    cmp = compare_players(
        _skater("compare_split_sniper.json"), _skater("compare_split_shutdown.json")
    )
    assert cmp.compatible is True
    assert cmp.overall_edge is None          # no single winner
    assert cmp.edge_kind == "split"
    # Names the tradeoff rather than papering it over.
    assert "offense" in cmp.overall.lower()
    assert "defense" in cmp.overall.lower()


# --- Cross-position compatibility guard ------------------------------------


def test_cross_position_is_refused_not_crowned():
    cmp = compare_players(_skater("celebrini.json"), _defense("synthetic_dman.json"))
    assert cmp.compatible is False
    assert cmp.overall_edge is None
    assert cmp.edge_kind == "incompatible"
    assert cmp.reason
    assert "position" in cmp.reason.lower() or "pool" in cmp.reason.lower()
    assert load_config()["caveats"]["within_position_only"] in cmp.caveats


def test_cross_position_does_not_compare_components():
    cmp = compare_players(_skater("celebrini.json"), _defense("synthetic_dman.json"))
    assert cmp.components == []


# --- Durability flag -------------------------------------------------------


def test_finishing_driven_edge_is_flagged_less_durable():
    a = SkaterCard(
        name="Finisher A (synthetic)", team="TEST", position="C", age=25,
        ev_offense=70, ev_defense=60, pp=60, pk=55, finishing=95, penalties=60,
        proj_war_pct=80, goals=90, first_assists=65,
    )
    b = SkaterCard(
        name="Driver B (synthetic)", team="TEST", position="C", age=26,
        ev_offense=68, ev_defense=60, pp=60, pk=55, finishing=45, penalties=60,
        proj_war_pct=60, goals=50, first_assists=60,
    )
    cmp = compare_players(a, b)
    assert cmp.overall_edge == "A"
    assert cmp.durability is not None
    assert "less durable" in cmp.durability.lower()
    assert load_config()["caveats"]["finishing_volatility"] in cmp.caveats


# --- focus -----------------------------------------------------------------


def test_focus_defense_can_pick_a_winner_within_an_area_even_on_a_split():
    # Overall the split pair refuses a winner; focused on defense, B leads.
    cmp = compare_players(
        _skater("compare_split_sniper.json"),
        _skater("compare_split_shutdown.json"),
        focus="defense",
    )
    assert cmp.focus == "defense"
    assert cmp.overall_edge == "B"
    assert set(_components(cmp)) <= {"ev_defense", "pk"}
