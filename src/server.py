"""fastmcp server exposing the hockey-card-analyst tools (PLAN sections 6, 7, 11).

Thin wiring only - all judgment lives in `engine/`. Each tool validates its input
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
from engine.common import strip_em_dashes as _scrub
from engine.compare import compare_players as _compare
from engine.glossary import explain_metric as _explain_metric
from reports.save import save_report as _save_report
from schemas import DefenseCard, DefenseMicroCard, ForwardMicroCard, GoalieCard, SkaterCard

mcp = FastMCP("hockey-card-analyst")


def _parse_card(card: Any, which: str = "card"):
    """Validate a raw card dict into the right pydantic schema, or fail loudly."""
    if not isinstance(card, dict):
        raise ToolError(f"`{which}` must be a JSON object of extracted card fields, got {type(card).__name__}.")
    if card.get("card_kind") == "micro":
        # Microstat ($10-tier) card. It shows no position box - the pool comes
        # from the footer ("percentile ranks among forwards/defencemen"), so the
        # extraction must state it; we never default silently.
        if "position" not in card:
            raise ToolError(
                f"`{which}`: a micro card needs `position` - \"F\" (or C/LW/RW) when the "
                "footer says 'among forwards', \"D\" when it says 'among defencemen'."
            )
        model = DefenseMicroCard if str(card.get("position", "")).upper() == "D" else ForwardMicroCard
    elif "position" in card:
        model = DefenseCard if str(card.get("position", "")).upper() == "D" else SkaterCard
    elif "role" in card:
        model = GoalieCard
    else:
        raise ToolError(
            f"`{which}`: can't tell a skater from a goalie - include `position` "
            "(skater: C/LW/RW/L/R/F, or D) or `role` (goalie: Starter/1A/1B/Backup)."
        )
    try:
        return model(**card)
    except ValidationError as exc:
        raise ToolError(
            f"`{which}` failed validation as {model.__name__} - fix the extraction and "
            f"retry, do not guess values:\n{exc}"
        )


@mcp.tool
def assess_player(card: dict[str, Any], micro_card: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Assess one player's card: overall tier, strengths, weaknesses, deployment, trajectory, caveats, and a one-line summary.

    YOU (Claude) read the card image and extract the fields; this server never sees
    the image - pass it clean structured data. The server maps percentiles to
    tiers, picks the strengths/weaknesses, and attaches the caveats. Narrate from
    what it returns, not from how you think WAR models generally work - the result
    carries the correct framing inline.

    `card` is one JSON object. Skater (forward or defenseman):
      name, position (C/LW/RW/L/R/F; D for a defenseman), [age],
      [toi_role, cap, competition, teammates], ev_offense, ev_defense,
      pp (null if NA), pk (null if NA), finishing, penalties, proj_war_pct,
      [goals, first_assists], [war_pct_trend: list of {season, value}].
    Goalie (no position; has role):
      name, [age], [gp_pct], role (Starter/1A/1B/Backup), [cap], proj_war_pct,
      even_strength, penalty_kill, high_danger, med_danger, low_danger,
      quality_starts, excellent_starts, bad_starts, rebound_control, consistency,
      [war_per60_trend, sv_vs_xsv_trend].

    MICROSTAT ($10-tier) card - the dark card with a WAR row on top and three
    columns of AllThreeZones tracked data, footer "Microstats: AllThreeZones;
    WAR: TopDownHockey". Skaters only (no goalie micro card exists). Extract
    with card_kind "micro" - that discriminator is REQUIRED - plus:
      card_kind: "micro", name, season (from the footer, e.g. "2025-26"),
      position ("F" or C/LW/RW when the footer says 'among forwards'; "D" when
      'among defencemen' - the card shows no position box),
      WAR row: ev_offense, ev_defense, pp (null if NA), pk (null if NA),
      penalties, finishing.
    Forward microstats: goals, chances, shots, in_zone_shots, rush_shots,
      shots_off_hd_passes, zone_entries, entries_w_possession, primary_assists,
      chance_assists, primary_shot_assists, in_zone_shot_assists,
      rush_shot_assists, high_danger_passes, zone_exits, exits_w_possession,
      skating_speed, chance_contributions, shot_contributions, in_zone_offense,
      rush_offense, forecheck_involvement, hits, d_zone_puck_touches.
    Defense microstats: goals, chances, shots, primary_assists, chance_assists,
      primary_shot_assists, nz_shot_assists, dz_shot_assists, passes, entries,
      entry_possession_rate, exits, exit_possession_rate, exit_success_rate,
      pass_exits, carry_exits, d_zone_retrievals, retrieval_success,
      shot_contributions, chance_contributions, in_zone_offense, rush_offense,
      success_per_poss_play, entry_denial_rate, poss_entry_prevention,
      entry_chance_prevention, hits.

    A micro card alone returns a MICRO assessment: WAR-row value reads, paired
    style profiles, tracked standouts/soft spots, and style reads (hits,
    skating speed, forecheck involvement - style facts, NEVER weaknesses). It
    has no Proj. WAR headline, so no overall tier is invented; it is one season
    at 5v5 per 60, not the standard card's three-year weighting - keep that
    framing.

    `micro_card` (optional): when the user supplies BOTH cards for the SAME
    player, pass the standard card as `card` and the micro card here - the
    standard assessment gains an articulation-only `micro_insights` synthesis
    (season-vs-projection divergences, tracked evidence behind the verdicts).
    The tier never moves. Never pass two different players.

    All percentiles are integers 0-100, already oriented so higher is better -
    including goalie Bad Starts and Consistency; do NOT invert them. A role the
    player doesn't have (e.g. no PK) is null/NA, not 0 - NA is an absence of role,
    not a weakness. Some cards (e.g. a UFA's) print a blank Age: omit age rather
    than guessing. IGNORE the team/logo on the card entirely - do not extract,
    pass, or mention team affiliation. Cards go stale as players are traded, so
    a logo (or a logo mismatch between two cards) is noise, never a finding; the
    read is about the player, not the team.

    Guardrails: never invent a stat that isn't on the card; a defenseman's finishing
    is descriptive only (excluded from his WAR, on both card kinds); surface the
    returned caveats rather than dropping them.

    Narrate the returned STRUCTURE, not your own regrouping: "strengths" and
    "weaknesses" are exactly the returned lists. The `descriptive` reads (goals,
    first assists) and the micro card's tracked columns are supporting color the
    engine deliberately keeps OUT of the value verdict - you may cite them as
    descriptive color, but NEVER present them as strengths, weaknesses, or part
    of the WAR case.

    Standing framing for every answer: Reads are model projections, not
    predictions. Numbers are percentiles unless noted. Never use em dashes
    anywhere in your answer; use commas, colons, or plain hyphens instead.

    Scope: this tool interprets ONLY what's on the card. Anything the card can't see
    - trades, contracts, current team, roster context, who leads a team in scoring,
    recent game stats - is out of scope and it does not provide it. If you fill such
    a gap from outside the card (e.g. the web), mark that content clearly as NOT from
    the card and note it should be independently verified; keep card-derived verdicts
    (traceable to the numbers) visibly separate from outside context (unverified).

    After presenting this assessment, ALWAYS close your answer by offering the
    user a downloadable PDF report of it - generated with the render_report tool
    (kind "assess_skater", "assess_goalie", or "assess_micro" for a micro-card
    assessment), passing THIS result verbatim.
    """
    parsed = _parse_card(card)
    parsed_micro = None
    if micro_card is not None:
        parsed_micro = _parse_card(micro_card, "micro_card")
        if not isinstance(parsed_micro, (DefenseMicroCard, ForwardMicroCard)):
            raise ToolError(
                "`micro_card` must be a microstat card (card_kind \"micro\") - "
                "pass the standard card as `card`."
            )
    try:
        return _scrub(_assess(parsed, micro_card=parsed_micro).model_dump())
    except ValueError as exc:
        raise ToolError(str(exc))


