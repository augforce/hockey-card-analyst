"""ILLUSTRATIVE DEMO - NOT SERVER CODE.

Renders the structured `compare_players()` output AND the plain-English answer a
human (Claude Desktop) would narrate from it. The headline is the GENUINE SPLIT
case: two forwards who are close, one better on offense, the other on defense,
with level projected WAR. The point is to read whether compare says "here's the
tradeoff" instead of pretending the numbers settled it. The clear-winner and
cross-position cases are printed briefly for contrast.

IMPORTANT: this is NOT the narration path. The server returns ONLY the structured
`Comparison`; narration is Claude Desktop's job at runtime. `narrate()` below is a
hand-written stand-in, derived only from the structured fields. Do not wire it
into the server.

Run:  .venv/bin/python examples/demo_compare.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.compare import compare_players  # noqa: E402
from schemas import DefenseCard, SkaterCard  # noqa: E402

FX = REPO / "tests" / "fixtures"


def _skater(name):
    return SkaterCard(**json.loads((FX / name).read_text()))


def _defense(name):
    return DefenseCard(**json.loads((FX / name).read_text()))


def narrate(cmp):
    """Stand-in for Claude Desktop's narration - derived only from the Comparison."""
    if not cmp.compatible:
        return f"Can't compare these two: {cmp.reason}"
    out = [f"{cmp.a_name} vs {cmp.b_name} - both {cmp.pool}s, so the percentile pools line up."]
    out.append("Component by component:")
    for c in cmp.components:
        if c.leader is None:
            out.append(f"  - {c.label}: {c.note}")
        elif c.leader == "tie":
            out.append(f"  - {c.label}: even ({c.a_value} vs {c.b_value})")
        else:
            who = cmp.a_name if c.leader == "A" else cmp.b_name
            out.append(f"  - {c.label}: {who} by {abs(c.gap)} ({c.a_value} vs {c.b_value})")
    out.append("")
    out.append("Verdict: " + cmp.overall)
    if cmp.durability and cmp.durability not in cmp.overall:
        out.append(cmp.durability)
    if cmp.caveats:
        out.append("Caveat: " + " ".join(cmp.caveats))
    return "\n".join(out)


def main():
    split = compare_players(
        _skater("compare_split_sniper.json"), _skater("compare_split_shutdown.json")
    )
    print("=" * 78)
    print("GENUINE SPLIT (the case to read) - does it refuse to crown a winner?")
    print("=" * 78)
    print("\n--- STRUCTURED (what the server returns) ---")
    print(split.model_dump_json(indent=2))
    print("\n--- NARRATED (illustration of what Claude Desktop would say) ---")
    print(narrate(split))

    print("\n")
    clear = compare_players(
        _skater("compare_clear_leader.json"), _skater("compare_clear_trailer.json")
    )
    cross = compare_players(_skater("celebrini.json"), _defense("synthetic_dman.json"))
    print("=" * 78)
    print("FOR CONTRAST")
    print("=" * 78)
    print(f"Clear winner   -> edge={clear.overall_edge} ({clear.edge_kind}): {clear.overall}")
    print(f"Cross-position -> compatible={cross.compatible} ({cross.edge_kind}): {cross.overall}")


if __name__ == "__main__":
    main()
