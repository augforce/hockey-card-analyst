> **Historical document.** This is the original planning document the project was built from, kept for reference — it is not current documentation. See `README.md` for what the project is today and `DECISIONS.md` for how it got there.

# Hockey Card Analyst: Build Plan

A planning overview to hand to Claude Code. Working repo name: `hockey-card-analyst` (rename as you like).

## 1. What this is

A local MCP server that turns JFresh / HockeyStats.com player cards into plain-English answers about NHL players. The user talks to Claude Desktop in normal language ("is this guy actually any good", "is player A better than player B", "someone said X about this player, is that true"). Claude reads the card, pulls the numbers into a structured shape, and routes the real judgment through this server's deterministic tools. Claude narrates the result like a hockey analyst.

The server is the grounded backbone. Claude is the voice. The split matters: Claude handles messy hockey language, the server handles the verdict logic so the answers stay honest and repeatable.

This mirrors the career-intelligence project: a rule-based core driven by a config file, wrapped as an MCP server with fastmcp, callable from Claude Desktop.

## 2. What it does (three jobs)

1. **Assess** a single player. Strengths, weaknesses, how he's deployed, trajectory, and the caveats that matter.
2. **Adjudicate a claim.** Take a statement about a player and grade it against the card: supported, partly supported, not supported, or not answerable from this card.
3. **Compare** two players. Component by component, with an overall edge and a note on how durable that edge is.

All three must work for forwards, defensemen, and goalies. Goalies are a v1 requirement, not a later add-on.

## 3. The core idea behind claim adjudication

This is the headline feature, so it gets its own section.

A claim is rarely one thing. Example: "sits in front of the net and scores goals, you'll love him unless he's asked to do more, probably your leading scorer next season." That is four separate assertions:

- "scores goals" maps to Finishing and Goals. Checkable.
- "asked to do more" maps to whether playmaking (1st Assists) and defense (EV Defense, PK) are weak. Checkable.
- "sits in front of the net" is a playing-style claim about shot location. A standard card does not measure this. It goes in the **not answerable** bucket, with a note that the $10 microstat card gets closer.
- "leading scorer next season" depends on his new team's roster, which the card does not know. **Partly supported** at best, with a team-context caveat.

The "not answerable from this card" bucket is the most valuable output. A tool that knows the limits of its own data is more trustworthy than one that pretends every claim is checkable. The HockeyStats methodology says the same thing repeatedly: WAR is a starting point for an argument, not the final word.

**Division of labor:** Claude Desktop decomposes the natural-language claim into a list of structured assertions (dimension plus direction, e.g. `{dimension: "finishing", direction: "high"}`). The server grades each assertion against the card and returns the verdict with the metric value as evidence. Claude writes it up.

## 4. The card data (three schemas)

Claude extracts these from the card image via vision and passes them to the server as structured data. The server never does vision; it receives clean fields. Use pydantic models so bad input fails loudly.

### Skater (forward)
- Context (does not affect value): `name`, `team`, `position`, `age`, `toi_role`, `cap`, `competition`, `teammates`
- WAR components (percentiles): `ev_offense`, `ev_defense`, `pp` (nullable / NA), `pk` (nullable / NA), `finishing`, `penalties`
- Headline: `proj_war_pct`
- Extra descriptive: `goals`, `first_assists`
- Trends (optional): `war_pct_trend` as a list of `{season, value}`

### Defenseman
Same as forward, with one rule: `finishing` may appear on the card but is **excluded** from `proj_war_pct`. The server must know this so it never credits a defenseman's WAR to finishing.

### Goalie (separate stat set, shares only the percentile format)
Verified against a real current card (Logan Thompson, WSH). The current HockeyStats goalie card does **not** split WAR into 5v5 / 4v5 / All. It uses a single headline plus ten percentile boxes in two rows.

