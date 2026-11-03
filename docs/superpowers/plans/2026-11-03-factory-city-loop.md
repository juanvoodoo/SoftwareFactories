# Factory City Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the batch city generator with a continuous design→build loop that shows each building in Unity the moment its spec lands, driven entirely by a script so the orchestrating model stays silent.

**Architecture:** Four pieces. Three are deliberately ignorant of their callers — `factory-city-generator` (ideas → `plan.json`), `factory-city-designer` (one idea → one spec, documentation only), `factory-city-element` (one spec → Unity geometry). The fourth, `factory-city-loop`, is a Python script that knows all three: it spawns designers as headless `claude -p` subprocesses, places each landed spec with a disk-persisted cursor, builds it immediately, and appends every event to a JSONL log that a static page renders live.

**Tech Stack:** Python 3 (stdlib only), `claude -p --output-format stream-json`, `python3 -m http.server`, Unity CLI at `/Users/juan/.unity/bin/unity`.

**Spec:** `docs/superpowers/specs/2026-11-03-factory-city-loop-design.md`

## Global Constraints

- **Isolation is absolute.** No file under `.claude/skills/factory-city-*/` may reference any path, script or agent under `.claude/skills/unity-city-*/`, and no existing `unity-city-*` file may be modified. Verified by a test in Task 7.
- **Buildings only.** No props, no roads. `kind` is always `"building"`.
- **No retries.** A refused or missing spec marks the element `failed` and the loop moves on.
- **The orchestrating model writes nothing during a run.** All progress output comes from scripts.
- **Stdlib only.** No new dependencies.
- **Tests are `--selftest` flags on the scripts themselves**, matching the existing convention in this repo. No test framework.
- Run artifacts live in `factory-runs/`, gitignored, never under `Assets/`.
- Materials land in `Assets/FactoryKit/Materials/<role>.mat`, not `CityKit`.
- K defaults to **4**, N defaults to **10**.

## Review Focus

Failure modes the spec implies but which no task's happy path exercises. Each has a test added to the task that owns the code.

1. **Unity Editor not connected.** Without a preflight the loop spends all N agents and then fails every build one by one. The loop must check the Editor once before spawning anything and abort with a clear message. — Task 5.
2. **Designer exits 0 but writes no spec, or writes malformed JSON.** Must mark the element `failed` with a reason, not raise. — Task 5.
3. **Designer process hangs.** Must time out, kill the process, mark `failed`, and let the loop continue. — Task 5.
4. **`name_taken`: a plan name collides with geometry already in the scene.** Must mark `failed` and continue, not abort the run. — Task 5.
5. **Resuming a run folder that already has a `cursor.json`.** Must continue the row where it stopped rather than restarting at x=0 and building on top of the previous run. — Task 3.

---

### Task 1: factory-city-element — the forked builder

**Files:**
- Create: `.claude/skills/factory-city-element/scripts/build_element.py` (fork of `.claude/skills/unity-city-element/scripts/build_element.py`)
- Create: `.claude/skills/factory-city-element/SKILL.md`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `python3 build_element.py <spec.json> [--dry-run] [--json] [--replace] [--preview PATH] [--save] [--schema] [--selftest]`. Exit codes unchanged from the original: 0 ok, 1 refused, 2 bad spec, 3 editor unavailable, 4 build failed. `--json` emits `{"ok", "elements":[{"name","parts","bounds":{"min","max"}}], "warnings", "errors":[{"code","message"}], ...}`. The module-level constant `SCHEMA` holds the input contract text; Task 4 imports that text into the designer brief.

- [ ] **Step 1: Copy the file verbatim**

```bash
mkdir -p .claude/skills/factory-city-element/scripts
cp .claude/skills/unity-city-element/scripts/build_element.py \
   .claude/skills/factory-city-element/scripts/build_element.py
```

This is the last moment the two files are related. Nothing from here on may reference the original.

- [ ] **Step 2: Strip road and prop, and repoint the materials folder**

In the new copy only:
- `PALETTE_DIR = "FactoryKit/Materials"` (was `"CityKit/Materials"`).
- Delete the road-overlap exemption at the original's lines 326-328 — the branch that lets two elements both marked `kind: "road"` overlap without a warning. Overlap is now always a warning.
- In `SCHEMA`, remove the `"kind"` key's `|"prop"|"road"` alternatives and the sentence explaining the road exemption; `kind` is documented as `"building"`. Update the `Materials land in Assets/...` line to `FactoryKit`.
- Update the module docstring to name this file, not the original.

