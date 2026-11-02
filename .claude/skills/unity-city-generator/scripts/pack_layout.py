#!/usr/bin/env python3
"""Lay designed elements out as a street, then emit one buildable spec.

Subagents design element SHAPES without deciding where they go, because they
run concurrently and cannot see each other's choices. This script receives
those shapes, works out each one's real footprint, and assigns positions so
nothing overlaps and the result reads as a street rather than a pile.

It never duplicates the builder's pivot arithmetic: footprints come from
`build_element.py --dry-run --json`, which is the same code that will place
the geometry, so what is packed here is exactly what gets built.

  pack_layout.py designed.json -o street.json [--origin-x 0] [--seed 0]

Input: {"elements": [ <element spec>, ... ]} where each element carries a
"kind" of "building", "prop" or "road", and NO "position" (any is ignored).
A "road" element is a 20 m tile prototype; it is cloned along the street to
cover whatever the frontages end up spanning. Omit it for no road.

Output: the same elements with "kind" stripped and "position" assigned,
ready for `build_element.py`.
"""
import argparse, json, os, random, subprocess, sys, tempfile

BUILDER = os.environ.get("CITY_BUILDER", os.path.join(
    os.path.dirname(__file__), "..", "..", "unity-city-element", "scripts",
    "build_element.py"))

# Street geometry, in metres. These numbers are not arbitrary: a facade closer
# than about 4 m to the kerb leaves no room for lights, benches or trees, and
# the street stops looking inhabited.
KERB_OUTER = 5.6     # outer edge of the kerb in the road tile
SETBACK = 4.5        # kerb edge to building facade
BUILDING_GAP = 3.0   # between neighbouring buildings on the same side
STRIP_Z = KERB_OUTER + SETBACK / 2.0   # where props sit


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def footprints(elements):
    """Ask the builder for each element's real bounds, at origin."""
    probe = {"elements": [{**{k: v for k, v in e.items() if k != "kind"},
                           "position": [0, 0, 0]} for e in elements]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(probe, f)
        path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, BUILDER, path, "--dry-run", "--json"],
            capture_output=True, text=True,
            env={**os.environ, "UNITY_CLI": "/nonexistent"})
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            die(f"could not read builder output: {proc.stdout[:300]}{proc.stderr[:300]}")
    finally:
        os.unlink(path)
    if out["errors"]:
        print("the designed elements were refused by the builder:", file=sys.stderr)
        for e in out["errors"]:
            print(f"  [{e['code']}] {e['message']}", file=sys.stderr)
        sys.exit(1)
    return {b["name"]: b["bounds"] for b in out["elements"]}


def report_palette_clashes(elements):
    """Flag roles that different designers defined differently.

    Subagents design concurrently and cannot see each other's palettes, so two
    of them inventing `Rust` in different shades is a predictable outcome, not
    a freak event. The builder resolves it first-wins, which is fine, but
    silently -- so say it out loud here, where it can still be fixed.
    """
    roles = {}
    for el in elements:
        for role, colour in (el.get("materials") or {}).items():
            roles.setdefault(role, {}).setdefault(colour, []).append(
                el.get("name", "?"))
    for role, variants in roles.items():
        if len(variants) > 1:
            detail = "; ".join(f"{c} from {', '.join(w)}"
                               for c, w in variants.items())
            print(f"warning: role '{role}' was defined differently by "
                  f"different designers ({detail}); the first wins. Declare it "
                  f"in the catalog palette up front to keep them consistent.",
                  file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("designed")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--origin-x", type=float, default=0.0,
                    help="shift the whole block along the street axis; use this "
                         "to start a new block clear of an existing one")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    spec = json.load(open(args.designed))
    elements = spec["elements"] if "elements" in spec else [spec]
    if not elements:
        die("no elements to lay out")

    names = [e.get("name") for e in elements]
    if len(set(names)) != len(names):
        die(f"element names must be unique: {names}")

    report_palette_clashes(elements)
    bounds = footprints(elements)
    buildings = [e for e in elements if e.get("kind", "building") == "building"]
    props = [e for e in elements if e.get("kind") == "prop"]
    roads = [e for e in elements if e.get("kind") == "road"]
    if len(roads) > 1:
        die("supply at most one 'road' element; it is tiled automatically")

    placed = []
    # Alternate sides so one frontage doesn't run away from the other, and so
    # the street never becomes a canyon with everything on one side.
    cursor = {-1: args.origin_x, 1: args.origin_x}
    side = -1
    for el in buildings:
        b = bounds[el["name"]]
        lo, hi = b["min"], b["max"]
        width = hi[0] - lo[0]
        pos_x = cursor[side] - lo[0]
        # front face on the facade line, body extending away from the road
        facade = side * (KERB_OUTER + SETBACK)
        pos_z = facade - (hi[2] if side < 0 else lo[2])
        placed.append((el, [round(pos_x, 3), 0, round(pos_z, 3)]))
        cursor[side] += width + BUILDING_GAP
        side = -side

    x_lo = args.origin_x
    x_hi = max(cursor.values()) - BUILDING_GAP
    if x_hi <= x_lo:
        x_hi = x_lo + 20.0

    # Props go on the strip between kerb and facade, spread over the frontage
    # and alternating sides.
    if props:
        step = (x_hi - x_lo) / (len(props) + 1)
        for i, el in enumerate(props):
            b = bounds[el["name"]]
            lo, hi = b["min"], b["max"]
            side_p = -1 if i % 2 == 0 else 1
            target_x = x_lo + step * (i + 1) + rng.uniform(-step * 0.15,
                                                           step * 0.15)
            pos_x = target_x - (lo[0] + hi[0]) / 2.0
            pos_z = side_p * STRIP_Z - (lo[2] + hi[2]) / 2.0
            placed.append((el, [round(pos_x, 3), 0, round(pos_z, 3)]))

    # Tile the road to span the whole frontage: a building facing bare ground
    # is the thing that makes a block look unfinished.
    if roads:
        proto = roads[0]
        b = bounds[proto["name"]]
        lo, hi = b["min"], b["max"]
        tile = hi[0] - lo[0]
        span_lo, span_hi = x_lo - BUILDING_GAP, x_hi + BUILDING_GAP
        n = max(1, int((span_hi - span_lo) / tile + 0.999))
        for i in range(n):
            clone = json.loads(json.dumps(proto))
            clone["name"] = f"{proto['name']}_{i + 1}"
            pos_x = span_lo + i * tile - lo[0]
            pos_z = -(lo[2] + hi[2]) / 2.0
            placed.append((clone, [round(pos_x, 3), 0, round(pos_z, 3)]))

    out = {"elements": []}
    for el, pos in placed:
        e = {k: v for k, v in el.items() if k != "kind"}
        e["position"] = pos
        out["elements"].append(e)
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1)

    print(f"packed {len(out['elements'])} elements "
          f"({len(buildings)} buildings, {len(props)} props, "
          f"{len(placed) - len(buildings) - len(props)} road tiles) "
          f"spanning x {x_lo:.1f} to {x_hi:.1f} m")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