- Context: `name`, `team`, `age`, `gp_pct`, `role` (Starter / 1A / 1B / Backup), `cap`
- Headline: `proj_war_pct`
- Performance by game state (percentiles): `even_strength`, `penalty_kill`
- Performance by shot danger (percentiles): `high_danger`, `med_danger`, `low_danger`
- Start quality, built on goals saved above expected, not save percentage: `quality_starts` (saved above 0), `excellent_starts` (saved 2+), `bad_starts` (allowed 2+)
- Reliability and puck handling: `rebound_control`, `consistency` (how predictable year to year)
- Trends (optional): `war_per60_trend` as `{season, value}`, `sv_vs_xsv_trend` as `{season, sv, xsv}`

Direction note for Claude Code: every goalie percentile on the card is already oriented so higher is better, including Bad Starts (92 means better than 92% of goalies at avoiding bad starts) and Consistency. Do not invert any of them.

## 5. Interpretation rules (live in a config file)

Put all of this in `config/interpretation.yaml` so it can be tuned without touching code. Same pattern as the career-intelligence YAML.

### Percentile tiers
Percentiles are compressed at the top, so the bands are not evenly spaced. Starting point:

| Band | Label |
| --- | --- |
| 95-100 | Elite |
| 85-94 | Excellent |
| 70-84 | Strong |
| 55-69 | Above average |
| 45-54 | Average |
| 30-44 | Below average |
| 15-29 | Weak |
| 0-14 | Among the worst at the position |

Rule: anything 95+ also gets a note that the gap from 95 to true elite (99 to 100) is large, so 95 and 99 are not the same player.

### Caveats the engine attaches automatically
- **Finishing volatility.** If a verdict leans on Finishing, attach: finishing swings year to year, play-driving (the RAPM components) is more repeatable. A lead built on finishing is shakier than one built on play-driving.
- **Deployment is not value.** Competition and Teammates describe how a player is used, not how good he is. They are already baked into WAR. Never treat them as a strength or weakness.
- **Within-position only.** Percentiles are ranked inside each position pool. Forward vs forward and D vs D are fine. Skater vs goalie, or forward vs defenseman, is not apples to apples and must be refused or heavily caveated.
- **Dangerous passing is underrated.** The model is known to underrate forwards who make dangerous passes and overrate shoot-first players. When a playmaking claim is borderline, note this.

### Goalie-specific reading rules
These came out of the real Thompson card and matter as much as the skater rules, since goalies are a priority.

- **Danger split is the profile.** High, Med, and Low Danger percentiles show where a goalie's value comes from. Elite on High Danger but only average on Low Danger (Thompson: 99 vs 56) means he makes the hard saves but is ordinary on routine shots. The reverse, weak on Low Danger, is a leaking-soft-goals flag.
- **Floor vs ceiling.** Quality Starts is the floor (gives his team a chance most nights). Excellent Starts is the ceiling (steals games). Bad Starts is the disaster rate. High Quality Starts with modest Excellent Starts (Thompson: 99 vs 53) reads as reliable but not a game-stealer. Report these as a profile, not three separate numbers.
- **Consistency is a volatility flag, not value.** A low Consistency percentile (Thompson: 23) paired with a steep recent WAR climb means the projection may be riding a recent spike rather than a settled level. Goalie performance is the least stable thing in the model, so every goalie projection gets tempered by the Consistency read.
- **Read the two save lines together.** On the Save % vs Expected Save % chart, when actual save percentage holds while expected save percentage falls, the goalie is increasingly beating expectation (rising goals saved above expected), which is what drives WAR up. Never read either line alone.
- **Rebound Control is a discrete skill.** Call it out as its own strength or weakness (Thompson: 35, a soft spot), not folded into the danger numbers.

### Dimension dictionary (claim language to card metric)
Helps Claude map hockey-talk consistently. Extendable in YAML. Representative entries:

