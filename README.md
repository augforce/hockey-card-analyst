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
`config/interpretation.yaml` (and a glossary), not in the model's memory — so the
answers stay grounded and repeatable.

## Tools (planned)

- `assess_player(card)` — overall tier, strengths/weaknesses, deployment,
  trajectory, caveats, one-line summary.
- `adjudicate_claim(card, assertions)` — grade each assertion `supported` /
  `partial` / `not_supported` / `unverifiable`, with the cited metric value.
- `compare_players(card_a, card_b, focus=None)` — position-compatibility check,
  component-by-component edge, and a durability flag.
- `explain_metric(name)` — plain-English definition plus caveats (optional).

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

## Build status

Built one phase at a time (see PLAN section 11 and `DECISIONS.md`).

- [x] **Phase 1 — Scaffold:** repo, venv, pyproject, config, the three card
  schemas, and the percentile tier logic with tests.
- [x] **Phase 2 — Assess (skater):** `assess_player` for forwards and
  defensemen (incl. the defenseman finishing-exclusion and NA-as-deployment
  rules), tested against the Celebrini fixture and a synthetic D.
- [ ] Phase 3 — Adjudicate (skater)
- [ ] Phase 4 — Compare (skater)
- [ ] Phase 5 — Goalies through all three tools
- [ ] Phase 6 — Wrap as a fastmcp server and wire into Claude Desktop
