# Factory city loop — design

**Date:** 2026-11-03
**Status:** awaiting approval

## Intent

Today a city run is a batch: invent a plan of N ideas, fan out N design agents,
wait for every one of them, pack all the footprints into a street layout, and
build the whole thing in a single Unity call. Nothing appears in the Editor
until the last designer has finished.

The user's words: *"no quiero esperar a que terminen todos los diseños para ver
el elemento en unity."*

This design replaces the batch with a continuous loop. The plan is still
invented up front — it is one cheap call. From there, designers run
concurrently and **each finished spec is placed and built on its own, the
moment it lands**. The first building appears in Unity while the rest are still
being designed.

A second intent, raised during the conversation and equally load-bearing: the
current `unity-city-generator` has accumulated jobs that are not its own. It
invents ideas, but it also writes agent briefs, inlines the builder's technical
contract, manages waves of 20, owns placement, owns roads and props, and runs a
cost audit. The user's words: *"creo que el skill unity-generator se ha excedido
en sus competencias... Todos deberian de ser cuanto mas estupidos posible y no
saber nada de los agentes que los llaman."*

So the work is split four ways, and three of the four are deliberately stupid.

## Goals

- First geometry visible in Unity in the time it takes to design **one**
  element, not N.
- Full live visibility into the run — files written, elements built, designs
  finished, timings, token usage, and the complete roster of agents — without
  the orchestrating model spending a single token to report it.
- Three single-purpose skills, each ignorant of its caller and of what comes
  after it, each testable alone with a file in and a file out.
- No agent runs that the user did not see named in the plan.

## Non-goals

- A layout that reads as a real city. Explicitly relegated by the user
  (*"El requisito de que parezca una ciudad queda relegado de momento"*) in
  exchange for immediacy. The loop lays elements in a row.
