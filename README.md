# Hockey Card Analyst

Turn an advanced hockey card into plain language you can say out loud and defend.

Hockey Card Analyst is a translator between advanced metrics and normal hockey
conversation. It reads one analytics model's card for a player and tells you, in
words, what the numbers actually say.

## What it's for

Advanced player cards pack a lot into a small grid: a dozen percentiles, a
couple of trend lines, and a headline number. The data is there, but reading it
well means knowing the model underneath. What's repeatable versus lucky, what's
a real skill versus an artifact of how a player is deployed, why a 95th
percentile isn't the same as a 99th, why a defenseman's finishing doesn't count
toward his value the way a forward's does. Most people looking at a card don't
have that model in their head, so the numbers get half-read or misread.

This tool does the reading. Some of what it's useful for, drawn from real use:

- Settling a claim. Someone says "he's a one-dimensional scorer who can't
  defend." The tool checks each part against the numbers and tells you which
  holds, which doesn't, and what the card can't answer.
- Pressure-testing a hot take. A scorer has a big year and everyone assumes he's
  due to regress. The tool can show whether the goals rest on repeatable
  play-driving or on finishing that tends to cool, and it works the other way
  too: a player whose scoring is quietly understated.
- Building a case for a player. If you're writing or arguing about how good
  someone actually is, it turns a wall of percentiles into a plain-language
  thesis you can stand behind, with every point traceable to a number.
- Reading a young breakout honestly. The card is a three-year weighted average,
  so a 20-year-old's number rests on a short sample. The tool flags how far to
  trust it rather than treating the percentile as settled.
- Understanding the metrics themselves. Ask what a stat measures and the one
  catch that keeps you from misreading it, without needing a verdict on a
  player.

It reads one analytics model's card and interprets it. It doesn't declare anyone
good or bad in some absolute sense, and it only tells you what the numbers on the
card support.

## What you can ask it

