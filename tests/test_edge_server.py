"""Server wiring for edge_card on assess_player: parse-by-primary-pool, loud
refusals, and the docstring's extraction contract (description-guarded like the
other load-bearing host steering)."""
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

import server

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _wedgewood_goalie_card() -> dict:
    return dict(
        name="Scott Wedgewood", age=33, role="Starter", proj_war_pct=85,
        even_strength=80, penalty_kill=60, high_danger=82, med_danger=70,
        low_danger=65, quality_starts=88, excellent_starts=70, bad_starts=75,
        rebound_control=60, consistency=55,
    )


def test_assess_player_accepts_edge_card():
    out = server.assess_player(_load("hughes.json"), edge_card=_load("hughes_edge.json"))
    assert out["edge_vetting"] is not None
    assert out["edge_vetting"]["season"] == "2025-26"


def test_goalie_edge_card_parses_against_the_goalie_schema():
    out = server.assess_player(_wedgewood_goalie_card(), edge_card=_load("wedgewood_edge.json"))
    assert out["edge_vetting"]["corroborations"]


def test_edge_card_as_primary_is_refused():
    # Edge data is never assessed on its own - it only rides alongside a card.
    with pytest.raises(ToolError, match="on its own"):
        server.assess_player(_load("hughes_edge.json"))


def test_wrong_edge_schema_fails_loudly():
    # A skater primary selects the skater Edge schema; a goalie page fails
    # validation loudly instead of half-parsing.
    with pytest.raises(ToolError, match="edge_card"):
        server.assess_player(_load("hughes.json"), edge_card=_load("wedgewood_edge.json"))


def test_invalid_edge_card_names_the_problem():
    bad = _load("hughes_edge.json")
    bad["sog_all"] = {"value": 228, "percentile": 43}  # fabricated sub-50
    with pytest.raises(ToolError, match="edge_card"):
        server.assess_player(_load("hughes.json"), edge_card=bad)


def test_name_mismatch_surfaces_as_tool_error():
    with pytest.raises(ToolError, match="different players"):
        server.assess_player(_load("hughes.json"), edge_card=_load("cotter_edge.json"))


def test_micro_primary_takes_an_edge_card():
    micro = _load("celebrini_micro.json")
    edge = _load("hughes_edge.json")
    edge["name"] = "Macklin Celebrini"
    out = server.assess_player(micro, edge_card=edge)
    assert out["edge_vetting"] is not None


# --- The docstring carries the extraction contract --------------------------


def test_description_documents_the_edge_extraction():
    doc = server.assess_player.__doc__
    assert "edge_card" in doc
    assert "nhl" in doc.lower() and "edge" in doc.lower()
    # The "<50th" rule: null percentile, never an invented number.
    assert "<50th" in doc
    assert "null" in doc
    # Legend tables only - the zone-map cell counts do not reconcile.
    assert "legend" in doc.lower()
    assert "zone map" in doc.lower() or "shot map" in doc.lower()
    # Supplemental only, articulation only.
    assert "never" in doc


def test_description_keeps_edge_secondary():
    doc = server.assess_player.__doc__.lower()
    assert "on its own" in doc or "never the primary" in doc
