#!/usr/bin/env python3
"""Build primitive city elements in Unity from a JSON spec.

This is a driver, not a designer: it takes a complete description of what to
build and makes Unity build it correctly. It decides nothing about shape,
proportion or colour -- that is the caller's job. What it owns is the part that
is mechanical and easy to get silently wrong: pivot arithmetic, URP material
assets, batched Editor calls, and refusing specs that would produce invisible
or buried geometry.

  build_element.py --schema            print the full input contract
  build_element.py spec.json [flags]   validate, then build

Flags:
  --dry-run        validate and report placements; never touches the Editor
  --json           emit one machine-readable JSON object (for agent callers)
  --replace        delete an existing element of the same name before building
  --preview [path] screenshot the result; default Assets/Screenshots/<name>.png
  --save           save the scene afterwards (otherwise it stays in-memory)
"""
import argparse, json, math, os, subprocess, sys

UNITY = os.environ.get("UNITY_CLI", "/Users/juan/.unity/bin/unity")
PALETTE_DIR = "CityKit/Materials"   # under the authoring root (Assets)
MAX_OPS = 180                       # CLI caps a batch at 200; leave headroom
EPS = 1e-4

# Native world size of each primitive at scale 1, in Unity units.
NATIVE = {
    "cube":     (1.0, 1.0, 1.0),
    "sphere":   (1.0, 1.0, 1.0),
    "cylinder": (1.0, 2.0, 1.0),   # two units tall, not one
    "capsule":  (1.0, 2.0, 1.0),   # the hemisphere caps are inside that 2
    "plane":    (10.0, 1.0, 10.0), # 10x10, flat; scaling y does nothing
    "quad":     (1.0, 1.0, 1.0),   # flat in XY, faces -Z
}

SCHEMA = """INPUT CONTRACT -- build_element.py

One element:
{
  "name": "OfficeTower",              required, unique among scene roots
  "position": [x, 0, z],              where the element's BASE sits. y must be >= 0.
  "materials": {"Concrete": "#A8A49BFF", "Glass": "#5B86A6FF"},
                                      role name -> hex #RRGGBBAA. Every material
                                      a part names must appear here.
  "parts": [ ...  ]                   at least one
}

Several elements in one call -- same format, wrapped:
{ "elements": [ {...}, {...} ] }

A part:
{
  "name": "TowerBody",                becomes the GameObject name
  "primitive": "cube",                cube|sphere|cylinder|capsule|plane|quad
  "material": "Concrete",             must be a key of "materials"
  "size": [x, y, z],                  REAL WORLD METRES, not a scale factor
  "at": [x, y, z],                    centre of the part's BOTTOM face, in
                                      element-local space. at:[0,0,0] = on the ground.
  "center": [x, y, z],                alternative to "at": the pivot centre
                                      directly. Use for rotated parts.
  "rotation": [x, y, z],              optional Euler degrees
  "below_ground": true                optional; permits this part to sit below y=0
}

Sizes are world metres. The script converts to Unity's centred pivots and
native primitive sizes itself -- never pre-divide a cylinder's height by 2.

REFUSES to build (nothing is created):
  unknown_primitive      primitive is not one of the six
  undefined_material     part names a material absent from "materials"
  bad_size               a size component is <= 0
  part_below_ground      part dips under y=0 without "below_ground": true
  part_hidden_inside     part lies entirely inside another and would be invisible
                         (primitives are solid; nothing nested in one can be seen)
  name_taken             a scene root already has this name; pass --replace
  origin_below_ground    element position y < 0
  duplicate_name         two elements in the spec share a name

WARNS but builds:
  origin_raised          element position y > 0, so it floats off the ground
  coplanar_faces         two same-facing surfaces share a plane and will flicker
                         (not checked for rotated parts, whose bounding box is
                         not their real surface)
  elements_overlap       two elements in the spec intrude on each other
  material_color_ignored the .mat already exists, so its current colour is kept
                         (the palette is shared; restyling it would repaint every
                         element already using it)

Materials land in Assets/CityKit/Materials/<role>.mat on URP/Lit (_BaseColor).
An existing one is reused as-is, never overwritten.
"""