- [ ] **Step 3: Write the failing selftest**

Add `--selftest` to the argument parser and a `selftest()` function. It must assert, with `UNITY_CLI=/nonexistent` so no Editor is touched:

```python
def selftest():
    # a two-part building validates clean and reports its bounds
    ok = _run({"name": "T", "position": [0, 0, 0],
               "materials": {"C": "#A8A49BFF"},
               "parts": [{"name": "Body", "primitive": "cube", "material": "C",
                          "size": [10, 6, 8], "at": [0, 0, 0]}]})
    assert ok["ok"] and ok["elements"][0]["parts"] == 1
    assert ok["elements"][0]["bounds"]["min"][0] == -5.0
    assert ok["elements"][0]["bounds"]["max"][1] == 6.0
    # a part buried inside another is refused
    bad = _run(... two concentric cubes ...)
    assert [e["code"] for e in bad["errors"]] == ["part_hidden_inside"]
    # an undefined material is refused
    assert "undefined_material" in codes_of(_run(... part naming "Nope" ...))
    # the materials path moved
    assert "FactoryKit" in SCHEMA and "CityKit" not in SCHEMA
```

`_run(spec)` writes the spec to a temp file, invokes this script's own `--dry-run --json` as a subprocess with `UNITY_CLI=/nonexistent`, and returns the parsed JSON.

- [ ] **Step 4: Run it**

Run: `python3 .claude/skills/factory-city-element/scripts/build_element.py --selftest`
Expected: PASS, printing a one-line ok.

- [ ] **Step 5: Write `SKILL.md`**

Describes one job: a spec file in, geometry in Unity out. States the input contract, the refusal codes, and that it decides nothing about shape, proportion, colour or placement. It must not mention runs, rows, cursors, loops, agents, briefs, props or roads, and must not name any `unity-city-*` path.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/factory-city-element
git commit -m "feat(factory): fork the element builder, buildings only, own material folder"
```

---

### Task 2: factory-city-generator — ideas only

**Files:**
- Create: `.claude/skills/factory-city-generator/SKILL.md`
- Create: `.claude/skills/factory-city-generator/scripts/validate_plan.py`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `python3 validate_plan.py <plan.json> --buildings <n> [--json] [--selftest]`. Exit 0 clean, 1 on any error. `--json` emits `{"ok", "buildings": n, "errors": [{"code","message"}], "warnings": [...]}`. The `plan.json` shape it enforces is what Task 5 reads.

`plan.json`:

```json
{"theme": "calle portuaria de los años 50",
 "palette": {"Rust": "#8A5236FF", "SaltedTimber": "#7A6A58FF"},
 "elements": [
   {"name": "Lonja", "kind": "building",
    "idea": "lonja de pescado de una planta, hormigón encalado, portones de chapa oxidada y rótulo descolorido",
    "footprint_m": [22, 14], "height_m": 7}
 ]}
```

- [ ] **Step 1: Write the failing selftest**

```python
def selftest():
    assert codes(check(plan_with_duplicate_names())) == ["duplicate_name"]
    assert "bad_name" in codes(check(plan_with_name("a/b")))      # path-unsafe
    assert "bad_kind" in codes(check(plan_with_kind("prop")))     # buildings only
    assert "bad_kind" in codes(check(plan_with_kind("road")))
    assert "missing_footprint" in codes(check(plan_without_footprint()))
    assert "count_mismatch" in codes(check(plan_of(3), buildings=10))
    assert "no_palette" in warn_codes(check(plan_without_palette()))
    assert "thin_idea" in warn_codes(check(plan_with_idea("a shop")))
    assert "flat_skyline" in warn_codes(check(plan_all_same_height()))
    assert check(good_plan(), buildings=2)["ok"]
```

`bad_name` matters beyond tidiness: Task 5 writes `agents/<name>.jsonl`, so a name containing `/` or `..` is a path-traversal. Accept `[A-Za-z][A-Za-z0-9_]*` only.

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-generator/scripts/validate_plan.py --selftest`
Expected: FAIL — file does not exist yet.

