"""Validate an engine result and write its PDF report to disk.

The MCP tool's backend. The passed result must round-trip through the
ENGINE'S OWN output model for that kind (Assessment, GoalieAssessment,
Comparison, Adjudication) - a retyped, reconstructed, or wrong-kind result
fails loudly instead of rendering a plausible-looking wrong report. The
interpretive kind has its own strict schema since Claude authors it.
"""
from __future__ import annotations

import datetime
import os
import re
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from engine.adjudicate import Adjudication
from engine.assess import Assessment, GoalieAssessment, MicroAssessment
from engine.compare import Comparison
from reports.render import render_pdf

DEFAULT_DIR = Path.home() / "Documents" / "HockeyCardReports"
ENV_DIR = "HOCKEY_CARD_REPORTS_DIR"  # test/user override for the output dir


class InterpretiveSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: Optional[str] = None
    body: str = Field(min_length=1)


class InterpretivePlayerRow(BaseModel):
    """One player's job on a unit: name, one-line read, the numbers behind it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    read: str = Field(min_length=1)
    key_numbers: Optional[str] = None


class InterpretiveUnit(BaseModel):
    """A named unit (line, pairing, goalie+pairing) with works/concerns."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    players: list[InterpretivePlayerRow] = []
    works: list[str] = []
    concerns: list[str] = []


class InterpretiveResult(BaseModel):
    """Claude-authored content for reads the engine has no tool for."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    subtitle: Optional[str] = None
    tone: Literal["positive", "negative", "mixed", "neutral"] = "neutral"
    players: list[str] = []
    units: list[InterpretiveUnit] = []
    sections: list[InterpretiveSection] = []
    caveat: Optional[str] = None
    summary: Optional[str] = None

    @model_validator(mode="after")
    def _needs_units_or_sections(self):
        if not self.units and not self.sections:
            raise ValueError(
                "an interpretive result needs 'units' (structured per-unit reads) "
                "and/or a non-empty 'sections' list of {heading?, body}."
            )
        return self


RESULT_MODELS = {
    "assess_skater": Assessment,
    "assess_goalie": GoalieAssessment,
    "assess_micro": MicroAssessment,
    "compare": Comparison,
    "claim_check": Adjudication,
    "interpretive": InterpretiveResult,
}


def save_report(kind: str, result: Any, title: Optional[str] = None) -> Path:
    """Validate, render, write; returns the absolute path. Raises ValueError."""
    if kind not in RESULT_MODELS:
        raise ValueError(
            f"Unknown report kind {kind!r} - expected one of {sorted(RESULT_MODELS)}."
        )
    model = RESULT_MODELS[kind]
    try:
        validated = model.model_validate(result)
    except ValidationError as exc:
        raise ValueError(
            f"`result` does not match the {model.__name__} shape for kind {kind!r} - "
            f"pass the engine result verbatim (never retyped or reconstructed):\n{exc}"
        )
    stub = _slug(_name_stub(kind, validated, title))
    date = datetime.date.today().isoformat()
    path = _unique_path(_reports_dir(), f"{stub}_{kind.replace('_', '-')}_{date}")
    path.write_bytes(render_pdf(kind, validated, title))
    return path.resolve()


def _name_stub(kind: str, validated: Any, title: Optional[str]) -> str:
    if kind in ("assess_skater", "assess_goalie", "assess_micro"):
        return validated.name
    if kind == "compare":
        return f"{validated.a_name} vs {validated.b_name}"
    # claim_check carries no player name; interpretive may carry players.
    players = ", ".join(getattr(validated, "players", None) or [])
    return title or players or kind.replace("_", " ")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "report"


def _reports_dir() -> Path:
    override = os.environ.get(ENV_DIR)
    directory = Path(override).expanduser() if override else DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _unique_path(directory: Path, base: str) -> Path:
    path = directory / f"{base}.pdf"
    n = 2
    while path.exists():
        path = directory / f"{base}-{n}.pdf"
        n += 1
    return path
