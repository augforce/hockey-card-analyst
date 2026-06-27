# Hockey Card Analyst

A local [MCP](https://modelcontextprotocol.io) server that turns JFresh /
HockeyStats.com player cards into honest, plain-English answers about NHL
players. You talk to Claude Desktop in normal language ("is this guy actually any
good?", "is player A better than player B?", "someone said X about him — true?").
Claude reads the card and routes the real judgment through this server's
deterministic tools, then narrates the result like a disciplined analyst.

Works for forwards, defensemen, and **goalies** (a v1 requirement).

## What Claude does vs what the server does

**Claude Desktop** reads the card image, extracts the numbers into a structured
shape, decomposes natural-language claims into assertions, and writes the final
answer.

**This server** validates the card, maps percentiles to tiers, grades
assertions, runs comparisons, attaches the right caveats, and decides what is
**not answerable** from the card. The methodology lives in
`config/interpretation.yaml`, not in the model's memory — so the answers stay
grounded and repeatable.

## Tools

Exposed over MCP by `src/server.py` (thin wrappers; the engine does the work):

- `assess_player(card)` — overall tier, strengths/weaknesses, deployment,
  trajectory, caveats, one-line summary.
- `adjudicate_claim(card, assertions)` — grade each assertion `supported` /
  `partial` / `not_supported` / `unverifiable`, with the cited metric value.
- `compare_players(card_a, card_b, focus=None)` — position-compatibility check,
  component-by-component edge, and a durability flag.

(`explain_metric` from the plan is optional and not built — it needs a metric
glossary, deferred.)

## Intellectual property

This repo ships **logic and rules, not HockeyStats data**. You bring your own
card, accessed through your own subscription; the server only interprets a card
you already have. Do not scrape, cache, or redistribute HockeyStats cards or
their underlying data.

## Development

Requires Python 3.11+ (developed on 3.14).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # or: pip install pydantic PyYAML pytest fastmcp
```

Run the tests:

```bash
.venv/bin/python -m pytest
```

## Run it (Claude Desktop, macOS)

1. **Install** (one time):

   ```bash
   cd /Users/michael/Desktop/hockey-card-analyst
   python3 -m venv .venv
   .venv/bin/python -m pip install fastmcp pydantic PyYAML
   ```

2. **Register the server.** Open (create the file if it doesn't exist):

   `~/Library/Application Support/Claude/claude_desktop_config.json`

   and add this block (merge into any existing `mcpServers`):

   ```json
   {
     "mcpServers": {
       "hockey-card-analyst": {
         "command": "/Users/michael/Desktop/hockey-card-analyst/.venv/bin/python",
         "args": ["/Users/michael/Desktop/hockey-card-analyst/src/server.py"]
       }
     }
   }
   ```

   It runs over **stdio**; launching `src/server.py` puts `src/` on the import
   path, so no `PYTHONPATH` is needed. The server never reads card images — Claude
   Desktop does the vision and passes structured data.

3. **Restart Claude Desktop** — quit it fully (⌘Q) and reopen so it reloads the
   config. The three tools (`assess_player`, `adjudicate_claim`,
   `compare_players`) should appear in the 🔨 tools menu.

4. **Test the loop.** Paste a player card image and ask, e.g.:

   > Someone told me this kid is an elite two-way center already — true?

   Claude should extract the card, route it through `adjudicate_claim` /
   `assess_player`, and narrate a grounded answer — support the offence, push back
   on the two-way half (EV defence 33rd, no PK role), note the tough competition,
   and flag the sharply rising trajectory.

## Build status

Built one phase at a time (see PLAN section 11 and `DECISIONS.md`).

- [x] **Phase 1 — Scaffold:** repo, venv, pyproject, config, the three card
  schemas, and the percentile tier logic with tests.
- [x] **Phase 2 — Assess (skater):** `assess_player` for forwards and
  defensemen (incl. the defenseman finishing-exclusion and NA-as-deployment
  rules), tested against the Celebrini fixture and a synthetic D.
- [x] **Phase 3 — Adjudicate (skater):** `adjudicate_claim` grades decomposed
  `{dimension, direction}` assertions into supported / partial / not_supported /
  unverifiable, with cited values and an overall read. Tested on the section 3
  four-part claim.
- [x] **Phase 4 — Compare (skater):** `compare_players` with the
  position-compatibility guard, component-by-component gaps, an overall edge that
  refuses to crown a winner on a genuine split, and a finishing-driven
  durability flag. `focus` narrows to offence / defence / overall / a role.
- [x] **Phase 5 — Goalies through all three tools:** the goalie schema and
  goalie reading rules (danger split, floor-vs-ceiling start quality,
  consistency-as-volatility, rebound control) over the same engine. Tested on the
  Thompson fixture (assess), a mixed goalie claim (adjudicate), and goalie-vs-
  goalie / goalie-vs-skater (compare).
- [x] **Phase 6 — Wrap & wire:** `src/server.py` exposes the three tools over
  fastmcp (stdio), with guardrail tool descriptions and strict input validation;
  registered in Claude Desktop. See "Run it" above.