- A claim gets made about a player ("he's just a net-front guy, can't do more
  than that") and you want to know whether the data agrees.
- You have an eye-test read and want to see if the metrics confirm it or
  complicate it.
- A trade gets floated and you want an honest answer to "is X an upgrade on Y."
- A young player breaks out and you want to know how far to trust it ("he's only
  20 — is this real, or too early to bank on?"). The card is a three-year weighted
  average, so a young number rests on a short, recent sample: the upside and the
  uncertainty are both bigger than the single percentile lets on.
- A scorer's goal total looks unsustainable ("is he due to regress?") and you want
  to know whether the scoring rests on repeatable play-driving or leans on hot
  finishing that tends to cool.
- The flip side ("is he actually better than his goals say?"): a player who drives
  play but hasn't been finishing may have scoring that's understated — a
  positive-regression candidate rather than a fluke.
- You hit a metric you don't know ("what does EV defense actually measure, and
  what's the catch?") and you want a plain-language definition plus the one caveat
  that keeps you from misreading it — for the metric itself, not a verdict on a
  player.

## Query Example

**(Using Claude Sonnet 5 with High thinking)**

### **"Give me a scouting report on how the Jack Hughes/Jesper Bratt/Anthony Mantha line will work together":**

<img width="705" height="616" alt="Screenshot 2026-07-19 at 7 23 07 AM" src="https://github.com/user-attachments/assets/7df41c00-0053-4684-a726-e7d514785e7d" />
<img width="704" height="681" alt="Screenshot 2026-07-19 at 7 23 24 AM" src="https://github.com/user-attachments/assets/4ca4f250-b156-4700-ba46-1226252fa6fc" />

### **PDF Report:**

[line-report-hughes-c-bratt-rw-mantha-lw_interpretive_2026-07-19.pdf](https://github.com/user-attachments/files/30164842/line-report-hughes-c-bratt-rw-mantha-lw_interpretive_2026-07-19.pdf)

## Why you can trust it

Every answer traces back to a number on the card. It tells you when a claim is
half-right, and which half. It admits what the card cannot see instead of
bluffing. It takes the noise out and leaves something you can explain to someone
else and stand behind.

It interprets one model's read of a player. It does not declare anyone good or
bad in some absolute sense.

The reading rules are also anchored in the model author's own published
methodology write-ups — how the WAR model is built, how the expected-goals
model was rebuilt, and how the impact numbers adjust for context. That's where
the tool learned that replacement level sits near the 37th percentile (so a
projection at or below it reads as replacement-level, not merely "below
average"), that the power play is the model's noisiest read on both sides of
the puck, that a forward's defensive impact is the less repeatable half of
play-driving, and that zone starts, score state, and schedule are already
adjusted for before the card is printed. These anchors sharpen the wording and
the caveats; they never move a verdict.

## How it works, under the hood

This is a local [MCP](https://modelcontextprotocol.io) server. The model you are
talking to (the LLM) reads the card image and handles the language. The server
does the deterministic part: it maps each percentile to a tier, grades claims
against the numbers, compares two players within the same position pool, attaches
the methodology caveats, and decides what the card cannot answer. The reading
rules live in `config/interpretation.yaml` and the metric definitions in
`config/glossary.yaml`, not in the model's memory, so the answers stay
consistent. Because the verdict is deterministic, the same card
values produce identical analysis on any host; what varies between hosts is how
well each model reads the card image and routes the numbers through the tools. It
works for forwards, defensemen, and goalies.

Five tools, thin wrappers over the engine:

- `assess_player(card, micro_card)`: overall tier, strengths and weaknesses,
  deployment, trajectory, caveats, a one-line summary. Takes a standard card or
  a microstat card (see below); given both cards for one player it adds a
  cross-card synthesis.
- `adjudicate_claim(card, assertions)`: grades each claim `supported` /
  `partial` / `not_supported` / `unverifiable`, with the cited number.
- `compare_players(card_a, card_b, focus)`: component by component, an overall
  edge or an honest split, and a durability flag.
- `explain_metric(metric)`: a plain-language definition of any card metric
  (skater, goalie, or microstat), plus its single most important interpretive
  caveat. It defines a metric in the abstract; it does not reason about a
  specific player.
- `render_report(kind, result, title)`: turns the answer you just got into a
  downloadable, styled PDF report (see below).

## Microstat ($10-tier) cards

The higher-tier subscription card — the dark card with a WAR row on top and
three columns of AllThreeZones tracked data — is supported alongside the
standard card, for forwards and defensemen (no goalie microstat card exists;
goalies stay standard-only). It is a different data regime: one season of 5v5
per-60 percentiles rather than the standard card's three-year-weighted
projection, no Proj. WAR headline, and no deployment context. The tools honor
that regime rather than papering over it:

- **Style claims become checkable.** "He's a rush player", "great skater",
  "physical", "relentless forechecker", "high motor", "net-front presence" —
  unverifiable on a standard card — are graded against the tracked numbers
  when a micro card is supplied, with the receipt cited. Playmaker claims
  grade on the passing process (dangerous passes thrown), not just assist
  outcomes. Style reads (hits, skating speed, forechecking) are never
  treated as value weaknesses; they describe how a player plays.
- **Built-in profile reads.** The paired reads the tracking methodology
  scripts — shots vs chances (perimeter volume vs selectivity), chance assists
  vs shot assists (dangerous passer vs point-funneler), rush vs in-zone
  offense, the defenseman rush-defense trio ("tight gap but gets walked"
  vs "soft gap protecting the slot", or dominant across the line when all
  three run high), and a defenseman breakout-style family (four shapes for
  how he moves the puck out of his own end) — come back as named profiles
  with the numbers attached.
- **Both cards together.** Supply a player's standard card and micro card in
  one question and the assessment adds an articulation-only synthesis: where
  this season ran hot or cold against the three-year projection, and where the
  tracked data backs (or undercuts) the WAR verdicts. The tier never moves.
- **Honest seams.** A micro card has no Proj. WAR, so no overall tier is
  invented ("is he elite?" needs the standard card), and a micro card is never
  compared head-to-head against a standard card — single-season tracked
  percentiles and a blended projection are different pools. When a claim
  needs a box the supplied card doesn't carry, the answer names the card
  type that actually carries it — and says so plainly when none does.

## NHL Edge vetting (optional)

Alongside either card you can also drop in a screenshot of the player's
[NHL Edge](https://www.nhl.com/nhl-edge) page — the league's own tracking,
unrelated to HockeyStats. It is strictly supplemental: Edge data is never
assessed on its own and never touches the claim or comparison tools; it rides
along with an assessment and vets it, adding corroborations and contradictions
between the card's verdicts and the tracking. The tier, strengths, and
weaknesses never move because of it — same articulation-only contract as the
both-cards synthesis.

The reading rules are deliberate about what Edge numbers can and can't say:

- **Rates drive the calls.** Save percentages, starts over .900, and zone-time
  shares are judged off the raw value against the comparison average printed
  on the same page (with NHL's exact percentile cited when the site gives one,
  which it only does from the 51st up — below that it prints "<50th", and no
  number is ever invented for that bucket).
- **Counts never do.** Shots against, goals against, saves, shots on goal —
  anything that accumulates with games played — is workload context only. A
  22-game goalie can show a 99th-percentile goals-against count at the same
  save percentage a 44-game goalie posts with a below-average one; the rate is
  the truth, so counts stay descriptive with games played named.
- **Tools are style.** Hardest shot, max skating speed, and miles skated are
  physical-tools color, never evidence of offensive value — players with
  near-identical tool readings sit at opposite ends of production.
- **Zone time is deployment-shaped.** Territorial tilt can back (or honestly
  contradict) an EV impact verdict, but it always carries the deployment
  caveat: where the puck lives with a player on the ice is not an isolated
  impact.

## PDF reports

After any assess, compare, or claim-check answer, ask for a PDF (the assistant
will offer one) and you get a styled report of that exact verdict written to
`~/Documents/HockeyCardReports/` — named after the player(s), the report kind,
and the date. Six report kinds: skater assessment, goalie assessment,
microstat assessment, head-to-head comparison, graded claim check, and an
"interpretive" kind for
reads the engine has no tool for (line synergy, goalie support, free-form
questions), which is prominently badged *"Interpretive read · AI — not an
engine verdict"* so an AI read can never pass as an engine one.

Two honesty rules are enforced, not advisory: the report is rendered from the
same structured result the engine just returned (a retyped or reconstructed
result is rejected), and the source card image is never embedded. Rendering is
fully local — an HTML template with bundled fonts, converted by
[WeasyPrint](https://weasyprint.org/) with no headless browser and no network.
On macOS, WeasyPrint needs one system library: `brew install pango`.

## What you need

A hockeystats.com subscription and a player card you have pulled yourself. The
tool does not fetch, scrape, or store cards. It only interprets a card you
supply, and the LLM reads the card image at runtime, so the server itself only
ever sees the numbers.

To run the server you need Python 3.11+ (tested on 3.14).

## How to run it

This is a standard MCP server that speaks over stdio, so any MCP-capable client
can use it. It was built and tested with Claude Desktop on macOS. The same
command works for other clients; you just put it in that client's MCP config.

1. Install (one time):

   ```bash
   git clone https://github.com/augforce/hockey-card-analyst.git
   cd hockey-card-analyst
   python3 -m venv .venv
   .venv/bin/python -m pip install fastmcp pydantic PyYAML
   ```

2. Register the server with your client. Every MCP client needs the same two
   things: the command (the venv Python) and one argument (the server script).
   Use absolute paths for your machine:

   - command: `/absolute/path/to/hockey-card-analyst/.venv/bin/python`
   - args: `["/absolute/path/to/hockey-card-analyst/src/server.py"]`

   **Claude Desktop (tested).** Edit
   `~/Library/Application Support/Claude/claude_desktop_config.json` (on Windows,
   `%APPDATA%\Claude\claude_desktop_config.json`) and merge:

   ```json
   {
     "mcpServers": {
       "hockey-card-analyst": {
         "command": "/absolute/path/to/hockey-card-analyst/.venv/bin/python",
         "args": ["/absolute/path/to/hockey-card-analyst/src/server.py"]
       }
     }
   }
   ```

   Quit Claude Desktop fully and reopen so it reloads the config.

   **Gemini CLI.** Add the same block under `mcpServers` in your Gemini settings
   (`~/.gemini/settings.json`), then restart the CLI.

   **Other stdio clients** (Cursor, VS Code, Cline, Continue, the OpenAI Agents
   SDK, and similar). Each has its own place to register an MCP server, but the
   entry is the same command and args shown above.

   **ChatGPT (more involved).** This is a different, heavier deployment than the
   stdio hosts above. ChatGPT connects to a remote MCP endpoint rather than a
   local stdio process, so you would run this server as a public HTTP endpoint
   using FastMCP's HTTP transport. Two things to know going in: FastMCP's HTTP
   transport enables DNS-rebinding/origin protection by default, which returns 403
   to every client until you configure the allowed origins and hosts; and exposing
   a public endpoint is a security responsibility you own. See the FastMCP HTTP
   transport docs (https://gofastmcp.com) for transport and security
   configuration. This path is not tested here.

3. Confirm the loop. Start a conversation, give the model a player card image,
   and ask in plain language, for example:

   > Someone told me this kid is an elite two-way center already. True?

   The model should read the card, route it through the tools, and answer from
   the numbers: back the offense where the card supports it, push back on the
   two-way side if the defensive numbers do not, note how the player is deployed,
   and flag the trajectory.

## Scope and sourcing

The tools read the card and **nothing else**. Every verdict traces back to a
percentile on the card, so the whole answer is auditable — you can check each
claim against a number you can see.

Team, roster, and contract context — trades, who's on the roster, who leads a
team in scoring, recent game results — is **out of scope by design**. The tools
don't fetch it and don't guess it (`adjudicate_claim` returns such claims as
`unverifiable`). Keeping that context out is what keeps the auditable trail
clean. This is the default, no-setup behavior: card-bound and honest.

### Optional: let the host model add outside context

If you want the host model to pull outside context (trades, contracts, roster
fit) and weave it into the answer, you can opt in with a standing instruction.
Put it wherever your host keeps persistent instructions: a system prompt, the
host's custom instructions, or a project. In Claude Desktop, for example, that is
a Project instruction (Projects, then your project, then instructions); other
hosts have their own equivalent. It lives in the host app, **not** in the MCP
config JSON, and **not** in this repo. Paste this in:

```text
When assessing hockey cards, anything the card itself can't answer (trades,
contracts, current team, roster context, recent stats) may be pulled from the
web. When you do, clearly mark which parts of the answer came from the web
rather than the card, and add a brief note that web-sourced facts should be
verified before being taken at face value. Card-derived verdicts come from the
hockey-card-analyst tools and are traceable to the numbers; web facts are
supporting context, not tool output. Keep the two visibly separate.
```

With this in place the model labels web-sourced facts separately from
card-derived verdicts, so the audit trail stays intact: the card verdicts remain
traceable to the numbers, and the outside context is clearly flagged as
unverified. Web augmentation is an opt-in you configure and label yourself.

## Intellectual property

This repo ships logic and rules, not HockeyStats data. You bring your own card,
accessed through your own subscription; the server only interprets a card you
already have. Do not scrape, cache, or redistribute HockeyStats cards or their
underlying data.

## Development

Run the tests:

```bash
.venv/bin/python -m pytest
```

The engine has no network or vision dependencies. It only transforms structured
numbers, so the suite is fast and deterministic. See `DECISIONS.md` for the
design rationale behind the reading rules.

## Status

v1.1: the three analysis tools plus `explain_metric` and PDF reports, for
forwards, defensemen, and goalies — now reading both the standard card and the
$10-tier microstat card (style claims, profile reads, and both-cards
synthesis), with the reading rules anchored in the model's published
methodology write-ups. Served over MCP and tested end to end on Claude
Desktop. See `DECISIONS.md` for the full build log.