class SpecError(Exception):
    pass


# ---------------------------------------------------------------- CLI plumbing

def unity(command, params, timeout=180):
    args = [UNITY, "--no-banner", "--non-interactive", "--json", "cmd", command]
    for k, v in params.items():
        args += [f"--{k}", v if isinstance(v, str) else json.dumps(v)]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SpecError(f"{command}: unreadable CLI output: "
                        f"{(proc.stdout or proc.stderr)[:300]}")
    if not payload.get("success"):
        raise SpecError(f"{command}: {json.dumps(payload.get('errors'))}")
    return (payload.get("data") or {}).get("result", {})


def preflight():
    """An Editor that isn't ready turns every later call into noise, so check once."""
    proc = subprocess.run(
        [UNITY, "--no-banner", "--non-interactive", "--json", "status"],
        capture_output=True, text=True, timeout=30)
    try:
        instances = json.loads(proc.stdout)["data"]["instances"]
    except Exception:
        raise SpecError("no Unity Editor reachable; open the project and retry")
    ready = [i for i in instances if i.get("state") == "ready"]
    if not ready:
        raise SpecError(f"Editor not ready (state: "
                        f"{[i.get('state') for i in instances]}); "
                        f"it may be compiling or in play mode")
    roots = unity("scene.get_hierarchy", {}).get("roots", [])
    return ready[0]["project"], {r["name"]: r["instanceId"] for r in roots}


# ------------------------------------------------------------------- geometry

def place(part):
    """World-space size + ground-anchored position -> Unity's centred-pivot
    localPosition and localScale."""
    prim = part["primitive"]
    size = [float(v) for v in part["size"]]
    nx, ny, nz = NATIVE[prim]
    scale = [size[0] / nx, size[1] / ny, size[2] / nz]
    if prim == "plane":
        scale[1] = 1.0
    if "center" in part:
        pos = [float(v) for v in part["center"]]
    else:
        at = [float(v) for v in part.get("at", [0, 0, 0])]
        lift = 0.0 if prim == "plane" else size[1] / 2.0
        pos = [at[0], at[1] + lift, at[2]]
    return pos, scale


def _rot_matrix(euler_deg):
    """Unity composes Euler angles as Y * X * Z."""
    x, y, z = (math.radians(float(a)) for a in euler_deg)
    cx, sx, cy, sy, cz, sz = (math.cos(x), math.sin(x), math.cos(y),
                              math.sin(y), math.cos(z), math.sin(z))
    rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    def mul(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                           for j in range(3)) for i in range(3))
    return mul(mul(ry, rx), rz)


def aabb(part, pos, scale, origin):
    """Axis-aligned bounds in world space. Rotated parts get the true rotated
    box bounds, so the ground and containment checks stay trustworthy."""
    prim = part["primitive"]
    half = [abs(scale[i] * NATIVE[prim][i]) / 2.0 for i in range(3)]
    if prim == "plane":
        half[1] = 0.0
    centre = [origin[i] + pos[i] for i in range(3)]
    rot = part.get("rotation")
    if rot and any(abs(float(r)) > EPS for r in rot):
        m = _rot_matrix(rot)
        ext = [sum(abs(m[i][j]) * half[j] for j in range(3)) for i in range(3)]
        half = ext
    return ([centre[i] - half[i] for i in range(3)],
            [centre[i] + half[i] for i in range(3)])


def contains(outer, inner):
    lo_o, hi_o = outer
    lo_i, hi_i = inner
    return all(lo_i[i] >= lo_o[i] - EPS and hi_i[i] <= hi_o[i] + EPS
               for i in range(3))


