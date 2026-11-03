#!/usr/bin/env python3
"""The brief one designer process receives. Owned by the loop, not the designer.

The loop is the only piece that knows all three others, so it is the loop that
tells a designer the builder's contract and where to write. The designer itself
knows nothing: it is handed a command, not a collaborator.

The contract travels INLINED. Measured on a 95-agent run, designers re-read a
SKILL.md 115 times between them despite never being told to, roughly a third of
all their API calls spent re-acquiring context the brief could have carried.
"""
import argparse, functools, os, subprocess, sys

BUILDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "factory-city-element", "scripts",
    "build_element.py")


@functools.lru_cache(maxsize=4)
def contract(builder_path):
    """The builder's own contract text, asked of the builder itself.

    Read from the builder rather than copied here, so the two can never drift;
    cached, so N designers cost one subprocess. The 'position' line is dropped:
    the designer must not emit one, and the loop stamps it afterwards.
    """
    text = subprocess.run([sys.executable, builder_path, "--schema"],
                          capture_output=True, text=True, check=True).stdout
    return "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith('"position"'))


BRIEF = """Design ONE building for a Unity city builder and write it to {out_path}.

Idea: {idea}
Target footprint: {w} x {d} m, height about {h} m

Theme: {theme}
Palette - use these exact role names and hex values. Invent a new role only for
something they genuinely lack, and name it for the material, not the object:
{palette}

Do NOT read any skill file and do NOT fetch a schema. The contract is here:

<contract>
{contract}
</contract>

Rules that cause refusals, so design around them:
- A part is one primitive with one colour. Split on material boundaries.
- `size` is real metres; `at` is the centre of the part's BOTTOM face.
  Anything rotated must use `center` instead of `at`.
- Primitives are SOLID. A part placed inside another is invisible and will be
  refused. Build hollows by implication and keep detail proud of its host.
- Nothing below y=0 unless a buried footing is meant (`"below_ground": true`).
- Offset coincident surfaces by ~0.02 or they flicker.
- A rotated part's bounding box is larger than it looks and can swallow a
  neighbour. If something is refused as hidden, move it clear rather than
  shrinking it.

Write ONE JSON object with exactly these keys: name (exactly "{name}"),
materials, parts. Do NOT include a placement key - that is assigned elsewhere.
Keep to at most {max_parts} parts.

Verify ONCE with:
  UNITY_CLI=/nonexistent python3 {builder} {out_path} --dry-run
and fix anything it refuses. Then report only the path and the part count.
"""


def build_brief(entry, theme, palette, out_path, builder_path, max_parts=28):
    w, d = entry["footprint_m"]
    return BRIEF.format(
        out_path=out_path, idea=entry["idea"], w=w, d=d, h=entry["height_m"],
        theme=theme, name=entry["name"], max_parts=max_parts,
        builder=builder_path, contract=contract(builder_path),
        palette="\n".join(f'  "{k}": "{v}"' for k, v in sorted(palette.items())))


# --------------------------------------------------------------------------


def selftest():
    b = build_brief({"name": "Lonja",
                     "idea": "lonja de pescado de una planta, hormigon encalado",
                     "footprint_m": [22, 14], "height_m": 7},
                    theme="puerto 50s", palette={"Rust": "#8A5236FF"},
                    out_path="/r/designed/Lonja.json", builder_path=BUILDER)
    assert "Lonja" in b and "22" in b and "#8A5236FF" in b, b
    assert "puerto 50s" in b
    assert "INPUT CONTRACT" in b, b
    assert "part_hidden_inside" in b, b          # refusals travel too
    assert "/r/designed/Lonja.json" in b
    assert "SKILL.md" not in b                   # no agent is sent to read one
    assert "--schema" not in b                   # nor to fetch the schema
    assert "factory-city-element" in b           # isolation: the forked builder
    assert '"position"' not in b                 # placement is not the designer's
    assert "--dry-run" in b                      # but self-checking is
    print("ok: brief selftest passed (10 checks)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    ap.error("--selftest is the only thing to run here; the loop imports this")


if __name__ == "__main__":
    sys.exit(main())
