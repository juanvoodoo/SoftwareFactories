---
name: factory-city-element
description: Build one city building in Unity from a JSON spec of parts, sizes and colours. Use when a spec already exists and needs to be turned into geometry, validated, or rebuilt after a refusal. It decides nothing about shape, proportion, colour or placement — it takes a complete description and makes Unity build it correctly.
---

# Factory city element

A driver, not a designer. It takes a complete description of one building and
makes Unity build it correctly. What it owns is the part that is mechanical and
easy to get silently wrong: pivot arithmetic, URP material assets, batched
Editor calls, and refusing specs that would produce invisible or buried
geometry.

It knows nothing about where the building goes. The `position` in the spec is
given to it; it does not choose one.

```bash
python3 scripts/build_element.py --schema          # the full input contract
python3 scripts/build_element.py spec.json [flags]
python3 scripts/build_element.py --selftest        # five checks, no Editor
```

| Flag | Effect |
|---|---|
| `--dry-run` | validate and report placements; never touches the Editor |
| `--json` | one machine-readable object on stdout |
| `--replace` | delete an existing element of the same name first |
| `--preview [path]` | screenshot the result |
| `--save` | save the scene (otherwise it stays in memory) |

Exit codes: `0` ok, `1` refused, `2` bad spec, `3` Editor unavailable,
`4` build failed.

## The spec

```json
{"name": "Lonja",
 "position": [0, 0, 0],
 "materials": {"Concrete": "#A8A49BFF"},
 "parts": [{"name": "Body", "primitive": "cube", "material": "Concrete",
            "size": [22, 7, 14], "at": [0, 0, 0]}]}
```

Several at once: `{"elements": [{...}, {...}]}`.

`size` is **real-world metres**, never a scale factor — the script converts to
Unity's centred pivots and native primitive sizes itself. `at` is the centre of
the part's **bottom** face, so `at: [0,0,0]` sits on the ground; use `center`
instead for anything rotated, whose bounding box is larger than it looks.

Primitives are **solid**. A part placed inside another is invisible and gets
refused — build hollows by implication and keep detail proud of its host.

## Refusals and warnings

Refuses, and builds nothing: `unknown_primitive`, `undefined_material`,
`bad_size`, `part_below_ground`, `part_hidden_inside`, `name_taken`,
`origin_below_ground`, `duplicate_name`.

Warns, and builds anyway: `origin_raised`, `coplanar_faces` (offset coincident
surfaces by ~0.02 or they flicker), `elements_overlap`, `material_color_ignored`.

Materials land in `Assets/FactoryKit/Materials/<role>.mat` on URP/Lit. An
existing one is reused as-is and never repainted, because the palette is shared
and restyling it would repaint everything already using it.
