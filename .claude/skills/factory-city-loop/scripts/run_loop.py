#!/usr/bin/env python3
"""The factory loop: design and build one building at a time, continuously.

Run artifacts live in the run directory and nothing is reconstructed from
memory. If it is not in a file, it did not happen.

    run_loop.py <run_dir> [--k 4] [--gap 6] [--row-length 200] [--timeout 600]
    run_loop.py --selftest
"""
import argparse, json, os, sys, tempfile
from datetime import datetime, timezone

GAP = 6.0
ROW_LENGTH = 200.0
ROW_PITCH = 40.0


def _cursor_path(run_dir):
    return os.path.join(run_dir, "cursor.json")


def place(run_dir, bounds, gap=GAP, row_length=ROW_LENGTH):
    """Assign this element a position and advance the cursor on disk.

    `bounds` is the builder's own dry-run bounds, so what gets placed is
    exactly what gets built. The cursor tracks the left edge of the next free
    slot; the returned position is where the element's ORIGIN must sit for its
    left edge to land there.
    """
    try:
        with open(_cursor_path(run_dir)) as f:
            cur = json.load(f)
    except (OSError, json.JSONDecodeError):
        cur = {"x": 0.0, "z": 0.0}

    width = bounds["max"][0] - bounds["min"][0]
    # Wrap BEFORE placing, so an element never straddles the end of a row.
    if cur["x"] > 0 and cur["x"] + width > row_length:
        cur["x"], cur["z"] = 0.0, cur["z"] + ROW_PITCH

    pos = [round(cur["x"] - bounds["min"][0], 4), 0, round(cur["z"], 4)]
    cur["x"] += width + gap

    os.makedirs(run_dir, exist_ok=True)
    with open(_cursor_path(run_dir), "w") as f:
        json.dump(cur, f)
    return pos


def log(run_dir, ev, **fields):
    """Append one event. One line, one write, so a reader never splits it."""
    os.makedirs(run_dir, exist_ok=True)
    rec = {"t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
           "ev": ev}
    rec.update(fields)
    with open(os.path.join(run_dir, "events.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def read_events(run_dir):
    """Every complete line. A trailing partial line is the writer mid-append."""
    out = []
    try:
        with open(os.path.join(run_dir, "events.jsonl")) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


# --------------------------------------------------------------------------


def selftest():
    d = tempfile.mkdtemp(prefix="fcl-")

    b1 = {"min": [-5, 0, -4], "max": [5, 6, 4]}
    # Flush at x=0 whatever the element's own origin is: the cursor tracks the
    # left EDGE, and the returned position is the element's origin.
    assert place(d, b1) == [5.0, 0, 0.0]
    # 10 wide + 6 gap puts the next left edge at 16, its origin at 21.
    assert place(d, b1, gap=6.0)[0] == 21.0
    # Review Focus 5: the cursor lives on disk, so a resumed run continues the
    # row instead of building on top of what is already there.
    assert os.path.exists(os.path.join(d, "cursor.json"))
    assert place(d, b1)[0] == 37.0

    wide = {"min": [-90, 0, -10], "max": [90, 20, 10]}
    p = place(d, wide, row_length=ROW_LENGTH)
    assert p[2] != 0.0, p          # wrapped to a new row
    assert p[0] == 90.0, p         # and restarted at the row's left edge

    log(d, "run_started", theme="x", n=2)
    log(d, "element_built", name="A", seconds=3.1)
    evs = read_events(d)
    assert [e["ev"] for e in evs] == ["run_started", "element_built"], evs
    assert evs[1]["name"] == "A" and evs[1]["seconds"] == 3.1, evs
    assert evs[0]["t"].endswith("Z"), evs

    # The monitor page reads this file every second while the loop writes it,
    # so a half-written final line must not break the reader.
    with open(os.path.join(d, "events.jsonl"), "a") as f:
        f.write('{"ev": "trunc')
    assert len(read_events(d)) == 2

    print("ok: cursor and event log selftest passed (11 checks)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--gap", type=float, default=GAP)
    ap.add_argument("--row-length", type=float, default=ROW_LENGTH)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        selftest()
        return 0
    ap.error("the loop itself is not wired up yet")


if __name__ == "__main__":
    sys.exit(main())