- goal scorer / finisher / sniper -> `finishing`, `goals`
- playmaker / passer / vision -> `first_assists` (attach dangerous-passing caveat)
- two-way / shutdown / responsible / 200-foot -> `ev_defense`, `pk`
- power play weapon -> `pp`
- penalty killer -> `pk`
- disciplined / takes too many penalties -> `penalties`
- elite / superstar / best player -> `proj_war_pct`
- plays tough minutes / matched against top lines -> `competition` (deployment, not value)
- carried by his linemates -> `teammates` (deployment, not value)
- goalie steals games / robs people / highlight reel -> `excellent_starts`, `high_danger`
- goalie lets in soft ones / leaks easy goals -> `low_danger`
- goalie gives you a chance every night / reliable / steady -> `quality_starts`
- goalie never has a stinker / no bad nights -> `bad_starts`
- goalie is consistent / you know what you'll get -> `consistency`
- goalie controls rebounds / no second chances -> `rebound_control`
- great on the kill / shorthanded -> `penalty_kill`
- workhorse / true starter / handles the load -> `gp_pct`, `role`
- elite goalie / top tier / Vezina -> `proj_war_pct`
- goalie style claims (aggressive, deep in his net, glove vs blocker) -> **not answerable** from the card
- net-front / screens / plays in the blue paint -> **not answerable** on a standard card, point to microstat
- team's leading scorer / team's best -> **partly answerable**, needs team context

## 6. The MCP tools

Three tools, plus one optional helper. Each takes structured input and returns structured findings. Claude narrates.

- `assess_player(card)` -> overall tier, top strengths, top weaknesses, deployment note, trajectory from trend, attached caveats, one-line summary.
- `adjudicate_claim(card, assertions)` where `assertions` is the list Claude extracted. Returns, per assertion: grade (`supported` / `partial` / `not_supported` / `unverifiable`), the metric value cited, and a one-line reason. Plus an overall read.
- `compare_players(card_a, card_b, focus=None)` -> position-compatibility check first (refuse or caveat if pools differ), then component-by-component, overall edge, and a durability flag (finishing-driven edge = less durable). `focus` can narrow to offense, defense, overall, or a role.
- `explain_metric(name)` (optional) -> plain-English definition plus caveats for any card metric, so the tool can also teach.

## 7. What Claude Desktop does vs what the server does

Be explicit about this in the README and in the tool descriptions, because it is what makes the thing behave like a disciplined analyst.

Claude does: read the card image, extract fields into the schema, decompose claims into assertions, write the final plain-English answer.

The server does: validate the card, map percentiles to tiers, grade assertions, run comparisons, attach the right caveats, decide what is not answerable.

Guardrails to state in the tool descriptions so Claude follows them: never invent a stat that is not on the card, always route a claim through `adjudicate_claim` rather than eyeballing it, always cite the metric value behind a verdict, never compare across position pools without flagging it, and surface the "not answerable" items rather than hiding them.

## 7b. Where the methodology knowledge comes from

Important point for Claude Code, because it determines what to build versus what to assume. The server does not read the HockeyStats About pages at runtime and does not call an LLM to understand metrics. The methodology is distilled once, by hand, into three forms:

1. **Encoded rules in `interpretation.yaml`.** The tier bands, the claim-to-metric dictionary, the caveats, and the not-answerable list. This is the methodology turned into deterministic lookups. Example of the translation: the source says finishing is goals scored above expected, is important for forwards, and is less repeatable than play-driving. That becomes a config entry where finishing maps from words like sniper and finisher, carries a high-volatility flag, and attaches a fixed caveat. The reading for this is already done and lives in section 5.
2. **A short metric glossary** (its own data file, or a section of the config). Plain-English, reworded definitions of every card metric plus its one important quirk. Powers the optional `explain_metric` tool.
3. **Inline grounding in tool outputs.** Every verdict the server returns carries the relevant one-line definition or caveat alongside the number, so the methodology-correct framing travels with the result. Claude narrates from what the tool returned, not from its own memory of how WAR models generally work. This is the main defense against Claude importing assumptions that are true of some other model but wrong for this one.

Write the glossary and config entries in your own words. Do not paste the About pages in verbatim, both to keep maintenance clean and to respect the no-redistribution line in section 9. Optionally keep a `METHODOLOGY.md` in the repo as a human reference, distilled from the WAR, RAPM, expected-goals, and player-card pages, but the server's behavior comes from the config and the glossary, not from that document.

