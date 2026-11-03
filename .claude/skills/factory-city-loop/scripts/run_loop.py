#!/usr/bin/env python3
"""The factory loop: design and build one building at a time, continuously.

Run artifacts live in the run directory and nothing is reconstructed from
memory. If it is not in a file, it did not happen.

    run_loop.py <run_dir> [--k 4] [--gap 6] [--row-length 200] [--timeout 600]
    run_loop.py --selftest
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brief import build_brief, BUILDER  # noqa: E402

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


DESIGNER_ARGV = ["claude", "-p", "--output-format", "stream-json", "--verbose",
                 "--allowedTools", "Write", "Bash",
                 "--permission-mode", "acceptEdits"]


PROBE = {"name": "__probe__", "materials": {},
         "parts": [{"name": "p", "primitive": "cube", "material": "X",
                    "size": [1, 1, 1], "at": [0, 0, 0]}]}


def _builder(builder_path, spec_path, dry_run=False):
    """Run the builder and return (parsed json, exit code)."""
    argv = [sys.executable, builder_path, spec_path, "--json"]
    if dry_run:
        argv.append("--dry-run")
    r = subprocess.run(argv, capture_output=True, text=True)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return {"ok": False, "elements": [], "warnings": [],
                "errors": [{"code": "builder_crashed",
                            "message": (r.stderr or r.stdout)[-400:]}]}, r.returncode


def preflight(builder_path):
    """One Editor call, before any agent is spent.

    Without this, a disconnected Editor costs every designer in the plan and
    then fails every build one by one. The probe is a spec that is REFUSED on
    its merits, so nothing is ever created: the builder checks the Editor
    first, so exit 3 means no Editor and anything else means we are fine.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(PROBE, f)
        tmp = f.name
    try:
        _, code = _builder(builder_path, tmp)
    finally:
        os.unlink(tmp)
    return code != 3


def _design(entry, run_dir, theme, palette, builder_path, timeout, designer_argv):
    """Spawn ONE designer as its own process; tee its whole stream to disk."""
    name = entry["name"]
    out_path = os.path.join(run_dir, "designed", f"{name}.json")
    agent_log = os.path.join(run_dir, "agents", f"{name}.jsonl")
    argv = [a.format(name=name, out=out_path) for a in designer_argv]
    text = build_brief(entry, theme, palette, out_path, builder_path)

    killed = []
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    timer = threading.Timer(timeout, lambda: (killed.append(True), proc.kill()))
    timer.start()
    tokens = 0
    try:
        proc.stdin.write(text)
        proc.stdin.close()
        with open(agent_log, "w") as f:
            for line in proc.stdout:
                f.write(line)
                f.flush()
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") == "result":
                    u = rec.get("usage") or {}
                    tokens = sum(v for kk, v in u.items()
                                 if kk.endswith("_tokens") and isinstance(v, int))
        proc.wait()
    except (BrokenPipeError, OSError):
        pass
    finally:
        timer.cancel()

    if killed:
        return {"ok": False, "reason": "timeout", "tokens": tokens}
    if not os.path.exists(out_path):
        return {"ok": False, "reason": "no_spec", "tokens": tokens}
    return {"ok": True, "reason": None, "tokens": tokens,
            "spec_path": out_path}


