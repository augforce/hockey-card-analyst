"""Engine result -> report HTML/PDF.

The context builders here are the view-model adapters: verdict headline
wording, the tone rule, and weakness merging all live in this module, so
every report kind phrases and colors the same verdict the same way.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from engine.common import ordinal
from reports.pdf import html_to_pdf

_TEMPLATES = Path(__file__).parent / "templates"
_FONTS_DIR = Path(__file__).parent / "fonts"

REPORT_KINDS = frozenset(
    {"assess_skater", "assess_goalie", "assess_micro", "compare", "claim_check", "interpretive"}
)

KIND_LABELS = {
    "assess_skater": "Player assessment",
    "assess_goalie": "Goalie assessment",
    "assess_micro": "Microstat assessment",
    "compare": "Head-to-head comparison",
    "claim_check": "Claim check",
    "interpretive": "Interpretive read",
}

# Light-theme status colors and the tone rule the templates color by.
STATUS_COLORS = {
    "supported": "#16a34a",
    "not_supported": "#dc2626",
    "partial": "#d97706",
    "unverifiable": "#7c8aa0",
}
TONE_COLORS = {
    "positive": "#16a34a",
    "negative": "#dc2626",
    "mixed": "#d97706",
    "neutral": "#2563eb",
}
GRADE_STATUS = {
    "supported": "SUPPORTED",
    "not_supported": "NOT SUPPORTED",
    "partial": "PARTIAL",
    "unverifiable": "UNVERIFIABLE",
}

# Latin subsets of the bundled fonts (OFL-licensed), shipped in
# reports/fonts so the module is self-contained.
_FONT_FACES = [
    ("IBM Plex Sans", 400, "fbaf1018-fca7-4d33-b711-3a53a3042aa5.woff2"),
    ("IBM Plex Mono", 400, "128d07ea-2201-4937-9d97-42221a8b222a.woff2"),
    ("IBM Plex Mono", 500, "a8db3202-11c5-4d2b-af3f-e7febf10e022.woff2"),
    ("Sora", 700, "546c261b-3d82-41dd-a96e-2dfd7ef7349e.woff2"),
]

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(kind: str, result: Any, title: Optional[str] = None) -> str:
    """Render one report kind to a self-contained HTML document."""
    if kind not in REPORT_KINDS:
        raise ValueError(
            f"Unknown report kind {kind!r} — expected one of {sorted(REPORT_KINDS)}."
        )
    data = _as_dict(result)
    context = _BUILDERS[kind](data)
    context.update(
        kind=kind,
        kind_label=KIND_LABELS[kind],
        title=title or context.get("default_title", KIND_LABELS[kind]),
        interpretive=(kind == "interpretive"),
        generated=datetime.date.today().isoformat(),
        font_faces=_font_faces(),
    )
    return _env.get_template(f"{kind}.html").render(**context)


def render_pdf(kind: str, result: Any, title: Optional[str] = None) -> bytes:
    return html_to_pdf(render_html(kind, result, title))


def _as_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    raise ValueError(f"result must be an engine output model or dict, got {type(result).__name__}")


def _font_faces() -> list[dict[str, Any]]:
    faces = []
    for family, weight, filename in _FONT_FACES:
        path = _FONTS_DIR / filename
        if path.is_file():  # missing fonts degrade to system stacks, not errors
            faces.append({"family": family, "weight": weight, "url": path.as_uri()})
    return faces


def _tone_from_pct(pct: int) -> str:
    return "positive" if pct >= 70 else "negative" if pct <= 44 else "mixed"


def _tone(tone: str) -> dict[str, str]:
    color = TONE_COLORS.get(tone, TONE_COLORS["neutral"])
    return {"tone": tone, "tone_color": color}


def _bar_reads(reads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": r["label"],
            "value": r["percentile"],
            "tier": r.get("tier"),
            "note": r.get("note"),
        }
        for r in reads
    ]


def _merged_weakness(weaknesses: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Port of assessToUI: worst weakness leads, the rest fold into its note."""
    if not weaknesses:
        return None
    ordered = sorted(weaknesses, key=lambda w: w["percentile"])
    worst, rest = ordered[0], ordered[1:]
    note = worst.get("note") or ""
    if rest:
        extra = ", ".join(f"{w['label']} ({ordinal(w['percentile'])})" for w in rest)
        note = f"{note} Also below the line: {extra}.".strip()
    return {
        "label": worst["label"],
        "value": worst["percentile"],
        "tag": worst["tier"],
        "note": note,
    }


def _trajectory(text: Optional[str]) -> Optional[dict[str, str]]:
    if not text:
        return None
    direction = "up" if re.search(r"up|ris", text, re.I) else \
        "down" if re.search(r"down|fall|slid", text, re.I) else "flat"
    color = {"up": "#16a34a", "down": "#dc2626", "flat": "#51617a"}[direction]
    return {"text": text, "direction": direction, "color": color}


# --- assess (skater) ---------------------------------------------------------


