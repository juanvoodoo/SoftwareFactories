---
name: unity-city-generator
description: Generate a whole block of city in Unity from a single command — invent a plan of varied building and prop ideas, design them all in parallel, lay them out as a street and build them in one pass. Use this whenever someone asks to generate, populate, fill, block out or create a city, town, street, block, neighbourhood or district rather than one specific object, or says something as short as "make me a city". Takes a style or theme and how many of each thing to build, in free text — "run-down industrial canal street, 10 buildings and lots of street furniture", "coastal old town, just three houses" — and defaults to 8 buildings and 8 props when unspecified. For a single named element use unity-city-designer instead.
---

# Unity city generator

Turns one command into a populated street. The work splits three ways, and the
split matters: **this skill invents and orchestrates**, subagents **design one
element each in parallel**, and the builder **places and creates the geometry
in a single pass**.

```
/unity-city-generator [style/theme] [counts]
   │
   ├─ 0. read the command                   (style, how many of what)
   ├─ 1. invent a plan of ideas             (this skill)
   ├─ 2. validate the plan                  (validate_plan.py) ← before any agent
   ├─ 3. one subagent per idea, concurrent  (each uses unity-city-designer)
   ├─ 4. pack the designed shapes           (pack_layout.py)
   └─ 5. build everything in one call       (build_element.py)
```

Subagents design **shape only and never a position**. They run concurrently, so
none can see the others' choices — placement is decided centrally once every
footprint is known. This is also why building happens in one call rather than
per agent: the Unity Editor is single-threaded, so parallel building buys no
speed, while parallel designing buys a great deal.

## 0. Read the command

Everything about scale and character comes from the user, not from this file.
Take from their words:

| | |
|---|---|
| **Style / theme** | Any free text — "run-down industrial canal street", "coastal old town", "1980s Tokyo back street". Drives every idea and the extra palette. |
| **How many buildings** | "8 buildings", "a dozen blocks", "just three". |
| **How many props** | "lots of street furniture", "keep it bare". |
| **Anything specific they named** | "there must be a church" — put it in the plan verbatim. |

Defaults when they didn't say, so a bare `/unity-city-generator` still works:
**8 buildings, 8 props, 1 road, contemporary generic city.** State the numbers
you settled on in one line before generating, so the user can redirect before
any agent runs — that is the last cheap moment to change scale.

Counts are not a detail. They set how many subagents get spawned, which is
where nearly all the cost of a run lives.

## 1. Invent the plan

This is the creative step, and it is deliberately **not** a menu. Invent ideas
that would plausibly share a street, given whatever theme the user gave (or a
generic contemporary city if they gave none).

Everything this run produces lives in one folder, so the city can be rebuilt or
tweaked later without paying for the design agents again. Pick a short slug from
the theme and create `city-runs/<run>/`:

```
city-runs/canal-street/
├── plan.json          the ideas (this step)
├── designed/*.json    one spec per element (step 3)
└── packed.json        everything, positioned (step 4)
```

`city-runs/` is gitignored — these are working files, not project sources, and
they stay out of `Assets/` so Unity doesn't import them as TextAssets.

Write `city-runs/<run>/plan.json`:

```json
{"theme": "post-war European high street",
 "palette": {"Rust": "#8A5236FF", "SootBrick": "#5E3B32FF"},
 "elements": [
  {"name": "Library", "kind": "building",
   "idea": "1960s civic library, 3 floors, board-formed concrete with deep window reveals and a brass-toned entrance canopy",
   "footprint_m": [18, 12], "height_m": 14},
  {"name": "Newsstand", "kind": "prop",
   "idea": "cramped corner newsstand, green painted steel, awning over a magazine rack",
   "footprint_m": [2.4, 1.8], "height_m": 2.6}
 ]}
```

Each entry needs only: a unique `name`, a `kind` of `building`, `prop` or
`road`, a one-line `idea` rich enough to design from, and rough
`footprint_m` / `height_m` so the layout can reserve space.

**Declare the theme's extra colors in `palette` up front.** The standard palette
in the designer's recipe catalog covers ordinary city materials; a theme usually needs
a few more — rust, soot, neon, moss. Decide them here and pass them to every
subagent, because designers run concurrently and cannot see each other's
choices. Left to themselves, three of them will invent three different rusts,
two under the same role name, and the street loses the shared palette that
makes it look like one place. `pack_layout.py` reports such clashes, but
preventing them is free and fixing them afterwards is not.

**Make them genuinely different.** A street of five similar offices is a
failure of this step, and no amount of good building later fixes it. Vary:

- **Use** — civic, retail, residential, office, workshop, leisure, derelict.
- **Scale** — mix a tower or two with low-rise; identical heights read as a
  wall. Something under 8 m and something over 20 m in the same block.
