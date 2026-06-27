"""Percentile -> tier label, plus the top-end compression note (PLAN section 5).

Percentiles are compressed at the top, so the bands are deliberately uneven.
Cutoffs, labels, and the compression note all live in
`config/interpretation.yaml` so they can be tuned without touching code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from config import load_config


@dataclass(frozen=True)
class Tier:
    """A percentile placed in a band, with the compression note when 95+."""

    percentile: int
    label: str
    band: tuple[int, int]
    note: Optional[str] = None


def classify_percentile(percentile: int, config: Optional[dict[str, Any]] = None) -> Tier:
    """Place a 0-100 percentile in its tier band.

    Raises TypeError for non-int (including bool) input and ValueError for a
    percentile outside 0-100. `config` defaults to the interpretation config.
    """
    if isinstance(percentile, bool) or not isinstance(percentile, int):
        raise TypeError(f"percentile must be an int 0-100, got {percentile!r}")
    if not 0 <= percentile <= 100:
        raise ValueError(f"percentile must be 0-100, got {percentile}")

    cfg = config if config is not None else load_config()

    note = None
    compression = cfg.get("elite_compression") or {}
    threshold = compression.get("threshold")
    if threshold is not None and percentile >= threshold:
        note = compression.get("note")

    for band in cfg["tiers"]:
        if band["min"] <= percentile <= band["max"]:
            return Tier(
                percentile=percentile,
                label=band["label"],
                band=(band["min"], band["max"]),
                note=note,
            )

    raise ValueError(f"no tier band configured for percentile {percentile}")