@mcp.tool
def adjudicate_claim(card: dict[str, Any], assertions: list[dict[str, Any]]) -> dict[str, Any]:
    """Grade a claim about a player against the card. ALWAYS route claims through this tool - never eyeball a claim yourself.

    YOU decompose the natural-language claim into a list of assertions; the server
    grades each one. Each assertion is {dimension, direction[, text]} where
    `direction` is "high" or "low" and `dimension` is a card dimension id or a
    recognizable phrase. Dimension ids include - skater: finishing, playmaking,
    two_way, power_play, penalty_kill, discipline, overall_skater, competition,
    teammates, skater_style, net_front, team_leading_scorer; goalie:
    game_stealer, soft_goals, reliability, no_stinkers, goalie_consistency,
    goalie_rebounds, goalie_pk, workhorse, overall_goalie, goalie_style.
    Include the original phrase as `text` so it can be echoed back.

    MICROSTAT card claims: style claims that are unverifiable on a standard
    card become ANSWERABLE when the supplied card is a micro card - dimension
    ids: skating, physicality, forechecking, motor (partial), rush_attack,
    cycle_game, shot_volume, chance_generation, dangerous_passing_micro,
    playmaking_micro (passer claims grade on tracked passing process - chance
    assists first - not assist outcomes), entry_driving, transition_exits,
    rush_defense, puck_management, retrievals, net_front_presence (partial:
    Shots off HD Passes proxies net-front/deflection presence). Use them (or
    the natural phrase) with a micro card; the same phrases on a standard card
    still come back unverifiable, correctly. Overall-value claims work the
    other way: a micro card has no Proj. WAR, so "he's elite" needs the
    standard card.

    Dimension ids are NOT the card's schema field names. NEVER pass `ev_offense`
    or `ev_defense` (or any other card field) as a `dimension`; map the claim to a
    dimension id instead - an offense / scoring claim -> `finishing` or
    `overall_skater`; a defensive / two-way claim -> `two_way`.

    Each verdict comes back as supported / not_supported / partial / unverifiable,
    with the cited metric value and a one-line reason, plus an overall read. Cite
    the returned value in your answer - never substitute your own number.

    `unverifiable` is first-class and MUST be surfaced, not hidden: claims the card
    cannot see (playing style, net-front / "sits in front of the net", "leading
    scorer next season" and other team-context claims) come back unverifiable on
    purpose. A direction that contradicts the metric comes back not_supported with
    the number as the receipt.

    Scope: this tool grades ONLY what's on the card. Beyond the card-can't-see
    claims above, that also rules out trades, contracts, current team, and recent
    game stats - out of scope, and `unverifiable` for the same reason. If you fill
    any such gap from outside the card (e.g. the web), mark it clearly as NOT from
    the card and flag it for verification; keep card-derived verdicts separate from
    outside context.

    `card`: the same JSON card object as assess_player. `assertions`: a list of
    {dimension, direction, [text]}.

    Standing framing for every answer: Reads are model projections, not
    predictions. Numbers are percentiles unless noted. Never use em dashes
    anywhere in your answer; use commas, colons, or plain hyphens instead.

    After presenting the graded claim, ALWAYS close your answer by offering the
    user a downloadable PDF report of it - generated with the render_report tool
    (kind "claim_check", the original claim as `title`), passing THIS result
    verbatim.
    """
    parsed = _parse_card(card)
    try:
        return _scrub(_adjudicate(parsed, assertions).model_dump())
    except ValidationError as exc:
        raise ToolError(
            "An assertion is malformed - each needs `dimension` (str) and "
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
    pool only: forward vs forward, D vs D, goalie vs goalie - and micro vs micro
    of the same position - are fair; forward vs defenseman or skater vs goalie is
    refused (`compatible` = false). A micro card vs a standard card is ALSO
    refused, even for the same player: single-season tracked percentiles and a
    three-year-weighted projection are different regimes. Never present a
    cross-pool (or cross-regime) winner - surface the refusal. A micro-vs-micro
    comparison has no Proj. WAR headline, so a genuine split stays a split.

    When the components genuinely split - one player better on offense while the
    other is better on defense; for goalies, one a game-stealer while the other is
    the reliable floor - the server returns NO single winner (`overall_edge` null,
    `edge_kind` "split", "better at what"). Do not collapse that into a winner;
    report the tradeoff. An edge built mainly on finishing (skaters) or resting on a
    low-consistency goalie is flagged less durable - pass that along.

    Scope: this tool compares ONLY what's on the cards - it knows nothing about
    trades, contracts, teams, roster fit, or recent stats. If you add such context
    from outside the cards (e.g. the web), mark it clearly as NOT from the cards and
    flag it for independent verification; keep the card-derived comparison separate
    from outside context.

    `card_a`, `card_b`: card JSON objects as in assess_player. `focus` (optional):
    "offense" / "defense" / "overall" / a role (e.g. "power play") to narrow it.

    Standing framing for every answer: Reads are model projections, not
    predictions. Numbers are percentiles unless noted. Never use em dashes
    anywhere in your answer; use commas, colons, or plain hyphens instead.

    After presenting the comparison, ALWAYS close your answer by offering the
    user a downloadable PDF report of it - generated with the render_report tool
    (kind "compare"), passing THIS result verbatim.
    """
    return _scrub(_compare(_parse_card(card_a, "card_a"), _parse_card(card_b, "card_b"), focus).model_dump())


@mcp.tool
def explain_metric(metric: str) -> dict[str, Any]:
    """Define a single card metric: what it measures, plus its one most important interpretive caveat.

    A thin dictionary lookup over the card's percentile boxes (skater and goalie).
    Pass the schema field name (e.g. `ev_defense`, `bad_starts`) or a natural
    phrase (e.g. "even strength defense", "no stinkers"); it resolves both. An
    input that isn't a card metric comes back with `found` false and a clear
    message - it never guesses.

    Returns: {query, found, metric, label, definition, caveat, message}. The
    `caveat` is the same one the other tools attach, served from one source.

    Scope: this tool DEFINES metrics in the abstract - it does NOT reason about any
    specific player. A deeper "why is this a risk for HIM" question is yours to
    answer from these definitions plus that player's assess_player result; it is
    not something this tool computes. Use it to ground your narration of a metric's
    meaning, not as a verdict.
    """
    return _scrub(_explain_metric(metric).model_dump())


@mcp.tool
def render_report(
    kind: str, result: dict[str, Any], title: Optional[str] = None
) -> dict[str, Any]:
    """Render an answer into a downloadable, styled PDF report; returns the absolute file path.

    After completing ANY assess / compare / claim answer, ALWAYS end by asking
    the user if they'd like a downloadable PDF report of it - every time, as
    the closing line of your answer, not only when they hint at it. Generate
    the PDF when they say yes (or asked for a report/PDF/download up front),
    then give them the returned path.

    `result` must be the EXACT structured object the engine tool just returned
    (assess_player / compare_players / adjudicate_claim), passed through
    verbatim - the same dict, not a summary of it. NEVER retype, round, rebuild,
    or trim fields: the server validates against the engine's own result shape
    and rejects anything else. If you no longer have the engine result, call the
    engine tool again first. Never pass the card, and never embed the card image.

    `kind` selects the template:
      - "assess_skater": an assess_player result for a forward or defenseman
      - "assess_goalie": an assess_player result for a goalie (has danger_profile)
      - "assess_micro": an assess_player result for a microstat card (has
        `season` and `profiles`)
      - "compare": a compare_players result (works for splits and refusals too)
      - "claim_check": an adjudicate_claim result - pass the original claim
        sentence as `title` (it headlines the report and names the file)
      - "interpretive": YOUR OWN content, for questions with no engine tool (line
        synergy, goalie support, roster construction, free-form reads). Pass
        {title, tone ("positive"/"negative"/"mixed"/"neutral"), players: [names],
        units, sections, caveat, summary} - at least one of units/sections.
        When the answer has per-unit structure (one block per line / pairing /
        goalie+pairing), pass it as `units`, one entry per unit:
        {name: "Line 1 - Hughes (C) / Gritsyuk (LW) / Bratt (RW)",
        players: [{name, read (their one-line job on the unit),
        key_numbers (e.g. "98 EVO · 85 FIN · 34 EVD")}, ...],
        works: [reasons it fits], concerns: [risks]} - each renders as a card
        with player rows and green-works / red-concerns columns. Use
        `sections` ([{heading, body}, ...]) only for genuinely freeform prose
        that doesn't fit a unit (method notes, extras/depth players); simple
        "- " bullet lines in a body render as a real list. Write PLAIN TEXT in
        every field - no markdown (**bold**, bullets, # headers): it is
        converted or stripped, never shown literally. Never use em dashes in
        any field; use commas, colons, or plain hyphens instead (the renderer
        also scrubs them, but write them out in the first place). The report is
        prominently badged "Interpretive read · AI - not an engine verdict".
        Never pass engine output as interpretive, and never pass your own prose
        under an engine kind - the badge is how the reader tells them apart.

    INTERPRETIVE READS - the contract for line synergy, goalie support, and
    free-form beyond-the-card reads, whether or not a PDF is ever made:
    - Label the CHAT answer itself as an interpretive/AI read, not an engine
      verdict - the same badge the PDF carries, said out loud, every time.
    - Unit shape is enforced by YOU: a forward line is EXACTLY 3 forwards; a
      defensive pairing is EXACTLY 2 defensemen; goalie support is 1 goalie
      plus EXACTLY 2 defensemen. Given a mismatched mix (wrong count, wrong
      positions), flag it and ask instead of reading the wrong unit.
    - Line synergy: judge how the cards fit TOGETHER, not how good each player
      is alone. Think complementarity: who drives play vs who finishes;
      whether weaknesses stack (two poor defensive players together);
      discipline exposure; whether one player's strengths cover another's
      gaps; role overlap (three finishers and no creator is a problem - so is
      nobody who can defend).
    - Goalie support: read the two directions against each other - do the
      defensemen suppress the danger areas where the goalie is weakest, or
      funnel chances into them? Does the goalie's rebound control cover a
      pairing that loses retrievals? Do discipline problems expose a weak
      penalty-kill goalie? Does a play-leaking pairing overload a
      workload-heavy starter?
    - Shape the read as: one role per player (their job on the unit plus the
      single most relevant percentile), what works (2-3 specific reasons,
      citing percentiles), concerns (1-3, or none if genuinely none), an
      honest caveat that unit fit is read from individual cards (there is no
      unit model), and a one-line summary. These map directly onto the
      interpretive report's `units` (player rows + works/concerns) when the
      user wants the PDF - one unit entry per line or pairing read.

    `title` (optional) overrides the report heading; player names still come
    from the result. The PDF lands in ~/Documents/HockeyCardReports/
    (created if missing; filename = player(s) + kind + date).
    """
    try:
        path = _save_report(kind, result, title)
    except ValueError as exc:
        raise ToolError(str(exc))
    return {"path": str(path), "kind": kind}


if __name__ == "__main__":
    mcp.run()  # stdio transport - what Claude Desktop launches