def run(run_dir, k=4, gap=GAP, row_length=ROW_LENGTH, timeout=600,
        builder_path=BUILDER, designer_argv=None, open_monitor=False):
    """Design and build continuously until every plan entry is terminal."""
    designer_argv = designer_argv or (DESIGNER_ARGV + [])
    started = time.time()
    for sub in ("designed", "agents"):
        os.makedirs(os.path.join(run_dir, sub), exist_ok=True)

    with open(os.path.join(run_dir, "plan.json")) as f:
        plan = json.load(f)
    entries = plan["elements"]
    roster = [e["name"] for e in entries]
    planned = set(roster)
    theme, palette = plan.get("theme", ""), plan.get("palette", {})

    log(run_dir, "run_started", theme=theme, n=len(entries), k=k, roster=roster)
    if open_monitor:
        log(run_dir, "monitor", url=start_monitor(run_dir))

    if not preflight(builder_path):
        log(run_dir, "run_aborted", reason="editor_unavailable",
            message=f"no Unity Editor on the bridge ({os.environ.get('UNITY_CLI', '/Users/juan/.unity/bin/unity')}); "
                    f"check `unity status` and try again. No agents were spent.")
        return {"built": 0, "failed": 0, "aborted": True, "tokens": 0}

    built = failed = tokens = unplanned = 0

    def spawn(entry):
        # The census is closed: a name not in the plan is a bug, not a feature.
        if entry["name"] not in planned:
            raise AssertionError(f"unplanned agent: {entry['name']}")
        log(run_dir, "designer_spawned", name=entry["name"])
        t0 = time.time()
        res = _design(entry, run_dir, theme, palette, builder_path, timeout,
                      designer_argv)
        res["seconds"] = round(time.time() - t0, 2)
        res["name"] = entry["name"]
        return res

    with ThreadPoolExecutor(max_workers=k) as ex:
        futures = {}
        for e in entries:
            if e["name"] not in planned:
                unplanned += 1
                continue
            futures[ex.submit(spawn, e)] = e

        # Builds happen HERE, in one thread: the Unity Editor is single-threaded,
        # so a designer finishing mid-build waits its turn rather than racing it.
        for fut in as_completed(futures):
            res = fut.result()
            name = res["name"]
            tokens += res["tokens"]
            log(run_dir, "designer_finished", name=name, seconds=res["seconds"],
                tokens=res["tokens"], ok=res["ok"])

            if not res["ok"]:
                failed += 1
                log(run_dir, "element_failed", name=name, reason=res["reason"])
                continue

            spec_path = res["spec_path"]
            dry, _ = _builder(builder_path, spec_path, dry_run=True)
            if not dry["ok"]:
                failed += 1
                code = dry["errors"][0]["code"] if dry["errors"] else "bad_spec"
                log(run_dir, "element_failed", name=name, reason=code,
                    message=dry["errors"][0]["message"] if dry["errors"] else "")
                continue

            el = dry["elements"][0]
            log(run_dir, "spec_written", name=name, path=spec_path,
                parts=el["parts"])

            pos = place(run_dir, el["bounds"], gap, row_length)
            with open(spec_path) as f:
                spec = json.load(f)
            spec["position"] = pos
            with open(spec_path, "w") as f:
                json.dump(spec, f, indent=1)

            t0 = time.time()
            out, _ = _builder(builder_path, spec_path)
            secs = round(time.time() - t0, 2)
            if out["ok"]:
                built += 1
                log(run_dir, "element_built", name=name, position=pos,
                    parts=el["parts"], seconds=secs)
            else:
                # No retries. A refusal is terminal, by design: a retry would be
                # a second agent for an entry that was licensed exactly one.
                failed += 1
                err = out["errors"][0] if out["errors"] else {}
                log(run_dir, "element_failed", name=name,
                    reason=err.get("code", "build_failed"),
                    message=err.get("message", ""), seconds=secs)

    log(run_dir, "run_finished", built=built, failed=failed, tokens=tokens,
        unplanned=unplanned, seconds=round(time.time() - started, 2))
    return {"built": built, "failed": failed, "tokens": tokens,
            "unplanned": unplanned, "aborted": False}


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
    selftest_loop()



FAKE_DESIGNER = r"""
import json, os, sys, time
mode, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
marks = os.path.join(os.path.dirname(out), "..", "marks")
os.makedirs(marks, exist_ok=True)
open(os.path.join(marks, name), "w").close()
with open(os.path.join(marks, "..", "concurrency.log"), "a") as f:
    f.write(str(len(os.listdir(marks))) + "\n")
first = name.endswith("_1")
if mode == "hang" and first:
    time.sleep(120)
elif mode == "nothing" and first:
    pass
elif mode == "garbage" and first:
    open(out, "w").write("{not json")
else:
    json.dump({"name": name, "materials": {"C": "#A8A49BFF"},
               "parts": [{"name": "Body", "primitive": "cube", "material": "C",
                          "size": [10, 6, 8], "at": [0, 0, 0]}]}, open(out, "w"))
print(json.dumps({"type": "result", "subtype": "success",
                  "usage": {"input_tokens": 10, "output_tokens": 20,
                            "cache_read_input_tokens": 100,
                            "cache_creation_input_tokens": 5},
                  "total_cost_usd": 0.01}))
os.remove(os.path.join(marks, name))
"""

FAKE_BUILDER = r"""
import json, os, sys
if "--schema" in sys.argv:
    print("INPUT CONTRACT -- fake\n\"position\": [x,0,z]  dropped by brief.py\n"
          "part_hidden_inside  a part inside another is invisible")
    sys.exit(0)
spec_path = sys.argv[1]
dry = "--dry-run" in sys.argv
if os.environ.get("FAKE_NO_EDITOR") and not dry:
    print(json.dumps({"ok": False, "elements": [], "warnings": [],
                      "errors": [{"code": "editor_unavailable", "message": "no bridge"}]}))
    sys.exit(3)
try:
    spec = json.load(open(spec_path))
except Exception as exc:
    print(json.dumps({"ok": False, "elements": [], "warnings": [],
                      "errors": [{"code": "bad_spec", "message": str(exc)}]}))
    sys.exit(2)
if spec.get("parts") is None:        # the preflight probe
    print(json.dumps({"ok": False, "elements": [], "warnings": [],
                      "errors": [{"code": "bad_size", "message": "probe"}]}))
    sys.exit(1)
name = spec["name"]
if not dry and os.environ.get("FAKE_REFUSE_FIRST") and name.endswith("_1"):
    print(json.dumps({"ok": False, "elements": [], "warnings": [],
                      "errors": [{"code": "name_taken", "message": name}]}))
    sys.exit(1)
print(json.dumps({"ok": True, "warnings": [], "errors": [], "elements": [
    {"name": name, "parts": len(spec["parts"]),
     "bounds": {"min": [-5, 0, -4], "max": [5, 6, 4]}}]}))
"""


