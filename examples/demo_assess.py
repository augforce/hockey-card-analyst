"""ILLUSTRATIVE DEMO — NOT SERVER CODE.

This script renders the plain-English paragraph a human (Claude Desktop) would
narrate from an `assess_player()` result, alongside the structured object the
server actually returns. It exists for ONE reason: everything the server returns
is structured data that nobody eyeballs, so this is the only window into whether
the *judgment reads honestly*. Keep one of these per phase; when a later phase
changes the engine, re-run it and check the prose still reads right.

IMPORTANT: this is NOT the narration path. The server returns ONLY the structured
`Assessment` (PLAN section 7); narration is Claude Desktop's job at runtime. The
`narrate()` function below is a hand-written stand-in for that, derived purely
from the structured fields. Do not import this from, or wire it into, the server.

Run:  .venv/bin/python examples/demo_assess.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.assess import assess_player  # noqa: E402
from schemas import DefenseCard, SkaterCard  # noqa: E402

FX = REPO / "tests" / "fixtures"


def _load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def phrase(read):
    return f"{read.tier.lower()} {read.label.lower()} ({ordinal(read.percentile)})"


def narrate(a):
    """Stand-in for Claude Desktop's narration — derived only from the Assessment."""
    pos = "defenseman" if a.position == "D" else "forward"
    plural = "defensemen" if a.position == "D" else "forwards"
    article = "an" if a.overall_tier[:1].lower() in "aeiou" else "a"
    shown = set()

    def once(note):
        if note and note not in shown:
            shown.add(note)
            return note
        return None

    out = [
        f"{a.name} ({a.team}) grades as {article} {a.overall_tier.lower()} {pos} — "
        f"{ordinal(a.overall_percentile)} percentile in projected WAR among {plural}."
    ]
    if once(a.overall_note):
        out.append(a.overall_note)
    if a.strengths:
        out.append("The value is built on " + "; ".join(phrase(r) for r in a.strengths) + ".")
        for r in a.strengths:
            if once(r.note):
                out.append(r.note)
    if a.descriptive:
        plain = [r for r in a.descriptive if not r.note]
        flagged = [r for r in a.descriptive if r.note]
        if plain:
            out.append("On the descriptive side: " + ", ".join(phrase(r) for r in plain) + ".")
        for r in flagged:
            if once(r.note):
                out.append(f"{phrase(r).capitalize()} — but {r.note[0].lower()}{r.note[1:]}")
            else:
                out.append(phrase(r).capitalize() + ".")
    if a.weaknesses:
        label = "soft spots" if len(a.weaknesses) > 1 else "soft spot"
        out.append(f"The {label}: " + "; ".join(phrase(r) for r in a.weaknesses) + ".")
    if a.scoring_profile:
        sp = a.scoring_profile
        out.append(
            f"Scoring profile — {sp.label.lower()}: EV offence {ordinal(sp.ev_offence)} "
            f"vs finishing {ordinal(sp.finishing)}. {sp.note}"
        )
    if a.deployment:
        out.append(" ".join(a.deployment))
    if a.trajectory:
        out.append(a.trajectory)
    if a.caveats:
        out.append("Honest caveats. " + "  ".join(a.caveats))
    return " ".join(out)


def show(title, card):
    a = assess_player(card)
    print("=" * 78)
    print(title)
    print("=" * 78)
    print("\n--- STRUCTURED (what the server returns) ---")
    print(a.model_dump_json(indent=2))
    print("\n--- NARRATED (illustration of what Claude Desktop would say) ---")
    print(narrate(a))
    print()


if __name__ == "__main__":
    show("CELEBRINI (forward) — golden fixture; scoring profile = both-high", SkaterCard(**_load("celebrini.json")))
    show("DOROFEYEV (forward) — scoring profile = negative-regression (conversion-led)", SkaterCard(**_load("dorofeyev.json")))
    show("SYNTHETIC D — finishing-exclusion proof; no scoring profile", DefenseCard(**_load("synthetic_dman.json")))
