"""explain_metric — a thin lookup over the metric glossary (skater + goalie).

It DEFINES a card metric: what it measures, plus the single most important
interpretive caveat for it. It deliberately does NOT reason about any player — a
"why is this a risk for him" question is for the host model to answer from these
definitions plus the player's assessment, not for this tool to compute.

The glossary (config/glossary.yaml) is the single source of metric meaning. Where
a metric's key caveat is one the engine already attaches elsewhere (finishing
volatility, goalie consistency, deployment, dangerous passing, rebound control),
the glossary entry references it via `caveat_ref` rather than retyping it, so the
sentence lives in exactly one place.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from config import load_config, load_glossary
from engine.common import LABELS


class MetricExplanation(BaseModel):
    """What explain_metric returns: a definition + the one key caveat, or a clear
    not-found message. `query` echoes what was asked; `metric` is the canonical
    schema field name when resolved."""

    query: str
    found: bool
    metric: Optional[str] = None
    label: Optional[str] = None
    definition: Optional[str] = None
    caveat: Optional[str] = None
    message: Optional[str] = None


def _normalize(text: str) -> str:
    """Fold a query to a canonical lookup key: lowercase, strip surrounding
    quotes/space, unify separators, and normalize American spellings to the
    card's British ones (defense -> defence, offense -> offence)."""
    key = text.strip().strip("\"'").lower()
    for ch in ("_", "-", "/"):
        key = key.replace(ch, " ")
    key = " ".join(key.split())
    return key.replace("offense", "offence").replace("defense", "defence")


def _alias_index(glossary: dict[str, Any]) -> dict[str, str]:
    """Map every normalized lookup key (canonical field name + aliases) to its
    metric. Raises on a collision — two metrics must never claim the same key, or
    the lookup would silently mislead."""
    index: dict[str, str] = {}
    for metric, entry in glossary["metrics"].items():
        keys = [metric] + list(entry.get("aliases", []))
        for raw in keys:
            norm = _normalize(raw)
            if norm in index and index[norm] != metric:
                raise ValueError(
                    f"glossary alias collision: '{norm}' maps to both "
                    f"'{index[norm]}' and '{metric}'"
                )
            index[norm] = metric
    return index


def _resolve_caveat(entry: dict[str, Any], cfg: dict[str, Any]) -> str:
    """Return the entry's caveat — inline text, or the canonical sentence pointed
    at by `caveat_ref` (a dotted path into interpretation.yaml). Exactly one of
    the two must be present."""
    if entry.get("caveat"):
        return entry["caveat"]
    ref = entry.get("caveat_ref")
    if not ref:
        raise ValueError(f"glossary entry has neither `caveat` nor `caveat_ref`: {entry}")
    node: Any = cfg
    for part in ref.split("."):
        node = node[part]
    return node


def explain_metric(metric: str, config: Optional[dict[str, Any]] = None) -> MetricExplanation:
    """Look up one card metric and return its definition and key caveat.

    Accepts the schema field name or a common alias / natural phrasing. Unknown
    input returns found=False with a clear message — it never guesses.
    """
    cfg = config if config is not None else load_config()
    glossary = load_glossary()
    index = _alias_index(glossary)

    norm = _normalize(metric)
    name = index.get(norm)
    if name is None:
        return MetricExplanation(
            query=metric,
            found=False,
            message=(
                f"'{metric}' is not a card metric. explain_metric only defines the "
                "percentile boxes on a HockeyStats card (skater or goalie); it does "
                "not guess at anything outside them."
            ),
        )

    entry = glossary["metrics"][name]
    return MetricExplanation(
        query=metric,
        found=True,
        metric=name,
        label=LABELS.get(name, name),
        definition=entry["definition"],
        caveat=_resolve_caveat(entry, cfg),
    )
