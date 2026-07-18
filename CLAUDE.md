2# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local [MCP](https://modelcontextprotocol.io) server that interprets one analytics model's NHL player card (JFresh / HockeyStats) into grounded, plain-English judgments. The host LLM reads the card *image* and passes clean structured JSON; this server does the deterministic interpretation and returns structured findings. It never does vision, and at runtime it never calls an LLM or hockeystats.com — every verdict is a pure function of the card numbers plus the config.

## Commands

```bash
# Install (one time)
python3 -m venv .venv
.venv/bin/python -m pip install fastmcp pydantic PyYAML jinja2 weasyprint   # or: .venv/bin/python -m pip install -e ".[dev]"
# PDF reports need one macOS system library: `brew install pango`

# Tests (pyproject sets pythonpath=["src"], so no install needed to import the engine)
.venv/bin/python -m pytest                                # whole suite
.venv/bin/python -m pytest tests/test_assess.py           # one file
.venv/bin/python -m pytest tests/test_assess.py::test_offense_and_finishing_are_strengths  # one test
.venv/bin/python -m pytest -k "scoring_profile"           # by name pattern

# Run the server over stdio (what an MCP client launches)
.venv/bin/python src/server.py

# Narration demos — the only window into whether the prose reads honestly (see below)
.venv/bin/python examples/demo_assess.py        # also demo_adjudicate / demo_compare / demo_goalie / demo_micro
.venv/bin/python examples/demo_reports.py       # renders eyeball PDFs into examples/report_previews/
```

There is no linter/formatter configured; the test suite is the check. The suite has no network or vision dependencies, so it is fast and deterministic.

## Architecture

Four layers, strictly separated. **All judgment lives in `src/engine/`; the server is thin wiring; the methodology lives in config data, not code; reports are presentation only.**

1. **Boundary — `src/schemas.py`.** Strict pydantic card schemas (`SkaterCard`, `DefenseCard`, `GoalieCard`, plus `ForwardMicroCard` / `DefenseMicroCard` for the $10-tier microstat card), `extra="forbid"`, percentiles bounded 0–100. A mis-extracted card fails loudly here rather than producing a wrong answer. Micro cards require an explicit `card_kind: "micro"` discriminator and a `season`; `_parse_card` refuses a micro card with no `position` (the pool comes from the card footer, never a silent default).

2. **Engine — `src/engine/`.** Pure transforms over a validated card:
   - `assess.py` — `assess_player(card, config, micro_card)` → `Assessment` (skater), `GoalieAssessment`, or `MicroAssessment` (microstat card). Dispatches on card type. With both cards for one player (standard `card` + `micro_card`) the `Assessment` gains an articulation-only `micro_insights` synthesis (season-vs-projection divergences ≥ `DIVERGENCE_MIN`, tracked evidence behind the verdicts) — the tier never moves.
   - `adjudicate.py` — `adjudicate_claim(card, assertions)` grades decomposed `{dimension, direction}` assertions as supported / partial / not_supported / unverifiable, citing the number. Micro cards resolve through the `micro` pool: style dimensions (skating, physicality, forechecking, rush_attack, rush_defense, …) are answerable there while the same aliases stay unverifiable on a standard card; a metric the card type doesn't carry gets an honest "isn't a box on this card type" verdict, distinct from an NA role.
   - `compare.py` — `compare_players(card_a, card_b, focus)`; refuses cross-pool comparisons, returns an honest split when components disagree, flags durability. Micro-vs-micro compares within `forward_micro` / `defense_micro` pools (edge logic on the WAR row only; no Proj. WAR headline means a genuine split stays a split); micro-vs-standard is refused as a cross-regime pair even for the same player.
   - `glossary.py` — `explain_metric(metric)` defines a card metric (definition + key caveat); a lookup only, it does **not** reason about any player.
   - Shared: `common.py` (`LABELS`, `STRENGTH_MIN=70`, `WEAKNESS_MAX=44`, `ordinal`), `tiers.py` (`classify_percentile` → `Tier`). `caveats.py` is a stub — caveat *text* lives in config and is attached inside the engines.

3. **Server — `src/server.py`.** Five `@mcp.tool` functions (`assess_player`, `adjudicate_claim`, `compare_players`, `explain_metric`, `render_report`). Each validates the raw dict via `_parse_card` (or, for `render_report`, against the engine's own output models), calls the engine, and returns `.model_dump()`. Adding an optional field to an engine output model flows through automatically — no server change needed. Tool descriptions carry load-bearing host steering (offer-the-PDF, don't-promote-descriptive-reads) guarded by description-content tests — don't reword them casually.

