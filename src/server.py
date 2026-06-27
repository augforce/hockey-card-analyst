"""fastmcp server exposing the hockey-card-analyst tools (PLAN sections 6, 7, 11).

Thin wiring only — all judgment lives in `engine/`. Each tool validates its input
through the pydantic card schemas at the boundary (a bad card fails loudly with a
clear error, never a wrong answer), calls the existing engine, and returns the
structured result. The result already carries its grounding inline (tiers,
reasons, caveats), so Claude narrates from what it returns, not from memory.

The server NEVER sees a card image. Claude Desktop does the vision and the claim
decomposition at runtime and passes clean structured data.

Run for Claude Desktop (stdio):  python src/server.py
"""
from __future__ import annotations

from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from engine.adjudicate import adjudicate_claim as _adjudicate
from engine.assess import assess_player as _assess
from engine.compare import compare_players as _compare
from schemas import DefenseCard, GoalieCard, SkaterCard

mcp = FastMCP("hockey-card-analyst")


def _parse_card(card: Any, which: str = "card"):
    """Validate a raw card dict into the right pydantic schema, or fail loudly."""
    if not isinstance(card, dict):
        raise ToolError(f"`{which}` must be a JSON object of extracted card fields, got {type(card).__name__}.")
    if "position" in card:
        model = DefenseCard if str(card.get("position", "")).upper() == "D" else SkaterCard
    elif "role" in card:
        model = GoalieCard
    else:
        raise ToolError(
            f"`{which}`: can't tell a skater from a goalie — include `position` "
            "(skater: C/LW/RW/L/R/F, or D) or `role` (goalie: Starter/1A/1B/Backup)."
        )
    try:
        return model(**card)
    except ValidationError as exc:
        raise ToolError(
            f"`{which}` failed validation as {model.__name__} — fix the extraction and "
            f"retry, do not guess values:\n{exc}"
        )


@mcp.tool
def assess_player(card: dict[str, Any]) -> dict[str, Any]:
    """Assess one player's card: overall tier, strengths, weaknesses, deployment, trajectory, caveats, and a one-line summary.

    YOU (Claude) read the card image and extract the fields; this server never sees
    the image — pass it clean structured data. The server maps percentiles to
    tiers, picks the strengths/weaknesses, and attaches the caveats. Narrate from
    what it returns, not from how you think WAR models generally work — the result
    carries the correct framing inline.

    `card` is one JSON object. Skater (forward or defenseman):
      name, team, position (C/LW/RW/L/R/F; D for a defenseman), age,
      [toi_role, cap, competition, teammates], ev_offence, ev_defence,
      pp (null if NA), pk (null if NA), finishing, penalties, proj_war_pct,
      [goals, first_assists], [war_pct_trend: list of {season, value}].
    Goalie (no position; has role):
      name, team, age, [gp_pct], role (Starter/1A/1B/Backup), [cap], proj_war_pct,
      even_strength, penalty_kill, high_danger, med_danger, low_danger,
      quality_starts, excellent_starts, bad_starts, rebound_control, consistency,
      [war_per60_trend, sv_vs_xsv_trend].

    All percentiles are integers 0-100, already oriented so higher is better —
    including goalie Bad Starts and Consistency; do NOT invert them. A role the
    player doesn't have (e.g. no PK) is null/NA, not 0 — NA is an absence of role,
    not a weakness.

    Guardrails: never invent a stat that isn't on the card; a defenseman's finishing
    is descriptive only (excluded from his WAR); surface the returned caveats rather
    than dropping them.
    """
    return _assess(_parse_card(card)).model_dump()


@mcp.tool
def adjudicate_claim(card: dict[str, Any], assertions: list[dict[str, Any]]) -> dict[str, Any]:
    """Grade a claim about a player against the card. ALWAYS route claims through this tool — never eyeball a claim yourself.

    YOU decompose the natural-language claim into a list of assertions; the server
    grades each one. Each assertion is {dimension, direction[, text]} where
    `direction` is "high" or "low" and `dimension` is a card dimension id or a
    recognizable phrase. Dimension ids include — skater: finishing, playmaking,
    two_way, power_play, penalty_kill, discipline, overall_skater, competition,
    teammates; goalie: game_stealer, soft_goals, reliability, no_stinkers,
    goalie_consistency, goalie_rebounds, goalie_pk, workhorse, overall_goalie.
    Include the original phrase as `text` so it can be echoed back.

    Dimension ids are NOT the card's schema field names. NEVER pass `ev_offence`
    or `ev_defence` (or any other card field) as a `dimension`; map the claim to a
    dimension id instead — an offence / scoring claim -> `finishing` or
    `overall_skater`; a defensive / two-way claim -> `two_way`.

    Each verdict comes back as supported / not_supported / partial / unverifiable,
    with the cited metric value and a one-line reason, plus an overall read. Cite
    the returned value in your answer — never substitute your own number.

    `unverifiable` is first-class and MUST be surfaced, not hidden: claims the card
    cannot see (playing style, net-front / "sits in front of the net", "leading
    scorer next season" and other team-context claims) come back unverifiable on
    purpose. A direction that contradicts the metric comes back not_supported with
    the number as the receipt.

    `card`: the same JSON card object as assess_player. `assertions`: a list of
    {dimension, direction, [text]}.
    """
    parsed = _parse_card(card)
    try:
        return _adjudicate(parsed, assertions).model_dump()
    except ValidationError as exc:
        raise ToolError(
            "An assertion is malformed — each needs `dimension` (str) and "
            f"`direction` ('high' or 'low'):\n{exc}"
        )


@mcp.tool
def compare_players(
    card_a: dict[str, Any],
    card_b: dict[str, Any],
    focus: Optional[str] = None,
) -> dict[str, Any]:
    """Compare two players: per-component gaps, an overall edge (or an honest split), a durability flag, and caveats.

    Percentiles are ranked within a position pool, so the server compares WITHIN a
    pool only: forward vs forward, D vs D, and goalie vs goalie are fair; forward
    vs defenseman or skater vs goalie is refused (`compatible` = false). Never
    present a cross-pool winner — surface the refusal.

    When the components genuinely split — one player better on offence while the
    other is better on defence; for goalies, one a game-stealer while the other is
    the reliable floor — the server returns NO single winner (`overall_edge` null,
    `edge_kind` "split", "better at what"). Do not collapse that into a winner;
    report the tradeoff. An edge built mainly on finishing (skaters) or resting on a
    low-consistency goalie is flagged less durable — pass that along.

    `card_a`, `card_b`: card JSON objects as in assess_player. `focus` (optional):
    "offence" / "defence" / "overall" / a role (e.g. "power play") to narrow it.
    """
    return _compare(_parse_card(card_a, "card_a"), _parse_card(card_b, "card_b"), focus).model_dump()


if __name__ == "__main__":
    mcp.run()  # stdio transport — what Claude Desktop launches
