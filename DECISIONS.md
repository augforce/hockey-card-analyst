# Decisions log

Choices made during the build that the PLAN did not fully specify. Section
numbers refer to `hockey-card-analyst-PLAN.md`. Section 13 open defaults are all
accepted as-is.

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
  components (`ev_offence`, `ev_defence`, `finishing`, `penalties`) and
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
  means he is not used there. (`ev_defence` = 33 is the actual defensive read;
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
- Three buckets: **WAR components** (`ev_offence`, `ev_defence`, `pp`, `pk`,
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
  "asked to do more" maps to BOTH playmaking and defence (section 3) — and they
  disagree: playmaking is Elite (95th, refutes "limited") while EV defence is
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
- Area leaders: offence = avg(ev_offence, pp, finishing); defence =
  avg(ev_defence, pk); a lead counts only at ≥ `MARGIN` (5).
- **Genuine split** (areas have opposite leaders) → `overall_edge=None`,
  `edge_kind="split"`, prose says "better at what" and names the tradeoff —
  UNLESS projected WAR differs by ≥ `PROJ_DECISIVE` (10), in which case the edge
  goes to the proj-WAR leader (`edge_kind="proj_war"`) with the tradeoff noted.
- Not a split: a player leading the area(s) → `broad`; else a proj-WAR gap ≥
  MARGIN → `proj_war`; else `even` (`overall_edge=None`).
- `MARGIN=5` / `PROJ_DECISIVE=10` are constants in `compare.py` (tunable).

### Durability flag
- If the winner's finishing lead exceeds their largest play-driving (EV
  offence/defence) lead, the edge is "less durable — leans on finishing" and the
  finishing-volatility caveat is attached; otherwise "durable — play-driving".

### focus
- `offence`/`defence` narrow to that area and CAN crown a within-area winner even
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
  the two split-areas. Skaters split offence-vs-defence; goalies split
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
