"""Render one PDF per report kind from the golden fixtures, for eyeballing.

Like the other demos this is the window into how the output READS - here,
how the report design actually looks on the page. Not server
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
from schemas import DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
OUT = Path(__file__).resolve().parent / "report_previews"


def _card(name, model):
    return model(**json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def main():
    OUT.mkdir(exist_ok=True)
    celebrini = _card("celebrini.json", SkaterCard)
    hughes = _card("hughes.json", SkaterCard)
    thompson = _card("thompson.json", GoalieCard)
    celebrini_micro = _card("celebrini_micro.json", ForwardMicroCard)
    schaefer_micro = _card("schaefer_micro.json", DefenseMicroCard)

    jobs = {
        "assess_skater_celebrini.pdf": (
            "assess_skater", assess_player(celebrini), None),
        "assess_micro_celebrini.pdf": (
            "assess_micro", assess_player(celebrini_micro), None),
        "assess_micro_schaefer.pdf": (
            "assess_micro", assess_player(schaefer_micro), None),
        "assess_skater_celebrini_with_synthesis.pdf": (
            "assess_skater",
            assess_player(celebrini, micro_card=celebrini_micro), None),
        "compare_micro_celebrini_vs_synthetic.pdf": (
            "compare",
            compare_players(
                celebrini_micro,
                ForwardMicroCard(**{
                    **json.loads((FIXTURES / "celebrini_micro.json").read_text(encoding="utf-8")),
                    "name": "Synthetic Micro Forward",
                    "ev_offense": 45, "ev_defense": 88, "pp": 20,
                    "penalties": 60, "finishing": 40,
                }),
            ),
            None),
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
                "subtitle": "Line-synergy question - read across two validated cards",
                "tone": "positive",
                "players": ["Macklin Celebrini", "Jack Hughes"],
                "sections": [
                    {"heading": "The fit",
                     "body": "Two elite play-drivers who both convert: EV offense 91st "
                             "and 93rd, finishing 92nd and 88th. Either can carry a shift; "
                             "together they compound rather than overlap."},
                    {"heading": "The risk",
                     "body": "Neither profiles as the defensive conscience - both EV "
                             "defense reads sit well below the line, so the pairing "
                             "tilts high-event in both directions."},
                ],
                "caveat": "Line fit is read across individual cards; the engine has no "
                          "unit model, so this is an AI read, not a graded verdict.",
                "summary": "A high-end offensive pairing that needs a stabilizing third.",
            },
            None,
        ),
        # Prose-sections path (no units): the flat goalie-support read.
        "interpretive_goalie_support.pdf": (
            "interpretive",
            {
                "title": "Goalie Support Read: Bobrovsky with Raddysh-Rielly",
                "tone": "negative",
                "players": ["Sergei Bobrovsky", "Darren Raddysh", "Morgan Rielly"],
                "sections": [
                    {"heading": "Roles",
                     "body": "Bobrovsky is the last line. His signature trait is elite "
                             "rebound control (92nd percentile), but he is a below-average "
                             "high-danger saver (27th) and weak on the penalty kill (27th). "
                             "Raddysh is an offense-first puck mover (78th EV offense, 75th "
                             "power play) with only average EV defense (51st). Rielly is a "
                             "pure offense generator (87th EV offense) with an EV defense "
                             "mark of 1st percentile - among the worst at the position."},
                    {"heading": "What works",
                     "body": "Both defensemen take few penalties (Raddysh 67th, Rielly 71st "
                             "discipline), which keeps Bobrovsky off the penalty kill, exactly "
                             "where he is weakest. His rebound control (92nd) limits "
                             "second-chance damage even when the first shot gets through."},
                    {"heading": "Concerns",
                     "body": "Rielly's EV defense gap is severe, and Raddysh is not a "
                             "defensive stopgap for it. That shot-suppression hole lines up "
                             "with Bobrovsky's own weakest spot: high-danger saves (27th)."},
                ],
                "caveat": "This is a read of three individual cards together, not a "
                          "unit-level model. Bobrovsky's consistency mark (33rd percentile) "
                          "means his high-danger weakness is not a fixed floor.",
                "summary": "This trio's biggest risk is compounding, not offsetting, "
                           "weaknesses - Rielly's defensive gap feeds shots into the exact "
                           "area Bobrovsky handles worst.",
            },
            None,
        ),
        # Structured-units path: per-line cards with player rows and
        # works/concerns columns, plus a freeform extras section.
        "interpretive_roster_construction.pdf": (
            "interpretive",
            {
                "title": "Optimal Line Construction - Card-Based Synergy Read",
                "subtitle": "Four forward lines from fourteen validated cards",
                "tone": "mixed",
                "players": [
                    "Jack Hughes", "Arseny Gritsyuk", "Jesper Bratt",
                    "Nico Hischier", "Timo Meier", "Dawson Mercer",
                    "Barrett Hayton", "Evan Rodrigues", "Connor Brown",
                    "Cody Glass", "Stefan Noesen", "Nick Bjugstad",
                    "Jesper Boqvist", "Lenni Hameenaho",
                ],
                "units": [
                    {
                        "name": "Line 1 - Hughes (C) / Gritsyuk (LW) / Bratt (RW)",
                        "players": [
                            {"name": "Hughes",
                             "read": "98th percentile, Elite: elite EV offense and finishing, but weak EV defense.",
                             "key_numbers": "98 EVO · 85 FIN · 34 EVD"},
                            {"name": "Gritsyuk",
                             "read": "84th, Strong: elite EV defense directly covers Hughes' gap, plus strong finishing.",
                             "key_numbers": "95 EVD · 79 FIN"},
                            {"name": "Bratt",
                             "read": "91st, Excellent: elite EV offense and power play; a positive-regression case - his EV offense sits well above his finishing, so there's more scoring in the tank.",
                             "key_numbers": "97 EVO · 49 FIN"},
                        ],
                        "works": [
                            "Gritsyuk's defense offsets the two defensive liabilities flanking him.",
                            "Bratt's playmaking (98th percentile primary assists) feeds two finishers.",
                        ],
                        "concerns": [
                            "All three are left-shot. Bratt on the off-wing actually helps his cross-ice feeds, but there's no true shutdown center if Gritsyuk gets pulled out of position.",
                            "Gritsyuk's discipline (16th percentile) adds penalty exposure.",
                        ],
                    },
                    {
                        "name": "Line 2 - Hischier (C) / Meier (LW) / Mercer (RW)",
                        "players": [
                            {"name": "Hischier",
                             "read": "97th, Elite: elite EV offense and power play; the only real hole is the penalty kill.",
                             "key_numbers": "5 PK"},
                            {"name": "Meier",
                             "read": "71st, Strong: elite-adjacent EV offense, weak EV defense - also a positive-regression case.",
                             "key_numbers": "84 EVO · 30 EVD"},
                            {"name": "Mercer",
                             "read": "54th, Average: elite penalty kill and strong EV defense, weak finishing and power play.",
                             "key_numbers": "92 PK · 70 EVD"},
                        ],
                        "works": [
                            "Mercer is the stabilizer - his PK and defense cover Meier's biggest hole while Hischier's playmaking ties the line together.",
                            "Balanced handedness (2 LH, 1 RH on his strong side).",
                        ],
                        "concerns": [
                            "No true high-event finisher beyond Meier; if Meier is off, this line's offense reverts mostly to Hischier alone.",
                        ],
                    },
                    {
                        "name": "Line 3 - Hayton (C) / Rodrigues (LW) / Brown (RW)",
                        "players": [
                            {"name": "Hayton",
                             "read": "39th, Below average: strong two-way, but 3rd-percentile finishing - generates without converting.",
                             "key_numbers": "83 EVO · 78 EVD · 3 FIN"},
                            {"name": "Rodrigues",
                             "read": "53rd, Average: strong EV defense plus elite penalty kill.",
                             "key_numbers": "73 EVD · 81 PK"},
                            {"name": "Brown",
                             "read": "27th, Weak: only asset is the penalty kill; weak everywhere else.",
                             "key_numbers": "80 PK"},
                        ],
                        "works": [
                            "Legitimate matchup/shutdown trio - two strong defensive profiles plus real PK depth (81/80). Good for tough defensive-zone assignments.",
                        ],
                        "concerns": [
                            "Almost no finishing anywhere on this line (3/20/15). This is a line built to suppress, not score - don't expect secondary scoring from it.",
                        ],
                    },
                    {
                        "name": "Line 4 - Glass (C) / Noesen (LW) / Bjugstad (RW)",
                        "players": [
                            {"name": "Glass",
                             "read": "65th, Above average: elite EV defense, weak EV offense - trending up sharply per his WAR chart.",
                             "key_numbers": "98 EVD · 38 EVO"},
                            {"name": "Noesen",
                             "read": "40th, Below average: strong EV defense on the card, but 7th-percentile discipline and heavily sheltered usage - the defensive number is soft evidence.",
                             "key_numbers": "74 EVD · 7 DISC"},
                            {"name": "Bjugstad",
                             "read": "34th, Below average: no flagged strengths, but his EV offense and goals (descriptive) are the only offense on this line.",
                             "key_numbers": "67 EVO · 57 G"},
                        ],
                        "works": [
                            "Glass anchors a real shutdown identity.",
                            "Bjugstad provides the only spark of secondary scoring.",
                        ],
                        "concerns": [
                            "Two poor-discipline forwards (Bjugstad 15th, Noesen 7th) stacked together - this line will take penalties.",
                            "All three shoot right, so there's zero off-wing shooting angle variety.",
                        ],
                    },
                ],
                "sections": [
                    {"heading": "Extras (not graded into the 12)",
                     "body": "Boqvist and Hameenaho graded out as replacement-level or "
                             "worse (30th and 2nd percentile, zero flagged strengths) - "
                             "Hameenaho's card explicitly carries the small-sample caveat "
                             "the engine attaches to young players. They're the 13th/14th "
                             "forwards, not lines 5-6. Lombardi has no card to grade, so "
                             "he's outside this analysis entirely rather than guessed into "
                             "a slot."},
                ],
                "caveat": "This is a synergy read built from four individual player cards "
                          "per line, not an engine verdict - there is no unit-level model "
                          "behind it. Line chemistry, deployment, and coaching usage in "
                          "real games can meaningfully change how these combinations "
                          "actually perform on ice.",
                "summary": "Lines 1 and 2 are firepower-heavy with a defensive complement "
                           "built in; Lines 3 and 4 trade scoring for two-way reliability, "
                           "with real penalty-discipline risk on Line 4.",
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
