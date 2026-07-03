"""render_report MCP tool (reports Phase 2).

The tool validates the passed result against the ENGINE's own output shapes
(so a retyped/reconstructed result fails loudly), writes the PDF to the
reports directory (env-overridable), and returns the absolute path.
"""
import asyncio
import datetime
import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

import server
from engine.adjudicate import adjudicate_claim
from engine.assess import assess_player
from engine.compare import compare_players
from schemas import GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def reports_dir(tmp_path, monkeypatch):
    """Point the tool at a temp dir — tests never write to ~/Documents."""
    out = tmp_path / "HockeyCardReports"
    monkeypatch.setenv("HOCKEY_CARD_REPORTS_DIR", str(out))
    return out


@pytest.fixture(scope="module")
def skater_result():
    return assess_player(SkaterCard(**_load("celebrini.json"))).model_dump()


@pytest.fixture(scope="module")
def goalie_result():
    return assess_player(GoalieCard(**_load("thompson.json"))).model_dump()


def test_render_report_is_registered():
    tools = asyncio.run(server.mcp.list_tools())
    assert "render_report" in {t.name for t in tools}


def test_assess_description_forbids_promoting_descriptive_to_strengths():
    # Live loop round 2: Claude presented the `descriptive` reads (goals,
    # first assists) as strengths in chat. The description must pin narration
    # to the returned lists.
    tools = {t.name: t.description for t in asyncio.run(server.mcp.list_tools())}
    desc = " ".join(tools["assess_player"].split())  # collapse doc line wraps
    assert "descriptive" in desc
    assert "NEVER present them as strengths" in desc


def test_engine_tools_tell_claude_to_offer_the_pdf():
    # The offer instruction must live on the tools Claude JUST USED when it
    # finishes an answer — render_report's own description isn't in its
    # attention at that moment (confirmed live in Phase 3).
    tools = {t.name: t.description for t in asyncio.run(server.mcp.list_tools())}
    for name in ("assess_player", "compare_players", "adjudicate_claim"):
        assert "PDF" in tools[name] and "render_report" in tools[name], name
    assert "ALWAYS" in tools["render_report"]


def test_assess_report_written_and_named_after_the_player(reports_dir, skater_result):
    out = server.render_report("assess_skater", skater_result)
    path = Path(out["path"])
    assert path.is_absolute()
    assert path.parent == reports_dir
    assert path.read_bytes().startswith(b"%PDF-")
    assert "macklin-celebrini" in path.name
    assert "assess-skater" in path.name
    assert datetime.date.today().isoformat() in path.name


def test_reports_dir_is_created_if_missing(reports_dir, skater_result):
    assert not reports_dir.exists()
    server.render_report("assess_skater", skater_result)
    assert reports_dir.is_dir()


def test_second_report_same_day_gets_a_distinct_name(skater_result):
    first = Path(server.render_report("assess_skater", skater_result)["path"])
    second = Path(server.render_report("assess_skater", skater_result)["path"])
    assert first != second
    assert second.exists()


def test_compare_report_named_after_both_players():
    result = compare_players(
        SkaterCard(**_load("celebrini.json")), SkaterCard(**_load("hughes.json"))
    ).model_dump()
    path = Path(server.render_report("compare", result)["path"])
    assert "macklin-celebrini-vs-jack-hughes" in path.name
    assert path.read_bytes().startswith(b"%PDF-")


def test_claim_check_report_uses_the_title_for_its_name():
    result = adjudicate_claim(
        SkaterCard(**_load("celebrini.json")),
        [{"dimension": "finishing", "direction": "high", "text": "elite finisher"}],
    ).model_dump()
    path = Path(server.render_report("claim_check", result, title="Celebrini elite finisher claim")["path"])
    assert "celebrini-elite-finisher-claim" in path.name
    assert path.read_bytes().startswith(b"%PDF-")


def test_interpretive_report_from_claude_prose():
    result = {
        "title": "Celebrini and Hughes on a line",
        "tone": "positive",
        "players": ["Macklin Celebrini", "Jack Hughes"],
        "sections": [{"heading": "Fit", "body": "Two play-drivers who both finish."}],
        "summary": "High-end offensive pairing.",
    }
    path = Path(server.render_report("interpretive", result)["path"])
    assert path.read_bytes().startswith(b"%PDF-")


def test_goalie_result_dispatches_by_kind(goalie_result):
    path = Path(server.render_report("assess_goalie", goalie_result)["path"])
    assert "logan-thompson" in path.name


# --- Fails loudly ------------------------------------------------------------


def test_unknown_kind_is_a_tool_error(skater_result):
    with pytest.raises(ToolError, match="kind"):
        server.render_report("assess_defense", skater_result)


def test_retyped_or_malformed_result_is_a_tool_error():
    with pytest.raises(ToolError, match="engine result"):
        server.render_report(
            "assess_skater",
            {"name": "Someone", "overall_tier": "Elite", "summary": "made up"},
        )


def test_wrong_kind_for_the_result_is_a_tool_error(goalie_result):
    # A goalie assessment passed as a skater report must not silently render.
    with pytest.raises(ToolError, match="engine result"):
        server.render_report("assess_skater", goalie_result)


def test_interpretive_without_sections_is_a_tool_error():
    with pytest.raises(ToolError, match="sections"):
        server.render_report("interpretive", {"title": "Empty", "sections": []})