def coplanar(a, b):
    """Two same-facing surfaces sharing a plane -- the z-fighting case. Boxes
    merely stacked face to face (one's top at the other's bottom) are normal
    and deliberately not reported."""
    lo_a, hi_a = a
    lo_b, hi_b = b
    for i in range(3):
        others = [j for j in range(3) if j != i]
        if not all(min(hi_a[j], hi_b[j]) - max(lo_a[j], lo_b[j]) > EPS
                   for j in others):
            continue
        if abs(hi_a[i] - hi_b[i]) < EPS:
            return True
        # Coincident *bottom* faces on Y are the normal case, not a defect:
        # every part of a grounded element rests on the same plane. Downward
        # faces are never seen in a city blockout, so flagging them would bury
        # the top and side coincidences that do flicker.
        if i != 1 and abs(lo_a[i] - lo_b[i]) < EPS:
            return True
    return False


# ------------------------------------------------------------------ validation

def normalise(spec):
    elements = spec["elements"] if isinstance(spec, dict) and "elements" in spec \
        else [spec]
    if not isinstance(elements, list) or not elements:
        raise SpecError("spec must be one element object, or {'elements': [...]}")
    return elements


def validate(elements, existing_roots, replace):
    """Resolve every placement and collect every problem before touching Unity,
    so a bad spec costs nothing and the caller gets the whole list at once
    rather than discovering faults one rebuild at a time."""
    errors, warnings, resolved = [], [], []
    seen_names = set()

    def err(code, msg):
        errors.append({"code": code, "message": msg})

    for el in elements:
        name = el.get("name")
        if not name:
            err("missing_name", "an element has no 'name'")
            continue
        if name in seen_names:
            err("duplicate_name", f"'{name}' appears twice in this spec")
        seen_names.add(name)
        if name in existing_roots and not replace:
            err("name_taken", f"scene root '{name}' already exists; "
                              f"pass --replace to rebuild it")

        origin = [float(v) for v in el.get("position", [0, 0, 0])]
        if origin[1] < -EPS:
            err("origin_below_ground",
                f"'{name}' position y={origin[1]} is below the ground plane")
        elif origin[1] > EPS:
            warnings.append({"code": "origin_raised",
                             "message": f"'{name}' position y={origin[1]}: it will "
                                        f"float rather than rest on the ground"})

        materials = el.get("materials") or el.get("palette") or {}
        parts = el.get("parts") or []
        if not parts:
            err("no_parts", f"'{name}' has no parts")
            continue

        placements = []
        for part in parts:
            label = f"{name}/{part.get('name', '?')}"
            prim = part.get("primitive")
            if prim not in NATIVE:
                err("unknown_primitive",
                    f"{label}: '{prim}' is not one of {', '.join(NATIVE)}")
                continue
            size = part.get("size")
            if not size or len(size) != 3 or any(float(v) <= 0 for v in size):
                err("bad_size", f"{label}: size must be three positive numbers")
                continue
            role = part.get("material")
            if role and role not in materials:
                err("undefined_material",
                    f"{label}: material '{role}' is not declared in 'materials'")
            pos, scale = place(part)
            box = aabb(part, pos, scale, origin)
            if box[0][1] < -1e-3 and not part.get("below_ground"):
                err("part_below_ground",
                    f"{label}: reaches y={box[0][1]:.3f}, under the ground plane; "
                    f"raise it or set \"below_ground\": true")
            placements.append((part, pos, scale, box))

        for i, (pa, _, _, ba) in enumerate(placements):
            for j, (pb, _, _, bb) in enumerate(placements):
                if i == j:
                    continue
                if contains(bb, ba):
                    err("part_hidden_inside",
                        f"{name}/{pa.get('name','?')} lies entirely inside "
                        f"{name}/{pb.get('name','?')} and would be invisible; "
                        f"primitives are solid, so move it clear of that surface")
                elif (i < j and not pa.get("rotation") and not pb.get("rotation")
                      and coplanar(ba, bb)):
                    warnings.append({
                        "code": "coplanar_faces",
                        "message": f"{name}/{pa.get('name','?')} and "
                                   f"{name}/{pb.get('name','?')} share a surface "
                                   f"plane and may flicker; offset one by ~0.02"})
        resolved.append({"name": name, "origin": origin,
                         "materials": materials, "placements": placements})

    # Elements that intrude on each other are usually a layout slip, but not
    # always -- a bench against a wall is fine -- so this warns rather than
    # refuses. Nothing else checks it: part containment is per element.
    for i in range(len(resolved)):
        for j in range(i + 1, len(resolved)):
            a, b = resolved[i], resolved[j]
            if not a["placements"] or not b["placements"]:
                continue
            boxes = []
            for el in (a, b):
                boxes.append((
                    [min(p[3][0][k] for p in el["placements"]) for k in range(3)],
                    [max(p[3][1][k] for p in el["placements"]) for k in range(3)]))
            overlap = [min(boxes[0][1][k], boxes[1][1][k])
                       - max(boxes[0][0][k], boxes[1][0][k]) for k in range(3)]
            if all(o > 1e-3 for o in overlap):
                warnings.append({
                    "code": "elements_overlap",
                    "message": f"'{a['name']}' and '{b['name']}' overlap by "
                               f"{overlap[0]:.2f} x {overlap[1]:.2f} x "
                               f"{overlap[2]:.2f} m; space them apart unless "
                               f"that is deliberate"})
    return resolved, errors, warnings