def _fixture(mode="ok", n=3, refuse_first=False):
    d = tempfile.mkdtemp(prefix="fcl-loop-")
    designer = os.path.join(d, "fake_designer.py")
    builder = os.path.join(d, "fake_builder.py")
    open(designer, "w").write(FAKE_DESIGNER)
    open(builder, "w").write(FAKE_BUILDER)
    json.dump({"theme": "t", "palette": {"C": "#A8A49BFF"},
               "elements": [{"name": f"B_{i+1}", "kind": "building",
                             "idea": "an idea long enough to be a real one",
                             "footprint_m": [10, 8], "height_m": 6}
                            for i in range(n)]},
              open(os.path.join(d, "plan.json"), "w"))
    if refuse_first:
        os.environ["FAKE_REFUSE_FIRST"] = "1"
    else:
        os.environ.pop("FAKE_REFUSE_FIRST", None)
    argv = [sys.executable, designer, mode, "{name}", "{out}"]
    return d, builder, argv


def _counts(run_dir):
    evs = read_events(run_dir)
    return {"built": sum(1 for e in evs if e["ev"] == "element_built"),
            "failed": sum(1 for e in evs if e["ev"] == "element_failed")}


def _reason(run_dir):
    return [e["reason"] for e in read_events(run_dir) if e["ev"] == "element_failed"]


def selftest_loop():
    # happy path
    d, b, argv = _fixture()
    run(d, k=2, builder_path=b, designer_argv=argv)
    assert _counts(d) == {"built": 3, "failed": 0}, (_counts(d), _reason(d))
    evs = read_events(d)
    assert evs[0]["ev"] == "run_started" and evs[0]["n"] == 3, evs[0]
    assert sorted(evs[0]["roster"]) == ["B_1", "B_2", "B_3"], evs[0]
    assert evs[-1]["ev"] == "run_finished" and evs[-1]["unplanned"] == 0, evs[-1]
    # the closed census: one agent log per plan entry, never more
    assert sorted(os.listdir(os.path.join(d, "agents"))) == \
        ["B_1.jsonl", "B_2.jsonl", "B_3.jsonl"], os.listdir(os.path.join(d, "agents"))
    assert evs[-1]["tokens"] == 3 * 135, evs[-1]
    # K is respected
    peak = max(int(l) for l in open(os.path.join(d, "concurrency.log")))
    assert peak <= 2, peak

    # Review Focus 2: exits 0, writes nothing -> failed, loop continues
    d, b, argv = _fixture(mode="nothing", n=2)
    run(d, k=2, builder_path=b, designer_argv=argv)
    assert _counts(d) == {"built": 1, "failed": 1}, _counts(d)
    assert _reason(d) == ["no_spec"], _reason(d)

    # Review Focus 2: malformed JSON -> failed, no traceback
    d, b, argv = _fixture(mode="garbage", n=2)
    run(d, k=2, builder_path=b, designer_argv=argv)
    assert _reason(d) == ["bad_spec"], _reason(d)

    # Review Focus 3: a designer that hangs is killed and marked failed
    d, b, argv = _fixture(mode="hang", n=2)
    run(d, k=2, builder_path=b, designer_argv=argv, timeout=2)
    assert _counts(d) == {"built": 1, "failed": 1}, _counts(d)
    assert _reason(d) == ["timeout"], _reason(d)

    # Review Focus 4: the builder refuses name_taken -> failed, run continues
    d, b, argv = _fixture(n=2, refuse_first=True)
    run(d, k=2, builder_path=b, designer_argv=argv)
    assert _counts(d) == {"built": 1, "failed": 1}, _counts(d)
    assert _reason(d) == ["name_taken"], _reason(d)
    os.environ.pop("FAKE_REFUSE_FIRST", None)

    # Review Focus 1: no Editor on the bridge spends NO agents at all
    d, b, argv = _fixture(n=3)
    os.environ["FAKE_NO_EDITOR"] = "1"
    try:
        out = run(d, k=2, builder_path=b, designer_argv=argv)
    finally:
        os.environ.pop("FAKE_NO_EDITOR", None)
    assert out["aborted"] and out["built"] == 0, out
    assert os.listdir(os.path.join(d, "agents")) == [], "agents were spent"
    assert [e["ev"] for e in read_events(d)][-1] == "run_aborted", read_events(d)

    print("ok: loop selftest passed (19 checks, no agents, no Editor)")


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
    if not a.run_dir:
        ap.error("a run directory is required (or --selftest)")
    out = run(a.run_dir, k=a.k, gap=a.gap, row_length=a.row_length,
              timeout=a.timeout, open_monitor=True)
    if out.get("aborted"):
        print("aborted: no Unity Editor on the bridge; no agents were spent",
              file=sys.stderr)
        return 1
    print(f"{out['built']} built, {out['failed']} failed, "
          f"~{out['tokens']:,} tokens (approx)")
    return 0 if out["built"] else 1


if __name__ == "__main__":
    sys.exit(main())
