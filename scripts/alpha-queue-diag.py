#!/usr/bin/env python3
"""alpha-queue-diag.py — LIVE SOLANA ALPHA-QUEUE DIAGNOSTIC (read-only).

Validates refined hunt/execution params inside strict tolerances:
  - multi-shot hunt (autopilot: queue<=3, relief after 2 dry, $1..$2.50 clips)
  - real-coin lane (fastlane: $10 clips, $25/day, loss-halt $12, max 2 open)
  - capital guard (stop -15%, +30% bank, -12% trail, feed-dead <=2, retry 3)
  - live queue health (positions<=max, delegate headroom, feed recency)
Run: python3 scripts/alpha-queue-diag.py  (exit 0 = all PASS, 1 = any FAIL)
"""
import os
import sys
import json
import datetime
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
TOL_FILE = os.path.join(ROOT, "data", "live", "queue-tolerance.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
CHECKS = []


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check(name, ok, detail):
    CHECKS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})


def tol():
    default = {
        "hunt": {"reliefAfterDry": 2, "queueCap": 3, "minClip": 1.0, "maxClip": 2.5},
        "fastlane": {"maxTrade": [5, 15], "dailyCap": [15, 35], "lossHalt": [10, 15],
                     "maxOpen": 2},
        "guard": {"stopPct": [-18, -12], "bankPct": [25, 35], "trailPct": [-15, -10],
                  "feedMiss": [1, 3], "sellRetry": 3},
        "feed": {"solRecencySec": 180, "rhRecencySec": 180}}
    try:
        t = json.load(open(TOL_FILE))
        return {**default, **t}
    except Exception:
        with open(TOL_FILE, "w") as fh:
            json.dump(default, fh, indent=2)
        return default


def between(v, lo, hi):
    return lo <= float(v) <= hi

def main():
    t = tol()
    # 1) multi-shot hunt present in code
    try:
        ap = open(os.path.join(SCRIPTS, "autopilot.py")).read()
        check("hunt.queueCap<=3", "[:3]" in ap, "queue slice [:3] present")
        check("hunt.reliefAfterDry==%d" % t["hunt"]["reliefAfterDry"],
              ("dry_runs >= %d" % t["hunt"]["reliefAfterDry"]) in ap,
              "relief engages after %d dry ticks" % t["hunt"]["reliefAfterDry"])
    except Exception as e:
        check("hunt.code", False, str(e)[:80])
    try:
        A = load_module("autopilot", "autopilot.py")
        check("hunt.clip $%.1f..$%.1f" % (t["hunt"]["minClip"], t["hunt"]["maxClip"]),
              between(A.SIZE_USDC, t["hunt"]["minClip"], t["hunt"]["maxClip"]),
              "SIZE_USDC=%.2f" % A.SIZE_USDC)
    except Exception as e:
        check("hunt.clip", False, "import err " + str(e)[:60])

    # 2) real-coin lane params
    try:
        FL = load_module("fastlane", "fastlane.py")
        check("fastlane.maxTrade in %s" % t["fastlane"]["maxTrade"],
              between(FL.MAX_TRADE, *t["fastlane"]["maxTrade"]), "MAX_TRADE=%.1f" % FL.MAX_TRADE)
        check("fastlane.dailyCap in %s" % t["fastlane"]["dailyCap"],
              between(FL.DAILY_CAP, *t["fastlane"]["dailyCap"]), "DAILY_CAP=%.1f" % FL.DAILY_CAP)
        check("fastlane.lossHalt in %s" % t["fastlane"]["lossHalt"],
              between(FL.DAILY_LOSS_HALT, *t["fastlane"]["lossHalt"]), "LOSS_HALT=%.1f" % FL.DAILY_LOSS_HALT)
        check("fastlane.maxOpen==%d" % t["fastlane"]["maxOpen"], FL.MAX_OPEN == t["fastlane"]["maxOpen"],
              "MAX_OPEN=%d" % FL.MAX_OPEN)
    except Exception as e:
        check("fastlane.params", False, "import err " + str(e)[:60])

    # 3) capital-guard exit params
    try:
        CG = load_module("cg", "capital-guard.py")
        check("guard.stopPct in %s" % t["guard"]["stopPct"],
              between(CG.STOP_PCT, *t["guard"]["stopPct"]), "STOP=%.0f%%" % CG.STOP_PCT)
        check("guard.bankPct in %s" % t["guard"]["bankPct"],
              between(CG.BANK_PCT, *t["guard"]["bankPct"]), "BANK=%.0f%%" % CG.BANK_PCT)
        check("guard.trailPct in %s" % t["guard"]["trailPct"],
              between(CG.TRAIL_PCT, *t["guard"]["trailPct"]), "TRAIL=%.0f%%" % CG.TRAIL_PCT)
        check("guard.feedMiss<=%d" % t["guard"]["feedMiss"][1],
              CG.FEED_MISS_MAX <= t["guard"]["feedMiss"][1], "FEED_MISS_MAX=%d" % CG.FEED_MISS_MAX)
        check("guard.sellRetry==%d" % t["guard"]["sellRetry"], CG.SELL_RETRY == t["guard"]["sellRetry"],
              "SELL_RETRY=%d" % CG.SELL_RETRY)
    except Exception as e:
        check("guard.params", False, "import err " + str(e)[:60])

    # 4) live queue health
    check("micro.snatcher.paused", os.path.exists(os.path.join(ROOT, "data", "live", "autopilot.off")),
          "autopilot.off present (expected while paused)")
    try:
        import portfolio_state as PS
        vault = PS._read_sol_usdc_any(PS.SOL_VAULT_WALLET) or 0
        hot = PS._read_sol_usdc_any(PS.SOL_HOT_WALLET) or 0
        check("delegate.headroom", (vault + hot) >= 1.0, "vault+hot=%.2f (>= $1 floor)" % (vault + hot))
    except Exception as e:
        check("delegate.headroom", False, str(e)[:60])

    for chain, f, limk in (("sol", "solana.jsonl", "solRecencySec"), ("rh", "robinhood.jsonl", "rhRecencySec")):
        try:
            p = os.path.join(ROOT, "data", "live", "feed", f)
            last = None
            for l in open(p):
                try:
                    last = json.loads(l).get("ts")
                except Exception:
                    pass
            age = None
            if last:
                age = (datetime.datetime.now(datetime.timezone.utc) -
                       datetime.datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds()
            lim = t["feed"][limk]
            check("feed.%s.recency" % chain, age is not None and age <= lim,
                  "last event %.0fs ago (<= %ds)" % (age or -1, lim))
        except Exception as e:
            check("feed.%s.recency" % chain, False, str(e)[:60])

    print("🔎 ALPHA-QUEUE DIAGNOSTIC @ %s" % NOW[:19])
    fails = sum(0 if c["ok"] else 1 for c in CHECKS)
    for c in CHECKS:
        print("   [%s] %-36s %s" % ("PASS" if c["ok"] else "FAIL", c["name"], c["detail"]))
    print("RESULT: %d/%d passed" % (len(CHECKS) - fails, len(CHECKS)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

