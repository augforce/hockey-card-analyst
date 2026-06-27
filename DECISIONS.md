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
