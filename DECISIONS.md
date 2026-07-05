# Decisions log

Choices made during the build that the PLAN did not fully specify. Section
numbers refer to `docs/hockey-card-analyst-PLAN.md`. Section 13 open defaults
are all accepted as-is.

## Phase 1 — Scaffold (2026-06-27)

### Environment & packaging
- **Python 3.14.3** is the local interpreter; `requires-python = ">=3.11"` in
  `pyproject.toml` (union types / builtin generics need 3.10+, headroom to 3.11).
- venv at `.venv`.
- Installed `pydantic` (2.13.4), `PyYAML` (6.0.3), `pytest` (9.1.1), and
  `fastmcp` (3.4.2). fastmcp is only needed for the Phase 6 server but is
  declared now as a project dependency (`fastmcp>=3.0`).
- **Flat `src/` layout per section 10** (modules live directly under `src/`, not
  in an installable package). Tests resolve imports via pytest
  `pythonpath = ["src"]` rather than installing the project. The project is not
  `pip install`-ed in Phase 1. `src/engine/` is a real package
  (`engine/__init__.py`); `src/schemas.py` and `src/config.py` are top-level
  modules imported as `import schemas`, `from engine.tiers import ...`.

### Config
- Added `src/config.py` (not in the section 10 tree) as the single loader for
  `config/interpretation.yaml`, resolving the path relative to the repo root and
  caching per-path. Every later engine module shares it.
- **Populated `interpretation.yaml` fully now**, not as a bare stub: tier bands,
  the elite-compression note, the four caveats, `position_rules`, the goalie
  reading rules, and the full claim-to-metric dimension dictionary. Section 5
  fully specifies this content and section 7b says the reading is "already done
  and lives in section 5," so it is data to transcribe, not logic to design.
  Wording is paraphrased in our own words (section 7b / section 9 no-redistribution).
- The defenseman finishing-exclusion rule (section 4) is encoded as **config
  data** (`position_rules.defense.war_excludes: [finishing]`) so the engine can
  read it in Phase 2 without hard-coding the rule.
- The **elite-compression note text lives in config** (`elite_compression.note`,
  `threshold: 95`) so both the cutoff and the wording are tunable.

### Schemas (section 4)
- `Percentile = int` constrained to `0..100` (cards show integer percentiles).
- **Strict models**: `extra="forbid"` so a mis-extracted card fails loudly.
- Required vs optional split: `name`, `team`, `position`/`role`, `age`, the WAR
  components (`ev_offense`, `ev_defense`, `finishing`, `penalties`) and
  `proj_war_pct` are required. `pp`/`pk` are nullable (NA when no PP/PK role).
  `toi_role`, `cap`, `competition`, `teammates`, `goals`, `first_assists`,
  `gp_pct` are optional. For goalies, all ten percentile boxes are required.
- `competition` and `teammates` modelled as percentiles but documented as
  deployment-only (never a strength/weakness — section 5).
- Forward `position` is a `Literal["C","LW","RW","L","R","F"]`; `DefenseCard`
  fixes `position="D"`; `GoalieCard` has no position field but a
  `role` `Literal["Starter","1A","1B","Backup"]`. These literal sets are tunable.
