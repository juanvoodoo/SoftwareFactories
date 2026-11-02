# SoftwareFactories

A Unity 6000.3.15f1 (URP) project with a three-skill stack for generating city
scenery out of Unity primitives, driven from Claude Code through a live Unity
Editor bridge.

Ask for a building and you get one. Ask for a city and you get a street.

---

## Requirements

- **Unity 6000.3.15f1** open on this project, with the command bridge running.
- The `unity` CLI at `/Users/juan/.unity/bin/unity` (not on `PATH` — always call
  it by full path). Override with the `UNITY_CLI` environment variable.
- **Python 3** for the two bundled scripts. No third-party packages.

Check the Editor is reachable before anything else:

```bash
/Users/juan/.unity/bin/unity --no-banner --non-interactive --json status
```

You need an instance with `"state": "ready"`. If it reports something else the
Editor is usually compiling or in play mode — wait and retry. If nothing is
connected, open the project; never fall back to hand-editing scene YAML.

---

## The skill stack

Three skills, each with one job. Only one is loaded per request, so the stack
costs no more than a single skill would.

| Skill | Decides | Produces |
|---|---|---|
| `unity-city-generator` | What a whole block contains | A built street |
| `unity-city-designer` | What one element looks like | A spec |
| `unity-city-element` | Nothing — it builds | Geometry in the scene |

```
"make me a city"          → unity-city-generator ─┐
                                                  ├→ unity-city-designer → spec
"add a corner shop"       → unity-city-designer ──┘                         │
                                                                            ▼
"build this spec file"    → ────────────────────────────→ unity-city-element
```

The hand-off between layers is a **JSON file and a shell command**, not a skill
invocation. A designer agent runs `build_element.py` directly; it never loads
the builder's own documentation.

---

## Using it

### One element

> "add a corner shop with a red awning"

`unity-city-designer` picks it up, adapts a validated recipe from its catalog,
writes a spec, builds it and screenshots the result. Review the image and say
what to change.

### A whole block

> "/unity-city-generator run-down industrial canal street, 8 buildings"

`unity-city-generator`:

1. **Invents a catalog** of element ideas — one line each, open-ended, not from
   a fixed list — plus any extra colours the theme needs.
2. **Spawns one subagent per idea**, all concurrently. Each designs a shape and
   writes a JSON file. They never choose a position and never touch Unity.
3. **Packs the designed shapes** into a street: facades on a common line,
   alternating sides, props on the strip between kerb and facade, road tiled to
   span the frontage.
4. **Builds everything in one call** and screenshots it.

Parallelism is in the *designing*. Building is one call because the Unity Editor
is single-threaded — concurrent builds gain nothing and race on material assets.

### Driving the builder yourself

```bash
B=.claude/skills/unity-city-element/scripts/build_element.py

python3 $B --schema                   # the complete input contract
python3 $B spec.json --dry-run        # validate only; needs no Editor
python3 $B spec.json --preview        # build and screenshot
python3 $B spec.json --replace --save # rebuild in place and persist
```

| Flag | Effect |
|---|---|
| `--dry-run` | Validate and print placements. No Editor contact. |
| `--json` | One machine-readable result object, for agent callers. |
| `--replace` | Delete a same-named element first instead of refusing. |
| `--preview [path]` | Screenshot to `Assets/Screenshots/<name>.png`. |
| `--preview-angle <deg>` | Camera elevation. Default 18 for one element, 72 for a layout. |
| `--save` | Save the scene. Without it the build stays in memory. |

Exit codes: `0` built · `1` spec refused · `2` unreadable spec · `3` no Editor ·
`4` build failed partway.

Packing designed elements into a street:

```bash
python3 .claude/skills/unity-city-generator/scripts/pack_layout.py \
    designed.json -o packed.json [--origin-x 0]
```

---

## Writing a spec by hand

```json
{
  "name": "CornerShop",
  "position": [0, 0, 0],
  "materials": {"Brick": "#9C5B45FF", "Glass": "#6FA8C7FF"},
  "parts": [
    {"name": "Walls",  "primitive": "cube", "material": "Brick",
     "size": [6, 4, 5],     "at": [0, 0, 0]},
    {"name": "Window", "primitive": "cube", "material": "Glass",
     "size": [3, 1.8, 0.2], "at": [0, 1, -2.55]}
  ]
}
```

Wrap several in `{"elements": [ ... ]}` to build a street in one call.

Two fields carry the geometry:

- **`size`** is real-world **metres**, not a scale factor.
- **`at`** is the centre of the part's **bottom face**. `"at": [0,0,0]` sits it
  on the ground. Use `"center"` instead for rotated parts.

