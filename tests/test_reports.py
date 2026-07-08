"""Reports renderer core (Phase 1): engine output -> styled HTML -> PDF.

The renderer takes the engine's structured results (or their dicts) and
renders them into a styled PDF. These tests check the
HTML carries the right content/design hooks and that every kind produces a
real PDF; visual fidelity is eyeballed via examples/demo_reports.py.
"""
import json
from html import unescape
from pathlib import Path

import pytest

from engine.adjudicate import adjudicate_claim
from engine.assess import assess_player
from engine.compare import compare_players
from reports import REPORT_KINDS, render_html, render_pdf
from schemas import DefenseCard, GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"

FOOTER = "Built on HockeyStats.com (JFresh Hockey) player cards."
INTERPRETIVE_BADGE = "Interpretive read"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def celebrini_card():
    return SkaterCard(**_load("celebrini.json"))


@pytest.fixture(scope="module")
def skater_result(celebrini_card):
    return assess_player(celebrini_card)


@pytest.fixture(scope="module")
def goalie_result():
    return assess_player(GoalieCard(**_load("thompson.json")))


@pytest.fixture(scope="module")
def compare_result(celebrini_card):
    return compare_players(celebrini_card, SkaterCard(**_load("hughes.json")))


@pytest.fixture(scope="module")
def claim_result(celebrini_card):
    # Covers all four grades: supported, not_supported, partial-ish, unverifiable.
    return adjudicate_claim(
        celebrini_card,
        [
            {"dimension": "finishing", "direction": "high", "text": "an elite finisher"},
            {"dimension": "two_way", "direction": "high", "text": "strong defensively"},
            {"dimension": "net_front", "direction": "high", "text": "owns the net-front"},
        ],
    )


@pytest.fixture(scope="module")
def interpretive_result():
    return {
        "title": "Would Celebrini and Hughes work on a line together?",
        "tone": "positive",
        "players": ["Macklin Celebrini", "Jack Hughes"],
        "sections": [
            {"heading": "The fit", "body": "Two play-drivers who both finish."},
            {"heading": "The risk", "body": "Neither profiles as the defensive conscience."},
        ],
        "caveat": "Line fit is read across individual cards; there is no unit model.",
        "summary": "A high-event pairing that tilts the ice but needs a stabilizer.",
    }


@pytest.fixture(scope="module")
def units_result():
    # Structured interpretive read: per-unit cards + a freeform extras section.
    return {
        "title": "Optimal line construction",
        "tone": "mixed",
        "players": ["Jack Hughes", "Arseny Gritsyuk", "Jesper Bratt"],
        "units": [
            {
                "name": "Line 1 — Hughes (C) / Gritsyuk (LW) / Bratt (RW)",
                "players": [
                    {"name": "Hughes", "read": "Elite EV offense and finishing, but weak EV defense.",
                     "key_numbers": "98 EVO · 85 FIN · 34 EVD"},
                    {"name": "Gritsyuk", "read": "Elite EV defense directly covers Hughes' gap.",
                     "key_numbers": "95 EVD · 79 FIN"},
                ],
                "works": ["Gritsyuk's defense offsets two defensive liabilities."],
                "concerns": ["No true shutdown center if Gritsyuk is pulled out of position."],
            },
        ],
        "sections": [
            {"heading": "Extras", "body": "Boqvist graded replacement-level; Lombardi has no card."},
        ],
        "caveat": "Synergy is read across individual cards; there is no unit model.",
        "summary": "Top-six firepower, bottom-six suppression.",
    }


def _result_for(kind, skater, goalie, cmp_, claim, interp):
    return {
        "assess_skater": skater,
        "assess_goalie": goalie,
        "compare": cmp_,
        "claim_check": claim,
        "interpretive": interp,
    }[kind]


# --- HTML content ------------------------------------------------------------


