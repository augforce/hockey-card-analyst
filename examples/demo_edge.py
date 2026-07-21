"""ILLUSTRATIVE DEMO - NOT SERVER CODE.

Narration stand-in for the NHL Edge vetting path: a goalie assessment vetted
against a real Edge page (Wedgewood corroborated, Vanecek's false 99th held to
descriptive), and the Hughes real+real golden pair plus the Miller tools
discipline for skaters. Same rule as every demo: the server returns ONLY
structured data; `narrate_vetting` below is a hand-written stand-in for Claude
Desktop, derived purely from the structured fields. Do not import this from
the server.

Run:  .venv/bin/python examples/demo_edge.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.assess import assess_player  # noqa: E402
from schemas import (  # noqa: E402
    DefenseCard,
    GoalieCard,
    GoalieEdgeCard,
    SkaterCard,
    SkaterEdgeCard,
)

FX = REPO / "tests" / "fixtures"


def _load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def narrate_vetting(a):
    """Stand-in narration derived only from the assessment + its edge_vetting."""
    v = a.edge_vetting
    out = [
        f"{a.name}: {a.summary}",
        f"Checked against his {v.season} NHL Edge page:",
    ]
    for c in v.corroborations:
        out.append(f"  [backs the card] {c}")
    for c in v.contradictions:
        out.append(f"  [tension] {c}")
    for d in v.descriptive:
        out.append(f"  [color only] {d}")
    out.append(f"  ({v.note})")
    out.append("  Caveats: " + " | ".join(v.caveats))
    return "\n".join(out)


def main():
    # --- Wedgewood: a strong goalie card, corroborated on the Edge page -----
    wedgewood = GoalieCard(
        name="Scott Wedgewood", age=33, role="Starter", proj_war_pct=85,
        even_strength=80, penalty_kill=60, high_danger=82, med_danger=70,
        low_danger=65, quality_starts=88, excellent_starts=70, bad_starts=75,
        rebound_control=60, consistency=55,
    )  # synthetic standard card - no real Wedgewood card in the fixture set
    print("=" * 72)
    print("GOALIE, CORROBORATED (synthetic standard card + real Edge page)")
    print("=" * 72)
    a = assess_player(wedgewood, edge_card=GoalieEdgeCard(**_load("wedgewood_edge.json")))
    print(narrate_vetting(a))

    # --- Vanecek: the false 99th stays descriptive --------------------------
    vanecek = GoalieCard(
        name="Vitek Vanecek", age=29, role="Backup", proj_war_pct=30,
        even_strength=35, penalty_kill=45, high_danger=40, med_danger=45,
        low_danger=50, quality_starts=30, excellent_starts=40, bad_starts=35,
        rebound_control=50, consistency=45,
    )  # synthetic
    print()
    print("=" * 72)
    print("GOALIE, TINY WORKLOAD (Vanecek's 99th-percentile goals against is")
    print("a games-played artifact - it must never surface as corroboration)")
    print("=" * 72)
    a = assess_player(vanecek, edge_card=GoalieEdgeCard(**_load("vanecek_edge.json")))
    print(narrate_vetting(a))

    # --- Hughes: the real+real golden pair ----------------------------------
    print()
    print("=" * 72)
    print("SKATER, REAL + REAL (Hughes card + Hughes Edge page)")
    print("=" * 72)
    a = assess_player(
        SkaterCard(**_load("hughes.json")),
        edge_card=SkaterEdgeCard(**_load("hughes_edge.json")),
    )
    print(narrate_vetting(a))

    # --- Miller: Makar-grade tools, ordinary offense ------------------------
    miller = DefenseCard(
        name="K'Andre Miller", position="D", age=25, ev_offense=55,
        ev_defense=75, pp=None, pk=70, finishing=35, penalties=50,
        proj_war_pct=65,
    )  # synthetic
    print()
    print("=" * 72)
    print("SKATER, TOOLS DISCIPLINE (Miller: near-Makar tools, ordinary")
    print("offense - the tools stay color, only the defense strength vets)")
    print("=" * 72)
    a = assess_player(miller, edge_card=SkaterEdgeCard(**_load("miller_edge.json")))
    print(narrate_vetting(a))


if __name__ == "__main__":
    main()
