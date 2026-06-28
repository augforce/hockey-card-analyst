# Hockey Card Analyst

Turn an advanced hockey card into plain language you can say out loud and defend.

Hockey Card Analyst is a translator between advanced metrics and normal hockey
conversation. It reads one analytics model's card for a player and tells you, in
words, what the numbers actually say.

## The problem it solves

Advanced player cards are everywhere now, but reading one well means knowing the
model underneath: what is repeatable versus lucky, what is a real skill versus an
artifact of how a player is deployed, why a 95th percentile is not the same as a
99th. Most fans do not have time to learn the methodology, so the metrics get
ignored or misread and the argument stays stuck at the eye test. The gap is not
access to data. It is interpretation.

It is for the fan who watches the games, trusts what they see, and wants the
numbers to back that up or check it.

## Query Example

Let's compare the three Hughes' brothers (using Claude Desktop):
<img width="804" height="641" alt="Screenshot 2026-06-28 at 10 29 55 AM" src="https://github.com/user-attachments/assets/0f392a95-d2eb-4f51-b672-13743d677a07" />
<img width="764" height="721" alt="Screenshot 2026-06-28 at 10 30 12 AM" src="https://github.com/user-attachments/assets/bfb11593-b0a8-4aa7-b103-b9bfc7943bab" />


## What you can ask it

- A claim gets made about a player ("he's just a net-front guy, can't do more
  than that") and you want to know whether the data agrees.
- You have an eye-test read and want to see if the metrics confirm it or
  complicate it.
- A trade gets floated and you want an honest answer to "is X an upgrade on Y."

## Why you can trust it

Every answer traces back to a number on the card. It tells you when a claim is
half-right, and which half. It admits what the card cannot see instead of
bluffing. It takes the noise out and leaves something you can explain to someone
else and stand behind.

It interprets one model's read of a player. It does not declare anyone good or
bad in some absolute sense.

## How it works, under the hood

This is a local [MCP](https://modelcontextprotocol.io) server. The model you are
talking to (the LLM) reads the card image and handles the language. The server
does the deterministic part: it maps each percentile to a tier, grades claims
against the numbers, compares two players within the same position pool, attaches
the methodology caveats, and decides what the card cannot answer. The reading
rules live in `config/interpretation.yaml`, not in the model's memory, so the
answers stay consistent. Because the verdict is deterministic, the same card
values produce identical analysis on any host; what varies between hosts is how
well each model reads the card image and routes the numbers through the tools. It
works for forwards, defensemen, and goalies.

Three tools, thin wrappers over the engine:

- `assess_player(card)`: overall tier, strengths and weaknesses, deployment,
  trajectory, caveats, a one-line summary.
- `adjudicate_claim(card, assertions)`: grades each claim `supported` /
  `partial` / `not_supported` / `unverifiable`, with the cited number.
- `compare_players(card_a, card_b, focus)`: component by component, an overall
  edge or an honest split, and a durability flag.

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
   the numbers: back the offence where the card supports it, push back on the
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

v1.0: all three tools for forwards, defensemen, and goalies, served over MCP, and
tested end to end on Claude Desktop. See `DECISIONS.md` for the full build log.