def test_assess_skater_html_carries_the_verdict(skater_result):
    html = render_html("assess_skater", skater_result)
    assert "Macklin Celebrini" in html
    assert "Excellent forward" in html          # verdict headline wording
    assert "94th percentile" in html
    assert skater_result.summary in html
    assert FOOTER in html


def test_assess_skater_html_renders_strength_bars_and_caveats(skater_result):
    html = render_html("assess_skater", skater_result)
    for s in skater_result.strengths:
        assert s.label in html
    assert "width:95%" in html                  # penalties 95 -> bar width
    for c in skater_result.caveats:
        assert c in unescape(html)              # engine prose carries apostrophes


def test_assess_skater_html_renders_descriptive_reads():
    # Goals / primary assists are supporting color in the engine's
    # `descriptive` list — the report shows them, labeled as color not value,
    # so chat and PDF carry the same data.
    hughes = assess_player(SkaterCard(**_load("hughes.json")))
    html = render_html("assess_skater", hughes)
    assert "Goals" in html
    assert "Primary assists" in html
    assert "width:89%" in html                  # goals 89 -> bar width
    assert "not the verdict" in html            # labeled as color, not value


def test_defenseman_finishing_exclusion_note_reaches_the_report():
    dman = assess_player(DefenseCard(**_load("synthetic_dman.json")))
    note = next(d.note for d in dman.descriptive if d.metric == "finishing")
    html = render_html("assess_skater", dman)
    assert "excluded" in note                   # the note is the exclusion text
    assert note in unescape(html)


def test_assess_goalie_html_carries_goalie_reads(goalie_result):
    html = render_html("assess_goalie", goalie_result)
    assert "Logan Thompson" in html
    assert goalie_result.danger_profile.shape in html
    assert goalie_result.start_quality_profile.shape in html
    assert goalie_result.workload in html
    assert FOOTER in html


def test_compare_html_shows_both_columns_and_gaps(compare_result):
    html = render_html("compare", compare_result)
    assert "Macklin Celebrini" in html
    assert "Jack Hughes" in html
    assert compare_result.overall in html
    for comp in compare_result.components:
        assert comp.label in html
    assert FOOTER in html


def test_claim_check_html_shows_graded_rows(claim_result):
    html = render_html("claim_check", claim_result)
    grades = {v.grade for v in claim_result.verdicts}
    assert "unverifiable" in grades             # fixture must exercise the 4th color
    assert "SUPPORTED" in html
    assert "UNVERIFIABLE" in html
    for v in claim_result.verdicts:
        assert v.reason in unescape(html)       # engine prose carries apostrophes
    assert claim_result.overall in unescape(html)
    assert FOOTER in html


def test_interpretive_caveat_frames_the_read(interpretive_result):
    # The honest caveat sits under the badge, BEFORE the confident prose —
    # it frames the interpretive read rather than qualifying it at the end.
    html = render_html("interpretive", interpretive_result)
    assert html.index(interpretive_result["caveat"]) < html.index(
        interpretive_result["sections"][0]["body"])


def test_interpretive_html_is_badged(interpretive_result):
    html = render_html("interpretive", interpretive_result)
    assert INTERPRETIVE_BADGE in html
    assert "not an engine verdict" in html
    for s in interpretive_result["sections"]:
        assert s["body"] in html
    assert FOOTER in html


def test_interpretive_units_render_player_rows_and_works_concerns(units_result):
    html = unescape(render_html("interpretive", units_result))
    assert "Line 1 — Hughes (C) / Gritsyuk (LW) / Bratt (RW)" in html
    for row in units_result["units"][0]["players"]:
        assert row["name"] in html
        assert row["read"] in html
        assert row["key_numbers"] in html
    # Works/concerns reuse the goalie-support two-column visual: green +
    # items and red − items under their own eyebrows.
    assert "What works" in html
    assert "Concerns" in html
    assert units_result["units"][0]["works"][0] in html
    assert units_result["units"][0]["concerns"][0] in html
    # The sections fallback still renders alongside the units.
    assert "Extras" in html
    assert units_result["sections"][0]["body"] in html