- [ ] **Step 3: Implement `check(plan: dict, buildings: int) -> dict` and the CLI**

Errors: `duplicate_name`, `bad_name`, `bad_kind` (anything but `"building"`), `missing_footprint` (absent, not length 2, or non-positive), `missing_idea`, `count_mismatch`. Warnings: `no_palette`, `thin_idea` (idea under 40 characters), `flat_skyline` (fewer than two distinct `height_m`, or max/min under 1.5).

- [ ] **Step 4: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-generator/scripts/validate_plan.py --selftest`
Expected: PASS

- [ ] **Step 5: Write `SKILL.md`**

One job: free text in, `plan.json` out. It carries the variety discipline — vary use, scale, material, era and condition; a street of five similar offices is a failure of this step that no later step can fix. It states that the palette is declared up front because designers cannot see each other's choices. It must not mention agents, briefs, Unity, the builder's contract, placement, cost, props or roads, and must not name any `unity-city-*` path.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/factory-city-generator
git commit -m "feat(factory): plan generator skill and buildings-only validator"
```

---

### Task 3: placement cursor and event log

**Files:**
- Create: `.claude/skills/factory-city-loop/scripts/run_loop.py` (cursor and events only; the loop itself arrives in Task 5)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `place(run_dir: str, bounds: dict, gap: float = 6.0, row_length: float = 200.0) -> list[float]` — returns `[x, 0, z]`, the `position` to stamp into the spec, and advances and persists the cursor. `bounds` is the `bounds` dict from the builder's `--dry-run --json`.
  - `log(run_dir: str, ev: str, **fields) -> None` — appends one JSON object to `events.jsonl` with `t` (UTC ISO-8601, `Z`) and `ev` set.
  - `read_events(run_dir: str) -> list[dict]`.

- [ ] **Step 1: Write the failing selftest**

```python
def selftest():
    d = tempdir()
    # first element sits flush at x=0 regardless of where its origin is
    b1 = {"min": [-5, 0, -4], "max": [5, 6, 4]}
    assert place(d, b1) == [5.0, 0, 0.0]          # shifted so its left edge is x=0
    # the next one clears the first by exactly `gap`
    assert place(d, b1, gap=6.0)[0] == 21.0       # 10 wide + 6 gap + 5 half
    # the cursor survives a restart  (Review Focus 5)
    assert place(d, b1)[0] == 37.0
    # a wide row wraps to a new z
    wide = {"min": [-90, 0, -10], "max": [90, 20, 10]}
    assert place(d, wide, row_length=200.0)[2] != 0.0
    # events round-trip, newest last, with a timestamp
    log(d, "run_started", theme="x", n=2)
    log(d, "element_built", name="A", seconds=3.1)
    evs = read_events(d)
    assert [e["ev"] for e in evs] == ["run_started", "element_built"]
    assert evs[1]["name"] == "A" and evs[0]["t"].endswith("Z")
    # a half-written final line does not break the reader
    append_raw(d, '{"ev": "trunc')
    assert len(read_events(d)) == 2
```

That last assertion matters because the monitor page reads the same file while the loop is writing it.

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: FAIL — file does not exist yet.

- [ ] **Step 3: Implement `place`, `log` and `read_events`**

Cursor state persists in `<run_dir>/cursor.json` as `{"x": float, "z": float}`. Placement: the returned x is `cursor.x - bounds.min[0]`, so the element's left edge lands exactly on the cursor; then `cursor.x += width + gap` where `width = max[0] - min[0]`. Wrap before placing, not after: if `cursor.x + width > row_length`, set `cursor.x = 0` and `cursor.z += 40.0`. Appends are a single `open(..., "a")` write of one line, so a reader never sees a partial line except at EOF — `read_events` skips a trailing line that does not parse.

