"""adjudicate_claim for skaters (PLAN sections 3, 6, 7).

Division of labor: the server does NOT parse natural language. Claude Desktop
decomposes a claim into structured assertions ({dimension, direction}); this
module grades each one against the card and returns a verdict with the cited
metric value and a one-line reason, plus an overall read.

Grades:
- supported     — the metric agrees with the claimed direction.
- not_supported — the metric contradicts the claimed direction (number is the receipt).
- partial       — the card half-answers it (team-relative, or right direction but middling).
- unverifiable  — the card cannot see it (net-front, playing style, team context,
                  an NA role, or an unknown dimension). First-class, never a guess.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel
from typing import Literal

from config import load_config
from engine.common import LABELS, STRENGTH_MIN, WEAKNESS_MAX, ordinal
from engine.tiers import classify_percentile
from schemas import DefenseCard, DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

SkaterLike = Union[SkaterCard, DefenseCard]
MicroLike = Union[ForwardMicroCard, DefenseMicroCard]
CardLike = Union[SkaterCard, DefenseCard, GoalieCard, ForwardMicroCard, DefenseMicroCard]

# The other card type the same player could supply. Used to answer honestly
# when a claim's metric isn't on the supplied card: name the counterpart only
# when it actually carries the box. Goalies have no counterpart (no goalie
# microstat card exists).
_COUNTERPARTS = {
    SkaterCard: ForwardMicroCard,
    ForwardMicroCard: SkaterCard,
    DefenseCard: DefenseMicroCard,
    DefenseMicroCard: DefenseCard,
}

Grade = Literal["supported", "partial", "not_supported", "unverifiable"]


class Assertion(BaseModel):
    """One decomposed piece of a claim (Claude Desktop produces these)."""

    dimension: str
    direction: Literal["high", "low"]
    text: Optional[str] = None  # the original phrase, echoed back for narration


class AssertionVerdict(BaseModel):
    """The grade for one assertion, with its evidence."""

    dimension: str
    direction: str
    grade: Grade
    metric: Optional[str] = None
    value: Optional[int] = None
    tier: Optional[str] = None
    reason: str
    caveat: Optional[str] = None
    text: Optional[str] = None


class Adjudication(BaseModel):
    """The full read on a claim: per-assertion verdicts plus an overall."""

    verdicts: list[AssertionVerdict]
    overall: str


def adjudicate_claim(
    card: CardLike,
    assertions: list[Union[Assertion, dict]],
    config: Optional[dict[str, Any]] = None,
) -> Adjudication:
    """Grade each decomposed assertion against the card (skater, goalie, or
    microstat)."""
    cfg = config if config is not None else load_config()
    verdicts = [_grade(card, _as_assertion(a), cfg) for a in assertions]
    overall = _overall(verdicts)
    if isinstance(card, (ForwardMicroCard, DefenseMicroCard)):
        overall += (
            " Verdicts come from one season of tracked data (5v5, per 60) — "
            "shape, not a settled level."
        )
    return Adjudication(verdicts=verdicts, overall=overall)


def _as_assertion(a: Union[Assertion, dict]) -> Assertion:
    return a if isinstance(a, Assertion) else Assertion(**a)


def _claim_pool(card: CardLike) -> str:
    """The dimension-dictionary pool a card belongs to (matches `applies_to`)."""
    if isinstance(card, GoalieCard):
        return "goalie"
    if isinstance(card, (ForwardMicroCard, DefenseMicroCard)):
        return "micro"
    return "skater"


def _resolve(dimension: str, cfg: dict[str, Any], pool: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Find a dimension entry by id, then by alias. On an alias collision, prefer
    the entry whose `applies_to` matches the card's pool (e.g. goalie vs skater
    'shorthanded')."""
    key = dimension.strip().lower()
    dims = cfg.get("dimensions", [])
    for entry in dims:
        if entry["id"].lower() == key:
            return entry
    alias_matches = [e for e in dims if key in [a.lower() for a in e.get("aliases", [])]]
    if not alias_matches:
        return None
    if pool:
        for entry in alias_matches:
            if entry.get("applies_to") in (pool, "both"):
                return entry
    return alias_matches[0]


def _primary_metric(card: CardLike, entry: dict[str, Any]):
    """First card metric on the entry that has a value. Fallback prefers a
    metric that at least exists on this card type (an NA role) over one the
    card type doesn't carry at all — the two get different honest messages."""
    metrics = entry.get("metrics", []) or []
    for metric in metrics:
        if getattr(card, metric, None) is not None:
            return metric, getattr(card, metric)
    for metric in metrics:
        if metric in type(card).model_fields:  # exists but NA
            return metric, None
    return (metrics[0] if metrics else None), None


