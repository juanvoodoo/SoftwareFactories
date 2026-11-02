---
name: unity-city-element
description: Build Unity city geometry from an existing JSON spec of parts, sizes and colors — the HOW-TO-DRAW half of city creation. Use this when a spec already exists, when the unity-city-designer skill hands one over, when a build was refused and needs fixing, or when the user explicitly asks to build, validate or rebuild a spec file. It handles Unity primitive pivot math, URP materials, batched Editor calls and refuses geometry that would be invisible or buried. It decides nothing about shape, proportion or color. For a request that has not been designed yet — "add a building", "make a city street" — use unity-city-designer instead, which decides what to build and then calls this.
---

# Unity city element builder

A driver, not a designer. The caller decides *what* the element looks like; this
skill makes Unity build exactly that, correctly.

It owns the mechanical parts that are easy to get silently wrong: Unity's
centred pivots and odd native primitive sizes, URP material assets, batched
Editor calls, and refusing descriptions that would produce invisible or buried
geometry. It deliberately owns no taste — if you find yourself deciding how many
parts a shop should have or what shade of brick looks right, stop and use the
**unity-city-designer** skill, which makes those decisions and then calls this.

## Build it

```bash
B=.claude/skills/unity-city-element/scripts/build_element.py
python3 $B --schema              # the full, authoritative input contract
python3 $B spec.json --dry-run   # validate only; never touches the Editor
python3 $B spec.json --preview   # build and screenshot
```

| Flag | Effect |
|---|---|
| `--dry-run` | Validate and print resolved placements. No Editor contact. |
| `--json` | One machine-readable result object. Use this when an agent is the caller. |
| `--replace` | Delete an element of the same name first, instead of refusing. |
| `--preview [path]` | Screenshot the result; defaults to `Assets/Screenshots/<name>.png`. |
| `--save` | Save the scene. Without it the build stays in memory. |

Exit codes: `0` built, `1` spec refused, `2` unreadable spec, `3` Editor
unavailable, `4` build failed partway.

## The spec

`--schema` prints the complete contract; this is the shape of it:

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

Wrap several in `{"elements": [ ... ]}` to build a whole street in one call —
cheaper than one invocation per building, and the preview frames them together.

Two fields carry all the geometry:

- **`size`** is real-world metres, *not* a scale factor.
- **`at`** is the centre of the part's **bottom face**, in element-local space.
  `"at": [0,0,0]` puts the part on the ground. Use `"center"` instead to give
  the pivot directly, which is what rotated parts need.

### Why metres and not scales

Unity primitives have centred pivots and inconsistent native sizes, which is the
single biggest source of wrong-looking primitive scenes:

| Primitive | Size at scale 1 | |
|---|---|---|
| cube, sphere, quad | 1 | |
| **cylinder, capsule** | 1 × **2** × 1 | two units tall, not one |
| plane | 10 × 10, flat | scaling y does nothing |

A 5m lamppost is a cylinder with `scale.y = 2.5` positioned at `y = 2.5` — two
separate corrections, and missing either buries it in the road. Passing `size`
and `at` lets the script derive both, so never pre-divide anything yourself.

## When it refuses

A refusal means **nothing was created**. Every fault in the spec is reported at
once, so one fix-and-retry clears them all. The script would rather refuse than
quietly repair, because a silent correction makes the caller's description a
lie and the mistake resurfaces later as a city that looks subtly wrong.

| Code | What it means |
|---|---|
| `part_hidden_inside` | The part sits entirely within another and would never be seen. |
| `part_below_ground` | It dips under y=0. Raise it, or set `"below_ground": true` if a buried footing is intended. |
| `undefined_material` | A part names a material missing from `materials`. |
| `unknown_primitive` | Not one of cube, sphere, cylinder, capsule, plane, quad. |
| `bad_size` | A size component is zero or negative. |
| `name_taken` | A scene root already uses that name. Pass `--replace`. |
| `origin_below_ground` | The element's own `position` has y < 0. |

Warnings don't stop a build: `coplanar_faces` (two same-facing surfaces share a
plane and will flicker — offset one by ~0.02), `origin_raised` (y > 0, so it
floats), `material_color_ignored` (see below).

### Primitives are solid

`part_hidden_inside` catches the most common modelling mistake. A primitive has
no interior, so anything placed inside one simply vanishes — water sunk into a
basin, a bulb inside a shade, a floor inside a room. Nothing in the command
output would tell you; only the screenshot would.

Build hollows by implication instead: the water disc sits slightly *above* the
basin's rim, a doorway is a darker slab on the facade rather than a hole. Keep
such surfaces a couple of centimetres clear of the face they sit on, since
exactly coplanar faces flicker.

## Materials

Materials live in one shared palette at `Assets/CityKit/Materials/<role>.mat`,
URP/Lit, colored via `_BaseColor`. Using the built-in `Standard` shader in this
project renders magenta.

The caller supplies exact colors; this skill only creates the assets. **An
existing material is reused untouched and never recolored** — the palette is
shared across the whole city, so restyling `Concrete` would repaint every
building already using it. Ask for a different shade by naming a different role
(`ConcreteDark`), not by redefining an existing one. If a spec requests a color
that differs from what's on disk, the build proceeds with the existing color and
says so via `material_color_ignored`.

## Verifying

Static validation catches geometry that is impossible or invisible. It cannot
tell you a tower looks squat or that two colors mush together — for a shape
being built for the first time, run `--preview` and actually open the image.
For a known shape with only dimensional tweaks, the validation is enough.

Don't reach for `capture.scene_view` with `Edit/Frame Selected` instead: framing
aims at the root pivot, which on a ground-anchored element sits at its feet, so
the camera ends up inside the geometry. `--preview` computes real bounds, uses a
temporary camera and deletes it again.

## Worth knowing

- **Nothing is saved unless you pass `--save`.** Saving is the only hard-to-undo
  step here, so it is always the caller's explicit choice.
- **Primitives arrive with colliders.** Fine for blockout; remove via
  `component.remove` only if asked.
- **The Editor must be `ready`.** The script checks first and fails cleanly;
  if nothing is connected, say so rather than hand-editing scene YAML.
- **CLI arguments are `--name value`**, not `name=value`, which fails with
  `INVALID_COMMAND_ARGS`. Only relevant if you drive the `unity` CLI directly.
