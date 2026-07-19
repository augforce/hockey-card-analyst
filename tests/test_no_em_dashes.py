"""No-em-dash rule (2026-07-19, user call).

No output surface may contain an em dash: not the structured tool results the
host narrates from, not the rendered PDFs. Source text is written dash-free
(the scan below), and `strip_em_dashes` is the runtime backstop at the server
and report boundaries. The character is spelled via its escape everywhere in
this file so the scan can include the test suite itself.
"""
import asyncio
import json
from pathlib import Path

import server
from engine.common import strip_em_dashes
from reports.render import render_html

EM_DASH = "\u2014"
ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- Source scan: canonical text is written without em dashes ----------------


def test_no_em_dashes_in_source_or_config():
    globs = [
        ("config", "*.yaml"),
        ("src", "**/*.py"),
        ("src/reports/templates", "*.html"),
        ("tests", "**/*.py"),
        ("tests/fixtures", "*.json"),
        ("examples", "*.py"),
    ]
    offenders = []
    for base, pattern in globs:
        for path in sorted((ROOT / base).glob(pattern)):
            if EM_DASH in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"em dash found in: {offenders}"


# --- Runtime backstop: the scrub helper and the two output boundaries --------


def test_strip_em_dashes_recurses_structures():
    dirty = {
        "a": f"x {EM_DASH} y",
        "b": [f"p{EM_DASH}q", {"c": f"{EM_DASH} lead"}],
        "n": 7,
        "none": None,
    }
    clean = strip_em_dashes(dirty)
    assert EM_DASH not in json.dumps(clean)
    assert clean["a"] == "x - y"
    assert clean["n"] == 7 and clean["none"] is None


def test_tool_outputs_contain_no_em_dashes():
    outputs = [
        server.assess_player(_load("celebrini.json")),
        server.assess_player(_load("thompson.json")),
        server.assess_player(_load("celebrini_micro.json")),
        server.assess_player(_load("celebrini.json"), micro_card=_load("celebrini_micro.json")),
        server.adjudicate_claim(
            _load("celebrini.json"), [{"dimension": "finishing", "direction": "high"}]
        ),
        server.compare_players(_load("celebrini.json"), _load("dorofeyev.json")),
        server.explain_metric("finishing"),
    ]
    for out in outputs:
        assert EM_DASH not in json.dumps(out, ensure_ascii=False)


def test_rendered_reports_contain_no_em_dashes():
    # Engine-result kinds.
    for kind, result in (
        ("assess_skater", server.assess_player(_load("celebrini.json"))),
        ("assess_goalie", server.assess_player(_load("thompson.json"))),
        ("assess_micro", server.assess_player(_load("celebrini_micro.json"))),
        ("compare", server.compare_players(_load("celebrini.json"), _load("dorofeyev.json"))),
        (
            "claim_check",
            server.adjudicate_claim(
                _load("celebrini.json"), [{"dimension": "finishing", "direction": "high"}]
            ),
        ),
    ):
        assert EM_DASH not in render_html(kind, result), kind


def test_interpretive_report_scrubs_claude_authored_em_dashes():
    # Claude-authored content may arrive dirty; the renderer must scrub it.
    result = {
        "title": f"Line read {EM_DASH} test",
        "tone": "neutral",
        "players": ["A", "B"],
        "sections": [
            {"heading": f"Fit {EM_DASH} overall", "body": f"Drives play {EM_DASH} finishes too."}
        ],
        "summary": f"Works {EM_DASH} with caveats.",
    }
    assert EM_DASH not in render_html("interpretive", result)


# --- Description steering: the host is told not to write them either ---------


def test_descriptions_steer_against_em_dashes():
    # The rule must be a prominent HARD STYLE RULE on EVERY tool, not a buried
    # aside: the host writes prose after whichever tool it just used (and live
    # use showed the buried version being ignored, 2026-07-19).
    descs = {
        t.name: " ".join(t.description.split())
        for t in asyncio.run(server.mcp.list_tools())
    }
    for name in (
        "assess_player",
        "adjudicate_claim",
        "compare_players",
        "explain_metric",
        "render_report",
    ):
        assert "HARD STYLE RULE: never use em dashes" in descs[name], name