4. **Reports — `src/reports/`.** Presentation only, no judgment: engine output → Jinja2 template (`templates/`) → PDF via WeasyPrint (`pdf.py`, fully local, no network, no headless browser). `save.py` validates a result against the engine's own output model for the kind and writes to `~/Documents/HockeyCardReports/` (`HOCKEY_CARD_REPORTS_DIR` override). Design tokens and the bundled OFL fonts live inside the module (`reports/fonts/`). The interpretive kind is Claude-authored prose and is always badged "AI — not an engine verdict"; the source card image is never embedded. On macOS WeasyPrint needs `brew install pango`; `reports/pdf.py` handles the dyld path in-process.

### Config is the methodology — `src/config.py` loads two cached YAML files

- `config/interpretation.yaml` — tier bands, the auto-attached caveats (including the micro caveats: `micro_single_season`, `micro_unadjusted`, `micro_style_not_value`, and `defense_repeatability` for forward EV-defense strengths), position rules, goalie reading rules, `war_reading` (the ~37th-percentile replacement anchor and point-estimate framing, distilled from the model author's methodology write-ups — articulation only, never moves a tier), `micro_rules` (the cross-regime WAR-row note), `micro_profiles` (the paired style reads: shot selectivity, passing quality, attack style, D rush defense — thresholds and wording), and the claim→metric `dimensions` dictionary (with aliases; micro dimensions use `applies_to: micro`). Tune behavior by editing YAML, not code.
- `config/glossary.yaml` — one entry per card metric (skater + goalie + microstat): plain-language `definition` + the single key interpretive `caveat`, plus `aliases` for `explain_metric` lookup. Six micro entries are inferred — the site publishes no official definitions for those boxes (checked 2026-07-18), so the inferred reads are canonical; their caveats disclose the inference (test-guarded; see DECISIONS.md).

**Single source of truth for caveats:** a metric's interpretive caveat lives in exactly one place. Glossary entries reuse engine-attached caveats via `caveat_ref` (a dotted path into `interpretation.yaml`, e.g. `caveats.finishing_volatility`) instead of retyping the sentence. When changing caveat wording, change it where it canonically lives; don't duplicate.

## Load-bearing domain rules (invariants that span files)

- **Percentiles are pre-oriented so higher is always better — never invert any of them.** This includes goalie `bad_starts` (higher = better at avoiding them) and `consistency`.
- **NA is an absence of role, not a zero.** `pp`/`pk` may be `None`; that is reported as deployment context, never as a weakness and never read as 0.
- **A defenseman's `finishing` is excluded from WAR.** It appears on the card but is config-excluded (`position_rules.defense.war_excludes`); the engine reports it descriptively and never credits a D's value to it.
- **Within-position only.** Percentiles rank within a position pool; forward-vs-D and skater-vs-goalie are not comparable and `compare` refuses them.
- **Card-bound scope.** Trades, contracts, current team, roster fit, and recent game stats are out of scope by design; `adjudicate_claim` returns such claims as `unverifiable`. The server interprets only what is on the card.
- **Goalie path is separate.** `assess_player` branches to a distinct goalie path with its own output shape and rules; skater-only changes must leave it untouched. There is no goalie microstat card — goalies are standard-card-only.
- **Micro card: WAR row is value, microstats are descriptive.** On a microstat card the six WAR components carry the value read; the tracked columns explain HOW and never become value strengths/weaknesses. The style trio (`hits`, `skating_speed`, `forecheck_involvement`) is style, never a weakness at any percentile. Micro profiles and the both-cards synthesis are articulation-only — they never move a tier.
- **Micro card is a different regime.** Single-season 5v5 per-60 percentiles (footer season required in the schema); `micro_single_season`/`micro_unadjusted` caveats always attach; micro-vs-standard comparisons are refused; no overall tier is invented (no `proj_war_pct` on the card).

## Conventions

- **The `examples/demo_*.py` scripts are the only window into the prose.** The server returns *only* structured data; the host LLM narrates. The demos hand-render that structure into the paragraph a host would say, so they are how you check a judgment reads honestly. They are **not** server code — never import them into `server.py`. Re-run the relevant demo after an engine change and confirm the prose still reads right.
- **Glossary/definition wording is reworded, never copied from hockeystats.com** (see the README's IP section). Keep definitions faithful to the model's methodology but in our own words.
- **`DECISIONS.md` is the design log** — the rationale behind the reading rules and each post-v1 enhancement (scoring profile, young-sample caveat, glossary). Read it before changing engine behavior, and add a dated checkpoint entry when you do.
- Test fixtures in `tests/fixtures/` are extracted card JSON (e.g. `celebrini.json`, `thompson.json`); synthetic ones are labelled as such in their `name`.
