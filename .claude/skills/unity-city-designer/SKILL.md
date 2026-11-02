---
name: unity-city-designer
description: Design and create city scenery in Unity — buildings, towers, houses, shops, streetlights, benches, bus stops, trees, traffic lights, kiosks, billboards, roads — and whole streets, blocks and plazas composed of them. Use this skill whenever someone asks to create, add, place, build, block out, greybox, prototype or populate anything urban in a Unity scene, including vague requests like "add a building", "make this look like a city street" or "put some props on the sidewalk". It decides what the thing should look like — parts, real-world proportions, colors, layout — and then builds it by writing a spec and running the unity-city-element builder script. Start here rather than placing primitives by hand.
---

# Unity city designer

This skill decides **what** a piece of city looks like. It does not touch Unity
directly: it writes a spec and hands it to the builder, which owns all the
Editor mechanics.

```
user request → [this skill: decide] → spec.json → build_element.py → scene
```

The builder is reached by **running its script**, not by invoking the
unity-city-element skill. Everything needed is in the command: `--schema`
prints the contract, and refusals name what to fix. Loading that skill as well
just costs tokens for information you already have below.

`references/catalog.md` holds two different things, used in opposite ways:

- **The standard palette** — shared colour roles. Use it. Reusing roles is what
  makes separate elements read as one city rather than a pile of props, and the
  builder shares materials by role name, so reuse costs nothing.
- **Twelve worked examples** — complete, validated breakdowns of common
  elements. These are *patterns, not a menu*. They show what a good spec looks
  like: how parts are split, what proportions read correctly, how detail is
  kept proud of its host. They do not limit what you can build.

## Build it

```bash
B=.claude/skills/unity-city-element/scripts/build_element.py
python3 $B spec.json --dry-run    # free: validates, no Editor contact
python3 $B spec.json --preview    # build and screenshot
```

Run `python3 $B --schema` if you need the exact spec contract. Useful flags:
`--json` (machine-readable result), `--replace` (rebuild an existing element),
`--save` (persist the scene — only when the user wants it).

## Designing one element

**Design whatever was actually asked for.** Most requests will not match one of
the twelve examples, and that is the normal case, not a problem. A disused
foundry with a sawtooth roof, a derelict stair tower with a water tank, a
floating market stall — none of these are in the file, and all of them are built
from the same six primitives by the same method.

If the request does match an example, adapting it is quicker and already
validated, so do that. Otherwise read one or two as a reference for *how* a
spec is assembled, then design the thing in front of you.

**A part is one primitive with one color.** Split on material boundaries, not
just geometry: a wall and its windows are separate parts because they're
different colors, even though both are boxes.

**Use the fewest parts that still read as the thing.** A box, a slab roof, a
darker ground-floor band and a strip of windows reads as a building. Thirty
parts modelling each brick reads no better and makes the scene heavier. Six to
fifteen parts suits most elements.

**Get real dimensions right before anything else.** Unity's unit is a metre, and
proportion matters more than any other choice — a correctly-proportioned grey
box reads as a building, a badly-proportioned colorful one doesn't.

| | | | |
|---|---|---|---|
| shop | ~4 m | house | 6–8 m |
| mid-rise | 12–20 m | office tower | 30 m+ |
| streetlight | 5–6 m | traffic light | 4 m |
| bench seat | 0.45 m | bus shelter | ~2.5 m |
| street tree | 5–7 m | kerb | 0.15 m |

**Name parts for what they are** (`Roof`, `Window_North`, `Pole`) — they become
GameObject names someone will read in the Hierarchy later.

**Take colors from the catalog palette** and name them by the role the color
plays (`Concrete`, `Glass`, `Brick`), never per object. Prefer slightly
desaturated values; fully saturated primaries read as a programmer-art test
scene rather than a city. Need a different shade? Name the difference
(`ConcreteDark`) — the builder shares materials by role and will refuse to
recolor one already in use, because that would repaint every element using it.

## Designing a layout

A street or block goes in **one spec** as `{"elements": [...]}`, built in one
call. Place each element with its own `position`; everything stays at y=0.

**Space by footprint.** Give each element its footprint plus 2–4 m between
buildings. The builder warns with `elements_overlap` if two intrude on each
other — treat that as a layout bug unless the overlap is deliberate, like a
bench against a wall.

**Lay out around the road, not the origin.** Put road segments down an axis and
build the frontages off them. Three numbers matter, and getting them wrong is
what makes a street look like buildings dumped in a field:

- **Tile the road to cover the whole frontage.** The example segment is 20 m;
  place several end to end (at x = -10, +10, +30 …) so no building faces bare
  ground. Segments that merely touch don't trigger an overlap warning.
- **Set facades back ~4–5 m from the outer kerb edge**, not 1–2 m. That strip is
  where lights, benches, bins, trees and shelters live, and without it the props
  are crushed against the wall and effectively invisible.
- **Don't wall in both sides.** Put taller blocks on one side and houses or
  low-rise on the other, or the street becomes a canyon with nothing to see.

Streetlights go roughly every 12–18 m, alternating sides on a wider road.

**Vary repeats.** Identical buildings in a row look cloned. Change height by a
few metres, swap the facade role between `Brick`, `Plaster` and `Concrete`, and
shift window bands. Three variants of a mid-rise read as a city block; one
variant repeated five times reads as a bug.

**Streetlights roughly every 12–18 m**, alternating sides for a wider road.

## What the builder will refuse

Design around these — the builder reports them all at once and creates nothing:

- **Primitives are solid.** Anything placed inside another part is invisible —
  water sunk into a basin, a bulb inside a shade. Build hollows by implication:
  the water disc sits *above* the basin rim, a doorway is a darker slab on the
  facade. (`part_hidden_inside`)
- **Nothing below y=0** unless a buried footing is genuinely meant, which needs
  `"below_ground": true`. (`part_below_ground`)
- **Every material a part names must be declared** in that element's
  `materials`. (`undefined_material`)
- **Six primitives only**: cube, sphere, cylinder, capsule, plane, quad.
  (`unknown_primitive`)
- **A scene root can't be reused** — pass `--replace` to rebuild.
  (`name_taken`)

Warnings worth acting on: `coplanar_faces` means two surfaces share a plane and
will flicker — offset one by ~0.02. Inset detail should sit slightly *proud* of
its host (glass panels a hair outside the wall) so it reads crisply.

## Finish the job

1. `--dry-run` first on anything non-trivial. It's free and catches every
   structural fault before the Editor is touched.
2. Build with `--preview`, then **open the screenshot and look at it.**
   Validation proves the geometry is possible; only the image tells you whether
   a tower looks squat or two colors mush together. For an element adapted from
   a worked example with only dimensional tweaks, validation alone is enough.

   A layout is previewed from near overhead, because at any street-level angle
   the nearest frontage hides everything behind it — and what you're checking in
   a layout is spacing and placement, which a plan view shows perfectly. Pass
   `--preview-angle 14` if you also want to see how the street reads at eye
   level, expecting the near buildings to block much of it.
3. Fix and rebuild with `--replace` if it doesn't read right. Rebuilding is
   cheap; leaving it wrong isn't.
4. **Only save when the user asks.** The build stays in memory until `--save`,
   which is the one step here that's hard to undo.
