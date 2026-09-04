#!/usr/bin/env python3
"""
coder-guard.py - Agentic Trading FIX/GUARD agent (on watch 24/7).

READ-ONLY patrol over the codebase. It NEVER edits code or touches money. When it
finds something it posts a PROPOSAL ticket to the TEAM HQ board (kind=fix,
status=needs-boss). Chief/boss approves before any change happens.

Checks (each run):
  1. All repo Python scripts compile.
  2. TODO/FIXME/BUG/XXX/HACK markers left in code.
  3. Core modules import cleanly.
Usage: python3 scripts/coder-guard.py
"""
import datetime
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import team_ops  # noqa: E402

MARKERS = ("TODO", "FIXME", "BUG", "XXX", "HACK", "WIP:")


def open_titles():
    b = team_ops._read_board()
    return {i["title"] for i in b["items"] if i["status"] in ("open", "claimed", "needs-boss")}


def propose(title, body, sev="P2"):
    """Post a guard proposal (no code change) unless an identical one is pending."""
    if title in open_titles():
        return False
    it = team_ops.assign("fix", title, body, priority=sev, needs_boss=True)
    b = team_ops._read_board()
    for x in b["items"]:
        if x["id"] == it["id"]:
            x["from"] = "guard"
    team_ops._write_board(b)
    return True


def main():
    posted = []
    # 1) compile all repo python
    bad = []
    for f in sorted(glob.glob(os.path.join(ROOT, "scripts", "*.py"))):
        r = subprocess.run([sys.executable, "-m", "py_compile", f],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((os.path.basename(f), (r.stderr or r.stdout)[:200]))
    if bad:
        for fname, err in bad:
            if propose("PY COMPILE FAIL: %s" % fname, err, "P1"):
                posted.append(fname)
    else:
        print("compile: all scripts OK")

    # 2) markers
    for f in sorted(glob.glob(os.path.join(ROOT, "scripts", "*.py"))):
        try:
            for i, ln in enumerate(open(f), 1):
                for m in MARKERS:
                    if m in ln and "#" in ln:
                        t = "Marker %s in %s:%d" % (m, os.path.basename(f), i)
                        if propose(t, ln.strip()[:300], "P3"):
                            posted.append(t)
                        break
        except Exception:
            continue

    # 3) core modules import
    try:
        import portfolio_state, portfolio_manager, autopilot, team_ops  # noqa
        print("imports: core modules OK")
    except Exception as e:
        propose("CORE IMPORT FAILURE", str(e)[:300], "P1")

    print("guard scan done. proposals posted:", len(posted))
    for t in posted:
        print("  -", t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
