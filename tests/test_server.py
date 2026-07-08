"""Smoke tests for the fastmcp wiring (Phase 6).

No new behavior — these confirm the three tools are registered, that each is a
thin pass-through to the engine returning structured data, that goalie/skater
dispatch works, and that a bad card fails loudly with a ToolError rather than a
wrong answer.
"""
import asyncio
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

import server

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_all_tools_are_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"assess_player", "adjudicate_claim", "compare_players", "explain_metric"} <= names


def test_assess_player_returns_structured_skater():
    out = server.assess_player(_load("celebrini.json"))
    assert out["overall_tier"] == "Excellent"
    assert "strengths" in out and "caveats" in out


def test_assess_player_dispatches_to_goalie():
    out = server.assess_player(_load("thompson.json"))
    assert out["overall_tier"] == "Elite"
    assert "danger_profile" in out  # goalie-only shape


def test_adjudicate_claim_passes_through():
    out = server.adjudicate_claim(
        _load("celebrini.json"), [{"dimension": "finishing", "direction": "high"}]
    )
    assert out["verdicts"][0]["grade"] == "supported"
    assert out["verdicts"][0]["value"] == 92  # grounding travels inline


def test_compare_players_cross_pool_refused():
    out = server.compare_players(_load("celebrini.json"), _load("synthetic_dman.json"))
    assert out["compatible"] is False
    assert out["edge_kind"] == "incompatible"


def test_explain_metric_passes_through():
    out = server.explain_metric("even strength defense")
    assert out["found"] is True
    assert out["metric"] == "ev_defense"
    assert out["definition"] and out["caveat"]


def test_explain_metric_unknown_is_not_found():
    out = server.explain_metric("grit")
    assert out["found"] is False
    assert "not a card metric" in out["message"].lower()


def test_unidentifiable_card_raises_toolerror():
    with pytest.raises(ToolError):
        server.assess_player({"name": "Mystery", "team": "X"})


def test_invalid_percentile_raises_toolerror():
    bad = _load("celebrini.json")
    bad["ev_offense"] = 150  # out of 0-100 range
    with pytest.raises(ToolError):
        server.assess_player(bad)


# --- Description steering for interpretive reads (2026-07-04) ---------------
# These guard prompt-level guidance the way test_reports_tool guards the PDF
# steering: a reworded description must not silently drop the contract.


def _descriptions():
    return {
        t.name: " ".join(t.description.split())  # collapse doc line wraps
        for t in asyncio.run(server.mcp.list_tools())
    }


def test_adjudicate_lists_the_style_and_context_dimension_ids():
    desc = _descriptions()["adjudicate_claim"]
    for dim in ("skater_style", "net_front", "team_leading_scorer", "goalie_style"):
        assert dim in desc, dim


def test_interpretive_reads_carry_unit_shape_and_reasoning_frames():
    desc = _descriptions()["render_report"]
    # Unit shape enforced in guidance.
    assert "EXACTLY 3 forwards" in desc
    assert "EXACTLY 2 defensemen" in desc
    # Line-synergy complementarity checklist.
    assert "three finishers and no creator" in desc
    # Goalie-support directional questions.
    assert "funnel chances into them" in desc
    assert "rebound control" in desc
    # Chat answers labeled interpretive, not just the PDF badge.
    assert "chat answer" in desc.lower()
    # Output shape: roles / works / concerns / caveat / summary.
    for word in ("role per player", "works", "concerns", "caveat", "summary"):
        assert word in desc, word


def test_render_report_steers_structured_units_and_plain_text():
    desc = _descriptions()["render_report"]
    # Structured answers (per-line / per-pairing) go through `units`, prose
    # through `sections` — and everything is plain text, never markdown.
    assert "units" in desc
    assert "key_numbers" in desc
    assert "per-unit structure" in desc
    assert "genuinely freeform" in desc
    assert "PLAIN TEXT" in desc
    assert "markdown" in desc.lower()


def test_verdict_tools_carry_the_standing_disclaimer():
    descs = _descriptions()
    line = "Reads are model projections, not predictions. Numbers are percentiles unless noted."
    for name in ("assess_player", "adjudicate_claim", "compare_players"):
        assert line in descs[name], name
