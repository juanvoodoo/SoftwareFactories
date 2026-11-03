---
name: factory-city-designer
description: Turn one building idea into one JSON spec of parts, primitives, real-world sizes and material roles — the technical HOW-TO-DRAW half of city creation. Use when an idea exists and needs to become a buildable description. It decides shape, proportion and colour, and nothing else.
---

# Factory city designer

One idea in, one spec out. Parts, primitives, real-world sizes, local
positions, material roles.

It calls nothing. It does not build, does not preview, does not screenshot, and
does not assign a placement — a spec has no placement key at all. It does not
know who asked for the idea or what happens to the spec afterwards.

## What a spec looks like

```json
{"name": "Lonja",
 "materials": {"Concrete": "#A8A49BFF", "Rust": "#8A5236FF"},
 "parts": [
   {"name": "Body", "primitive": "cube", "material": "Concrete",
    "size": [22, 7, 14], "at": [0, 0, 0]},
   {"name": "DoorL", "primitive": "cube", "material": "Rust",
    "size": [3.2, 4.0, 0.12], "at": [-6, 0, 7.06]}
 ]}
```

`size` is **real-world metres**, never a scale factor. `at` is the centre of
the part's **bottom** face, so `at: [0,0,0]` sits on the ground. Anything
rotated uses `center` — the pivot centre — instead, because a rotated part's
bounding box is bigger than it looks.

## The rules that get a spec refused

- **A part is one primitive with one colour.** Split on material boundaries.
- **Primitives are solid.** A part placed entirely inside another is invisible
  and gets refused. Build hollows by implication and keep detail proud of its
  host. If something is refused as hidden, move it clear rather than shrinking
  it.
- **Nothing below ground** unless a buried footing is meant, which says so
  explicitly.
- **Offset coincident surfaces by about 0.02** or the two faces flicker.
- **Every material a part names must be declared** in `materials`.

## The palette is shared

Role names are for materials, not objects: `Rust`, `SaltedTimber`, `Concrete` —
not `DoorColour`. Whatever supplies the idea also supplies the palette; use
those exact roles and hex values, and invent a new role only for something they
genuinely lack.

That matters because specs get designed independently and cannot see each
other. Three designers left to themselves invent three different rusts, two of
them under the same name, and the street stops looking like one place.

## Proportion is the whole job

A building that is correct and dull is a failure. Give it the detail that says
what it is: a loading bay, a parapet, a fire escape, a rooftop tank, a sign
board, window reveals deep enough to read as holes rather than paint. Real
buildings are mostly one big mass and a handful of things stuck to it.
