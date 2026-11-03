#!/usr/bin/env python3
"""Validate a plan of building ideas before anything is spent on designing them.

A fault found here costs nothing. The same fault found after the designers have
run costs a whole round of them, so this runs every time, with no exceptions.

    validate_plan.py plan.json --buildings 10 [--json]
    validate_plan.py --selftest

Exit 0 when clean, 1 on any error. Warnings never fail the run; they are about
whether the street will be any good, which is a judgement, not a fault.
"""
import argparse, json, re, sys

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
THIN_IDEA_CHARS = 40


def check(plan, buildings):
    """Return {"ok", "buildings", "errors", "warnings"}; never raises on content."""
    errors, warnings = [], []

    def err(code, msg):
        errors.append({"code": code, "message": msg})

    def warn(code, msg):
        warnings.append({"code": code, "message": msg})

    elements = plan.get("elements") or []
    if not isinstance(elements, list) or not elements:
        err("no_elements", "plan has no 'elements' list")
        return {"ok": False, "buildings": 0, "errors": errors, "warnings": warnings}

    seen, heights = set(), []
    for i, e in enumerate(elements):
        name = e.get("name")
        where = name if isinstance(name, str) and name else f"element #{i}"
        if not isinstance(name, str) or not NAME_RE.match(name):
            # The loop writes agents/<name>.jsonl, so a name with a separator
            # or a dot-dot is a path traversal, not just untidy.
            err("bad_name", f"{where}: names must match [A-Za-z][A-Za-z0-9_]*")
        elif name in seen:
            err("duplicate_name", f"{name}: used more than once")
        else:
            seen.add(name)

        if e.get("kind") != "building":
            err("bad_kind", f"{where}: kind is {e.get('kind')!r}; "
                            f"'building' is the only kind")

        idea = e.get("idea")
        if not isinstance(idea, str) or not idea.strip():
            err("missing_idea", f"{where}: no idea to design from")
        elif len(idea.strip()) < THIN_IDEA_CHARS:
            warn("thin_idea", f"{where}: a designer given {len(idea.strip())} "
                              f"characters produces that much building")

        fp = e.get("footprint_m")
        if (not isinstance(fp, list) or len(fp) != 2
                or not all(isinstance(v, (int, float)) and v > 0 for v in fp)):
            err("missing_footprint", f"{where}: footprint_m must be two "
                                     f"positive numbers")

        h = e.get("height_m")
        if isinstance(h, (int, float)) and h > 0:
            heights.append(float(h))
        else:
            err("missing_height", f"{where}: height_m must be a positive number")

    if len(elements) != buildings:
        err("count_mismatch",
            f"{len(elements)} elements but {buildings} buildings were asked for")

    if not plan.get("palette"):
        warn("no_palette", "no shared palette; designers run blind to each "
                           "other and will invent three different rusts")

    if len(heights) > 1 and (len(set(heights)) < 2
                             or max(heights) / min(heights) < 1.5):
        warn("flat_skyline", "every building is about the same height; that "
                             "reads as a wall, not a street")

    return {"ok": not errors, "buildings": len(elements),
            "errors": errors, "warnings": warnings}


# --------------------------------------------------------------------------


def _plan(elements, palette=True, theme="a street"):
    p = {"theme": theme, "elements": elements}
    if palette:
        p["palette"] = {"Rust": "#8A5236FF"}
    return p


def _b(name, idea="a four-storey brick warehouse with loading bays and a "
                  "painted sign", footprint=(18, 12), height=14, kind="building"):
    e = {"name": name, "kind": kind, "idea": idea, "height_m": height}
    if footprint is not None:
        e["footprint_m"] = list(footprint)
    return e


def _codes(out, key="errors"):
    return [e["code"] for e in out[key]]


def selftest():
    assert "duplicate_name" in _codes(check(_plan([_b("A"), _b("A")]), 2))
    assert "bad_name" in _codes(check(_plan([_b("a/b")]), 1))
    assert "bad_name" in _codes(check(_plan([_b("..")]), 1))
    assert "bad_kind" in _codes(check(_plan([_b("A", kind="prop")]), 1))
    assert "bad_kind" in _codes(check(_plan([_b("A", kind="road")]), 1))
    assert "missing_footprint" in _codes(check(_plan([_b("A", footprint=None)]), 1))
    assert "missing_footprint" in _codes(check(_plan([_b("A", footprint=(0, 12))]), 1))
    assert "missing_idea" in _codes(check(_plan([_b("A", idea="")]), 1))
    assert "count_mismatch" in _codes(check(_plan([_b("A"), _b("B"), _b("C")]), 10))

    assert "no_palette" in _codes(check(_plan([_b("A")], palette=False), 1), "warnings")
    assert "thin_idea" in _codes(check(_plan([_b("A", idea="a shop")]), 1), "warnings")
    flat = _plan([_b("A", height=12), _b("B", height=12), _b("C", height=12)])
    assert "flat_skyline" in _codes(check(flat, 3), "warnings")

    good = _plan([_b("Lonja", height=7), _b("Almacen", height=22)])
    out = check(good, 2)
    assert out["ok"] and out["errors"] == [] and out["buildings"] == 2, out
    assert "flat_skyline" not in _codes(out, "warnings"), out

    print("ok: plan validator selftest passed (14 checks)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?")
    ap.add_argument("--buildings", type=int, default=10)
    ap.add_argument("--json", dest="as_json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return 0
    if not a.plan:
        ap.error("a plan file is required (or --selftest)")

    try:
        with open(a.plan) as f:
            out = check(json.load(f), a.buildings)
    except (OSError, json.JSONDecodeError) as exc:
        out = {"ok": False, "buildings": 0,
               "errors": [{"code": "bad_plan", "message": str(exc)}],
               "warnings": []}

    if a.as_json:
        print(json.dumps(out, indent=2))
    else:
        for e in out["errors"]:
            print(f"ERROR   [{e['code']}] {e['message']}", file=sys.stderr)
        for w in out["warnings"]:
            print(f"warning [{w['code']}] {w['message']}", file=sys.stderr)
        if out["ok"]:
            print(f"{out['buildings']} buildings, plan is clean")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
