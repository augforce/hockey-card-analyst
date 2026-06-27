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