- **Material and era** — brick, render, concrete, glass, timber.
- **Condition** — new, tired, boarded up, recently refitted.

Produce exactly the counts settled in step 0, plus exactly one `road`. Props
are what sell it as inhabited: lights, benches, bins, trees, shelters, signage,
kiosks, bollards.

The road entry is a 20 m tile prototype that gets cloned to span the block, so
describe one segment, not the whole street.

## 2. Validate the plan before spending agents

```bash
python3 .claude/skills/unity-city-generator/scripts/validate_plan.py \
    city-runs/<run>/plan.json --buildings <n> --props <n> --check-scene
```

Run this every time, with no exceptions. Fanning out is the expensive step, and
a fault found afterwards costs a whole round of agents to redo; found here it
costs nothing. `--check-scene` also catches a name already used in the scene,
which would otherwise surface as `name_taken` after every agent had finished.

**Errors (exit 1) mean spawn nothing.** Duplicate or malformed names, a bad
`kind`, a missing footprint, two roads, a count that doesn't match what the user
asked for. Fix the plan and re-validate.

**Warnings are about whether the street will be any good**, and they are usually
worth acting on before spending agents rather than after seeing the preview:
`flat_skyline` (every building the same height reads as a wall), `thin_idea` (a
designer given two words produces two words' worth of building), `few_props`,
`no_palette`. Revise unless the user asked for exactly that.

## 3. Design every element in parallel

Spawn one subagent per plan entry, all in a single message so they run
concurrently. Give each exactly this brief, filled in:

```
Design ONE element for the Unity city builder and write it to <out_path>.

Idea: <idea>
Kind: <building|prop|road>
Target footprint: <w> x <d> m, height about <h> m

Theme: <theme>
Theme palette — use these exact roles and hex values for these materials:
<the plan's palette block>

Method and the standard palette:
  .claude/skills/unity-city-designer/SKILL.md
  .claude/skills/unity-city-designer/references/catalog.md
The exact contract:  python3 .claude/skills/unity-city-element/scripts/build_element.py --schema

Write ONE JSON object to <out_path> with keys: name (exactly "<name>"),
materials, parts. Do NOT include "position" — placement is assigned centrally.
Do NOT build anything; another step does that.
Stay within the target footprint. Use the standard palette and the theme palette
above; invent a new role only for something neither covers, and name it for the
material, not the object (SootBrick, not FoundryWall).
Verify with:
  python3 .claude/skills/unity-city-element/scripts/build_element.py <out_path> --dry-run
and fix anything it refuses before you finish.
```

Point each subagent at `city-runs/<run>/designed/<Name>.json`.

Have each subagent **write a file** rather than return JSON in prose — parsing
a file is reliable, parsing a report is not. Tell it to dry-run its own work:
that check is free, needs no Editor, and means a bad element is caught by the
agent that made it rather than surfacing at the end.

## 4. Pack and build

Merge `designed/*.json` into `{"elements": [...]}`, keeping each entry's `kind`,
then:

```bash
R=city-runs/<run>
python3 .claude/skills/unity-city-generator/scripts/pack_layout.py \
    $R/designed.json -o $R/packed.json
python3 .claude/skills/unity-city-element/scripts/build_element.py \
    $R/packed.json --preview Screenshots/city.png
```

The packer assigns every position: buildings alternate sides of the street with
their facades on a common line, props spread along the strip between kerb and
facade, and the road tiles to cover the whole frontage. It takes footprints
from the builder's own dry-run, so what it packs is exactly what gets built,
and it refuses rather than guessing if any element is invalid.

**Adding to a city that already exists**: read the scene once
(`scene.get_hierarchy`), and pass `--origin-x` far enough along the street to
clear what's there. The packer prevents overlap among the elements it places,
but it cannot see geometry built by an earlier run.

## 5. Review and save

Open the preview. A layout is shot from near overhead, which is the right view
for judging spacing and variety — exactly what can go wrong here. Ask whether
the block reads as a street and whether the buildings look like different
buildings.

**Rebuilding or changing a past run** is why the folder is kept. Everything is
already on disk, so none of it needs agents again:

```bash
R=city-runs/<run>
B=.claude/skills/unity-city-element/scripts/build_element.py
python3 $B $R/packed.json --replace --preview Screenshots/city.png
```

To change one element, edit its file in `designed/`, re-pack and rebuild — or
re-run just that one subagent. To extend the block, add entries to `plan.json`,
design only the new ones, and pack with `--origin-x` past the existing frontage.

Never re-run the whole generator to fix one building: it invents a *different*
city, and discards work you have already paid for.

**Nothing is saved unless asked.** Pass `--save` only when the user says so.