def _grade(card: CardLike, assertion: Assertion, cfg: dict[str, Any]) -> AssertionVerdict:
    entry = _resolve(assertion.dimension, cfg, _claim_pool(card))

    def verdict(grade, metric=None, value=None, tier=None, reason="", caveat=None):
        return AssertionVerdict(
            dimension=(entry["id"] if entry else assertion.dimension),
            direction=assertion.direction,
            grade=grade,
            metric=metric,
            value=value,
            tier=tier,
            reason=reason,
            caveat=caveat,
            text=assertion.text,
        )

    if entry is None:
        return verdict(
            "unverifiable",
            reason=f"'{assertion.dimension}' is not a recognized card dimension — the card can't speak to it.",
        )

    answerability = entry.get("answerability", "answerable")

    # Things the card simply cannot see (net-front, playing style, ...).
    if answerability == "not_answerable":
        return verdict("unverifiable", reason=entry.get("note", "Not measured on a standard card."))

    metric, value = _primary_metric(card, entry)
    label = LABELS.get(metric, metric) if metric else "this"

    # Team-relative / context-dependent claims: half-answerable at best.
    if answerability == "partial":
        tier = classify_percentile(value, cfg).label if value is not None else None
        receipt = f"{label} is {ordinal(value)} ({tier})" if value is not None else "the card"
        note = entry.get("note", "Only partly answerable from the card.")
        note = note[0].lower() + note[1:] if note else note
        return verdict("partial", metric=metric, value=value, tier=tier, reason=f"{receipt}, but {note}")

    # Answerable, but no value on this card — we don't guess. Three honest
    # cases: the metric exists on this card type but is NA (a role absence);
    # the counterpart card type for this player genuinely carries it (say so);
    # or NO card type carries it for this position (say that instead — never
    # point at a card that lacks the box).
    if value is None:
        if metric and metric in type(card).model_fields:
            return verdict(
                "unverifiable",
                metric=metric,
                reason=f"{label} is NA on this card (no role) — the player isn't used there, so the card can't assess it.",
            )
        counterpart = _COUNTERPARTS.get(type(card))
        if counterpart is not None and metric and metric in counterpart.model_fields:
            other = "standard" if isinstance(card, (ForwardMicroCard, DefenseMicroCard)) else "microstat"
            return verdict(
                "unverifiable",
                metric=metric,
                reason=f"{label} isn't a box on this card type — the {other} card carries it.",
            )
        return verdict(
            "unverifiable",
            metric=metric,
            reason=f"{label} isn't tracked on either card type for this position — the cards can't assess it.",
        )

    tier = classify_percentile(value, cfg)
    grade = _direction_grade(assertion.direction, value)
    reason = _reason(label, assertion.direction, value, tier.label, grade)
    caveat = _caveat(entry, grade, cfg)
    return verdict(grade, metric=metric, value=value, tier=tier.label, reason=reason, caveat=caveat)


def _direction_grade(direction: str, value: int) -> Grade:
    if direction == "high":
        if value >= STRENGTH_MIN:
            return "supported"
        if value <= WEAKNESS_MAX:
            return "not_supported"
        return "partial"
    # direction == "low"
    if value <= WEAKNESS_MAX:
        return "supported"
    if value >= STRENGTH_MIN:
        return "not_supported"
    return "partial"


def _reason(label: str, direction: str, value: int, tier: str, grade: Grade) -> str:
    claimed = "high" if direction == "high" else "low"
    receipt = f"{label} is {ordinal(value)} ({tier})"
    if grade == "supported":
        return f"{receipt} — backs a '{claimed}' claim."
    if grade == "not_supported":
        opposite = "strong" if direction == "low" else "weak"
        return f"Claim says {claimed}, but {receipt} — the card says the opposite ({opposite} side)."
    return f"{receipt} — only middling, so a '{claimed}' claim is overstated."


def _caveat(entry: dict[str, Any], grade: Grade, cfg: dict[str, Any]) -> Optional[str]:
    key = entry.get("caveat")
    if not key:
        return None
    caveats = cfg.get("caveats", {})
    # Dangerous-passing only matters when playmaking is borderline (partial).
    if key == "dangerous_passing":
        return caveats.get(key) if grade == "partial" else None
    # Style-not-value rides along on EVERY grade: refuting "he's physical" with
    # a low Hits number needs the reminder that style is not a value weakness.
    if key == "micro_style_not_value":
        return caveats.get(key)
    # Finishing-volatility / deployment-not-value: when the verdict leans on it.
    if grade in ("supported", "partial"):
        return caveats.get(key)
    return None


def _overall(verdicts: list[AssertionVerdict]) -> str:
    buckets: dict[str, list[str]] = {
        "supported": [],
        "not_supported": [],
        "partial": [],
        "unverifiable": [],
    }
    for v in verdicts:
        buckets[v.grade].append(v.text or v.dimension)

    parts = []
    if buckets["supported"]:
        parts.append("supports " + _join(buckets["supported"]))
    if buckets["not_supported"]:
        parts.append("refutes " + _join(buckets["not_supported"]))
    if buckets["partial"]:
        parts.append("only partly answers " + _join(buckets["partial"]))
    if buckets["unverifiable"]:
        parts.append("is unverifiable on " + _join(buckets["unverifiable"]))

    if not parts:
        return "No assertions to grade."

    head = ""
    if buckets["supported"] and buckets["not_supported"]:
        head = "Half-right claim. "
    return head + "This card " + "; ".join(parts) + "."


def _join(items: list[str]) -> str:
    items = [f"'{i}'" for i in items]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