- [ ] **Step 4: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/factory-city-loop/scripts/run_loop.py
git commit -m "feat(factory): persistent placement cursor and event log"
```

---

### Task 4: the designer brief and one headless designer

**Files:**
- Create: `.claude/skills/factory-city-loop/scripts/brief.py`
- Create: `.claude/skills/factory-city-designer/SKILL.md`

**Interfaces:**
- Consumes: the `SCHEMA` text from Task 1's builder.
- Produces: `build_brief(entry: dict, theme: str, palette: dict, out_path: str, builder_path: str) -> str` — the complete prompt text handed to one `claude -p` process.

- [ ] **Step 1: Write the failing selftest**

```python
def selftest():
    b = build_brief({"name": "Lonja", "idea": "lonja de pescado...",
                     "footprint_m": [22, 14], "height_m": 7},
                    theme="puerto 50s", palette={"Rust": "#8A5236FF"},
                    out_path="/r/designed/Lonja.json",
                    builder_path="/b/build_element.py")
    assert "Lonja" in b and "22" in b and "#8A5236FF" in b
    assert "INPUT CONTRACT" in b            # the contract travels inlined
    assert "/r/designed/Lonja.json" in b
    assert "SKILL.md" not in b              # no agent may be sent to read one
    assert "--schema" not in b              # nor to fetch the schema
    assert "unity-city" not in b            # isolation
    assert '"position"' not in b            # placement is not the designer's
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-loop/scripts/brief.py --selftest`
Expected: FAIL

- [ ] **Step 3: Implement `build_brief`**

The brief is self-contained: the idea, kind, target footprint and height, the theme, the palette as exact role→hex pairs, the builder's `SCHEMA` text inlined, the rules that cause refusals, and the output path. It ends by telling the agent to verify once with

```
UNITY_CLI=/nonexistent python3 <builder_path> <out_path> --dry-run
```

and to fix anything refused, then report only the path and part count.

That verify line is the one place the architecture bends, and deliberately: the loop knows all three pieces and injects the builder's path into the brief. The *designer* still knows nothing — it is told a command, not a collaborator. Without this the no-retry policy would turn every small mistake into a lost building.

The brief must never instruct the agent to read a SKILL.md or run `--schema`; measured on a 95-agent run those cost roughly a third of all agent API calls.

- [ ] **Step 4: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-loop/scripts/brief.py --selftest`
Expected: PASS

- [ ] **Step 5: Prove one real designer end to end, by hand**

```bash
mkdir -p /tmp/fcl/designed
claude -p "$(python3 -c '...build_brief for one entry...')" \
  --output-format stream-json --verbose \
  --allowedTools Write Bash
```

Expected: `/tmp/fcl/designed/<Name>.json` exists, and
`UNITY_CLI=/nonexistent python3 .claude/skills/factory-city-element/scripts/build_element.py /tmp/fcl/designed/<Name>.json --dry-run` exits 0.

Record in the commit message the exact flags that worked, the shape of the final `result` stream-json message, and where its token `usage` sits. Task 5 depends on all three.

- [ ] **Step 6: Write `SKILL.md`**

Documentation for a human: what a spec file looks like, what the parts and materials mean, what gets refused. It states plainly that it calls nothing, assigns no position, and does not know who asked. It must not name any `unity-city-*` path.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/factory-city-loop/scripts/brief.py .claude/skills/factory-city-designer
git commit -m "feat(factory): self-contained designer brief, verified against a live headless run"
```

---

### Task 5: the loop

**Files:**
- Modify: `.claude/skills/factory-city-loop/scripts/run_loop.py`

**Interfaces:**
- Consumes: `place`/`log` (Task 3), `build_brief` (Task 4), the builder CLI (Task 1), `plan.json` (Task 2).
- Produces: CLI `python3 run_loop.py <run_dir> [--k 4] [--gap 6] [--row-length 200] [--timeout 600] [--selftest]`. Prints one final summary line: `N built, M failed, ~T tokens`. Exit 0 if at least one element built, 1 if none did.

- [ ] **Step 1: Write the failing selftest**

The loop is tested with a **fake designer and a fake builder**, injected as the two command templates, so no agent and no Editor is needed:

```python
def selftest():
    # happy path: three entries, all design and build
    r = run_fake(plan_of(3), designer=writes_valid_spec, builder=succeeds)
    assert counts(r) == {"built": 3, "failed": 0}
    assert [e["ev"] for e in read_events(r)][0] == "run_started"
    assert sum(1 for e in read_events(r) if e["ev"] == "element_built") == 3
    assert all(os.path.exists(f"{r}/agents/{n}.jsonl") for n in names_of(r))

    # Review Focus 2: exits 0, writes nothing -> failed, loop continues
    r = run_fake(plan_of(2), designer=writes_nothing_for_first)
    assert counts(r) == {"built": 1, "failed": 1}
    assert reason(r, "failed") == "no_spec"

    # Review Focus 2: writes malformed JSON -> failed, no traceback
    assert reason(run_fake(plan_of(1), designer=writes_garbage), "failed") == "bad_spec"

    # Review Focus 3: hangs -> killed at the timeout, failed, loop continues
    r = run_fake(plan_of(2), designer=hangs_on_first, timeout=1)
    assert counts(r) == {"built": 1, "failed": 1}
    assert reason(r, "failed") == "timeout"

    # Review Focus 4: builder refuses name_taken -> failed, run continues
    r = run_fake(plan_of(2), builder=refuses_first("name_taken"))
    assert counts(r) == {"built": 1, "failed": 1}

    # the closed census: never more agent logs than plan entries
    r = run_fake(plan_of(3), designer=writes_valid_spec)
    assert len(os.listdir(f"{r}/agents")) == 3
    assert read_events(r)[-1]["ev"] == "run_finished"
    assert read_events(r)[-1]["unplanned"] == 0

    # K is respected: never more than K designers in flight at once
    assert max_concurrent(run_fake(plan_of(8), k=2)) == 2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: FAIL on the new assertions; the Task 3 assertions still pass.

