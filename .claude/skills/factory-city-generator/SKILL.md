---
name: factory-city-generator
description: Invent a plan of varied building ideas for a city from a style or theme in free text, and write it as plan.json. Use when someone asks for a set of buildings rather than one specific object — "run-down industrial canal street, 10 buildings", "coastal old town, just three houses". Produces ideas and a shared palette, nothing else.
---

# Factory city generator

Free text in, `plan.json` out. Ideas and a palette. That is the whole job.

This is the creative step and it is deliberately **not** a menu. Invent
buildings that would plausibly share a street, given whatever theme you were
given, or a generic contemporary city if you were given none.

Write the plan to the path you were asked to write it to.

```json
{"theme": "calle portuaria de los años 50",
 "palette": {"Rust": "#8A5236FF", "SaltedTimber": "#7A6A58FF"},
 "elements": [
   {"name": "Lonja", "kind": "building",
    "idea": "lonja de pescado de una planta, hormigón encalado, portones de chapa oxidada y rótulo descolorido",
    "footprint_m": [22, 14], "height_m": 7},
   {"name": "AlmacenGrano", "kind": "building",
    "idea": "silo-almacén de seis plantas, ladrillo ennegrecido, ventanas estrechas y escalera exterior de hierro",
    "footprint_m": [16, 16], "height_m": 24}
 ]}
```

Each entry needs only a unique `name` (letters, digits and underscores, starting
with a letter), `kind: "building"`, a one-line `idea` rich enough to design
from, and rough `footprint_m` / `height_m`.

## Make them genuinely different

A street of five similar offices is a failure of this step, and no amount of
good work later fixes it. Vary:

- **Use** — civic, retail, residential, office, workshop, leisure, derelict.
- **Scale** — mix something tall with low-rise. Identical heights read as a
  wall. Put something under 8 m and something over 20 m in the same set.
- **Material and era** — brick, render, concrete, glass, timber.
- **Condition** — new, tired, boarded up, recently refitted.

## Declare the palette up front

The theme's extra colours — rust, soot, neon, moss — are decided **here**, as
role name to `#RRGGBBAA`, named for the material and not the object.

This is not tidiness. Whatever designs these ideas later cannot see what the
others chose, so left to themselves three of them invent three different rusts,
two under the same role name, and the street stops looking like one place.

## Validate before the plan leaves

```bash
python3 scripts/validate_plan.py <plan.json> --buildings <n>
```

Every time, no exceptions — a fault found here costs nothing, and the same
fault found later costs a whole round of work.

**Errors mean fix the plan and run it again:** `bad_name`, `duplicate_name`,
`bad_kind`, `missing_idea`, `missing_footprint`, `missing_height`,
`count_mismatch`.

**Warnings are about whether the street will be any good**, and are usually
worth acting on: `flat_skyline`, `thin_idea`, `no_palette`. Revise unless you
were asked for exactly that.
