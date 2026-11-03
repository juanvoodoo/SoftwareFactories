#!/usr/bin/env python3
"""Prove the new factory skills and the old city skills never touch.

The requirement is two-way: nothing new may name anything old, and nothing old
may name anything new. Coupling is easy to add by accident in a comment and
impossible to notice later, so it is checked rather than remembered.

Documentation under docs/ is exempt: the design document necessarily discusses
both, which is its job.

    check_isolation.py            exit 0 clean, 1 with every offending path
"""
import glob, os, subprocess, sys

REPO = os.path.abspath(__file__)
for _ in range(5):          # scripts / skill / skills / .claude / repo
    REPO = os.path.dirname(REPO)
NEW_DIRS = ".claude/skills/factory-city-*"
OLD_DIRS = ".claude/skills/unity-city-*"
OLD_FILES = [".claude/agents/city-element-designer.md"]

NEW_MUST_NOT_NAME = ["unity-city", "city-runs", "CityKit"]
OLD_MUST_NOT_NAME = ["factory-city", "factory-runs", "FactoryKit"]


def files_in(pattern):
    out = []
    for d in glob.glob(os.path.join(REPO, pattern)):
        for root, dirs, names in os.walk(d):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            out += [os.path.join(root, n) for n in names
                    if not n.startswith(".") and not n.endswith(".pyc")
                    # this file names both sides on purpose; that is its job
                    and os.path.join(root, n) != os.path.abspath(__file__)]
    return sorted(out)


def offences(paths, needles):
    bad = []
    for f in paths:
        try:
            text = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for n in needles:
            if n in text:
                bad.append((os.path.relpath(f, REPO), n))
    return bad


def main():
    new = files_in(NEW_DIRS)
    old = files_in(OLD_DIRS) + [os.path.join(REPO, f) for f in OLD_FILES
                                if os.path.exists(os.path.join(REPO, f))]
    assert new, "no factory-city-* files found; wrong repo root?"
    assert old, "no unity-city-* files found; wrong repo root?"

    bad = [("new names old", p, n) for p, n in offences(new, NEW_MUST_NOT_NAME)]
    bad += [("old names new", p, n) for p, n in offences(old, OLD_MUST_NOT_NAME)]

    # The old skills must also be untouched on this branch, not merely silent.
    base = subprocess.run(["git", "merge-base", "main", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    if base:
        changed = subprocess.run(["git", "diff", "--name-only", base, "HEAD"],
                                 cwd=REPO, capture_output=True,
                                 text=True).stdout.split()
        for c in changed:
            if c.startswith(".claude/skills/unity-city-") or c in OLD_FILES:
                bad.append(("old file modified on this branch", c, ""))

    for kind, path, needle in bad:
        print(f"{kind}: {path}" + (f"  ({needle!r})" if needle else ""),
              file=sys.stderr)
    if bad:
        print(f"{len(bad)} isolation violation(s)", file=sys.stderr)
        return 1
    print(f"ok: {len(new)} new files and {len(old)} old files, no coupling "
          f"either way")
    return 0


if __name__ == "__main__":
    sys.exit(main())
