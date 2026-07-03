"""ILLUSTRATIVE DEMO — NOT SERVER CODE.

Goalies through all three tools, with the structured output AND the plain-English
answer a human (Claude Desktop) would narrate from it. The headline is the
Thompson assessment, which must hold the 96th-WAR / 23rd-consistency tension
together — a strong starter whose three-year record is short and uneven — not
lead with 96 and stop.

IMPORTANT: this is NOT the narration path. The server returns ONLY the structured
objects; narration is Claude Desktop's job at runtime. The narrate functions
below are hand-written stand-ins, derived only from the structured fields. Do not
wire them into the server.

Run:  .venv/bin/python examples/demo_goalie.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.adjudicate import adjudicate_claim  # noqa: E402
from engine.assess import assess_player  # noqa: E402
from engine.common import ordinal  # noqa: E402
from engine.compare import compare_players  # noqa: E402
from schemas import GoalieCard, SkaterCard  # noqa: E402

FX = REPO / "tests" / "fixtures"


def _goalie(name):
    return GoalieCard(**json.loads((FX / name).read_text()))


def _skater(name):
    return SkaterCard(**json.loads((FX / name).read_text()))


def _article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def narrate_assessment(a):
    """Stand-in for Claude Desktop's narration — derived only from the GoalieAssessment."""
    context = f"{a.team}, {a.role}" if a.team else a.role
    out = [
        f"{a.name} ({context}) projects as {_article(a.overall_tier)} "
        f"{a.overall_tier.lower()} starter — {ordinal(a.overall_percentile)} in projected WAR."
    ]
    if a.overall_note:
        out.append(a.overall_note)
    if a.strengths:
        out.append("Strengths: " + ", ".join(f"{s.label.lower()} ({ordinal(s.percentile)})" for s in a.strengths) + ".")
    out.append("Danger split — " + a.danger_profile.shape)
    out.append("Start quality — " + a.start_quality_profile.shape)
    if a.weaknesses:
        out.append("Soft spots: " + ", ".join(f"{w.label.lower()} ({ordinal(w.percentile)})" for w in a.weaknesses) + ".")
    out.append("Volatility — " + a.consistency.note)
    if a.trajectory:
        out.append("Trajectory — " + a.trajectory)
    out.append("")
    out.append("Bottom line: " + a.summary)
    return "\n".join(out)


LEAD = {
    "supported": "True",
    "not_supported": "Not really",
    "partial": "Partly",
    "unverifiable": "Can't tell from this card",
}


def narrate_claim(adj):
    out = []
    for v in adj.verdicts:
        out.append(f"- {LEAD[v.grade]} — “{v.text or v.dimension}”: {v.reason}")
    out.append("Bottom line: " + adj.overall)
    return "\n".join(out)


def main():
    thompson = _goalie("thompson.json")

    print("=" * 78)
    print("THOMPSON ASSESSMENT — top-tier starter, or riding a hot streak? (both true)")
    print("=" * 78)
    a = assess_player(thompson)
    print("\n--- STRUCTURED (what the server returns) ---")
    print(a.model_dump_json(indent=2))
    print("\n--- NARRATED (illustration of what Claude Desktop would say) ---")
    print(narrate_assessment(a))

    print("\n")
    print("=" * 78)
    print("GOALIE CLAIM — mixes supported / refuted / unverifiable style claim")
    print("=" * 78)
    claim = [
        {"dimension": "reliability", "direction": "high", "text": "gives you a chance every night"},
        {"dimension": "game_stealer", "direction": "high", "text": "robs people / steals games"},
        {"dimension": "goalie_rebounds", "direction": "high", "text": "controls his rebounds"},
        {"dimension": "goalie_style", "direction": "high", "text": "plays really deep in his net"},
    ]
    adj = adjudicate_claim(thompson, claim)
    print("\n--- STRUCTURED ---")
    print(adj.model_dump_json(indent=2))
    print("\n--- NARRATED ---")
    print(narrate_claim(adj))

    print("\n")
    print("=" * 78)
    print("GOALIE COMPARE")
    print("=" * 78)
    split = compare_players(_goalie("compare_goalie_peak.json"), _goalie("compare_goalie_floor.json"))
    cross = compare_players(thompson, _skater("celebrini.json"))
    print(f"Goalie vs goalie -> edge={split.overall_edge} ({split.edge_kind}): {split.overall}")
    print(f"Goalie vs skater -> compatible={cross.compatible} ({cross.edge_kind}): {cross.overall}")


if __name__ == "__main__":
    main()
