---
name: factory-city-loop
description: Generate a street of buildings in Unity as a continuous design-to-build loop, with a live browser monitor. Each building appears in the Editor the moment its design lands, instead of waiting for the whole batch. Use whenever someone asks to generate, populate, fill, block out or create a city, town, street, block or neighbourhood rather than one specific object — "make me a city", "run-down industrial canal street, 10 buildings". For a single named building use factory-city-designer instead.
---

# Factory city loop

One command, a street that builds itself while you watch.

```
/factory-city-loop [theme] [how many]
```

The work splits four ways, and the split is the point. **This skill
orchestrates and knows all three others. They know nothing — not each other,
not their caller.**

```
         ideas          how to draw it        build it
plan.json ──▶ designer ──▶ spec.json ──▶ element ──▶ geometry
    ▲            (K at a time, headless)       │
    └── factory-city-generator                 └──▶ events.jsonl ──▶ browser
```

## 0. Read the command

| | |
|---|---|
| **Theme** | Any free text. Drives every idea and the palette. |
| **How many buildings** | Defaults to **10**. |

Say the numbers you settled on in one line before generating. That is the last
cheap moment for the user to change scale — counts decide how many agents run,
which is where nearly all the cost lives. Roughly **$0.50 and 90 seconds per
building**, designed four at a time.

## 1. Invent and validate the plan

Pick a short slug from the theme. Use the **factory-city-generator** skill to
write `factory-runs/<slug>/plan.json`, and validate it:

```bash
python3 .claude/skills/factory-city-generator/scripts/validate_plan.py \
    factory-runs/<slug>/plan.json --buildings <n>
```

Errors mean fix the plan and run it again. Spawn nothing until it is clean.

## 2. Start the loop, then be quiet

```bash
python3 .claude/skills/factory-city-loop/scripts/run_loop.py \
    factory-runs/<slug> --k 4
```

It opens the monitor in a browser tab, checks the Editor once, then runs K
designers at a time and builds each spec the moment it lands.

**Say nothing until it exits.** This is the one rule that matters here. Every
turn spent reporting progress re-sends the entire conversation context; a
measured 72-agent batch run spent 96.7M orchestrator tokens against the agents'
32.8M doing exactly that. The browser page is the progress report, it costs
nothing, and it is better than anything that could be typed. When the script
finishes, report its summary line in one message.

## 3. What the run leaves behind

```
factory-runs/<slug>/
├── plan.json            the closed census: one entry, one agent, no exceptions
├── events.jsonl         the timeline
├── agents/<name>.jsonl  one per agent, every operation it performed
├── designed/<name>.json each spec, with the position the loop assigned
└── cursor.json          where the row got to
```

Nothing is reconstructed from memory. If it is not in a file, it did not
happen. The folder is not cleaned up between runs — the audit trail is the
point, and the cursor is what lets a later run continue the row instead of
building on top of it.

## What it will not do

- **Retry.** A designer that writes nothing, writes nonsense, hangs, or
  produces a spec the builder refuses marks that building `failed` and the loop
  moves on. The run finishes short and says so. A retry would be a second agent
  for an entry licensed exactly one.
- **Compose a city.** Buildings go in a row. Looking like a real city is not
  this version's job.
- **See what is already in the scene.** The cursor is per run folder and starts
  at x=0, so a *new* run folder will place buildings on top of geometry an
  earlier run left there. Either reuse the same run folder, which continues the
  row where it stopped, or clear the scene first.

## Running the same folder again

Safe, and the cheapest way to finish a run that came up short. Anything
`events.jsonl` already records as built is skipped — no agent, no cost — and
only the failed and the never-attempted get designed. The cursor continues the
row rather than restarting it, so nothing lands on top of what is there.

To redesign something that did build, delete its `element_built` line from
`events.jsonl`, or start a new run folder.
- **Save the scene.** Nothing is persisted unless the user asks.

## When it aborts

`aborted: no Unity Editor on the bridge` means the preflight found no Editor
and **no agents were spent**. Check `unity status`, then run the same command
again — `plan.json` is still there and costs nothing to reuse.