def _build_assess_skater(a: dict[str, Any]) -> dict[str, Any]:
    kind_word = "defenseman" if a.get("position") == "D" else "forward"
    strengths = _bar_reads(a.get("strengths", []))
    compression = a.get("overall_note") or next(
        (s["note"] for s in strengths if s.get("note")), None
    )
    return {
        **_tone(_tone_from_pct(a["overall_percentile"])),
        "default_title": a["name"],
        "player_line": " · ".join(filter(None, [a.get("team"), a.get("position")])),
        "headline": f"{a['overall_tier']} {kind_word}",
        "verdict_line": f"{ordinal(a['overall_percentile'])} percentile projected WAR.",
        "pct": a["overall_percentile"],
        "strengths": strengths,
        "compression_note": compression,
        "weakness": _merged_weakness(a.get("weaknesses", [])),
        "descriptive": _bar_reads(a.get("descriptive", [])),
        "profile": a.get("scoring_profile"),
        "trajectory": _trajectory(a.get("trajectory")),
        "deployment": a.get("deployment", []),
        "caveats": a.get("caveats", []),
        "summary": a["summary"],
        "micro_insights": a.get("micro_insights"),
    }


# --- assess (microstat card) -------------------------------------------------


def _build_assess_micro(a: dict[str, Any]) -> dict[str, Any]:
    kind_word = "defenseman" if a.get("position") == "D" else "forward"
    return {
        **_tone("neutral"),
        "default_title": a["name"],
        "player_line": " · ".join(
            filter(None, [a.get("team"), a.get("position"), f"{a['season']} microstats"])
        ),
        "headline": f"Microstat profile — {kind_word}, {a['season']}",
        "verdict_line": None,
        "overall_note": a.get("overall_note"),
        "strengths": _bar_reads(a.get("strengths", [])),
        "weakness": _merged_weakness(a.get("weaknesses", [])),
        "descriptive": _bar_reads(a.get("descriptive", [])),
        "profiles": [
            {"label": p["label"], "note": p["note"], "reads": _bar_reads(p["reads"])}
            for p in a.get("profiles", [])
        ],
        "micro_highs": _bar_reads(a.get("micro_highs", [])),
        "micro_lows": _bar_reads(a.get("micro_lows", [])),
        "style_reads": _bar_reads(a.get("style_reads", [])),
        "deployment": a.get("deployment", []),
        "caveats": a.get("caveats", []),
        "summary": a["summary"],
    }


# --- assess (goalie) ---------------------------------------------------------


def _build_assess_goalie(a: dict[str, Any]) -> dict[str, Any]:
    def profile(p):
        return {"label": p["label"], "shape": p["shape"], "reads": _bar_reads(p["reads"])}

    return {
        **_tone(_tone_from_pct(a["overall_percentile"])),
        "default_title": a["name"],
        "player_line": " · ".join(filter(None, [a.get("team"), a.get("role")])),
        "headline": f"{a['overall_tier']} goaltender",
        "verdict_line": f"{ordinal(a['overall_percentile'])} percentile projected WAR.",
        "pct": a["overall_percentile"],
        "compression_note": a.get("overall_note"),
        "danger_profile": profile(a["danger_profile"]),
        "start_quality_profile": profile(a["start_quality_profile"]),
        "strengths": _bar_reads(a.get("strengths", [])),
        "weakness": _merged_weakness(a.get("weaknesses", [])),
        "consistency": a.get("consistency"),
        "workload": a.get("workload"),
        "trajectory": _trajectory(a.get("trajectory")),
        "caveats": a.get("caveats", []),
        "summary": a["summary"],
    }


# --- compare -------------------------------------------------------------------


