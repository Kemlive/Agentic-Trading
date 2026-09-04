#!/usr/bin/env python3
"""feedmerge.py — STEP 3: MERGE own-chain feeds into one unified stream + metrics.

Consumes data/live/feed/solana.jsonl + robinhood.jsonl, normalizes into
data/live/feed/unified.jsonl (dedup, source tags), and writes coverage metrics.
Feed-only. The trading BOT is a separate, later subscriber to this stream.
Run   : python3 scripts/feedmerge.py
"""
import os
import json
import time
import collections
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "data", "live", "feed")
SOL = os.path.join(FD, "solana.jsonl")
RH = os.path.join(FD, "robinhood.jsonl")
UNI = os.path.join(FD, "unified.jsonl")
METRICS = os.path.join(FD, "metrics.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def rows(p):
    try:
        return [json.loads(l) for l in open(p)]
    except Exception:
        return []


def uni_sol(r):
    return {"chain": "solana", "venue": r.get("venue"), "blk": r.get("slot"),
            "blockTime": r.get("blockTime"), "tx": r.get("tx"),
            "tokens": r.get("mints"), "err": r.get("err"), "src": "solfeed",
            "ts": r.get("ts")}


def uni_rh(r):
    return {"chain": "robinhood", "venue": r.get("venue"), "blk": r.get("block"),
            "tx": r.get("tx"), "idx": r.get("logIndex"),
            "tokens": [r.get("token")] if r.get("token") else None,
            "contract": r.get("token"), "from": r.get("from"), "to": r.get("to"),
            "src": "rhfeed", "ts": r.get("ts")}


def main():
    s = [uni_sol(r) for r in rows(SOL)]
    h = [uni_rh(r) for r in rows(RH)]
    allr = s + h
    seen = set()
    uniq = []
    for r in allr:
        k = (r["chain"], r["venue"], r.get("tx"), r.get("blk"), r.get("idx") or r.get("blockTime"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    with open(UNI, "w") as f:
        for r in uniq:
            f.write(json.dumps(r) + "\n")
    cnt = collections.Counter((r["chain"], r["venue"]) for r in uniq)
    per_chain = collections.Counter(r["chain"] for r in uniq)
    # recency: latest blockTime (solana has it) vs now; RH approximate via block delta
    now = time.time()
    sol_times = [float(r["blockTime"]) for r in s if r.get("blockTime")]
    recency_sol = (now - max(sol_times)) if sol_times else None
    metrics = {
        "asOf": NOW,
        "unifiedRows": len(uniq),
        "byChainVenue": {("%s/%s" % k): v for k, v in cnt.items()},
        "perChain": dict(per_chain),
        "solanaRecencySec": (round(recency_sol, 1) if recency_sol is not None else None),
        "note": "coverage vs aggregators (earliness proof) is the next metric to add",
    }
    with open(METRICS, "w") as f:
        json.dump(metrics, f, indent=2)
    print("🛰️ UNIFIED FEED @ %s | rows: sol=%d rh=%d unified=%d" % (NOW[:19], len(s), len(h), len(uniq)))
    for k, v in cnt.items():
        print("   %s/%s -> %d" % (k[0], k[1], v))
    print("metrics saved ->", METRICS)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("feedmerge error:", e)
