#!/usr/bin/env python3
"""feedbot-paper.py — SUPERVISED DRY WATCH for the feed-bot (no orders, ever).

Hourly (launchd com.agentic-trading.feedbot-paper): runs the exact feed-bot
pipeline (coins.json intel -> feed shortlist -> DexScreener -> fastlane real-coin
gates) and LOGS what WOULD have entered, plus per-candidate gate outcomes, so the
boss can eyeball signal quality before real money engages.

Outputs: logs/feedbot-paper.jsonl (history) + data/live/feedbot-paper.json (latest)
"""
import os
import sys
import json
import importlib.util as _iu
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "feedbot-paper.jsonl")
STATE = os.path.join(ROOT, "data", "live", "feedbot-paper.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_mod(name, path):
    s = _iu.spec_from_file_location(name, path)
    m = _iu.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def main():
    fl = load_mod("fl", os.path.join(ROOT, "scripts", "fastlane.py"))
    fw = load_mod("fw", os.path.join(ROOT, "scripts", "fast-watch.py"))
    cfg = fl.bot_feed_cfg()
    rec = {"asOf": NOW, "cfg": {k: cfg[k] for k in ("enabled", "tiers", "minT60", "minAgeSec")}}

    # feed shortlist (what the bot is allowed to look at this hour)
    fm = fl.feed_intel_candidates(cfg)
    rec["feedShortlist"] = [{"mint": m} for m in fm]
    rec["feedShortlistCount"] = len(fm)

    # per-shortlist gate outcome (why each candidate did/did not clear the lanes)
    per = []
    if fm:
        try:
            js = fw.get(fw.DEX_BATCH.format(",".join(fm)))
        except Exception:
            js = None
        for addr, pairs in fw.group((js or {}).get("pairs") or []):
            pr = fw.best_pair(pairs)
            if not pr:
                per.append({"mint": addr, "gate": "NO-PAIR"})
                continue
            chg = pr.get("priceChange") or {}
            try:
                h1 = float(chg.get("h1")) if chg.get("h1") is not None else None
            except Exception:
                h1 = None
            per.append({"mint": addr,
                        "symbol": ((pr.get("baseToken") or {}).get("symbol") or addr[:6]),
                        "liqUsd": round(float((pr.get("liquidity") or {}).get("usd") or 0), 0),
                        "h1Pct": h1,
                        "gate": fl.buy_px_checks(pr)})
    rec["perCandidate"] = per

    # full pipeline result (watch + feed) exactly as the live tick computes it
    cands = fl.collect_candidates()
    open_n = fl.lane_open_count()
    would = next((c for c in cands if not fl.held(c["mint"])), None)
    rec["wouldEnter"] = ({"symbol": would.get("symbol"), "mint": would.get("mint"),
                          "signal": would.get("signal"), "liqUsd": round(would.get("liq") or 0, 0),
                          "px": would.get("px")} if would else None)
    rec["openPositions"] = open_n
    rec["note"] = "DRY only — nothing was bought or sold."

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    with open(STATE, "w") as f:
        json.dump(rec, f, indent=2)

    print("📋 FEED-BOT PAPER @ %s | shortlist=%d gated=%d open=%d"
          % (NOW[:19], len(fm), len(per), open_n))
    for p in per[:8]:
        print("   %s %-8s liq=$%.0f h1=%s gate=%s" % (p.get("mint", "")[:8], p.get("symbol", "?"),
                                                      p.get("liqUsd") or 0, p.get("h1Pct"), p.get("gate")))
    print("   WOULD-ENTER:", json.dumps(rec["wouldEnter"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("feedbot-paper error:", e)
        sys.exit(1)
