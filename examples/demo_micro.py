"""ILLUSTRATIVE DEMO - NOT SERVER CODE.

Narration stand-in for the microstat-card paths: a micro assessment on its own
(forward and defenseman), and the both-cards synthesis attached to a standard
assessment. Same rule as every demo: the server returns ONLY structured data;
the `narrate_*` functions below are hand-written stand-ins for Claude Desktop,
derived purely from the structured fields. Do not import this from the server.

Run:  .venv/bin/python examples/demo_micro.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from engine.assess import assess_player  # noqa: E402
from schemas import DefenseMicroCard, ForwardMicroCard, SkaterCard  # noqa: E402

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


def narrate_micro(a):
    """Stand-in narration derived only from the MicroAssessment."""
    pos = "defenseman" if a.position == "D" else "forward"
    who = a.name
    out = [f"{who}'s {a.season} microstat card, read as a {pos}."]
    out.append(a.overall_note)
    if a.strengths:
        out.append(
            "This season's value drivers on the WAR row: "
            + "; ".join(phrase(r) for r in a.strengths) + "."
        )
    if a.weaknesses:
        out.append("WAR-row soft spots: " + "; ".join(phrase(r) for r in a.weaknesses) + ".")
    for d in a.descriptive:
        if d.note:
            out.append(f"{phrase(d).capitalize()} - but {d.note[0].lower()}{d.note[1:]}")
    for p in a.profiles:
        nums = ", ".join(f"{r.label.lower()} {ordinal(r.percentile)}" for r in p.reads)
        out.append(f"{p.label} ({nums}). {p.note}")
    if a.micro_highs:
        out.append(
            "Tracked standouts: "
            + ", ".join(phrase(r) for r in a.micro_highs[:5])
            + (" - descriptive shape, not the value verdict." )
        )
    if a.micro_lows:
        out.append(
            "Tracked soft spots: " + ", ".join(phrase(r) for r in a.micro_lows) + "."
        )
    if a.style_reads:
        nums = ", ".join(f"{r.label.lower()} {ordinal(r.percentile)}" for r in a.style_reads)
        out.append(f"Style reads ({nums}) - how he plays, never a value weakness.")
    if a.deployment:
        out.append(" ".join(a.deployment))
    if a.caveats:
        out.append("Honest caveats. " + "  ".join(a.caveats))
    return " ".join(out)


def narrate_synthesis(a):
    """Stand-in narration for the micro_insights block on a standard assessment."""
    syn = a.micro_insights
    out = [
        f"Reading {a.name}'s {syn.season} microstat card against the standard "
        f"card's verdict (which is unchanged: {a.overall_tier.lower()}, "
        f"{ordinal(a.overall_percentile)} percentile projected WAR):"
    ]
    out.extend(syn.divergences)
    out.extend(syn.insights)
    out.append(syn.note)
    return " ".join(out)


def show(title, body):
    print("=" * 78)
    print(title)
    print("=" * 78)
    print(body)
    print()


if __name__ == "__main__":
    celebrini_micro = ForwardMicroCard(**_load("celebrini_micro.json"))
    schaefer_micro = DefenseMicroCard(**_load("schaefer_micro.json"))
    celebrini_std = SkaterCard(**_load("celebrini.json"))

    a = assess_player(celebrini_micro)
    show("CELEBRINI MICRO (forward) - STRUCTURED", a.model_dump_json(indent=2))
    show("CELEBRINI MICRO (forward) - NARRATED", narrate_micro(a))

    d = assess_player(schaefer_micro)
    show("SCHAEFER MICRO (defenseman) - NARRATED", narrate_micro(d))

    combined = assess_player(celebrini_std, micro_card=celebrini_micro)
    show("CELEBRINI BOTH CARDS - SYNTHESIS NARRATED", narrate_synthesis(combined))
