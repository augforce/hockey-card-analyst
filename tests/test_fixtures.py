"""Golden fixtures load cleanly and hold the verified box values.

These numbers were hand-verified off the card images, not re-extracted, so this
test guards against a fixture typo or a schema change silently corrupting the
Phase 2 / Phase 5 ground truth. The exact box percentiles are asserted; the
trend numbers were eyeballed off line charts and are only checked for shape.
"""
import json
from pathlib import Path

from schemas import GoalieCard, SkaterCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_celebrini_fixture_loads_with_verified_values():
    card = SkaterCard(**_load("celebrini.json"))

    assert card.name == "Macklin Celebrini"
    assert card.position == "C"
    assert card.age == 20

    # Exact, legible box percentiles.
    assert card.ev_offense == 91
    assert card.ev_defense == 33
    assert card.pp == 72
    assert card.finishing == 92
    assert card.penalties == 95
    assert card.proj_war_pct == 94
    assert card.goals == 91
    assert card.first_assists == 95
    assert card.competition == 89
    assert card.teammates == 72

    # PK is NA - an absence of role, not a zero. Must read as None.
    assert card.pk is None

    # Trend present and shaped, values not asserted (approximate).
    assert card.war_pct_trend is not None
    assert len(card.war_pct_trend) == 2


def test_gritsyuk_fixture_loads_without_team_or_age():
    # Real card with a blank Age field and no team shown anywhere (UFA card).
    # Both are context-only; their absence must not fail validation.
    card = SkaterCard(**_load("gritsyuk.json"))

    assert card.name == "Arseny Gritsyuk"
    assert card.team is None
    assert card.age is None
    assert card.position == "LW"
    assert card.cap == "UFA"

    # Exact, legible box percentiles.
    assert card.ev_offense == 82
    assert card.ev_defense == 95
    assert card.pp == 30
    assert card.finishing == 79
    assert card.penalties == 16
    assert card.proj_war_pct == 84
    assert card.goals == 62
    assert card.first_assists == 84
    assert card.competition == 55
    assert card.teammates == 63

    # PK is NA - an absence of role, not a zero. Must read as None.
    assert card.pk is None


def test_thompson_fixture_loads_with_verified_values():
    card = GoalieCard(**_load("thompson.json"))

    assert card.name == "Logan Thompson"
    assert card.role == "Starter"
    assert card.age == 27
    assert card.gp_pct == 71

    # Exact, legible box percentiles.
    assert card.proj_war_pct == 96
    assert card.even_strength == 96
    assert card.penalty_kill == 74
    assert card.high_danger == 99
    assert card.med_danger == 73
    assert card.low_danger == 56
    assert card.quality_starts == 99
    assert card.excellent_starts == 53
    assert card.bad_starts == 92
    assert card.rebound_control == 35
    assert card.consistency == 23

    # Trends present and shaped, values not asserted (approximate).
    assert card.war_per60_trend is not None
    assert len(card.war_per60_trend) == 3
    assert card.sv_vs_xsv_trend is not None
    assert len(card.sv_vs_xsv_trend) == 3
