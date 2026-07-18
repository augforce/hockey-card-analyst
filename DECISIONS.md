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
  image by an AI vision pass and hand-verified box-for-box
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

## MCP parity port — description-level (2026-07-04)

The user is consolidating onto the MCP server; a full audit mapped every
capability of a private companion tool (since retired) against the tools. These
gaps were closed at the description/prompt level only — no engine logic,
no schema changes. All are guarded by description-content tests
(test_server.py) so rewording can't silently drop them.

- **Interpretive-read contract** (render_report description — all MCP tool
  descriptions co-load in the host's context, so guidance there is always
  visible): unit shape enforced by the host (EXACTLY 3 forwards for a line,
  2 defensemen for a pairing, goalie + 2 D for support; mismatched mix →
  flag and ask, don't read the wrong unit); the line-synergy
  complementarity checklist and the goalie-support directional questions
  ported nearly verbatim from the companion tool's prompts; output shaped
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

## Microstat cards — the $10-tier card across all tools (2026-07-18)

Schemas + config + engine + server + reports. The goalie path, the standard
skater path, and every existing verdict are untouched (all 207 pre-existing
tests pass unmodified); goalies remain standard-card-only because no goalie
microstat card exists.

### What the card is (and why it's a regime, not just more boxes)

- Verified against two real cards: Celebrini (forward micro) and Schaefer
  (defense micro). Both surfaced fields the hand-collected definitions list
  missed — Celebrini: Entries w/ Possession, Exits w/ Possession, D-Zone Puck
  Touches; Schaefer: Entry Possession Rate, Pass Exits, Carry Exits — which is
  exactly why the schema was built from card images, not from the list alone.
- **Single-season, 5v5, per-60** (footer: "percentile ranks among
  forwards/defencemen … in 2025-26"), microstats tracked by AllThreeZones, WAR
  row from TopDownHockey. No Proj. WAR headline, no age/TOI/cap, no
  competition/teammates, no trend charts. `season` is a REQUIRED schema field —
  the sample window is load-bearing context for every verdict.
- **Skating Speed is forward-only** (NHL Edge tracking, not AllThreeZones) —
  the D card does not carry it, so "great skater" claims about a defenseman
  stay honestly unanswerable even on the micro card.

### Design calls

- **Explicit `card_kind: "micro"` discriminator, and `_parse_card` refuses a
  micro card without `position` (the reason: no position box exists on the
  card).** The pool comes from footer text, so the extraction must state it —
  a silent forward default would misread every D micro card. Field-presence
  sniffing was rejected: a mis-extraction should fail loudly, not guess.
- **WAR row is value; microstats are descriptive — the same
  descriptive-not-value discipline as goals/first assists, extended to 24-27
  boxes.** Microstats are raw tracked rates, not teammate/competition-adjusted
  isolates, so `MicroAssessment` keeps strengths/weaknesses on the WAR row and
  reports the tracked columns as profiles + standouts/soft spots. No overall
  tier is invented (no `proj_war_pct` box; `overall_note` says to get the
  standard card).
- **The style trio (hits, skating speed, forecheck involvement) is never a
  weakness at any percentile.** Celebrini's 27th-percentile Hits is a style
  fact. `micro_style_not_value` lives in `caveats.*` and — deliberately —
  attaches on EVERY adjudication grade including `not_supported`: refuting
  "he's physical" with a low Hits number is precisely when the reminder is
  needed.
- **Paired profiles are articulation-only config shapes
  (`micro_profiles`), same pattern as `scoring_profile`.** Shot selectivity
  (chances vs shots), passing quality (chance assists vs shot assists), attack
  style (rush vs in-zone), and the D rush-defense trio — the source
  methodology literally scripts these reads ("tight gap but gets walked",
  "soft gap protecting the slot"), so they're encoded as shapes with
  `high_min: 70`, `gap: 15`. A family with no clear shape is omitted, never
  forced (Celebrini's 91-vs-79 shooting profile stays silent at gap 15 — by
  design). Rush-defense front = mean of denial + possession prevention;
  chance prevention listed first because the definitions call it the most
  important of the three.
- **Claim routing reuses the alias-collision pool preference — config-only
  where promised.** `_claim_pool` returns "micro"; micro dimensions
  (`applies_to: micro`) share aliases with the standard `skater_style`
  catch-all on purpose: same phrase, answerable with a receipt on a micro
  card, honestly unverifiable on a standard card. The standard-card
  `skater_style`/`net_front` notes were corrected — the old text claimed
  skating and physicality aren't measured on the micro card; the real card
  disproved that.
- **Two honest "no value here" messages in adjudicate.** A metric that exists
  but is None reads as an NA role; a metric the card type doesn't carry reads
  as "isn't a box on this card type — the standard/microstat card carries it"
  (`_primary_metric` prefers an existing-but-NA metric over an absent one so
  the right message fires). "He's elite" against a micro card points at the
  standard card instead of claiming a role absence.
- **Compare: micro pools are new pools, and micro-vs-standard is refused even
  for the same player.** `forward_micro`/`defense_micro` specs put the tracked
  columns in the component display but keep edge logic on the WAR row.
  `proj_gap` is None for micro pools: no headline tiebreak exists, so a
  genuine split STAYS a split — the refusal-to-crown discipline survives the
  missing headline. The same-position cross-regime pair gets its own refusal
  reason citing `micro_rules.war_row`.
- **Both-cards synthesis is articulation-only and guarded.**
  `assess_player(card, micro_card=…)` requires same player (casefolded name)
  and same pool; goalie + micro raises. Divergences fire at
  `DIVERGENCE_MIN = 15` (Celebrini: EV defense 33 projected vs 67 this season
  fires; finishing 92 vs 91 stays silent). Insights read tracked evidence
  against the standard verdicts (finishing backed/undercut by chance volume,
  the dangerous-passing caveat resolving into HD-passes evidence, D impact vs
  tracked rush defense). Tier equality is asserted by test.
- **Six definitions are INFERRED, pending verification** (marked in
  glossary.yaml comments): entries_w_possession, exits_w_possession,
  d_zone_puck_touches, entry_possession_rate, pass_exits, carry_exits. The
  meanings were inferred from the documented tracking conventions with
  Michael's sign-off; each carries a caveat noting the inference. Swap in the
  official wording when pulled — the entries are the only place it lives.
- **Reports: new `assess_micro` kind** (neutral banner, no WAR pct block,
  profile panels, standouts/soft-spots/style panels); the skater template
  gains a micro-synthesis panel badged "Articulation only — the verdict above
  is unchanged". Same engine-result-only contract: `save_report` validates
  against `MicroAssessment`.

### Tests / demos

- TDD throughout: schemas (12), config coverage (53, incl. per-metric glossary
  parametrization introspecting the schema fields), assess (22), adjudicate
  (12), compare (8), reports (7), server wiring + description guards (10).
  Full suite 207 → 331 passed.
- `examples/demo_micro.py` narrates the forward micro, defense micro, and
  both-cards synthesis reads; `demo_reports.py` now also renders
  assess_micro (F + D), the synthesis skater report, and a micro-vs-micro
  compare into `report_previews/`. Prose eyeballed; Schaefer PDF page 1
  visually checked.

## WAR methodology anchors — distilled from the model author's write-up (2026-07-18)

Config + one engine hook + glossary enrichment, from the TopDownHockey "NHL
WAR Explained" write-up Michael supplied. Articulation only throughout — no
tier, threshold, or verdict moves (asserted by test). Most of the write-up
validated what was already encoded (dangerous-passing shortcoming, finishing
vs play-driving repeatability, deployment-not-value, point-estimate framing);
four things were new and are now in config:

- **Replacement level ≈ 37th percentile (`war_reading.replacement_pct`).**
  The source: 0 WAR is 37th percentile over three seasons among skaters with
  ≥200 minutes. The engine appends `war_reading.replacement_note` to a skater
  assessment whose proj WAR sits at or below it — "Below average (34th)"
  under-reads what the model is actually saying there. Skaters only (the
  figure is skater-derived; goalie replacement is defined differently).
- **The model overweights shooting, understates play-driving — by the
  author's own admission** (ridge shrinkage biases play-driving toward
  average; replacement-level shooting is disproportionately bad; "if I were
  to weigh each component… less emphasis on shooting"). Folded into
  `caveats.finishing_volatility` rather than a second caveat — same voice,
  one sentence, and it flows to every place that caveat already attaches
  (finishing strengths, conversion-led profiles, finishing-driven compare
  edges, the glossary).
- **PP is the noisiest component** ("the expected goal models can't even be
  classified as good on the power play") — appended to the `pp` glossary
  caveat, keeping the load-bearing NA-role wording intact (guarded by test).
- **Point-estimate framing + factual enrichments.** `proj_war_pct` now
  carries `war_reading.point_estimate` via caveat_ref (value added ≠ how
  good; starting point, never the ending point) and its definition names the
  37th-percentile replacement anchor. EV definitions note the empty-net
  exclusion (EV = 5v5/4v4/3v3 with both goalies in). Penalties definition
  prices the minute (~0.11 goals) and credits the defensive half of a drawn
  penalty. `caveats.dangerous_passing` gains the linemate-contamination
  mechanism (an elite passer's linemates post hot finishing numbers, a
  shoot-first star's run cold — the MacKinnon/Matthews example generalized).
- **Not adopted:** re-weighting anything. The author says he would weigh
  shooting down "in an entirely arbitrary manner" — the tool stays on the
  published numbers and carries the admission as a caveat instead, which is
  the difference between reading the model honestly and quietly building a
  different model.

Tests: `tests/test_war_reading.py` (8) — replacement note fires at 37 and
below, silent at 38 and for Celebrini, tier unchanged at 37; caveat/definition
content guards for the weighting admission, PP noise (NA wording preserved),
point-estimate framing, empty-net exclusion, and the 0.11 price. Full suite
331 → 339 passed.

## xG substrate anchors — distilled from the model rebuild write-up (2026-07-18)

Config-only (two glossary caveats, one goalie rule), from the HockeyStats
expected-goals rebuild article Michael supplied (tracking changes, short
misses, model drift, the new nested-CV/half-life model). Articulation only;
full suite 339 → 343.

- **What was deliberately NOT encoded (the main call of this entry).** Most of
  the article is substrate engineering — short-miss reclassification, nested
  cross-validation, the half-life hyperparameter, per-season calibration,
  AUC tables. The card percentiles the tool receives already come OUT of the
  rebuilt model, so teaching the tool the model's internals would be trivia,
  not reading rules. Also skipped: the "goalies +82 GSAx this half-season"
  observation (season-specific, will go stale) and the legacy-model
  inflation story (the tool never sees legacy-model cards). Only durable
  reading rules were kept.
- **Cross-season drift slack on the goalie trend read.** The Save% vs
  Expected Save% chart's expected line is a model output on a tracking
  substrate that has demonstrably drifted (statistically significant
  season-over-season changes in short misses, crease-shot share, behind-net
  share), and the model is recalibrated season by season. Appended to
  `goalie_rules.save_lines`, which already attaches automatically whenever a
  goalie card carries the sv-vs-xsv trend — a cross-season level shift in
  the gap can be partly model-side, not goalie-side.
- **PK reads inherit the PP-xG weakness, on both card types.** The write-up's
  own validation grades power-play xG weakest (AUC 0.695 vs 0.800 at EV) —
  and shorthanded save performance / PK defense are measured against
  power-play shots. Appended to the goalie `penalty_kill` glossary caveat
  (isolates-the-goalie wording preserved) and the skater `pk` caveat
  (NA-role wording preserved, both guarded by test). This completes the
  component-reliability picture started in the WAR-anchors entry: EV
  strongest, PP/PK noisiest, on both sides of the puck.

Tests: `tests/test_xg_substrate.py` (4) — caveat content guards plus an
end-to-end assertion that the drift slack reaches a Thompson assessment via
the existing save-lines attachment.

## RAPM context anchors — distilled from the isolating-impact write-up (2026-07-18)

Config + one engine attachment, from the RAPM methodology article Michael
supplied (the regression dataframe, ridge regularization, prior-informed
daisy chain). Articulation only; full suite 343 → 351.

- **Deployment-artifact claims are now answered with the full adjustment
  list.** The write-up documents that EV RAPM adjusts for zone starts, score
  state, home ice, back-to-backs, and power-play-expiry shifts — far more
  than the "teammates and competition" the config previously cited.
  `caveats.deployment_not_value` and both EV glossary definitions now name
  the list, so "he only produces because of easy zone starts" gets the
  correct answer: that context is priced in before the card is printed. New
  `competition` aliases (sheltered / easy minutes / protected deployment)
  route those claims to the deployment machinery.
- **Forward defensive impact is the less repeatable half — new
  `caveats.defense_repeatability`.** The published prior-trend coefficients
  (forward offense 0.446 vs forward defense 0.280) mean the model's own
  priors regress a forward's past defensive impact roughly twice as hard
  toward average. The caveat is canonical in one place and attaches three
  ways: engine-side when a forward's assessment has `ev_defense` as a
  strength (mirroring the finishing-volatility pattern), on `two_way`
  claims via the dimension dictionary, and as the `ev_defense` glossary
  caveat via caveat_ref — where it absorbs the prior impact-not-hits
  sentence so the identity framing survives (guarded by test). Forwards
  only: the published coefficients are forward-specific, so a defenseman's
  defensive verdict does not get it (also guarded by test).
- **Not encoded:** the regression mechanics themselves (dataframe
  construction, lambda cross-validation, the unregularized-APM cautionary
  chart, the daisy chain). Same reasoning as the xG entry: the percentiles
  already come out of this machinery; the tool needs the reading rules, not
  the recipe. The regularization section independently re-confirms the
  ridge-shrinkage sentence already living in `finishing_volatility`.

Tests: `tests/test_rapm_context.py` (8) — adjustment-list content, sheltered
routing with deployment caveat, the repeatability caveat firing for a
forward EV-defense strength / two_way claim and NOT for Celebrini (33rd) or
a shutdown defenseman, and glossary identity+repeatability coexistence.

## Inferred micro definitions are now canonical (2026-07-18)

Resolves the "verify against the site glossary" flag from the microstat
checkpoint entry. Michael checked the source: the site publishes NO official
definitions for the six undocumented boxes (entries_w_possession,
exits_w_possession, d_zone_puck_touches, entry_possession_rate, pass_exits,
carry_exits). There is nothing to verify against, so the inferred readings —
derived from the documented tracking conventions for the neighboring metrics
(e.g. Exit Possession Rate's published definition implies its entry-side
twin) — are canonical.

- **The honesty framing changed, not the definitions.** The caveats promised
  a verification that can never happen ("pending verification against the
  source glossary"); they now state the truth: "No official definition is
  published for this box — the read is inferred from the card's documented
  tracking conventions," keeping each entry's metric-specific tail. The
  glossary comments and CLAUDE.md pointer were updated to match.
- **The disclosure is now test-guarded** (`test_inferred_entries_disclose_
  the_inference` in test_micro_config.py): each of the six caveats must keep
  the words "inferred" and "no official definition" — the inference must
  never silently pass as sourced.
- If the site ever publishes definitions for these boxes, this entry is the
  pointer: update the six entries, keep the caveat_ref-free structure, and
  drop the disclosure only if the official meaning matches the inference.

Full suite 351 → 352 passed.

## Scouting-report calibration — motor scope + missing-metric honesty (2026-07-18)

Config + one adjudicate fix, from comparing an engine-narrated Celebrini read
(both cards) against the site's prose scouting report. The comparison mostly
validated the engine — transition identity, dangerous-passing insight (the
site's deception/pre-shot-movement passages describe exactly what xG can't
see), and the improving-but-not-bankable EV defense arc all agreed — but two
divergences generalized into fixes. Full suite 352 → 359.

- **Motor/compete claims are broader than Forecheck Involvement — new `motor`
  dimension (micro pool, answerability partial).** The site's loudest theme
  ("unmatched motor", "elite puck-battler on the wall", stick-lifts, all-ice
  pursuit) coexists with Celebrini's ordinary 57th forecheck involvement,
  because that box tracks only offensive-zone recoveries and exit pressures.
  A motor claim now grades PARTIAL with the number as one slice, never
  settled by the box; "high motor"/"grinder"/"puck battler" moved off the
  `forechecking` dimension (which keeps the specifically-forechecking
  aliases, answerable, unchanged). The forecheck_involvement glossary caveat
  now scopes the metric the same way. Narration lesson recorded: an earlier
  read inferred "wins pucks by skating, not hounding" from the 57th — an
  over-read the scope caveat now prevents.
- **The missing-metric message must not point at a card that lacks the box.**
  "Turnover-prone" about a FORWARD resolved to Success per Poss. Play (a
  D-card-only box) and answered "the standard card carries it" — false; no
  card tracks forward puck security. `_COUNTERPARTS` maps each card type to
  its same-player counterpart (goalies map to none); the fallback now names
  the other card only when it actually carries the metric, else says
  "isn't tracked on either card type for this position." Regressions
  guarded: overall-value claims on a micro card still point at the standard
  card (proj_war_pct really is there); style claims on a standard card still
  point at the micro card; goalie missing-metric messages claim no
  counterpart.
- **Deliberately NOT changed:** the cycle tension. The site praises his
  cycling craft while the card grades in-zone offense 64th — style prose and
  per-60 production share can disagree without either being wrong, and the
  rush-led profile is the correct arbitration. Player-specific scouting
  claims (breakaway moves, net-crashing timing, puck protection) stay
  unencodable by design — the engine reads cards, not players.

Tests: `tests/test_scouting_calibration.py` (7) — motor partial with receipt,
forechecker unchanged, glossary scope caveat, forward-turnover honesty (no
false pointer), plus the three pointer regressions.

## Scouting-report calibration II — defensemen (2026-07-18)

Config + tests only, from comparing the engine's Luke Hughes read (both
cards) against the site's prose scouting report. Full suite 359 → 361.

- **Validation, mostly.** The comparison was the tool's strongest showing
  yet: the prose omitted the turnover crisis entirely ("moves the puck well
  in transition" vs 19th exit success / 7th retrieval success / 24th success
  per possession play) and compressed a present, measured defensive crisis
  (5th projected EVD, 3rd this season, 12th entry chance prevention, falling
  75→28→25 arrow) into "a lack of elite awareness may hold him back." Both
  divergences are the failure modes the engine exists to resist — no changes
  from them. Direct agreements: hits 6th ↔ "hardly ever throws a body
  check"; the dangerous-passer profile ↔ "quality and efficient playmaking";
  the PP-ran-hot divergence flag ↔ "flashed serious skills with the man
  advantage"; discipline 87th ↔ "drawing penalties."
- **Motor claims about defensemen now cite the D-side slice.** The `motor`
  dimension cited only forecheck_involvement, which D cards don't carry —
  so "works hard without the puck, chasing down loose pucks" about a D came
  back "not tracked at all," which is too strong: D cards track one slice of
  motor (D-zone retrieval workload). `d_zone_retrievals` appended to the
  dimension's metrics (position-resolution falls through automatically) and
  the note reworded to name the per-position slice. Still partial, never
  settled — wall battles and stick checks remain untracked, per the note.
- **Skating-on-D honesty confirmed in a test.** "Skates faster than almost
  any other blueliner" is unverifiable on a D card — Skating Speed is a
  forward-card-only box — and the counterpart-aware message correctly says
  the position isn't tracked rather than pointing at a card that lacks the
  box. Now pinned by `test_skating_claim_on_defenseman_is_honestly_untracked`.

Tests: two added to `tests/test_scouting_calibration.py` (9 total there).

## Scouting-report calibration III — the physical winger (2026-07-18)

Config + description + tests, from the Will Cuylle comparison (both cards vs
the site's prose report) — the deliberately-chosen inverse archetype: the
first sample where the prose LEADS with physicality and motor. Full suite
361 → 365.

- **Net-front claims on a micro card now use the proxy — partial, with the
  receipt.** Cuylle validated Shots off HD Passes as the net-front proxy in
  the strongest possible way: a scouted "solid net-front presence with great
  hand-eye for deflections" posted a 96th there against 23rd in-zone shots
  and 45th chances — that shape has exactly one explanation. New
  `net_front_presence` dimension (micro pool, answerability partial,
  metrics [shots_off_hd_passes]): the claim grades partial with the number
  cited and the note honest that literal location still isn't tracked. On a
  standard card the same phrase still routes to `net_front` (unverifiable) —
  regression-pinned. The prior stance (keep it unverifiable everywhere) was
  set before evidence existed that the proxy tracks the trait; Cuylle is
  that evidence.
- **Passer claims on a tracking card grade on process, not assist
  outcomes — new `playmaking_micro`.** The site's "not much of a passer" was
  emphatically supported by process (9th shot assists, 36th chance assists,
  18th HD passes) yet the engine graded it against primary assists (66th —
  an outcomes stat that rides on linemates finishing) and pushed back on the
  scout. `playmaking_micro` shares the standard `playmaking` aliases (pool
  preference routes the phrase) with metrics ordered chance_assists →
  primary_shot_assists → primary_assists. Principled, not overfit: grading
  passing claims on tracked passing process is the same results-vs-process
  distinction the whole card system is built on. Id-based `playmaking` calls
  are unchanged (existing test still passes).
- **Validated, no changes:** hits 97th stayed a style read under maximum
  pressure (the prose leads with "crushing body-checks"; the engine credits
  the style while the value verdict rests on the WAR row — his discipline,
  7th/15th, is where the physicality's cost shows up as value, matching the
  prose's own "crossing the line" admission). The trajectory bounce note
  caught the hidden 59th peak season. The forward-EVD repeatability caveat
  fired on his 91st. And the prose never mentioned that 91st/97th EV defense
  IS his value case — the same eye-test blind spot for unglamorous value as
  the Hughes turnover omission, recorded as validation.
- **Deliberated, kept as-is:** shot_selectivity stayed silent for shots 60 /
  chances 45 (gap 15 but below `high_min`) even though the prose confirms
  the perimeter-volume lean. The threshold exists to keep noise-level leans
  quiet; one confirmed sub-threshold case doesn't justify loosening it.
  Revisit only if sub-threshold leans keep matching prose.

Tests: four added to test_scouting_calibration.py (net-front partial +
standard regression, passer-on-process + elite-passer regression), micro-dims
description list extended, `cuylle_micro.json` golden fixture added.

## Scouting-report calibration IV — the elite shutdown D (2026-07-18)

Config + engine, from the Jaccob Slavin comparison (both cards vs the site's
prose report) — the positive-defensive archetype, deliberately the last gap
in the calibration grid. All four fixes are in the POSITIVE direction: the
engine could name every failure shape but went quiet on excellence. Full
suite 365 → 371. Golden fixtures slavin.json / slavin_micro.json added.

- **`line_dominant` rush-defense shape.** Front-of-line defense at 96th/95th
  with chance prevention 63rd fit no shape, so the engine said nothing about
  the rush defense of the best rush defender yet fed to it — while the
  site's whole thesis ("specializes in defending one-on-one... closing out
  rapidly") is those two numbers. New shape: elite front, ordinary ECP —
  with the note carrying the selection-effect insight that the entries he
  erases never reach the chance-prevention box. Schaefer regression pinned
  (still lockdown).
- **`breakout_style` profile family (D only).** Exit success 94th on
  possession retention 21st is the site's "makes the right simple play to
  get it out of danger" — a deliberate style executed well — but the engine
  left 21st/23rd sitting in the lows reading as flaws. Four shapes off
  success-vs-retention, with BOTH poles validated by real cards and prose:
  Slavin (safe_and_effective) and the earlier Hughes card (74th retention /
  19th success = ambitious_and_costly). This is the D-transition
  counterpart of scoring_profile: two numbers that can only be read as a
  pair.
- **Blue-line corroboration in the synthesis.** The D insight rule keyed
  only on ECP >= 70, so a 99th-percentile defensive impact got ZERO tracked
  corroboration despite 96/95 at the line. New branch: when ECP is
  ordinary but the front is elite, corroborate at the blue line and explain
  the ECP number rather than ignoring it.
- **No finishing divergences for a D.** Slavin's finishing ran 48 -> 16 and
  the synthesis flagged it — noise, since finishing is excluded from a D's
  value on both cards. The divergence loop now skips war_excludes for
  defensemen.
- **Validations, no change:** hits at the 1st percentile for an elite
  shutdown D is the style-not-value rule's crowning exhibit (the prose
  never mentions physicality either); "get shots through" matched the
  volume_led selectivity shape (71st shots / 41st chances — point shots);
  "can head up-ice with it himself" matched rush_led 90th; the trajectory
  bounce named the hidden 89th down-year inside a holding-steady-at-elite
  read; and the site's technique catalogue (stick detail, sprawling) is
  correctly untracked.

Tests: six added to test_scouting_calibration.py (19 there; line_dominant,
both breakout poles, blue-line corroboration, D-finishing divergence
suppression, Schaefer lockdown regression).
