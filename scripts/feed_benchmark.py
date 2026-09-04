#!/usr/bin/env python3
"""feed_benchmark.py — EARLINESS COMPARISON HARNESS (feed-only; no keys/balances/trading).

Proves how early OUR unified feed sees a new mint vs when public aggregators list it.
  T_direct      = when our feed caught the mint (blockTime / observed ts)
  T_dexscreener = first time DexScreener registers a pair for that mint
  Delta         = T_dexscreener - T_direct   (target: >30s structural lead)
Also records first-observed liquidity per token -> "Liquidity vs Speed Delta Matrix".
Modes:
  python3 scripts/feed_benchmark.py --watch 60   # follow unified.jsonl live
  python3 scripts/feed_benchmark.py --replay     # benchmark tokens already in feed
Outputs: data/live/feed/bench.jsonl + bench-matrix.json
"""
import os
import sys
import json
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "data", "live", "feed")
UNI = os.path.join(FD, "unified.jsonl")
BENCH = os.path.join(FD, "bench.jsonl")
MATRIX = os.path.join(FD, "bench-matrix.json")
SKIP = {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "So11111111111111111111111111111111111111112"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def dex_pairs(mint):
    try:
        req = urllib.request.Request("https://api.dexscreener.com/latest/dex/tokens/" + mint,
                                     headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return d.get("pairs") or []
    except Exception:
        return None


def first_liq(pairs):
    best = None
    for p in pairs or []:
        try:
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
        except Exception:
            liq = 0
        if best is None or liq > best[0]:
            best = (liq, p)
    return best


def candidate_mints(row):
    toks = []
    if row.get("chain") == "solana":
        toks = row.get("tokens") or []
    elif row.get("contract"):
        toks = [row.get("contract")]
    out = []
    for t in toks:
        if not t or t in SKIP:
            continue
        if t.lower().endswith("pump") or len(t) >= 32:
            out.append(t)
    return out


def direct_time(row):
    return row.get("blockTime") or row.get("ts")


def benchmark(mint, row, poll=5, attempts=60):
    t0 = direct_time(row)
    try:
        t0f = float(t0)
    except Exception:
        t0f = time.time()
    started = time.time()
    seen = liq = None
    pairs = None
    for _ in range(attempts):
        pairs = dex_pairs(mint)
        if pairs:
            seen = time.time()
            bl = first_liq(pairs)
            liq = bl[0] if bl else 0
            break
        time.sleep(poll)
    rec = {"mint": mint, "chain": row.get("chain"), "venue": row.get("venue"),
           "directTime": t0f, "directIso": (row.get("ts") or now_iso()),
           "dexFirstSeenEpoch": seen, "deltaSec": (round(seen - t0f, 1) if seen else None),
           "dexNow": pairs is not None, "liqUsd": liq,
           "pollSpentSec": round(time.time() - started, 1), "ts": now_iso()}
    with open(BENCH, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    if seen is not None:
        print("   ✓ %s %s delta=%ss liq=$%s" % (mint[:10] + "…", row.get("chain"), rec["deltaSec"], liq))
    else:
        print("   ○ %s not on DexScreener yet (waited %ss)" % (mint[:10] + "…", rec["pollSpentSec"]))
    return rec


def replay():
    rows = [json.loads(l) for l in open(UNI)] if os.path.exists(UNI) else []
    print("🛰️ BENCHMARK (replay) @ %s | rows %d | historical tokens -> DexScreener current state"
          % (now_iso()[:19], len(rows)))
    done = set()
    for row in rows:
        for m in candidate_mints(row):
            if m in done:
                continue
            done.add(m)
            benchmark(m, row, poll=2, attempts=5)
    matrix()


def watch(secs):
    print("🛰️ BENCHMARK (live watch) @ %s | following unified.jsonl for %ds" % (now_iso()[:19], secs))
    done = set()
    if os.path.exists(BENCH):  # never re-benchmark a mint we already measured
        for l in open(BENCH):
            try:
                m = json.loads(l).get("mint")
                if m:
                    done.add(m)
            except Exception:
                pass
    end = time.time() + secs
    with open(UNI, "r") as fh:
        fh.seek(0, 2)
        while time.time() < end:
            line = fh.readline()
            if not line:
                time.sleep(0.5)
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            for m in candidate_mints(row):
                if m in done:
                    continue
                done.add(m)
                benchmark(m, row, poll=3, attempts=8)  # live: tight poll, bounded wait
    matrix()


def matrix():
    rows = [json.loads(l) for l in open(BENCH)] if os.path.exists(BENCH) else []
    with_d = [r for r in rows if r.get("deltaSec") is not None]
    avg = sum(r["deltaSec"] for r in with_d) / len(with_d) if with_d else None
    out = {"asOf": now_iso(), "benchmarks": len(rows), "withDelta": len(with_d),
           "avgDeltaSec": round(avg, 1) if avg is not None else None,
           "note": "negative delta = aggregator saw it before our sample feed window; live watch measures the forward edge",
           "liquidityVsDelta": [{"liqUsd": r.get("liqUsd"), "deltaSec": r.get("deltaSec"),
                                 "chain": r.get("chain"), "mint": r.get("mint")[:10]} for r in with_d]}
    with open(MATRIX, "w") as fh:
        json.dump(out, fh, indent=2)
    print("📊 MATRIX: benchmarked=%d withDelta=%d avgDelta=%ss -> %s"
          % (len(rows), len(with_d), avg if avg is not None else "n/a", MATRIX))


def main():
    args = sys.argv[1:]
    if "--replay" in args:
        replay()
    else:
        secs = 60
        if "--watch" in args:
            secs = int(args[args.index("--watch") + 1])
        watch(secs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
    except Exception as e:
        print("feed_benchmark error:", e)
