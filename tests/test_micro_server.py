"""Server wiring and description steering for the microstat card.

Same guard style as test_server.py: the tool descriptions carry load-bearing
host steering (how to extract a micro card, which dimension ids became
answerable, the cross-regime refusal), and a reworded description must not
silently drop it.
"""
import asyncio
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

import server

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _descriptions():
    return {
        t.name: " ".join(t.description.split())
        for t in asyncio.run(server.mcp.list_tools())
    }


# --- Wiring ------------------------------------------------------------------


def test_assess_player_dispatches_micro():
    out = server.assess_player(_load("celebrini_micro.json"))
    assert out["season"] == "2025-26"
    assert "profiles" in out
    assert "overall_note" in out


def test_assess_player_accepts_micro_card_companion():
    out = server.assess_player(_load("celebrini.json"), micro_card=_load("celebrini_micro.json"))
    assert out["overall_tier"] == "Excellent"     # verdict unchanged
    assert out["micro_insights"] is not None
    assert out["micro_insights"]["season"] == "2025-26"


def test_micro_card_companion_must_be_micro():
    with pytest.raises(ToolError):
        server.assess_player(_load("celebrini.json"), micro_card=_load("hughes.json"))


def test_mismatched_companion_names_fail_loudly():
    with pytest.raises(ToolError):
        server.assess_player(_load("celebrini.json"), micro_card=_load("schaefer_micro.json"))


def test_adjudicate_micro_claim_end_to_end():
    out = server.adjudicate_claim(
        _load("celebrini_micro.json"),
        [{"dimension": "rush player", "direction": "high", "text": "a rush threat"}],
    )
    assert out["verdicts"][0]["grade"] == "supported"
    assert out["verdicts"][0]["value"] == 96


def test_compare_micro_vs_standard_refused_end_to_end():
    out = server.compare_players(_load("celebrini.json"), _load("celebrini_micro.json"))
    assert out["compatible"] is False


# --- Description steering ----------------------------------------------------


def test_assess_description_teaches_micro_extraction():
    desc = _descriptions()["assess_player"]
    assert 'card_kind' in desc
    assert '"micro"' in desc or "'micro'" in desc
    assert "season" in desc
    assert "micro_card" in desc
    # Key micro fields for both variants are listed for the extractor.
    for field in ("entries_w_possession", "entry_chance_prevention", "skating_speed"):
        assert field in desc, field


def test_adjudicate_description_lists_micro_dimensions():
    desc = _descriptions()["adjudicate_claim"]
    for dim in ("skating", "physicality", "forechecking", "rush_attack",
                "rush_defense", "puck_management"):
        assert dim in desc, dim
    # And says style claims resolve on a micro card.
    assert "micro" in desc.lower()


def test_compare_description_states_cross_regime_refusal():
    desc = _descriptions()["compare_players"]
    assert "micro" in desc.lower()
    assert "refus" in desc.lower()


def test_render_report_lists_assess_micro_kind():
    desc = _descriptions()["render_report"]
    assert "assess_micro" in desc