def test_interpretive_units_without_sections_are_enough():
    html = render_html("interpretive", {
        "title": "Units only",
        "units": [{"name": "Pairing — A / B", "works": ["Their skills complement."]}],
    })
    assert "Their skills complement." in html


def test_interpretive_caveat_still_frames_units(units_result):
    # Honest-caveat-near-the-top: the caveat precedes the first unit card.
    html = unescape(render_html("interpretive", units_result))
    assert html.index(units_result["caveat"]) < html.index(units_result["units"][0]["name"])


def test_interpretive_markdown_never_renders_literally():
    html = render_html("interpretive", {
        "title": "Markdown input",
        "sections": [{
            "heading": "Read",
            "body": "**Hughes** is *elite*.\n- covers the gap\n- feeds two finishers",
        }],
        "units": [{
            "name": "Line 1 — **Hughes** / Bratt",
            "players": [{"name": "**Hughes**", "read": "**elite** EVO"}],
            "works": ["**Bratt** feeds two finishers"],
            "concerns": ["- all three are the same hand"],
        }],
        "summary": "A **strong** top line.",
    })
    assert "**" not in html                      # never literal markdown
    assert "<strong>Hughes</strong>" in html     # bold converts, not strips
    assert "<li>covers the gap</li>" in html     # bullets become real lists
    assert "<li>feeds two finishers</li>" in html
    assert "- all three" not in html             # stray bullet chars stripped
    assert "all three are the same hand" in html


def test_interpretive_markdown_conversion_still_escapes_html():
    html = render_html("interpretive", {
        "title": "Escape check",
        "sections": [{"heading": None, "body": "**bold** and <script>alert(1)</script>"}],
    })
    assert "<script>" not in html
    assert "<strong>bold</strong>" in html


def test_engine_kinds_are_not_badged_interpretive(skater_result, goalie_result, compare_result, claim_result):
    for kind, result in [
        ("assess_skater", skater_result),
        ("assess_goalie", goalie_result),
        ("compare", compare_result),
        ("claim_check", claim_result),
    ]:
        assert INTERPRETIVE_BADGE not in render_html(kind, result)


def test_no_kind_ever_embeds_an_image(skater_result, goalie_result, compare_result, claim_result, interpretive_result):
    for kind in REPORT_KINDS:
        html = render_html(kind, _result_for(
            kind, skater_result, goalie_result, compare_result, claim_result, interpretive_result))
        assert "<img" not in html.lower()


def test_dict_results_render_the_same_as_models(skater_result):
    assert render_html("assess_skater", skater_result.model_dump()) == render_html(
        "assess_skater", skater_result)


def test_title_override_lands_in_the_html(skater_result):
    html = render_html("assess_skater", skater_result, title="Trade-deadline read")
    assert "Trade-deadline read" in html


# --- Failure modes -----------------------------------------------------------


def test_unknown_kind_fails_loudly(skater_result):
    with pytest.raises(ValueError, match="kind"):
        render_html("assess_defense", skater_result)


def test_interpretive_without_sections_fails_loudly():
    with pytest.raises(ValueError, match="sections"):
        render_html("interpretive", {"title": "Empty", "sections": []})


def test_interpretive_with_neither_sections_nor_units_fails_loudly():
    with pytest.raises(ValueError, match="sections"):
        render_html("interpretive", {"title": "Empty", "sections": [], "units": []})


# --- PDF output --------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(REPORT_KINDS))
def test_every_kind_renders_a_real_pdf(kind, skater_result, goalie_result, compare_result, claim_result, interpretive_result):
    pdf = render_pdf(kind, _result_for(
        kind, skater_result, goalie_result, compare_result, claim_result, interpretive_result))
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000                      # a styled page, not a stub


def test_interpretive_units_render_a_real_pdf(units_result):
    pdf = render_pdf("interpretive", units_result)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000