def _build_compare(c: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for comp in c.get("components", []):
        gap = comp.get("gap")
        rows.append(
            {
                "label": comp["label"],
                "a_value": comp.get("a_value"),
                "b_value": comp.get("b_value"),
                "a_leads": comp.get("leader") == "A",
                "b_leads": comp.get("leader") == "B",
                "gap_text": (
                    "NA" if gap is None else "even" if gap == 0 else f"{gap:+d}"
                ),
                "note": comp.get("note"),
            }
        )
    edge_kind = c.get("edge_kind", "even")
    tone = "neutral" if c.get("overall_edge") else ("mixed" if edge_kind == "split" else "neutral")
    overall = c.get("overall", "")
    durability = c.get("durability")
    if durability and durability in overall:  # engine folds durability into overall
        durability = None
    return {
        **_tone(tone),
        "default_title": f"{c['a_name']} vs {c['b_name']}",
        "a_name": c["a_name"],
        "b_name": c["b_name"],
        "pool": c.get("pool"),
        "focus": c.get("focus"),
        "rows": rows,
        "overall": overall,
        "edge_kind": edge_kind,
        "split": edge_kind == "split",
        "durability": durability,
        "caveats": c.get("caveats", []),
        "incompatible_reason": c.get("reason"),
        "compatible": c.get("compatible", True),
    }


# --- claim check ----------------------------------------------------------------


def _build_claim_check(adj: dict[str, Any]) -> dict[str, Any]:
    verdicts = adj.get("verdicts", [])
    counts = {g: 0 for g in GRADE_STATUS}
    for v in verdicts:
        counts[v["grade"]] = counts.get(v["grade"], 0) + 1
    # Port of adjudicationToUI's overall wording + tone.
    if counts["supported"] and counts["not_supported"]:
        headline, tone = "Half-right.", "mixed"
    elif counts["supported"] and not counts["not_supported"] and not counts["partial"]:
        headline, tone = "Supported.", "positive"
    elif counts["not_supported"] and not counts["supported"]:
        headline, tone = "Not supported.", "negative"
    elif counts["partial"]:
        headline, tone = "Partly right.", "mixed"
    else:
        headline, tone = "The card can’t see this.", "neutral"
    rows = []
    for v in verdicts:
        receipt = None
        if v.get("value") is not None:
            receipt = ordinal(v["value"])
            if v.get("tier"):
                receipt += f" · {v['tier']}"
        rows.append(
            {
                "claim": f"“{v['text']}”" if v.get("text") else v["dimension"],
                "status": GRADE_STATUS.get(v["grade"], v["grade"].upper()),
                "color": STATUS_COLORS.get(v["grade"], STATUS_COLORS["unverifiable"]),
                "receipt": receipt,
                "evidence": v["reason"] + (f" — {v['caveat']}" if v.get("caveat") else ""),
            }
        )
    return {
        **_tone(tone),
        "default_title": "Claim check",
        "headline": headline,
        "rows": rows,
        "overall": adj.get("overall", ""),
    }


# --- interpretive ------------------------------------------------------------------

# The interpretive result is Claude-authored, so its text can arrive with
# markdown in it (**bold**, bullet lines). The PDF must never show those
# characters literally: escape the text first, then convert the few inline
# marks to real styling and bullet lines to real lists.

_MD_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_MD_EM = re.compile(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])|(?<![\w_])_([^_\n]+?)_(?![\w_])")
_MD_CODE = re.compile(r"`([^`\n]+)`")
_MD_BULLET = re.compile(r"^\s*(?:[-*+•‣·]|\d+[.)])\s+")
_MD_HEADING = re.compile(r"^#{1,6}\s+")


def _md_inline(text: Optional[str]) -> Optional[Markup]:
    """Escape, then style inline markdown; stray bullet/heading marks drop."""
    if text is None:
        return None
    s = _MD_HEADING.sub("", _MD_BULLET.sub("", str(text).strip()))
    s = str(escape(s))
    s = _MD_BOLD.sub(lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", s)
    s = _MD_EM.sub(lambda m: f"<em>{m.group(1) or m.group(2)}</em>", s)
    s = _MD_CODE.sub(r"\1", s)
    return Markup(s)


def _md_blocks(text: str) -> Markup:
    """Paragraphs and bullet lines -> real <p>/<ul> blocks, inline-styled."""
    out: list[str] = []
    para: list[str] = []
    bullets: list[str] = []

    def flush_para():
        if para:
            out.append(f"<p>{_md_inline(' '.join(para))}</p>")
            para.clear()

    def flush_bullets():
        if bullets:
            items = "".join(f"<li>{_md_inline(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            flush_para()
            flush_bullets()
        elif _MD_BULLET.match(line):
            flush_para()
            bullets.append(_MD_BULLET.sub("", line))
        elif _MD_HEADING.match(line):
            flush_para()
            flush_bullets()
            out.append(f"<p><strong>{_md_inline(line)}</strong></p>")
        else:
            flush_bullets()
            para.append(line)
    flush_para()
    flush_bullets()
    return Markup("".join(out))


def _build_interpretive(r: dict[str, Any]) -> dict[str, Any]:
    sections = r.get("sections") or []
    units = r.get("units") or []
    if not sections and not units:
        raise ValueError(
            "interpretive result needs 'units' (structured per-unit reads) "
            "and/or a non-empty 'sections' list of {heading?, body}."
        )
    if not all(isinstance(s, dict) and s.get("body") for s in sections):
        raise ValueError(
            "each interpretive section needs a non-empty 'body' ({heading?, body})."
        )
    return {
        **_tone(r.get("tone", "neutral")),
        "default_title": r.get("title", "Interpretive read"),
        "subtitle": r.get("subtitle"),
        "players": r.get("players", []),
        "units": [
            {
                "name": _md_inline(u["name"]),
                "players": [
                    {
                        "name": _md_inline(p["name"]),
                        "read": _md_inline(p["read"]),
                        "key_numbers": _md_inline(p.get("key_numbers")),
                    }
                    for p in u.get("players") or []
                ],
                "works": [_md_inline(w) for w in u.get("works") or []],
                "concerns": [_md_inline(c) for c in u.get("concerns") or []],
            }
            for u in units
        ],
        "sections": [
            {"heading": _md_inline(s.get("heading")), "body": _md_blocks(s["body"])}
            for s in sections
        ],
        "caveat": _md_inline(r.get("caveat")),
        "summary": _md_inline(r.get("summary")),
    }


_BUILDERS = {
    "assess_skater": _build_assess_skater,
    "assess_goalie": _build_assess_goalie,
    "assess_micro": _build_assess_micro,
    "compare": _build_compare,
    "claim_check": _build_claim_check,
    "interpretive": _build_interpretive,
}
