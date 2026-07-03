"""Render one PDF per report kind from the golden fixtures, for eyeballing.

Like the other demos this is the window into how the output READS — here,
how the report looks against the webapp assess screen it mirrors. Not server
code; never imported by src/. PDFs land in examples/report_previews/.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine.adjudicate import adjudicate_claim
from engine.assess import assess_player
from engine.compare import compare_players
from reports import render_pdf
from schemas import GoalieCard, SkaterCard

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
OUT = Path(__file__).resolve().parent / "report_previews"


def _card(name, model):
    return model(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def main():
    OUT.mkdir(exist_ok=True)
    celebrini = _card("celebrini.json", SkaterCard)
    hughes = _card("hughes.json", SkaterCard)
    thompson = _card("thompson.json", GoalieCard)

    jobs = {
        "assess_skater_celebrini.pdf": (
            "assess_skater", assess_player(celebrini), None),
        "assess_goalie_thompson.pdf": (
            "assess_goalie", assess_player(thompson), None),
        "compare_celebrini_vs_hughes.pdf": (
            "compare", compare_players(celebrini, hughes), None),
        "claim_check_celebrini.pdf": (
            "claim_check",
            adjudicate_claim(celebrini, [
                {"dimension": "finishing", "direction": "high", "text": "an elite finisher"},
                {"dimension": "playmaking", "direction": "high", "text": "a great playmaker"},
                {"dimension": "two_way", "direction": "high", "text": "responsible defensively"},
                {"dimension": "net_front", "direction": "high", "text": "dominant at the net-front"},
            ]),
            "“Celebrini is an elite finisher, a great playmaker, responsible "
            "defensively, and dominant at the net-front”",
        ),
        "interpretive_line_synergy.pdf": (
            "interpretive",
            {
                "title": "Celebrini and Hughes on the same line",
                "subtitle": "Line-synergy question — read across two validated cards",
                "tone": "positive",
                "players": ["Macklin Celebrini", "Jack Hughes"],
                "sections": [
                    {"heading": "The fit",
                     "body": "Two elite play-drivers who both convert: EV offense 91st "
                             "and 93rd, finishing 92nd and 88th. Either can carry a shift; "
                             "together they compound rather than overlap."},
                    {"heading": "The risk",
                     "body": "Neither profiles as the defensive conscience — both EV "
                             "defense reads sit well below the line, so the pairing "
                             "tilts high-event in both directions."},
                ],
                "caveat": "Line fit is read across individual cards; the engine has no "
                          "unit model, so this is an AI read, not a graded verdict.",
                "summary": "A high-end offensive pairing that needs a stabilizing third.",
            },
            None,
        ),
    }
    for filename, (kind, result, title) in jobs.items():
        path = OUT / filename
        path.write_bytes(render_pdf(kind, result, title))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