- `age` bounded `15..60` as a sanity guard.
- `cap` is a free string (preserves the card's formatting, e.g. "$0.95M"); it is
  context only and never affects value.
- Goalie trends use distinct point models: WAR/60 (`value: float`) and
  Save% vs xSave% (`sv`, `xsv`: float) are rates, **not** percentiles.

### Tier logic (section 5)
- `engine/tiers.classify_percentile(percentile, config=None)` returns a frozen
  `Tier(percentile, label, band, note)`. `note` carries the elite-compression
  text when `percentile >= 95`, else `None`.
- Out-of-range percentiles raise `ValueError`; `bool` is rejected with
  `TypeError` (guards against `True`/`False` slipping through `int`).
- Bands are read from config, so cutoffs are tunable without code changes.

### Scope / structure
- Created **docstring-only placeholders** for the later-phase modules
  (`engine/caveats.py`, `engine/assess.py`, `engine/adjudicate.py`,
  `engine/compare.py`, `server.py`) so the tree matches section 10 without
  implementing Phase 2+. No placeholder *test* files were created.
- `tests/fixtures/` is empty (`.gitkeep`); the golden fixtures
  `celebrini.json` (Phase 2) and `thompson.json` (Phase 5) are deferred to their
  phases. Source card images already exist in `cardExamples/`.
- The metric **glossary** and the optional `explain_metric` tool (section 7b /
  section 6) are deferred; not required for Phase 1.
- `git init`-ed the repo with a `.gitignore` (`.venv`, `__pycache__`, etc.).

### Phase 1 checkpoint additions (after review)
- **Golden fixtures created early** from hand-verified numbers (not re-extracted
  from the images): `tests/fixtures/celebrini.json` (forward) and
  `tests/fixtures/thompson.json` (goalie). The box percentiles are exact; the
  trend numbers were eyeballed off the line charts and are treated as
  approximate. `tests/test_fixtures.py` loads both through their schemas, asserts
  the exact box values, and checks trend *shape* only (no decimal assertions).
- **NA is encoded as JSON `null`**, never the string `"NA"` (the string is
  correctly rejected by validation). Celebrini's `pk` is `null`. Confirmed `pp`
  and `pk` are both nullable / omittable on `SkaterCard`.
- **`cardExamples/` is gitignored** (PLAN section 9 — do not redistribute card
  images; they are painful to remove from history later). Derived JSON fixtures
  stay tracked. `.claude/settings.local.json` is also ignored.
- `war_per60_trend` values read off Thompson's chart (38 / 91 / 100) look like a
  0-100 index rather than a raw WAR/60 rate; `sv`/`xsv` are stored in
  percentage-point form (90.8, not 0.908). The schema accepts floats either way,
  so loading is unaffected — see the Phase 5 flag below.

## Carry-forward for Phase 2 (assess) — load-bearing

- **NA (`pp`/`pk` = None) is the absence of a role, not a weakness.** Assess must
  report it as deployment context and must never let it read as a zero or pull a
  verdict down. Celebrini has no PK; that does not make him defensively bad, it
  means he is not used there. (`ev_defense` = 33 is the actual defensive read;
  `pk` = NA is separate.)
- **Defenseman finishing is descriptive only.** Finishing appears on a D card but
  is excluded from projected WAR (`position_rules.defense.war_excludes`). Assess
  may mention it descriptively but must never credit a defenseman's value to it.

## Flag for Phase 5 (goalies)

- Decide whether `war_per60_trend.value` is a percentile/index or a raw WAR/60
  rate, and whether `sv`/`xsv` are percentage points (90.8) or proportions
  (0.908), then normalise the fixtures/glossary accordingly. No code change
  needed for Phase 1 loading.

No commits were made until the Phase 1 checkpoint commit (see git log).

## Phase 2 — assess_player for skaters (2026-06-27)

### Output shape
- `assess_player(card, config=None) -> Assessment` (pydantic), so it serializes
  cleanly for MCP later. `Assessment` carries: `overall_tier` / `overall_percentile`
  / `overall_note`, `strengths`, `weaknesses`, `descriptive`, `deployment`,
  `trajectory`, `caveats`, `summary`. Each metric read is a `ComponentRead`
  (metric, label, percentile, tier, note).

### What counts as what
- Three buckets: **WAR components** (`ev_offense`, `ev_defense`, `pp`, `pk`,
  `finishing`, `penalties`) drive strengths/weaknesses; **descriptive**
  (`goals`, `first_assists`) is supporting colour only (section 4 "extra
  descriptive"); **deployment** (`competition`, `teammates`) is never a
  strength/weakness (section 5).
- **Strength/weakness thresholds:** strength = percentile ≥ 70 (Strong+),
  weakness = ≤ 44 (Below average−); 45–69 is neutral and not listed. Constants
  `STRENGTH_MIN=70` / `WEAKNESS_MAX=44` mirror the config band edges.

### The two load-bearing rules (as flagged)
- **NA (`pp`/`pk` = None)** becomes a deployment note ("No penalty kill role
  (NA) — an absence of usage, not a weakness") and never enters strengths,
  weaknesses, or reads as a zero.
- **Defenseman finishing** is read from config (`position_rules.defense.war_excludes`),
  pulled out of the WAR-component ranking, and emitted under `descriptive` with
  an exclusion note. The finishing-volatility caveat does **not** fire for a D
  (the verdict isn't built on finishing). Verified by the synthetic-D test:
  finishing 95 (Elite) present descriptively, `strengths` empty, overall stays
  Above average (57th).

### Caveat firing
- `finishing_volatility`: only when a **forward's** verdict leans on finishing
  (finishing is a strength).
- `deployment_not_value`: whenever competition/teammates are present.
- `dangerous_passing`: forwards only, when `first_assists` is borderline (45–69).
- `within_position_only`: **not** attached in assess — reserved for
  `compare_players` (Phase 4), where cross-pool comparison is the actual risk.

### Other
- Metric display labels live in a `LABELS` dict in `assess.py` for now; a fuller
  glossary (section 7b) can absorb them later.
- Trajectory from `war_pct_trend`: Δ ≥ 15 "pointing sharply up", ≥ 5 "trending
  up", symmetric for down, else "holding steady".
- **Narration stays out of the server** (section 7: server returns structure,
  Claude narrates). The plain-English paragraph was produced by an illustrative
  demo (`scratchpad/demo_assess.py`) that derives text purely from the
  `Assessment` fields; it is not committed. Can be persisted to `examples/` on
  request.
- Added synthetic fixture `tests/fixtures/synthetic_dman.json`, clearly labelled
  not a real player.
- Fixed an ordinal-formatting bug (was printing "72th"; now "72nd") in the
  deployment/summary strings.

## Phase 3 — adjudicate_claim for skaters (2026-06-27)

### Division of labor (the thing to get right)
- The server does **not** parse natural language. `adjudicate_claim(card,
  assertions, config=None)` receives assertions already decomposed by Claude
  Desktop into `Assertion(dimension, direction)` (direction is `high`/`low`;
  optional `text` echoes the original phrase). Dicts or `Assertion` objects both
  accepted.
- `dimension` is resolved against the config dimension dictionary by **id first,
  then alias** (case-insensitive), so Claude can send either.

### The four grades
- `supported` / `not_supported` via direction vs metric: high → ≥70 supported,
  ≤44 not_supported; low → inverted. The 45–69 middle is `partial` ("right
  direction but overstated").
- `partial` also covers config `answerability: partial` (team-context, e.g.
  `team_leading_scorer`): grade partial, cite `proj_war_pct`, attach the
  team-context note.
- `unverifiable` is **first-class, never a guess**: config
  `answerability: not_answerable` (net-front, goalie style) → unverifiable with
  the config note; an **NA role** (primary metric is None) → unverifiable
  ("no role, the card can't assess it"); an **unknown dimension** → unverifiable.
- Every verdict cites the metric value as the receipt; `not_supported` puts the
  contradicting number in the reason.

### Per-verdict caveat
- `caveat` is attached only when the verdict leans on it: finishing →
  finishing-volatility (supported/partial); playmaking → dangerous-passing
  (partial/borderline only); deployment dims → deployment-not-value.

### Overall read
- Enumerates by grade and never papers over a mix; prefixes "Half-right claim."
  when both supported and not_supported assertions are present, so it always says
  which half.

### Test claim decomposition
- The section 3 four-part claim is decomposed into **five** assertions because
  "asked to do more" maps to BOTH playmaking and defense (section 3) — and they
  disagree: playmaking is Elite (95th, refutes "limited") while EV defense is
  Below average (33rd, supports it). That disagreement is the half-right nuance.

### Refactor / housekeeping
- Extracted `engine/common.py` (`ordinal`, `STRENGTH_MIN`, `WEAKNESS_MAX`) as a
  single source of truth; `assess.py` now imports them (no behavior change).
  Added `tests/test_common.py` with the one small ordinal test — the sanctioned
  response to the "72th" class of bug now that ordinals recur in claim reasons.
- Added `examples/demo_adjudicate.py` (illustrative narration window, NOT server
  code), same per-phase pattern as `demo_assess.py`.
- Goalie dimensions sent with a skater card resolve to a missing metric → None →
  unverifiable; the full goalie path is Phase 5.

## Phase 4 — compare_players for skaters (2026-06-27)

### Order of operations
`compare_players(card_a, card_b, focus=None)`: (1) position-compatibility check,
(2) component-by-component, (3) overall edge, (4) durability flag.

### Compatibility guard (first)
- Pool comes from the card type: `SkaterCard` → forward, `DefenseCard` →
  defense, `GoalieCard` → goalie. Different pools (forward-vs-D, skater-vs-goalie)
  → **refused**: `compatible=False`, `edge_kind="incompatible"`,
  `overall_edge=None`, no components, a `reason`, and the within-position-only
  caveat. Chose a clean refusal over a heavily-caveated result — clearer.

### Components
- Each WAR component reports both values, the gap (a − b), and the leader
  (A/B/tie, or None+note when NA). D-vs-D excludes finishing (`position_rules`).
  NA components are dropped from area aggregates.

### Overall edge — refuses false winners (the carried-over discipline)
- Area leaders: offense = avg(ev_offense, pp, finishing); defense =
  avg(ev_defense, pk); a lead counts only at ≥ `MARGIN` (5).
- **Genuine split** (areas have opposite leaders) → `overall_edge=None`,
  `edge_kind="split"`, prose says "better at what" and names the tradeoff —
  UNLESS projected WAR differs by ≥ `PROJ_DECISIVE` (10), in which case the edge
  goes to the proj-WAR leader (`edge_kind="proj_war"`) with the tradeoff noted.
- Not a split: a player leading the area(s) → `broad`; else a proj-WAR gap ≥
  MARGIN → `proj_war`; else `even` (`overall_edge=None`).
- `MARGIN=5` / `PROJ_DECISIVE=10` are constants in `compare.py` (tunable).

### Durability flag
- If the winner's finishing lead exceeds their largest play-driving (EV
  offense/defense) lead, the edge is "less durable — leans on finishing" and the
  finishing-volatility caveat is attached; otherwise "durable — play-driving".

### focus
- `offense`/`defense` narrow to that area and CAN crown a within-area winner even
  when the overall comparison splits; `overall`/None run the full logic; a
  role/metric (`pp`, `power play`, `pk`, `penalty kill`, or a metric name) narrows
  to a single component. `offense`/`defense` normalize to the British spelling.

### Housekeeping
- Consolidated `LABELS` into `engine/common.py` (now its third user); `assess`
  and `adjudicate` import it.
- Synthetic fixtures `compare_clear_leader/trailer.json` and
  `compare_split_sniper/shutdown.json`, labelled "(synthetic)". Cross-position
  test reuses `celebrini.json` + `synthetic_dman.json`.
- Added `examples/demo_compare.py` (split case narrated; clear + cross-position
  for contrast).

## Phase 5 — goalies through all three tools (2026-06-27)

Goalies are a new schema + new reading rules over the **same engine**. The tools
dispatch on card type rather than getting goalie clones: `assess_player`,
`adjudicate_claim`, and `compare_players` each route a `GoalieCard` to goalie
logic while reusing tiers, the strength/weakness thresholds, the four grades, the
split refusal, the position guard, and the durability pattern.

### assess_player (goalie) — `GoalieAssessment`
- **Danger split is a profile, not three numbers** (`Profile`: the three reads +
  a `shape`). Heuristic: high ≥70 and high−low ≥20 → "makes the hard saves,
  ordinary on routine shots"; low ≤44 → leaking-soft-goals flag. Thompson 99/56
  reads as hard-saves / ordinary-routine.
- **Floor vs ceiling** is one profile: quality (floor) / excellent (ceiling) /
  bad (disaster avoided). High floor + modest ceiling → "reliability over
  game-stealing."
- **Consistency is a volatility flag** (`ConsistencyRead`), never a
  strength/weakness; tempered harder when paired with a steep WAR climb.
- **Rebound control** is one of the discrete skills (even_strength,
  penalty_kill, rebound_control) that feed strengths/weaknesses, so it gets
  called out on its own (Thompson 35th → weakness) — never folded into danger.
- Workload = gp_pct + role (deployment, not value). Caveats always include
  consistency-volatility, plus save-lines when the sv/xsv trend is present.
- **Summary holds the tension** (96th WAR AND 23rd consistency, both halves) —
  the section 12 goalie test.

### Goalie trends (resolves the Phase 1 flag)
- `war_per60_trend` value is a **percentile rank**: tiered and read as rising
  standing, not a raw rate.
- `sv_vs_xsv_trend` is in **percentage points**, read as a GAP (sv − xsv): actual
  holding while expected falls = beating expectation by more = rising GSAx = what
  drives WAR up. Never read either line alone.

### adjudicate_claim (goalie)
- Broadened the card type to `CardLike` (skater or goalie). `_resolve` is now
  **pool-aware**: on an alias collision it prefers the entry whose `applies_to`
  matches the card's pool, so a goalie's "shorthanded" resolves to `goalie_pk`,
  not the skater `pk`. Goalie style claims → unverifiable (like net-front).

### compare_players (goalie)
- Refactored to be **spec-driven**: `_spec(pool)` returns the component list and
  the two split-areas. Skaters split offense-vs-defense; goalies split
  **ceiling** (excellent_starts, high_danger) **vs floor** (quality_starts,
  low_danger, bad_starts). The split refusal is the same code.
- Goalie durability is **consistency-based**: an edge resting on a low-consistency
  goalie is "less durable" with the consistency-volatility caveat (the goalie
  analog of the skater finishing-volatility flag).
- Goalie-vs-skater trips the existing position guard — confirmed, not rebuilt.

### Housekeeping
- Goalie metric labels added to `engine/common.LABELS`.
- Synthetic fixtures `compare_goalie_peak.json` / `compare_goalie_floor.json`
  (peak/game-stealer vs floor/reliable, level WAR → split).
- Goalie tests live in `tests/test_goalies.py` (all three tools in one place).
  `examples/demo_goalie.py` narrates the Thompson assessment, a mixed claim, and
  the goalie comparisons.

## Phase 6 — wrap as a fastmcp server + wire into Claude Desktop (2026-06-27)

Exposure and wiring only — **no `engine/` changes**.

### Server (`src/server.py`)
- Three fastmcp tools: `assess_player`, `adjudicate_claim`, `compare_players` —
  thin wrappers that validate input, call the existing engine, and return
  `result.model_dump()`. The grounding (tiers, reasons, caveats) is already in the
  model fields, so it travels inline (PLAN 7b).
- **Card input is a JSON dict**, not a typed union, because the card is polymorphic
  (three schemas). `_parse_card` discriminates by `position` (skater; `D` →
  DefenseCard) vs `role` (goalie), then validates with the pydantic schema. On
  failure it raises `ToolError` with the validation detail — a bad card fails
  loudly with a clear, actionable message, never a wrong answer. The tool
  descriptions document the card fields so Claude knows what to extract.
- **Tool descriptions carry the section 7 guardrails** (Claude does vision +
  claim-decomposition, the server grades; never invent a stat; route claims
  through adjudicate; cite the value; never compare across pools; surface
  unverifiable). These docstrings are the runtime steering, so they're written
  deliberately.
- `explain_metric` is **not built** (optional; it needs the metric glossary that
  was deferred in Phase 1).

### fastmcp 3.4.2 specifics
- `@mcp.tool` leaves the function callable, so the wrappers are unit-testable
  directly; `mcp.list_tools()` is async; `mcp.run()` defaults to the **stdio**
  transport (the FastMCP banner prints to stderr, which is correct for stdio).
- Running `src/server.py` puts `src/` on `sys.path`, so `engine` / `schemas` /
  `config` import with no `PYTHONPATH`; the config path resolves relative to the
  module, independent of CWD. Verified the server launches over stdio cleanly.

### Wiring
- Claude Desktop config at
  `~/Library/Application Support/Claude/claude_desktop_config.json`: `command` =
  the absolute `.venv/bin/python`, `args` = the absolute `src/server.py`. Restart
  Claude Desktop (⌘Q + reopen) to load it. README has the "Run it" section.

### Tests
- `tests/test_server.py` smoke-tests registration, skater/goalie dispatch,
  pass-through structure, and `ToolError` on an unidentifiable / invalid card.
  98 tests pass.

## Post-v1 — card-bound scope + source honesty (2026-06-28)

Doc/description-only (no `engine/` or schema changes): a card-bound scope + source-
honesty norm added to all three tool descriptions, and a "Scope and sourcing"
section added to the README.

- **What:** card-bound interpretation is the default, no-setup behavior — every
  verdict traces to a percentile on the card, so the audit trail stays clean.
  Pulling outside context (trades, contracts, roster fit, recent stats) is an
  **opt-in** the user configures themselves via a Claude Desktop *Project*
  instruction (verbatim text lives in the README); it labels web-sourced facts as
  separate from card-derived verdicts. It is not in the MCP config and not in this
  repo.

- **Why documented, not enforced (the principle behind the whole design):** an MCP
  server can only expose tools — it cannot install behavior in the host model. So
  anything *every* user must get has to ride in the tool descriptions or the README
  (the only channels that reach every caller), and host conversational habits (when
  to go to the web, how to label it) are the user's to configure, not the server's
  to impose. That is why scope/sourcing is stated as a norm in the descriptions +
  README rather than coded as a guardrail — the same reason the section 7 guardrails
  live in the tool descriptions in the first place.

## Post-v1 — scoring profile (EV offense vs finishing) (2026-06-29)

Engine + config enhancement to `assess_player`, skaters only (goalie path, schemas,
and the server wrapper untouched; the new optional field rides through `model_dump()`).

### The read
- Reads EV offense (play-driving, repeatable) against finishing (conversion,
  volatile) — both already on the card — and attaches a `scoring_profile` insight to
  the `Assessment`. `scoring_profile.high_min: 70` (the Strong cutoff) and `gap: 10`
  live in config, tunable. Precedence: **both_high** (both ≥ high — generates and
  converts, the durable profile) → **positive_regression** (EV ≥ high, EV − fin ≥
  gap — generates chances he isn't converting, scoring may be understated) →
  **negative_regression** (fin ≥ high, fin − EV ≥ gap — conversion-led, regression
  risk) → else `None`. Forwards only: a D's finishing is excluded from his value, so
  reading a scoring profile off it would contradict that exclusion.

### Why articulation-only, and why it shares the finishing caveat's voice (the reason this entry is worth reading)
- The profile flags the *direction* of regression; it never moves the tier or the
  WAR verdict, because the model already prices EV offense and finishing into WAR —
  re-scoring off them would double-count what WAR already counted. It is a separate
  insight beside the verdict, not an input to it.
- It deliberately speaks as **one voice** with the `finishing_volatility` caveat
  rather than duplicating it. The caveat's firing rule is unchanged (it fires when
  finishing is a strength); the profile note **tempers** it when play-driving backs
  the scoring (`both_high` — Celebrini: "well-supported, so the caveat is tempered")
  and **reinforces** it when it doesn't (`negative_regression` — Dorofeyev: "this
  reinforces the finishing-volatility caveat"). So the two are **not** redundant and
  neither should be cut: the caveat says *finishing is volatile*, the profile says
  *and here is which way that volatility points*. Future-you: leave both in.

### Tests / demo
- TDD, 8 tests. Celebrini → both_high (tempered); new `dorofeyev.json` (EV 61 /
  fin 97; real player, illustrative card) → negative_regression (reinforced);
  synthetic-D → no profile (the exclusion holds). `demo_assess.py` narrates the
  profile for both forwards. Full suite 106 passed.

## Post-v1 — young-sample uncertainty caveat (2026-06-29)

Engine + config enhancement to `assess_player`, skaters only (goalie path and schemas
untouched). The card is a three-year weighted average.

### The read
- The card being a three-year weighted average is the whole point: a young skater's
  number rests on a short, recent, still-developing sample. `_caveats` attaches the
  `young_sample` caveat when `card.age <= age_uncertainty.max_age` (config, starts at
  22, tunable) — both the upside and the uncertainty are larger than the point
  estimate suggests. **Position-agnostic** (forward or D): a thin sample is thin
  regardless of position, so unlike finishing-volatility / dangerous-passing this one
  is not gated on `is_defense`.
- **Paired with the trajectory** when the trend points up: `_trend_is_up` (≥ 5 over
  the span — the same margin `_trajectory` reads as "up") appends the
  `young_sample_rising` clause, tying the youth uncertainty to the rising number (the
  recent, heavier-weighted seasons are pulling it higher, so the upside is real but
  may be running ahead of a settled level). Young + flat/down/no-trend → base caveat
  only.

### Why articulation-only
- It never moves the tier or the WAR verdict — it is one more string in `caveats`,
  same as the other auto-attached caveats. The projection is what it is; this only
  frames *how much weight the point estimate can bear* for a young player, which is a
  reading instruction, not a re-scoring.

### Tests / demo
- TDD, 5 tests against the Celebrini fixture (age 20, trend up): caveat fires, pairs
  with the rising trend, and leaves tier/verdict at Excellent/94. Negative controls:
  an inline vet (age 28) gets nothing; an inline young player with no upward trend
  gets the base caveat without the pairing. `demo_assess.py` shows it on Celebrini
  (Dorofeyev/synthetic-D, both 26, correctly get nothing). Full suite 111 passed.

## Post-v1 — metric glossary + explain_metric (2026-06-29)

A data file and a fourth tool. Skater and goalie. The analysis engines
(`assess`/`adjudicate`/`compare`) were left **untouched** — this only adds a lookup.

### The glossary (`config/glossary.yaml`)
- One entry for every card metric — 22, spanning the skater and goalie cards — each
  with a plain-language `definition` and its single most important interpretive
  `caveat`, plus `aliases` for lookup. Written in our own words, **not** copied from
  hockeystats.com (the IP line in the README). Faithfulness verified against the
  site's own player-card page and the JFresh explainer; the goalie start-quality
  metrics are **goals-saved-above-expected** based (quality = saved 0+, excellent =
  saved 2+, bad = allowed 2+), NOT save percentage — a first draft got `excellent_starts`
  wrong and it was corrected.

### `explain_metric(metric)` (`engine/glossary.py`, 4th server tool)
- A thin lookup returning `{query, found, metric, label, definition, caveat, message}`.
  Resolves the schema field name or a natural alias (case/space/underscore folded;
  British spellings accepted: `defence`→`defense`, `offence`→`offense`). Unknown input
  → `found: false` with a clear "not a card metric" message; it never guesses.
- Scope is fixed in the tool description: it **defines** a metric, it does not reason
  about a player. "Why is this a risk for HIM" is the host's job (these definitions +
  that player's `assess_player` result), not this tool's to compute.

### Single source of truth (the dedup — why it matters later)
- The caveats the engine already attaches are **not retyped** in the glossary. The
  entries for finishing, competition/teammates, first_assists, rebound_control, and
  goalie consistency use `caveat_ref` — a dotted path into `interpretation.yaml` — so
  each caveat sentence lives in exactly one place. `explain_metric("finishing").caveat`
  **is** the `finishing_volatility` sentence `assess` attaches, asserted by test. Chose
  reference-into-`interpretation.yaml` over moving the text into the glossary precisely
  so the engines (including `compare`, which reads those keys) stay untouched.
- Per the chosen design there is **no** new grounding field on the `assess`/`adjudicate`
  output; definitions are reachable via `explain_metric`, not embedded in verdicts.

### Lookup hygiene
- An alias index built at load **raises on any collision**, so two metrics can never
  silently share a normalized key. This caught the one real clash: the goalie field
  `penalty_kill` normalizes to "penalty kill", which the skater `pk` also wanted — the
  goalie field (its literal name) wins the bare phrase, and the skater PK is reached
  via "pk". The guard is itself a test.

### Tests
- TDD. `tests/test_glossary.py` — lookup by field name and alias, normalization, the
  honest not-found path, full 22-metric coverage, the single-source dedup, and the
  no-collision guard — plus two server smoke tests. Full suite 145 passed.

## Post-v1 — American spelling (offense / defense) (2026-06-30)
- **Symptom.** Host narrations kept reading "EV offence" / "EV defence". The codebase
  had standardized on British spelling as canonical — schema field keys (`ev_offence`,
  `ev_defence`), `LABELS` values, config caveat/definition prose, `compare` focus
  values, and the two normalizers (`glossary._normalize`, `compare._norm_focus`) which
  actively converted American *input* → British. The host LLM sees those field keys and
  labels and echoes them, so the British spelling leaked straight into the prose.
- **Decision.** Flip canonical to **American everywhere** — field keys are now
  `ev_offense` / `ev_defense`; labels, config text, focus values, fixtures, tests,
  demos, and docs all read offense/defense. A prose-only patch was rejected: leaving the
  British field keys visible in the schema/server docstrings would keep priming the host
  to echo British. Safe to rename the keys because this is a local single-user server
  with no external caller — the host is driven by the live tool schema.
- **Graceful input.** The two normalizers were flipped, not deleted: British spellings
  are still accepted as aliases and folded to the American canonical (`offence`→`offense`,
  `defence`→`defense`), so a host or user typing "ev defence" or `focus="defence"` still
  resolves. Asserted by the existing glossary normalization test (which now exercises
  `EVEN-STRENGTH DEFENCE` → `ev_defense`).
- **Invariant unchanged.** Pure spelling/identifier rename — no reading rule, tier band,
  or verdict changed. Full suite 145 passed; the four narration demos re-run clean with
  zero British spelling in any output.

## Post-v1 — skater_style dimension (2026-07-01)

Config + test only — no engine change (see below for why that's not just a claim).

- **What.** The skater-side parallel to `goalie_style`: closes the gap where
  `adjudicate_claim` could otherwise overreach on a skater playing-style claim
  ("physical, north-south power forward") that a standard card genuinely cannot
  measure. New dimension `skater_style` (`applies_to: skater`, `metrics: []`,
  `answerability: not_answerable`), with 15 aliases covering rush-vs-cycle, north-
  south/east-west, skating/speed, physicality, forechecking, and archetype words
  (grinder, agitator, pest, power forward). Note points to the $10 microstat card
  for zone-entry/rush tendencies, but is explicit that skating and physicality
  aren't measured there either.
- **Why `physical` sits here and not in `discipline` (the call someone would
  otherwise second-guess).** `discipline`'s metric is `penalties` — the penalty
  *differential* (drawn minus taken), not physicality itself, and the glossary
  caveat on that metric already says so: "a low mark is an undisciplined flag, not
  a lack of physicality. Do not invert it." A player can hit hard and stay
  disciplined, or play a soft north-south game and still take bad penalties — the
  card only ever speaks to the second thing. So "physical" (the style trait) is
  unanswerable and lives in `skater_style`; "takes too many penalties" (the
  measured claim) stays in `discipline`. Keeping the alias here rather than in
  `discipline` keeps this dimension consistent with that glossary caveat instead
  of contradicting it.
- **No engine change, and this is the point.** `adjudicate.py`'s not-answerable
  branch is generic over `answerability: not_answerable` + config `note` — it has
  no per-dimension logic, so it already worked for any new id added to the
  dictionary. `net_front` and `goalie_style` proved the path; `skater_style` is
  the third data point confirming it, not a new case to handle. Verified via
  `git diff src/engine/adjudicate.py` (empty) before committing.
- **Tests.** TDD — one test added confirming a compound style claim ("physical,
  north-south power forward") resolves to `unverifiable` with the config note
  surfaced, watched fail (unrecognized dimension) before the config entry existed.
  Full suite 146 passed.

## PDF report generation (2026-07-03)

New fourth layer `src/reports/` plus a fifth MCP tool `render_report(kind,
result, title?)`: turn the answer the host just gave into a downloadable,
styled PDF at ~/Documents/HockeyCardReports/ (filename = player(s) + kind +
date). Built in three phases against a private local web companion whose
assess-screen design is the visual spec; consolidated here for this repo.

- **Renderer core:** engine structured output -> Jinja2 HTML -> WeasyPrint,
  fully local (no headless browser, no network, no LLM at render time).
  Five kinds: assess_skater, assess_goalie, compare (two columns, per-
  component gaps, honest split/refusal), claim_check (graded rows with all
  four statuses incl. UNVERIFIABLE), and interpretive — Claude-authored
  prose, prominently badged "Interpretive read · AI — not an engine
  verdict", with the honest-caveat box placed ABOVE the prose so it frames
  the read. Footer attribution ("Built on HockeyStats.com (JFresh Hockey)
  player cards.") + page counter on every page via @page margin boxes. The
  source card image is never embedded (tested). Fonts (IBM Plex Sans/Mono +
  Sora latin subsets, OFL) are bundled in reports/fonts. On macOS,
  WeasyPrint needs `brew install pango`; reports/pdf.py extends
  DYLD_FALLBACK_LIBRARY_PATH in-process before the deferred import
  (ctypes' find_library reads it at call time), so the MCP host needs no
  launcher env config and a missing native lib surfaces as a ToolError,
  never a dead server.
- **Validation IS the engine's own output models:** save_report round-trips
  the passed result through Assessment / GoalieAssessment / Comparison /
  Adjudication for the chosen kind, so a retyped, trimmed, or wrong-kind
  result fails loudly instead of rendering a plausible wrong report.
  Interpretive has its own strict schema (extra="forbid", sections
  non-empty). claim_check carries no player name in its result, so the
  host passes the claim sentence as `title` and it names the file.
- **Live-loop steering (host-tested in Claude Desktop):** the offer-the-PDF
  instruction rides on the ENGINE tools' descriptions (the tool the host
  just used — its own description is what it re-reads), not only on
  render_report; and assess_player's description pins narration to the
  returned structure after the host was seen promoting the `descriptive`
  reads (goals/first assists — color, deliberately outside the value
  verdict) into "strengths". The assess report renders descriptive reads
  in their own "Color, not the verdict" panel. Both steering rules are
  guarded by description-content tests — don't reword casually.

## Post-v1 — trajectory bounciness (2026-07-02)

Engine + config, skaters and goalies, TDD, articulation only (no tier or
verdict moves — asserted by test). Closes the nit that a non-monotonic trend
reads as its endpoints: Hughes's real card (93 → 97 → 92) said "holding
steady," hiding the peak season.

### The rule (and the two calibration calls that differ from the request)
- `_bounce_note(values, cfg)` — shared by `_trajectory` and
  `_goalie_trajectory` (both now take cfg): an interior season is named only
  when it (a) breaks past BOTH endpoints and (b) deviates from the straight
  endpoint-to-endpoint line by more than `trajectory.bounce_margin`.
  Peak → "with a peak season (97th) in between"; dip → "with a down year
  (45th) in between"; both → both, largest of each.
- **Why the envelope condition (a):** the request said "any interior point
  deviates from the line by more than a threshold," but Thompson's monotonic
  38 → 90 → 99 deviates from the line by +21 and the request requires it to
  stay clean. A rise that comes fast-then-slow is still just a rise; only a
  true peak/dip (outside the endpoint envelope) is a shape worth naming. The
  envelope makes monotonic series structurally immune, at any margin.
- **Why `bounce_margin: 4`, not the requested 10:** the real Hughes card's
  hidden peak deviates from the endpoint line by 4.5 points (97 vs the
  92.5 line) — a margin of 10 hides the exact case the feature exists for.
  Chart-reading noise is ~1–3 points; 4 separates. Both flagged for review;
  tunable in `interpretation.yaml`.
- Bonus articulation from the requested example string: "holding steady" at
  min(endpoint) ≥ STRENGTH_MIN reads "holding steady at a high level"
  (steady at 92 and steady at 45 are different facts) — `_trend_phrase`,
  shared by both paths.

### Fixture + the vision-path catch
- New fixture `tests/fixtures/hughes.json`, extracted from the real card
  image via the webapp's own `/api/read-card` and hand-verified box-for-box
  against the image (trend values approximate per fixture convention). This
  was the FIRST real-card end-to-end run — and it caught a real extraction
  bug: vision invented an `offence_defence_finishing_trend` key for the
  card's second chart; the strict schema rejected it loudly (as designed).
  Fixed in the extraction prompt ("output ONLY the fields listed; other
  charts have no field"), after which both real cards extract cleanly.
- Tests (11): Hughes peak named + tier/verdict unchanged; dip case; Thompson
  (fixture) and a synthetic skater riser stay clean; flat stays clean (low
  flat gets no level tag, high flat gets the tag but no note); goalie dip;
  margin config-tunable (override kills the note); 2-point noise stays
  quiet; two-point trends byte-identical. Full suite 202; all four demos
  re-run with prose unchanged except the intended strings.

## Team and age are optional card context (2026-07-03)

Real trigger: a real UFA card (Gritsyuk) — its Age line is printed blank
and no team appears anywhere on the card. The host was correctly refusing
to guess, and the strict schema then rejected the card ("team/age Field
required"), which made an honest extraction impossible. TDD (fixture + 3
new tests).

- **Schema:** `team` and `age` are now `Optional` on `_SkaterBase` and
  `GoalieCard` (age keeps its 15–60 bound when present). They are context
  fields — they never feed a verdict — so their absence is unknown context,
  not a validation failure. The strictness principle is unchanged: a
  MIS-extracted card still fails loudly; a field the card genuinely does
  not carry no longer does.
- **Engine:** unknown age is not young — the young-sample caveat requires
  `age is not None` before comparing against `age_uncertainty.max_age`
  (evidence to fire, absence stays silent). `Assessment.team` /
  `GoalieAssessment.team` are Optional and simply echo through.
- **Host extraction guidance** (assess_player tool description): the card
  shapes bracket [team, age] as optional, with an explicit rule to omit
  them when the card doesn't print them and NEVER to infer the team from
  the jersey/photo.
- **Demos:** narrators drop the "(team)" parenthetical when team is absent
  instead of printing "(None)".
- New fixture `tests/fixtures/gritsyuk.json` (real card, team/age absent).

## MCP parity port from the webapp — description-level (2026-07-04)

The user is consolidating onto the MCP server; a full audit mapped every
capability of the private local web companion against the tools. These
gaps were closed at the description/prompt level only — no engine logic,
no schema changes. All are guarded by description-content tests
(test_server.py) so rewording can't silently drop them.

- **Interpretive-read contract** (render_report description — all MCP tool
  descriptions co-load in the host's context, so guidance there is always
  visible): unit shape enforced by the host (EXACTLY 3 forwards for a line,
  2 defensemen for a pairing, goalie + 2 D for support; mismatched mix →
  flag and ask, don't read the wrong unit); the line-synergy
  complementarity checklist and the goalie-support directional questions
  ported nearly verbatim from the companion app's prompts; output shaped
  roles / works / concerns / caveat / summary, mapping 1:1 onto the
  interpretive PDF's sections.
- **Interpretive labeling in chat:** the read is labeled interpretive/AI in
  the chat answer itself, every time — the PDF badge said out loud, not
  only rendered.
- **adjudicate_claim dimension list** gained skater_style, net_front,
  team_leading_scorer, goalie_style — all long since in
  config/interpretation.yaml; the docstring list just lagged.
- **Standing disclaimer** on all three verdict tools: "Reads are model
  projections, not predictions. Numbers are percentiles unless noted."

## Interpretive report: structured units + markdown-safe text (2026-07-05)

Live gap: a structured chat answer (four-line roster construction — per-line
player reads, works, concerns) flattened into paragraph soup in the
interpretive PDF, with literal `**` and `-` markdown characters where the
chat had bold and bullets.

- **`InterpretiveResult` grew `units`** (save.py): each unit is
  {name, players: [{name, read, key_numbers}], works: [], concerns: []},
  `extra="forbid"` throughout; `sections` is no longer required on its own —
  the model now demands at least one of units/sections. Units render as one
  card per unit: player rows (display-font name, mono accent key numbers,
  one-line read) over the companion app's goalie-support what-helps/
  what-hurts two-column boxes (green + items / red − items), ported into
  base.html CSS. Sections stay as the freeform fallback (extras, method
  notes) and now render real paragraphs/lists.
- **Markdown never renders literally.** Interpretive text is Claude-authored,
  so render.py escapes it, then converts `**bold**`/`*em*` to styled text and
  leading `-`/`•`/`1.` lines to real `<ul>` lists; stray heading/bullet
  markers are stripped. Escape-first keeps autoescape's HTML-injection
  guarantee (guarded by a test).
- **render_report description steers the choice** (test-guarded like the rest
  of the host steering): per-line/per-pairing answers go through `units`,
  `sections` only for genuinely freeform prose, and every field is PLAIN
  TEXT — markdown is converted or stripped, never shown.
- Badge, caveat-before-content placement, footer attribution, and the engine
  kinds are untouched. demo_reports.py gained a goalie-support preview
  (sections path) and the roster-construction preview (units path) as the
  eyeball cases.