# ------------------------------------------------------------------- building

def _hex_to_rgba(value):
    h = str(value).lstrip("#")
    if len(h) == 6:
        h += "FF"
    if len(h) != 8:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
    except ValueError:
        return None


def _existing_colour(path):
    """Read _BaseColor straight out of the .mat YAML.

    Reading the file beats asking the Editor: it is one open() instead of a
    round trip, and it runs before we have touched Unity at all."""
    try:
        with open(path) as fh:
            for line in fh:
                if "_BaseColor:" in line and "{" in line:
                    body = line[line.index("{") + 1:line.rindex("}")]
                    vals = {}
                    for pair in body.split(","):
                        k, _, v = pair.partition(":")
                        vals[k.strip()] = float(v)
                    return (vals.get("r", 0), vals.get("g", 0),
                            vals.get("b", 0), vals.get("a", 1))
    except (OSError, ValueError):
        pass
    return None


def material_path(role):
    return f"Assets/{PALETTE_DIR}/{role}.mat"


def ensure_materials(resolved, project_root):
    """Create only the palette entries that don't exist yet. An existing one is
    reused untouched: the palette is shared across the whole city, so silently
    restyling it would repaint every element already built from it."""
    wanted = {}
    for el in resolved:
        for role, colour in el["materials"].items():
            wanted.setdefault(role, colour)
    created, reused, ignored = [], [], []
    ops = []
    for role, colour in wanted.items():
        disk = os.path.join(project_root, material_path(role))
        if os.path.exists(disk):
            reused.append(role)
            # Only flag it when the caller actually asked for a different
            # colour. Reuse is the normal, desired case; warning every time
            # would bury the one occasion that matters.
            want = _hex_to_rgba(colour)
            have = _existing_colour(disk)
            if want and have and any(abs(want[i] - have[i]) > 0.004
                                     for i in range(4)):
                ignored.append(role)
            continue
        created.append(role)
        i = len(ops)
        ops.append({"id": f"c{i}", "command": "asset create", "params": {
            "path": f"{PALETTE_DIR}/{role}.mat", "type": "UnityEngine.Material",
            "shader": "Universal Render Pipeline/Lit"}})
        ops.append({"id": f"p{i}", "command": "material set_properties", "params": {
            "material": {"path": material_path(role)},
            "properties": {"_BaseColor": colour}}})
    if ops:
        # Asset writes live outside the Editor's Undo system, so the CLI rejects
        # them inside a transactional batch.
        unity("job.batch", {"transactional": "false", "operations": ops})
    return created, reused, ignored