### Why metres and not scales

Unity primitives have centred pivots and inconsistent native sizes — the single
biggest source of wrong-looking primitive scenes:

| Primitive | Size at scale 1 | |
|---|---|---|
| cube, sphere, quad | 1 | |
| **cylinder, capsule** | 1 × **2** × 1 | two units tall, not one |
| plane | 10 × 10, flat | scaling y does nothing |

A 5 m lamppost is a cylinder with `scale.y = 2.5` placed at `y = 2.5` — two
corrections, and missing either buries it in the road. Give `size` and `at` and
the builder derives both.

---

## When the builder refuses

A refusal creates **nothing**, and reports every fault at once so one fix clears
them all. It refuses rather than quietly repairing, because a silent correction
makes the caller's description a lie.

| Code | Meaning |
|---|---|
| `part_hidden_inside` | The part is entirely within another and would be invisible. |
| `part_below_ground` | It dips under y=0. Raise it, or set `"below_ground": true`. |
| `undefined_material` | A part names a material missing from `materials`. |
| `unknown_primitive` | Not cube, sphere, cylinder, capsule, plane or quad. |
| `bad_size` | A size component is zero or negative. |
| `name_taken` | A scene root already has that name — pass `--replace`. |
| `origin_below_ground` | The element's own `position` has y < 0. |

Warnings don't stop a build: `elements_overlap`, `coplanar_faces`,
`material_color_ignored`.

### Primitives are solid

`part_hidden_inside` catches the most common modelling mistake. A primitive has
no interior, so anything placed inside one simply vanishes — water sunk into a
basin, a bulb inside a shade. No command output would tell you; only a
screenshot would.

Build hollows by implication: the water disc sits slightly *above* the basin
rim, a doorway is a darker slab on the facade. Keep such surfaces a couple of
centimetres clear of the face they sit on, since exactly coplanar faces flicker.

---

## Materials

One shared palette at `Assets/CityKit/Materials/<Role>.mat`, URP/Lit, coloured
via `_BaseColor`. The built-in `Standard` shader renders magenta in this
project.

Materials are named for the **role** the colour plays (`Concrete`, `Glass`,
`Brick`), never per object, and **an existing one is reused untouched and never
recoloured** — the palette is shared across the whole city, so restyling
`Concrete` would repaint every building using it. Need another shade? Name the
difference (`ConcreteDark`). Requesting a different colour for an existing role
builds with the existing one and warns `material_color_ignored`.

The standard palette lives in
`.claude/skills/unity-city-designer/references/catalog.md`, alongside twelve
validated element recipes.

---

## Verifying

Static validation proves geometry is possible. It cannot tell you a tower looks
squat or that two colours mush together, so **open the preview image**.

- A **single element** is shot from a low angle — you're judging whether it
  reads as the thing.
- A **layout** is shot from near overhead, because at street level the nearest
  frontage hides everything behind it, and what you're checking is spacing and
  variety. Pass `--preview-angle 14` for an eye-level look as well.

Don't use `capture.scene_view` with `Edit/Frame Selected`: framing aims at the
root pivot, which on a ground-anchored element is at its feet, so the camera
ends up inside the geometry.

---

## Gotchas

- **Nothing is saved unless you pass `--save`.** Saving is the only
  hard-to-undo step, so it's always an explicit choice.
- **Primitives arrive with colliders.** Fine for blockout; remove with
  `component.remove` if you don't want them.
- **Unity CLI arguments are `--name value`**, not `name=value`, which fails with
  `INVALID_COMMAND_ARGS`.
- **Adding to an existing city**: `pack_layout.py` prevents overlap only among
  the elements it places. It cannot see geometry from an earlier run — read the
  scene first and pass `--origin-x` clear of it.
- **Rotated parts get weaker checks.** The coplanar test skips them and bounds
  come from their bounding box, so pitched roofs and angled signage are
  validated less tightly than upright geometry.
- **Concurrent designers can't see each other's palettes.** Declare a theme's
  extra colours in the catalog up front; `pack_layout.py` reports any role that
  two designers defined differently.

---

## Layout

```
.claude/skills/
├── unity-city-generator/
│   ├── SKILL.md                     invent a catalog, fan out, pack, build
│   └── scripts/pack_layout.py       assign positions from real footprints
├── unity-city-designer/
│   ├── SKILL.md                     decompose, proportion, colour, layout
│   └── references/catalog.md        12 validated recipes + standard palette
└── unity-city-element/
    ├── SKILL.md                     the contract, flags, refusal codes
    └── scripts/build_element.py     validate, place, build, screenshot
```

See `CLAUDE.md` for the general Unity CLI workflow in this project.
