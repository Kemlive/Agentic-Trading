#!/usr/bin/env python3
"""subagent-report.py — recurring SUBAGENT + ACCOUNT report (auto, no manual ask).
Summarizes every lane (pid alive, artifact age), latest learning-log entries, newest research,
open positions, and account deltas -> research/SUBAGENT-REPORT-<ts>.md + prints a short console digest."""
import datetime, json, os, glob, subprocess

ROOT = "/Users/earn/Agentic-Trading"
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")
LOGS = os.path.join(ROOT, "logs", "feed")
LL = os.path.join(ROOT, "agents", "learning-log.md")

def read(p, d=None):
    try: return json.load(open(p))
    except Exception: return d

def age(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        s = int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds())
        return "now" if s < 30 else (f"{s//60}m" if s < 3600 else f"{s/3600:.1f}h")
    except Exception: return "?"

def pid(name):
    if name == "feed_dashboard":
        try:
            p = subprocess.run(["pgrep", "-f", "feed_dashboard.py"], capture_output=True, text=True).stdout.split()[0]
            return int(p) if p else None
        except Exception: return None
    try:
        return int(open(os.path.join(LOGS, name + ".pid")).read().strip())
    except Exception: return None

def alive(name):
    p = pid(name)
    if not p: return False, None
    try: os.kill(p, 0); return True, p
    except Exception: return False, p

now = datetime.datetime.now(datetime.timezone.utc)
out = {"asOf": now.isoformat(), "lanes": {}, "learningLogTail": [], "newestResearch": [], "open": {}, "account": {}}
lanes = ["sol", "rh", "rhpot", "merge", "bench", "ponsfresh", "ponsauto", "feed_dashboard"]
for l in lanes:
    a, p = alive(l)
    out["lanes"][l] = {"alive": a, "pid": p}

ll = []
try:
    for line in open(LL):
        if line.startswith("## "): ll.append(line.strip())
except Exception: pass
out["learningLogTail"] = ll[-8:][::-1]
out["newestResearch"] = sorted(glob.glob(os.path.join(ROOT, "research", "*.md")), key=os.path.getmtime, reverse=True)[:6]

# open positions / state
fp = read(os.path.join(LIVE, "fastlane-positions.json"), {})
pos = fp.get("positions") if isinstance(fp, dict) else fp
posList = pos if isinstance(pos, list) else []
out["open"]["solOpen"] = sum(1 for p in posList if (p.get("qty") or 0) != 0)
out["open"]["solClosed"] = sum(1 for p in posList if (p.get("qty") or 0) == 0)
ps = read(os.path.join(LIVE, "pons-autopilot-state.json"), {})
out["open"]["ponsDryPos"] = bool(ps.get("pos")); out["open"]["ponsMode"] = read(os.path.join(LIVE, "pons-autopilot.json"), {}).get("mode")
fc = read(os.path.join(FD, "pons-live-fresh.json"), {})
out["account"]["ponsFreshN"] = fc.get("freshN"); out["account"]["rhTiers"] = {k: len(v) for k, v in (read(os.path.join(FD, "rh-potential.json"), {}).get("tiers") or {}).items()}

ts = now.strftime("%Y%m%d-%H%M")
base = os.path.join(ROOT, "research", "SUBAGENT-REPORT-" + ts)
md = ["# Subagent & Account Report (%s UTC)" % now.strftime("%Y-%m-%d %H:%M"), "",
      "| lane | alive | pid |", "|---|---|---|"]
for l in lanes: md.append("| %s | %s | %s |" % (l, out["lanes"][l]["alive"], out["lanes"][l]["pid"]))
md += ["", "## Latest memory/log entries", ""]
for e in out["learningLogTail"]: md.append("- " + e)
md += ["", "## Newest research", ""]
for r in out["newestResearch"]: md.append("- " + os.path.basename(r))
md += ["", "## State", "", "- pons-live fresh: %s | rh tiers: %s | SOL open: %s (closed: %s) | pons dry pos: %s (mode %s)" % (
    out["account"]["ponsFreshN"], out["account"]["rhTiers"], out["open"]["solOpen"], out["open"]["solClosed"], out["open"]["ponsDryPos"], out["open"]["ponsMode"])]
open(base + ".md", "w").write("\n".join(md))
alive_n = sum(1 for v in out["lanes"].values() if v["alive"])
print("[SUBAGENT REPORT %s] lanes up %d/%d | SOL open %s | pons-live %s | file %s" % (
    ts, alive_n, len(lanes), out["open"].get("solOpen", 0), out["account"]["ponsFreshN"], os.path.basename(base)))