def build(resolved, existing_roots, replace):
    calls = 0
    built = []
    for el in resolved:
        name = el["name"]
        if replace and name in existing_roots:
            unity("gameobject.delete", {"target": f"/{name}"})
            calls += 1
        root = unity("gameobject.create", {"name": name})
        unity("gameobject.set_transform",
              {"target": {"instanceId": root["instanceId"]},
               "position": el["origin"]})
        calls += 2

        ops = []
        for i, (part, pos, scale, _) in enumerate(el["placements"]):
            pid = f"g{i}"
            ops.append({"id": pid, "command": "gameobject create", "params": {
                "name": part.get("name", f"{part['primitive']}_{i}"),
                "primitive": part["primitive"],
                "parent": {"instanceId": root["instanceId"]}}})
            t = {"target": {"instanceId": f"${pid}.instanceId"},
                 "position": pos, "scale": scale}
            if part.get("rotation"):
                t["rotation"] = [float(v) for v in part["rotation"]]
            ops.append({"id": f"t{i}", "command": "gameobject set_transform",
                        "params": t})
            if part.get("material"):
                ops.append({"id": f"m{i}", "command": "component set_field",
                            "params": {
                                "target": {"instanceId": f"${pid}.instanceId"},
                                "component": "MeshRenderer",
                                "field": "m_Materials.Array.data[0]",
                                "value": {"path": material_path(part["material"])}}})

        # Chunk on part boundaries: splitting between a `create` and the $ref
        # that depends on it would break the reference.
        chunks, cur = [], []
        for op in ops:
            if op["id"].startswith("g") and len(cur) + 3 > MAX_OPS:
                chunks.append(cur)
                cur = []
            cur.append(op)
        if cur:
            chunks.append(cur)

        for chunk in chunks:
            res = unity("job.batch", {"operations": chunk, "timeout": 120})
            calls += 1
            failed = [r for r in res.get("results", []) if not r.get("success")]
            if failed:
                raise SpecError("; ".join(f"{r['id']}: {r.get('error')}"
                                          for r in failed[:5]))
        lo = [min(p[3][0][i] for p in el["placements"]) for i in range(3)]
        hi = [max(p[3][1][i] for p in el["placements"]) for i in range(3)]
        built.append({"name": name, "hierarchyPath": root["hierarchyPath"],
                      "parts": len(el["placements"]),
                      "bounds": {"min": [round(v, 3) for v in lo],
                                 "max": [round(v, 3) for v in hi]}})
    return built, calls