## 8. Scope

**In scope for v1:** the standard $5-tier player cards, for forwards, defensemen, and goalies. All three tools.

**Out of scope for v1:** the $10 microstat cards (zone entries, passing data), the scouting reports, any web front end, and anything that pulls data from HockeyStats.com directly. Leave clean seams so a web wrapper or microstat support can be added later, but do not build them now.

## 9. Intellectual property and terms of service

The repo ships logic and rules, not HockeyStats data. The user brings their own card, accessed through their own subscription. The server interprets a card the user already has. Do not scrape, cache, or redistribute HockeyStats cards or their underlying data. Put a short note to this effect in the README so anyone cloning the repo understands the boundary.

## 10. Tech stack and structure

- Python with a `.venv`, same as career-intelligence.
- `fastmcp` for the server.
- `pydantic` for the three card schemas and tool inputs.
- `PyYAML` for the config.
- `pytest` for tests.

```
hockey-card-analyst/
  README.md
  DECISIONS.md
  pyproject.toml
  config/
    interpretation.yaml        # tiers, caveats, dimension dictionary
  src/
    schemas.py                 # pydantic models: SkaterCard, DefenseCard, GoalieCard
    engine/
      tiers.py                 # percentile -> tier + compression note
      caveats.py               # finishing volatility, deployment, within-position
      assess.py
      adjudicate.py
      compare.py
    server.py                  # fastmcp server exposing the four tools
  tests/
    fixtures/
      celebrini.json           # golden skater card
      thompson.json            # golden goalie card
    test_tiers.py
    test_assess.py
    test_adjudicate.py
    test_compare.py
```

Keep a `DECISIONS.md` log, same habit as career-intelligence.

## 11. Build phases

1. **Scaffold.** Repo, venv, pyproject, config skeleton, the three pydantic schemas, and the tier logic with tests. Load `interpretation.yaml`.
2. **Assess (skater).** Build `assess_player` for forwards and defensemen, including the defenseman finishing-exclusion rule. Test against a Celebrini fixture.
3. **Adjudicate (skater).** Build `adjudicate_claim`, including the `unverifiable` path for net-front and team-context claims. Test with the four-part example claim from section 3.
4. **Compare (skater).** Build `compare_players` with the position-compatibility check and durability flag.
5. **Goalies.** Add the goalie schema and the goalie path through all three tools. This is required for v1, not optional.
6. **Wrap and wire.** Stand up the fastmcp server, register it in Claude Desktop, and run end to end with a real card image: ask a question in plain English, confirm Claude extracts, calls the tool, and narrates a grounded answer.

## 12. How to know it works

A good end-to-end test: paste the Celebrini card and say "someone told me this kid is an elite two-way center already, true?" The tool should support the offensive half loudly (elite EV offense, finishing, primary assists), push back on the two-way half (EV defense sits at 33, below average, no PK role), note he does it against tough competition, and flag that his arrow is pointing sharply up. That is the kind of honest, sourced answer the whole thing exists to produce.

The goalie equivalent, using the Thompson card: paste it and say "is this guy a top-tier starter or is he riding a hot streak?" The tool should support the top-tier read (96th in projected WAR, 99th high danger, 99th quality starts, rarely a bad night at 92nd), but also surface the real tension: Consistency sits at 23, his WAR per 60 climbed steeply over three years rather than holding, Rebound Control is a weak 35, and his Excellent Starts are only middling at 53, so the ceiling is reliability rather than game-stealing. The honest verdict is a genuinely strong starter whose three-year track record is short and uneven, which is exactly the volatility goalies are known for. Both halves true at once is the point.

## 13. Open defaults to confirm

Things I picked so the build can start. Change any of them.

- Repo name `hockey-card-analyst`.
- The tier band cutoffs in section 5.
- Tool names in section 6.
- Goalies sequenced as phase 5 but treated as v1-required.
- Microstat cards and any web UI held for later.
