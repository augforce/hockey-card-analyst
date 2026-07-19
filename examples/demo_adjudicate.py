"""ILLUSTRATIVE DEMO - NOT SERVER CODE.

Renders the structured `adjudicate_claim()` output AND the plain-English answer a
human (Claude Desktop) would narrate from it, for the PLAN section 3 four-part
claim run on Celebrini. It's the window into whether the *judgment reads
honestly*; re-run it after later phases touch the engine.

IMPORTANT: this is NOT the narration path. The server returns ONLY the structured
`Adjudication`; Claude Desktop decomposes the claim and writes the prose at
runtime. `narrate()` below is a hand-written stand-in, derived only from the
structured verdicts. Do not wire it into the server.

Run:  .venv/bin/python examples/demo_adjudicate.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.adjudicate import adjudicate_claim  # noqa: E402
from schemas import SkaterCard  # noqa: E402

FX = REPO / "tests" / "fixtures"

# What a fan said. Claude Desktop would decompose this into the assertions below;
# the server only grades them.
CLAIM = (
    "He sits in front of the net and scores goals - you'll love him unless he's "
    "asked to do more, and he's probably your leading scorer next season."
)
ASSERTIONS = [
    {"dimension": "finishing", "direction": "high", "text": "scores goals"},
    {"dimension": "playmaking", "direction": "low", "text": "limited if asked to do more"},
    {"dimension": "two_way", "direction": "low", "text": "limited if asked to do more (defense)"},
    {"dimension": "net_front", "direction": "high", "text": "sits in front of the net"},
    {"dimension": "team_leading_scorer", "direction": "high", "text": "leading scorer next season"},
]

LEAD = {
    "supported": "True",
    "not_supported": "Not really",
    "partial": "Partly",
    "unverifiable": "Can't tell from this card",
}


def narrate(adj):
    """Stand-in for Claude Desktop's narration - derived only from the verdicts."""
    out = ["Here's what the card actually says, piece by piece."]
    for v in adj.verdicts:
        piece = v.text or v.dimension
        out.append(f"- {LEAD[v.grade]} - “{piece}”: {v.reason}")
        if v.caveat:
            out.append(f"    (Caveat: {v.caveat})")
    out.append("")
    out.append("Bottom line: " + adj.overall)
    return "\n".join(out)


def main():
    card = SkaterCard(**json.loads((FX / "celebrini.json").read_text()))
    adj = adjudicate_claim(card, ASSERTIONS)

    print("=" * 78)
    print("CLAIM:", CLAIM)
    print("=" * 78)
    print("\n--- STRUCTURED (what the server returns) ---")
    print(adj.model_dump_json(indent=2))
    print("\n--- NARRATED (illustration of what Claude Desktop would say) ---")
    print(narrate(adj))


if __name__ == "__main__":
    main()