def preview(built, out_path, width=1100, height=800, elevation=None):
    """Frame everything just built and screenshot it.

    Selecting the root and using 'Frame Selected' aims at the root pivot, which
    for a ground-anchored element sits at its feet -- the camera ends up inside
    the geometry. We know the real bounds, so we can place a camera that sees
    the whole thing, and delete it again (a stray camera left behind silently
    hijacks rendering for whoever opens the project next)."""
    lo = [min(b["bounds"]["min"][i] for b in built) for i in range(3)]
    hi = [max(b["bounds"]["max"][i] for b in built) for i in range(3)]
    centre = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    radius = max(math.dist(hi, lo) / 2.0, 0.5)
    dist = radius / math.tan(math.radians(30.0)) * 1.25  # 60 deg vertical FOV
    if elevation is None:
        # A low angle flatters a single element: you are judging whether it
        # reads as the thing. Across a layout the nearest buildings simply hide
        # everything behind them at any oblique angle, and the question being
        # asked is different -- spacing and placement -- so a near plan view
        # answers it with no occlusion at all. Override with --preview-angle
        # when you want a street-level look at a layout.
        elevation = 18.0 if len(built) == 1 else 72.0
    az, el_ = math.radians(35.0), math.radians(float(elevation))
    cam = [centre[0] + dist * math.sin(az) * math.cos(el_),
           centre[1] + dist * math.sin(el_),
           centre[2] - dist * math.cos(az) * math.cos(el_)]
    d = [centre[i] - cam[i] for i in range(3)]
    name = "_PreviewCam"
    unity("gameobject.create", {"name": name})
    try:
        unity("component.add", {"target": f"/{name}", "type": "Camera"})
        unity("gameobject.set_transform", {
            "target": f"/{name}", "position": cam,
            "rotation": [math.degrees(math.atan2(-d[1], math.hypot(d[0], d[2]))),
                         math.degrees(math.atan2(d[0], d[2])), 0]})
        res = unity("capture.game_view", {"width": width, "height": height,
                                          "camera": name, "save_path": out_path})
    finally:
        unity("gameobject.delete", {"target": f"/{name}"})
    return res.get("savedPath", out_path)


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--schema", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", dest="as_json", action="store_true")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--preview", nargs="?", const="", default=None)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--preview-angle", type=float, default=None,
                    help="camera elevation in degrees; default 18 for a single "
                         "element, 72 (near plan view) for a layout")
    args = ap.parse_args()

    if args.schema:
        print(SCHEMA)
        return 0
    if not args.spec:
        ap.error("a spec file is required (or --schema)")

    out = {"ok": False, "elements": [], "materials": {}, "warnings": [],
           "errors": [], "preview": None, "saved": False, "calls": 0}

    def finish(code):
        if args.as_json:
            print(json.dumps(out, indent=2))
        else:
            for e in out["errors"]:
                print(f"REFUSED [{e['code']}] {e['message']}", file=sys.stderr)
            for w in out["warnings"]:
                print(f"warning [{w['code']}] {w['message']}", file=sys.stderr)
            for b in out["elements"]:
                print(f"built {b['hierarchyPath']}  {b['parts']} parts  "
                      f"bounds {b['bounds']['min']} -> {b['bounds']['max']}")
            m = out["materials"]
            if m.get("created"):
                print(f"materials created: {', '.join(m['created'])}")
            if m.get("reused"):
                print(f"materials reused:  {', '.join(m['reused'])}")
            if out["preview"]:
                print(f"preview: {out['preview']}  <- open it and check it reads right")
            if out["elements"] and not out["saved"]:
                print("scene is dirty; pass --save to persist it")
        return code

    try:
        with open(args.spec) as f:
            spec = json.load(f)
        elements = normalise(spec)
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        out["errors"].append({"code": "bad_spec", "message": str(exc)})
        return finish(2)

    existing = {}
    project_root = None
    if not args.dry_run:
        try:
            project_root, existing = preflight()
        except SpecError as exc:
            out["errors"].append({"code": "editor_unavailable", "message": str(exc)})
            return finish(3)

    resolved, errors, warnings = validate(elements, existing, args.replace)
    out["errors"], out["warnings"] = errors, warnings
    if errors:
        return finish(1)

    if args.dry_run:
        out["ok"] = True
        for el in resolved:
            lo = [min(p[3][0][i] for p in el["placements"]) for i in range(3)]
            hi = [max(p[3][1][i] for p in el["placements"]) for i in range(3)]
            out["elements"].append({
                "name": el["name"], "hierarchyPath": f"/{el['name']}",
                "parts": len(el["placements"]),
                "bounds": {"min": [round(v, 3) for v in lo],
                           "max": [round(v, 3) for v in hi]},
                "placements": [
                    {"name": p[0].get("name"), "primitive": p[0]["primitive"],
                     "position": [round(v, 4) for v in p[1]],
                     "scale": [round(v, 4) for v in p[2]]}
                    for p in el["placements"]]})
        if not args.as_json:
            for el in out["elements"]:
                for p in el["placements"]:
                    print(f"{el['name']}/{p['name']:<18} {p['primitive']:<9} "
                          f"pos={p['position']} scale={p['scale']}")
        return finish(0)

    try:
        created, reused, ignored = ensure_materials(resolved, project_root)
        out["materials"] = {"created": created, "reused": reused}
        for role in ignored:
            out["warnings"].append({
                "code": "material_color_ignored",
                "message": f"'{role}' already exists with a different colour and "
                           f"keeps the one it has; rename the role "
                           f"(e.g. '{role}Dark') if you need a new shade"})
        built, calls = build(resolved, existing, args.replace)
        out["elements"], out["calls"] = built, calls
        if args.preview is not None:
            path = args.preview or f"Screenshots/{built[0]['name']}.png"
            out["preview"] = preview(built, path,
                                     elevation=args.preview_angle)
            out["calls"] += 4
        if args.save:
            unity("scene.save", {})
            out["saved"] = True
            out["calls"] += 1
    except SpecError as exc:
        out["errors"].append({"code": "build_failed", "message": str(exc)})
        return finish(4)

    out["ok"] = True
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