- Props. Removed entirely for this iteration (*"eliminemos los props de
  momento... Quiero un proyecto limpio para testearlo"*). Buildings only.
- Roads. Removed on the same grounds (builder's call, see Decisions).
- Changing the existing `unity-city-*` skills. They stay exactly as they are.

## Anti-goals

Things that mean this failed even if it works:

- **The orchestrator narrating progress.** The existing skill measured a
  72-agent run where the orchestrator burned 96.7M tokens against the agents'
  32.8M, because 164 turns each re-read 566k of context to say "65/72 done".
  Every live-progress feature here must be written by scripts, not by the model.
  This is the single reason the event log exists.
- **Any coupling between old and new.** No file, path, import, or agent
  definition on either side may reference the other, in either direction.
- **An agent the user did not know about.** The plan is a closed census.

## Constraints

- Unity's Editor is single-threaded. Building is serial no matter what, so
  concurrency buys nothing on the build side and a great deal on the design
  side.
- The agent concurrency cap is 20; exceeding it fails the surplus calls rather
  than queueing them. The loop stays well under at K=4.
- Unity work goes through the Unity CLI at
  `/Users/juan/.unity/bin/unity` (see project `CLAUDE.md`).
- Run artifacts stay out of `Assets/` so Unity does not import them as
  TextAssets, and stay gitignored.

## The four pieces

```
user prompt
     │
     ▼
factory-city-loop  ─────────────────────────────────── the only piece that
     │                                                  knows the other three
     ├─ calls factory-city-generator  → plan.json
     │
     └─ loop, until N:
          ├─ K designers in flight, each: factory-city-designer → spec.json
          ├─ as each spec lands: assign position (cursor), then
          │                      factory-city-element → geometry in Unity
          └─ append every event to events.jsonl
                                    │
                                    ▼
                          browser page, auto-opened, auto-refreshing
```

### factory-city-generator — ideas

Free text in, `plan.json` out. Invents a set of varied building ideas and the
theme's shared palette. That is the whole job.

It does not know that design agents exist, does not know the builder's contract,
does not decide placement, and does not mention props, roads, waves, cost, or
Unity.

Plan entry: a unique `name`, `kind: "building"`, a one-line `idea` rich enough
to design from, and rough `footprint_m` / `height_m`.

The palette is declared here because designers run concurrently and cannot see
each other's choices; left to themselves, three of them invent three different
rusts under the same role name.

Keeping the existing variety discipline matters — a street of five similar
offices is a failure of this step that no amount of good building later fixes.
Vary use, scale, material, era, condition.

### factory-city-designer — how to draw it

One idea in, one spec JSON out. The technical half: parts, primitives, real-world
sizes, local positions, material roles.

It does not know who asked, does not know what happens to the spec, and **calls
nothing**. In particular it does not build, does not preview, and does not assign
a position — the spec has no `position` key at all.

`factory-city-designer/SKILL.md` is documentation for humans. What a designer
process actually receives is a self-contained brief — the idea, the palette, and
the builder's input contract inlined — owned by the loop. No design agent reads
a SKILL.md or fetches a schema. That is carried over deliberately: measured on
a 95-agent run, agents re-read the designer SKILL.md 115 times between them
despite the brief never naming it, roughly a third of their API calls spent
re-acquiring context the brief could have carried.

### factory-city-element — build it

One spec in, geometry in Unity out. Validates, refuses what would be invisible
or buried, creates URP materials, places primitives with correct pivot maths.

It does not know about layout, streets, rows, or runs. It takes a position it is
given and builds there.

The existing `unity-city-element/scripts/build_element.py` is already close to
this; the new copy is that logic with anything layout-aware stripped out.

### factory-city-loop — the factory

The only piece with knowledge of the others. Responsibilities:

1. Call the generator once, get `plan.json`.
2. Open the browser page.
3. Run up to K designers concurrently, drawing from the plan in order.
4. As each spec file lands: assign a position from the cursor, hand it to the
   element builder, move on.
5. Append an event per thing that happens, and keep each agent's full
   transcript (see Audit trail).
6. Stop when every plan entry has reached a terminal state — `built` or
   `failed`. N defaults to **10**, or whatever the user asked for.

**The loop is a script, and designers are headless subprocesses.** This is the
decision that makes the anti-goal achievable. A Python script cannot use the
`Agent` tool, and a model-driven loop spends a turn per spawn and per landing —
the 96.7M-token failure mode by construction. So the loop spawns each designer
as its own `claude -p` process and never returns to the orchestrating model
until the run is over. The model gives the start order and then goes quiet.

Consequences the builder must plan for:

- No `subagent_type`; the designer "agent definition" becomes a prompt plus a
  tool allowance passed on the command line.
- The Agent tool's cap of 20 does not apply. K=4 is now a throughput choice
  about machine load, not a cap workaround.
- Each designer is an independent session, so per-agent token attribution is no
  longer handed to us (see Audit trail).

**Placement is a cursor, not a packer.** State lives on disk in the run folder:
place at `x = cursor`, then `cursor += width + gap`; when `x` passes the row
length, start a new row. Nothing else occupies the strip, so no free-space
search is needed. This replaces `pack_layout.py` (~300 lines) with ~30.

A side benefit: because the cursor persists, extending an existing run no longer
needs a hand-computed `--origin-x`.

**The census is closed.** One plan entry equals one agent. The loop may only
spawn an agent whose name appears in `plan.json`. No retry agents in disguise,
no reviewers, no helpers. The designer agent definition carries `Bash` and
`Write` only — no `Agent` tool — so a designer cannot spawn anything either.

## When a spec is refused

No retries. A refused spec is terminal: the element is marked **failed**, the
reason is recorded, and the loop moves to the next plan entry. The run finishes
with fewer buildings than planned and says so.

This is what keeps the closed census honest — a retry is a second agent for an
entry that was only ever licensed one — and it is what makes the stop condition
terminate. The loop stops when every entry is `built` or `failed`, never when a
count is reached.

## The monitor

`factory-runs/<run>/events.jsonl`, one JSON object per line, appended by the
scripts as they run. The model writes none of it.

Events to cover, from the user's *"quiero saber TODO lo que esta pasando,
ficheros creados, edificios creados, diseño creado, tiempos, tokens usados"*:

- run started: theme, N, K, the full agent roster from the plan
- designer spawned / finished, with element name and elapsed seconds
- spec file written, with path and part count
- element built, with position and elapsed seconds
- refusal, with the refusal code and reason
- run finished, with totals

Token usage is **best-effort, and that is accepted**. Because designers are
independent sessions rather than registered subagents, exact per-agent
attribution is not handed to us. The loop takes what the headless process
reports about itself and sums it; the figure is a working estimate for spotting
outliers, not an invoice. The page labels it as approximate.

A small local page renders it, opens itself with `webbrowser.open()` at run
start, and refreshes on its own. It shows the agent roster with per-element
status (`pending → designing → built`, or `refused` with the code), and a
totals line including a count of **unplanned agents, which must stay at zero**.

The page is read-only. There is no approval gate — the user considered one and
withdrew it: *"he cambiado de opinion. No quiero intervenir en el proceso."*

## Audit trail

A hard requirement, and separate from the live monitor: **every operation of
every agent must be recorded somewhere durable, so a finished run can be
audited afterwards.** The monitor is for watching; this is for reading later.

Because each designer is its own process, the loop captures that process's
complete stream — every tool call it made, every file it touched, its own
reported token counts — into `factory-runs/<run>/agents/<name>.jsonl`, one file
per agent, written as it runs rather than reconstructed at the end.

So a run folder holds three layers, coarse to fine:

```
factory-runs/<run>/
├── plan.json           the closed census
├── events.jsonl        the run's timeline: what happened and when
├── agents/<name>.jsonl one per agent, its full operation log
├── designed/<name>.json each spec
└── cursor.json         placement state
```

Nothing here is reconstructed from memory or from the orchestrator's account of
events. If it is not in a file, it did not happen.

Keeping these is the point, so the folder is not cleaned up between runs.

## Isolation

Hard requirement, user's words: *"Asegurate que los nuevos no utilizaran los
viejos en ningun momento ni los viejos los nuevos."*

- New skills live in their own directories under `.claude/skills/factory-city-*/`
  with their own `scripts/`.
- A new agent definition, separate from `city-element-designer`.
- Run artifacts in `factory-runs/`, not `city-runs/`. Gitignored.
- No path, import, or documentation cross-reference in either direction.
- `make_props.py` and `pack_layout.py` stay where they are, untouched and
  unused by anything new.

## Decisions made by the builder, not the user

Flagged so they can be checked while reading:

- **No road.** The plan carries buildings only. Same reasoning the user gave for
  dropping props: a clean project to test. The old skill defaulted to exactly one
  road tile; this one has none.
- **K = 4** concurrent designers. Enough that Unity is rarely idle, far below the
  cap of 20.
- **Prefix `factory-`**, with the loop named `factory-city-loop` — the user
  confirmed this name.
- **Nothing is saved to the scene unless the user asks**, carried over from the
  existing skills.
- **The designer's SKILL.md is for humans**; the brief template belongs to the
  loop and carries the builder contract inlined.
- **The forked builder is a near-verbatim copy.** The existing
  `build_element.py` turned out to contain almost nothing layout-aware, so there
  is little to strip beyond the `road` and `prop` concepts, which are non-goals
  this iteration. Two copies that diverge from here is the accepted cost of the
  isolation requirement.
- **Its own materials folder**, so a new run does not inherit palette colours
  baked by an old one — the builder reuses an existing `.mat` as-is and never
  repaints it. GameObject names still share the scene's namespace, so a
  collision with old geometry surfaces as `name_taken` and is handled by the
  refusal policy above.

## What is left to the builder

- The exact event schema and page layout.
- The exact `claude -p` invocation per designer: output format, tool
  allowance, and how its stream is tee'd to both the agent log and the
  completion check.
- How the loop detects a designer finishing — process exit, the spec file
  appearing, or both.
- Row length and gap for the cursor.
- The runnable check for each piece. Each of the three stupid skills takes a
  file and produces a file, so each gets a self-check that fails if its logic
  breaks.
