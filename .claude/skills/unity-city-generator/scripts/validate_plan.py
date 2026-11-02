#!/usr/bin/env python3
"""Check a generated plan BEFORE any design subagent is spawned.

Fanning out is the expensive step: N concurrent agents, each reading skills and
writing a spec. Every fault caught here costs nothing, and the same fault found
afterwards costs a whole round of agents. So this runs in between.

It checks two different kinds of thing:

  errors   - structural faults that would break the pipeline downstream
             (duplicate names, bad kinds, missing footprints, a name already
             taken in the scene). Exit 1; spawn nothing; fix the plan.
  warnings - quality faults that would produce a dull or unconvincing street
             (every building the same height, ideas too thin to design from,
             no props). Exit 0, but worth revising before spending agents.

  validate_plan.py city-runs/<run>/plan.json [--buildings N] [--props N] [--check-scene]
"""
import argparse, json, os, re, subprocess, sys

UNITY = os.environ.get("UNITY_CLI", "/Users/juan/.unity/bin/unity")
KINDS = {"building", "prop", "road"}
RESERVED = {"Main Camera", "Directional Light", "Global Volume"}


def scene_roots():
    """Existing root names, so a clash is caught now and not as `name_taken`
    after every agent has already run."""
    try:
        proc = subprocess.run(
            [UNITY, "--no-banner", "--non-interactive", "--json",
             "cmd", "scene.get_hierarchy"],
            capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
        if not data.get("success"):
            return None
        return {r["name"] for r in data["data"]["result"]["roots"]}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--buildings", type=int, default=None,
                    help="how many buildings the user asked for")
    ap.add_argument("--props", type=int, default=None)
    ap.add_argument("--check-scene", action="store_true",
                    help="also check names against the open scene")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    errors, warnings = [], []

    def err(code, msg):
        errors.append({"code": code, "message": msg})

    def warn(code, msg):
        warnings.append({"code": code, "message": msg})

    try:
        plan = json.load(open(args.plan))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read plan: {exc}", file=sys.stderr)
        return 2

    elements = plan.get("elements")
    if not isinstance(elements, list) or not elements:
        err("no_elements", "plan has no 'elements' list")
        elements = []

    if not plan.get("theme"):
        warn("no_theme", "no 'theme' recorded; designers lose the one piece of "
                         "shared context that keeps elements coherent")
    if not plan.get("palette"):
        warn("no_palette", "no 'palette' declared. Designers run concurrently "
                           "and cannot see each other, so each will invent its "
                           "own rust/soot/neon and the shared palette splits")

    seen, kinds = {}, {"building": [], "prop": [], "road": []}
    for i, el in enumerate(elements):
        label = el.get("name") or f"entry {i + 1}"
        name = el.get("name")
        if not name or not isinstance(name, str):
            err("missing_name", f"{label}: needs a 'name'")
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            err("bad_name", f"{name}: use letters, digits and underscores, "
                            f"starting with a letter (it becomes a GameObject)")
        if name in seen:
            err("duplicate_name", f"{name}: appears twice in the plan")
        seen[name] = True
        if name in RESERVED:
            err("reserved_name", f"{name}: collides with a default scene object")

        kind = el.get("kind")
        if kind not in KINDS:
            err("bad_kind", f"{name}: kind '{kind}' is not "
                            f"{', '.join(sorted(KINDS))}")
        else:
            kinds[kind].append(el)

        idea = (el.get("idea") or "").strip()
        if not idea:
            err("missing_idea", f"{name}: needs an 'idea' to design from")
        elif len(idea.split()) < 6:
            warn("thin_idea", f"{name}: the idea is {len(idea.split())} words. "
                              f"A designer given little produces little - say "
                              f"what it is made of and what state it is in")

        fp = el.get("footprint_m")
        if not (isinstance(fp, list) and len(fp) == 2
                and all(isinstance(v, (int, float)) and v > 0 for v in fp)):
            err("bad_footprint", f"{name}: footprint_m must be [width, depth] "
                                 f"in positive metres")
        h = el.get("height_m")
        if not (isinstance(h, (int, float)) and h > 0):
            err("bad_height", f"{name}: height_m must be a positive number")

    if len(kinds["road"]) > 1:
        err("many_roads",
            f"{len(kinds['road'])} road elements; supply exactly one tile "
            f"prototype, it is cloned to span the street")

    if args.check_scene:
        roots = scene_roots()
        if roots is None:
            warn("scene_unreadable", "could not read the scene to check names; "
                                     "a clash will surface later as name_taken")
        else:
            for name in seen:
                if name in roots:
                    err("name_taken", f"{name}: already exists in the scene; "
                                      f"rename it or plan to use --replace")

    nb, np_ = len(kinds["building"]), len(kinds["prop"])
    if args.buildings is not None and nb != args.buildings:
        err("wrong_building_count",
            f"{args.buildings} buildings were asked for, plan has {nb}")
    if args.props is not None and np_ != args.props:
        err("wrong_prop_count",
            f"{args.props} props were asked for, plan has {np_}")

    # --- quality: the things that make a street dull rather than broken ---
    if not kinds["road"]:
        warn("no_road", "no road element; buildings will face bare ground")
    if nb and np_ == 0:
        warn("no_props", "no props. Lights, benches, bins and trees are what "
                         "make a street look inhabited rather than modelled")
    elif nb and np_ < nb / 2:
        warn("few_props", f"{np_} props for {nb} buildings reads as sparse; "
                          f"aim for roughly one per building")

    heights = [el["height_m"] for el in kinds["building"]
               if isinstance(el.get("height_m"), (int, float))]
    if len(heights) >= 3:
        lo, hi = min(heights), max(heights)
        if hi / max(lo, 0.1) < 1.6:
            warn("flat_skyline",
                 f"every building is {lo:g}-{hi:g} m. A row of equal heights "
                 f"reads as a wall; mix something low with something tall")
        if not any(h < 8 for h in heights):
            warn("nothing_small", "nothing under 8 m to give the street scale")
        if not any(h > 20 for h in heights):
            warn("nothing_tall", "nothing over 20 m to give the street a skyline")

    ideas = [(el.get("name"), (el.get("idea") or "").lower())
             for el in kinds["building"]]
    for i in range(len(ideas)):
        for j in range(i + 1, len(ideas)):
            a, b = set(ideas[i][1].split()), set(ideas[j][1].split())
            if a and b and len(a & b) / len(a | b) > 0.5:
                warn("similar_ideas",
                     f"{ideas[i][0]} and {ideas[j][0]} describe much the same "
                     f"building; vary use, era or material")

    out = {"ok": not errors, "buildings": nb, "props": np_,
           "roads": len(kinds["road"]), "errors": errors, "warnings": warnings}
    if args.as_json:
        print(json.dumps(out, indent=2))
    else:
        for e in errors:
            print(f"REJECTED [{e['code']}] {e['message']}", file=sys.stderr)
        for w in warnings:
            print(f"warning  [{w['code']}] {w['message']}", file=sys.stderr)
        if not errors:
            print(f"plan ok: {nb} buildings, {np_} props, "
                  f"{len(kinds['road'])} road"
                  + (f", {len(warnings)} warning(s) to consider"
                     if warnings else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