- [ ] **Step 3: Implement the preflight (Review Focus 1)**

Before any designer is spawned, run the builder once on a trivial throwaway spec without `--dry-run`. Exit code 3 (`editor_unavailable`) means abort with a message naming the Unity CLI and the `unity status` check, logging `run_aborted` and spawning nothing. This costs one Editor call and saves N agents.

- [ ] **Step 4: Implement the loop**

`run(run_dir, k, gap, row_length, timeout) -> dict`.

Read `plan.json`. Log `run_started` with the theme, N, K and the full roster of names — that roster is what the page shows as `pending`. Keep at most `k` designer subprocesses in flight, each `claude -p <brief> --output-format stream-json --verbose --allowedTools Write Bash`, each with its stdout tee'd line by line to `agents/<name>.jsonl` as it arrives, not buffered to the end.

Every spawn is checked against the set of names in `plan.json`; a name not in it is a bug, not a feature — raise rather than spawn, and count it in `run_finished.unplanned`, which must be 0.

When a process ends: `--dry-run --json` its spec to get bounds, `place()` them, stamp `position` into the spec, build it. Each of `no_spec`, `bad_spec`, `timeout`, and a builder refusal is terminal — log `element_failed` with `name`, `reason` and, for a refusal, the builder's own code and message. No retries, ever. Then start the next pending entry.

Because the Editor is single-threaded, builds are serialised; a designer finishing while a build is in progress waits its turn rather than racing it.

Token totals are summed from each process's final `result` stream-json message and reported as approximate.

Finish when every entry is `built` or `failed`. Log `run_finished` with built, failed, elapsed, approximate tokens, and `unplanned`.

- [ ] **Step 5: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/factory-city-loop/scripts/run_loop.py
git commit -m "feat(factory): the design-to-build loop, with no-retry failure policy and per-agent audit logs"
```

---

### Task 6: the live monitor

**Files:**
- Create: `.claude/skills/factory-city-loop/scripts/monitor.html`
- Modify: `.claude/skills/factory-city-loop/scripts/run_loop.py`

**Interfaces:**
- Consumes: `events.jsonl` (Task 3), `run()` (Task 5).
- Produces: `start_monitor(run_dir: str) -> str` — copies `monitor.html` into the run folder, starts `python3 -m http.server` rooted there on a free port, opens the browser at it, and returns the URL. The server is a daemon subprocess the loop terminates at the end.

- [ ] **Step 1: Write the failing selftest**

```python
def selftest():
    d = tempdir_with_events()
    url = start_monitor(d)
    assert url.startswith("http://127.0.0.1:")
    assert fetch(url).status == 200                      # page served
    assert "events.jsonl" in fetch(url).text             # page reads the log
    assert fetch(url.rsplit("/",1)[0] + "/events.jsonl").status == 200
    assert os.path.exists(f"{d}/monitor.html")
