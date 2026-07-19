"""Microstat card schemas: golden fixtures + the strict-validation contract.

The microstat ($10-tier) card is a different data regime from the standard card:
single-season percentiles at 5v5 per 60 (AllThreeZones microstats; TopDownHockey
WAR components), no Proj. WAR headline, no age/TOI/cap/competition/teammates,
no trend charts. Forwards and defensemen carry different microstat sets - the
golden fixtures here were hand-verified off the real Celebrini (F) and Schaefer
(D) card images.

Same boundary discipline as the standard schemas: extra fields forbidden,
percentiles bounded 0-100, `card_kind: "micro"` as an explicit discriminator so
a mis-extracted card fails loudly instead of validating as the wrong type.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas import DefenseMicroCard, ForwardMicroCard

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_celebrini_micro_fixture_loads_with_verified_values():
    card = ForwardMicroCard(**_load("celebrini_micro.json"))

    assert card.name == "Macklin Celebrini"
    assert card.card_kind == "micro"
    assert card.season == "2025-26"

    # WAR-component row (single-season, TopDownHockey).
    assert card.ev_offense == 89
    assert card.ev_defense == 67
    assert card.pp == 75
    assert card.penalties == 93
    assert card.finishing == 91
    # PK is NA - an absence of role, not a zero. Must read as None.
    assert card.pk is None

    # Shooting column.
    assert card.goals == 92
    assert card.chances == 91
    assert card.shots == 79
    assert card.in_zone_shots == 73
    assert card.rush_shots == 92
    assert card.shots_off_hd_passes == 76
    assert card.zone_entries == 98
    assert card.entries_w_possession == 96

    # Passing column.
    assert card.primary_assists == 96
    assert card.chance_assists == 98
    assert card.primary_shot_assists == 99
    assert card.in_zone_shot_assists == 58
    assert card.rush_shot_assists == 93
    assert card.high_danger_passes == 93
    assert card.zone_exits == 97
    assert card.exits_w_possession == 93

    # Composite / style column.
    assert card.skating_speed == 84
    assert card.chance_contributions == 99
    assert card.shot_contributions == 98
    assert card.in_zone_offense == 64
    assert card.rush_offense == 96
    assert card.forecheck_involvement == 57
    assert card.hits == 27
    assert card.d_zone_puck_touches == 98


def test_schaefer_micro_fixture_loads_with_verified_values():
    card = DefenseMicroCard(**_load("schaefer_micro.json"))

    assert card.name == "Matthew Schaefer"
    assert card.card_kind == "micro"
    assert card.position == "D"
    assert card.season == "2025-26"

    # WAR-component row - PP and PK both present on this card.
    assert card.ev_offense == 96
    assert card.ev_defense == 65
    assert card.pp == 12
    assert card.pk == 27
    assert card.penalties == 99
    assert card.finishing == 95

    # Production column.
    assert card.goals == 90
    assert card.chances == 58
    assert card.shots == 67
    assert card.primary_assists == 76
    assert card.chance_assists == 77
    assert card.primary_shot_assists == 51
    assert card.nz_shot_assists == 84
    assert card.dz_shot_assists == 1
    assert card.passes == 57

    # Transition column.
    assert card.entries == 100
    assert card.entry_possession_rate == 95
    assert card.exits == 100
    assert card.exit_possession_rate == 30
    assert card.exit_success_rate == 89
    assert card.pass_exits == 56
    assert card.carry_exits == 98
    assert card.d_zone_retrievals == 71
    assert card.retrieval_success == 86

    # Composite / rush-defense column.
    assert card.shot_contributions == 58
    assert card.chance_contributions == 70
    assert card.in_zone_offense == 25
    assert card.rush_offense == 73
    assert card.success_per_poss_play == 85
    assert card.entry_denial_rate == 63
    assert card.poss_entry_prevention == 78
    assert card.entry_chance_prevention == 81
    assert card.hits == 27


def test_micro_card_has_no_proj_war_or_deployment_context():
    """The micro card carries no Proj. WAR headline and no deployment boxes -
    passing them must fail loudly (extra='forbid'), not silently absorb."""
    data = _load("celebrini_micro.json")
    for extra in ("proj_war_pct", "competition", "teammates", "toi_role"):
        bad = dict(data)
        bad[extra] = 90 if extra != "toi_role" else "1st Line"
        with pytest.raises(ValidationError):
            ForwardMicroCard(**bad)


def test_micro_percentiles_are_bounded():
    data = _load("celebrini_micro.json")
    data["chances"] = 150
    with pytest.raises(ValidationError):
        ForwardMicroCard(**data)


def test_micro_requires_card_kind_and_season():
    data = _load("celebrini_micro.json")
    for missing in ("card_kind", "season"):
        bad = {k: v for k, v in data.items() if k != missing}
        with pytest.raises(ValidationError):
            ForwardMicroCard(**bad)


def test_forward_micro_rejects_defense_micro_fields():
    """A D micro card mis-extracted as a forward must fail loudly - the D-only
    boxes (rush-defense metrics) are unknown fields on the forward schema."""
    data = _load("schaefer_micro.json")
    data["position"] = "F"
    with pytest.raises(ValidationError):
        ForwardMicroCard(**data)


def test_defense_micro_rejects_forward_micro_fields():
    data = _load("celebrini_micro.json")
    data["position"] = "D"
    with pytest.raises(ValidationError):
        DefenseMicroCard(**data)


def test_na_pp_is_none_not_zero():
    """NA on the WAR row is an absence of role - same invariant as the standard
    card. The fixture's pk: null must parse to None, never 0."""
    card = ForwardMicroCard(**_load("celebrini_micro.json"))
    assert card.pk is None
    assert card.pk != 0


# --- Server-boundary discrimination -----------------------------------------


def test_parse_card_discriminates_micro_forward_and_defense():
    import server

    assert isinstance(server._parse_card(_load("celebrini_micro.json")), ForwardMicroCard)
    assert isinstance(server._parse_card(_load("schaefer_micro.json")), DefenseMicroCard)


def test_parse_card_micro_without_position_fails_loudly():
    """A micro card's pool comes from the footer text, not a position box - the
    extraction must say which pool it read. No position -> loud error, never a
    silent forward default."""
    import server
    from fastmcp.exceptions import ToolError

    data = {k: v for k, v in _load("celebrini_micro.json").items() if k != "position"}
    with pytest.raises(ToolError):
        server._parse_card(data)


def test_parse_card_still_discriminates_standard_cards():
    """Regression: the micro discriminator must not disturb standard dispatch."""
    import server
    from schemas import GoalieCard, SkaterCard

    assert isinstance(server._parse_card(_load("celebrini.json")), SkaterCard)
    assert isinstance(server._parse_card(_load("thompson.json")), GoalieCard)
