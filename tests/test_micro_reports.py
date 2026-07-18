"""Reports for the microstat card: the assess_micro kind, the synthesis panel
on a standard skater report, and micro comparisons through the compare kind.

Same honesty rules as every other kind: the result must round-trip through the
engine's own output model (a retyped result is rejected), and the report is
rendered from engine output alone.
"""
import json
import os
from pathlib import Path

import pytest

from engine.assess import assess_player
from engine.compare import compare_players
from reports.render import render_html
from reports.save import save_report
from schemas import DefenseMicroCard, ForwardMicroCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def micro_assessment():
    return assess_player(ForwardMicroCard(**_load("celebrini_micro.json")))


@pytest.fixture
def d_micro_assessment():
    return assess_player(DefenseMicroCard(**_load("schaefer_micro.json")))


def test_assess_micro_renders_html(micro_assessment):
    html = render_html("assess_micro", micro_assessment)
    assert "Macklin Celebrini" in html
    assert "2025-26" in html
    # The WAR-row value reads and a profile label make it to the page.
    assert "Rush-led attack" in html
    # The style trio is present and framed as style.
    assert "Hits" in html
    assert "Style, not value" in html
    # The no-headline honesty line is on the page.
    assert "standard card" in html


def test_assess_micro_defense_renders_rush_defense(d_micro_assessment):
    html = render_html("assess_micro", d_micro_assessment)
    assert "Matthew Schaefer" in html
    assert "Entry chance prevention" in html


def test_assess_micro_rejects_retyped_result(tmp_path, micro_assessment):
    os.environ["HOCKEY_CARD_REPORTS_DIR"] = str(tmp_path)
    try:
        with pytest.raises(ValueError):
            save_report("assess_micro", {"name": "Someone", "summary": "made up"})
    finally:
        del os.environ["HOCKEY_CARD_REPORTS_DIR"]


def test_assess_micro_saves_pdf_named_after_player(tmp_path, micro_assessment):
    os.environ["HOCKEY_CARD_REPORTS_DIR"] = str(tmp_path)
    try:
        path = save_report("assess_micro", micro_assessment.model_dump())
        assert path.exists()
        assert "macklin-celebrini" in path.name
        assert "assess-micro" in path.name
    finally:
        del os.environ["HOCKEY_CARD_REPORTS_DIR"]


def test_standard_report_shows_synthesis_when_present():
    std = SkaterCard(**_load("celebrini.json"))
    micro = ForwardMicroCard(**_load("celebrini_micro.json"))
    combined = assess_player(std, micro_card=micro)
    html = render_html("assess_skater", combined)
    assert "synthesis" in html.lower() or "micro" in html.lower()
    # A divergence sentence makes it to the page.
    assert "three-year projection" in html


def test_standard_report_unchanged_without_synthesis():
    std = SkaterCard(**_load("celebrini.json"))
    html = render_html("assess_skater", assess_player(std))
    assert "three-year projection" not in html


def test_micro_compare_renders_through_compare_kind():
    a = ForwardMicroCard(**_load("celebrini_micro.json"))
    data = _load("celebrini_micro.json")
    data.update(name="Synthetic Trailer", ev_offense=40, ev_defense=35, pp=20,
                penalties=30, finishing=38)
    b = ForwardMicroCard(**data)
    html = render_html("compare", compare_players(a, b))
    assert "Synthetic Trailer" in html
    assert "Chances" in html  # tracked components present in the table