```

`file://` is not an option here: a page opened from disk cannot `fetch` a sibling file. That is the whole reason for the server.

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: FAIL on the monitor assertions.

- [ ] **Step 3: Write `monitor.html`**

A single self-contained file, no CDN, no build step. It re-fetches `events.jsonl` every second, replays it from the start, and renders:

- a roster table, one row per name from `run_started`, with status `pending → designing → built`, or `failed` with its reason, plus the element's seconds and part count once known;
- a totals line: `N planeados · K corriendo · M terminados · F fallidos · ~T tokens (aprox) · 0 no planeados`;
- the `0 no planeados` counter styled to stand out if it is ever non-zero;
- a timeline of the raw events, newest last.

It stops polling after `run_finished` and leaves the final state on screen. It is read-only — no buttons, no approval gate.

- [ ] **Step 4: Implement `start_monitor` and wire it into `run()`**

`run()` calls `start_monitor(run_dir)` immediately after logging `run_started` and before the preflight, so the page is up and showing the roster while the Editor check happens. Bind the server to `127.0.0.1` on port 0 and read back the assigned port. Terminate the server after `run_finished`, but only after a short grace period so the page catches the final state.

- [ ] **Step 5: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-loop/scripts/run_loop.py --selftest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/factory-city-loop/scripts/monitor.html .claude/skills/factory-city-loop/scripts/run_loop.py
git commit -m "feat(factory): live monitor page, auto-opened and auto-refreshing"
```

---

### Task 7: the loop skill, isolation proof, and a real run

**Files:**
- Create: `.claude/skills/factory-city-loop/SKILL.md`
- Create: `.claude/skills/factory-city-loop/scripts/check_isolation.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: everything above.
- Produces: the user-facing entry point, `/factory-city-loop <theme> <counts>`.

- [ ] **Step 1: Write the failing isolation test**

```python
def selftest():
    new = files_under(".claude/skills/factory-city-*") + \
          ["docs/superpowers/specs/...", ...]   # skills only; docs are exempt
    old = files_under(".claude/skills/unity-city-*") + [".claude/agents/city-element-designer.md"]
    for f in new:
        assert "unity-city" not in read(f), f           # new never names old
        assert "city-runs" not in read(f), f
        assert "CityKit" not in read(f), f
    for f in old:
        assert "factory-city" not in read(f), f         # old never names new
        assert "factory-runs" not in read(f), f
    assert git_untouched(old)                           # old files unmodified on this branch
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 .claude/skills/factory-city-loop/scripts/check_isolation.py`
Expected: FAIL — the script does not exist, and any leftover reference in a new file is reported by path.

- [ ] **Step 3: Implement it and fix every reference it names**

- [ ] **Step 4: Run it to verify it passes**

Run: `python3 .claude/skills/factory-city-loop/scripts/check_isolation.py`
Expected: PASS

- [ ] **Step 5: Add `factory-runs/` to `.gitignore`**

Next to the existing `city-runs/` line. Run artifacts are working files and the audit logs may hold large transcripts.

- [ ] **Step 6: Write `SKILL.md`**

The only document that names all four pieces. It covers: read the theme and counts from the user (defaults 10 buildings, K=4); invent and validate `plan.json` into `factory-runs/<slug>/`; launch `run_loop.py`; **then say nothing until it exits**, because a turn spent narrating re-sends the whole context and that is the one thing this design exists to avoid; finally report the summary line in one message.

It states the no-retry policy and that nothing is saved to the scene unless the user asks.

- [ ] **Step 7: One real end-to-end run**

```bash
python3 .claude/skills/factory-city-loop/scripts/run_loop.py factory-runs/smoke --k 2
```

with a hand-written 3-building `plan.json` and a connected Editor.

Expected: the browser opens within a second or two; the first building appears in Unity well before the third designer finishes; `factory-runs/smoke/` ends up holding `plan.json`, `events.jsonl`, `cursor.json`, `agents/*.jsonl` (one per entry, no more), and `designed/*.json`; the page's `no planeados` counter reads 0. Record the wall-clock time to first visible geometry in the commit message — that number is the whole point of this plan.

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/factory-city-loop .gitignore
git commit -m "feat(factory): loop skill, isolation check, verified end to end"
```
