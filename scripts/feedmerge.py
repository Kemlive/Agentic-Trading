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
import math
import bisect
import collections
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")
SOL = os.path.join(FD, "solana.jsonl")
RH = os.path.join(FD, "robinhood.jsonl")
UNI = os.path.join(FD, "unified.jsonl")
METRICS = os.path.join(FD, "metrics.json")
COINS = os.path.join(FD, "coins.json")
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
            "blockTime": r.get("blockTime"),
            "tx": r.get("tx"), "idx": r.get("logIndex"),
            "tokens": [r.get("token")] if r.get("token") else None,
            "contract": r.get("token"), "from": r.get("from"), "to": r.get("to"),
            "symbol": r.get("symbol"), "src": "rhfeed", "ts": r.get("ts")}


# ---------- COIN REGISTRY (intel lives INSIDE the feed, real chain time) ----------
def chain_ts(r):
    bt = r.get("blockTime")
    if bt is not None and bt != "":
        try:
            return float(int(bt))
        except Exception:
            pass
    try:
        return datetime.datetime.fromisoformat(str(r.get("ts")).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def win_count(ts, ref, w):
    return len(ts) - bisect.bisect_left(ts, ref - w)


def unique_from_in(fr, ref, w):
    lo = bisect.bisect_left(fr, (ref - w, ""))
    return len({a for _, a in fr[lo:]})


def load_intel_cfg():
    p = os.path.join(LIVE, "feed-intel.json")
    def_ = {"scan": {"topN": 40, "minT1h": 1},
            "score": {"wT5m": 2.0, "wT1h": 1.0, "wU1h": 1.5, "wAccel": 0.5, "uPow": 0.5},
            "tiers": {"newMaxAgeSec": 1800, "migWindowSec": 7200, "trendPct": 90, "watchPct": 70,
                      "accelFloor": 0.0, "gainerMinT24": 24, "gainerRecentShare": 0.3},
            "quotes": {"solMints": ["So11111111111111111111111111111111111111112",
                                    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                                    "Es9vMFrzaCwm7JwkzdQonNupPga3jTdp9NyDqW9R4yRz"]}}
    try:
        return {**def_, **json.load(open(p))}
    except Exception:
        return def_


def registry(s, h):
    cfg = load_intel_cfg()
    S, T, SC = cfg["score"], cfg["tiers"], cfg["scan"]
    now = time.time()
    meta = {}
    try:
        a = json.load(open(os.path.join(FD, "rh_alpha.json")))
        meta = {k.lower(): v for k, v in (a.get("tokenMeta") or {}).items()}
    except Exception:
        pass
    quotes_sym = set()
    try:
        rc = json.load(open(os.path.join(LIVE, "rh-assets.json")))
        quotes_sym = set((rc.get("natives") or []) + (rc.get("stables") or []))
    except Exception:
        pass
    qm = set(cfg.get("quotes", {}).get("solMints", []))
    items = []
    # robinhood coins (quotes excluded, like Robinscan top-tokens)
    coin = {}
    for r in h:
        if r.get("venue") != "asset_transfer":
            continue
        tok = (r.get("contract") or "").lower()
        t = chain_ts(r)
        if not tok or t is None:
            continue
        d = coin.setdefault(tok, {"ts": [], "fr": []})
        d["ts"].append(t)
        if r.get("symbol"):
            d["sym"] = r.get("symbol")
        fr = (r.get("from") or "").lower()
        if fr and fr != "0x0000000000000000000000000000000000000000":
            d["fr"].append((t, fr))
    refRh = now
    if coin:
        refRh = min(now, max(max(v["ts"]) for v in coin.values()) + 5)
    for tok, d in coin.items():
        sym = d.get("sym") or (meta.get(tok) or {}).get("symbol")
        if sym and sym.upper() in quotes_sym:
            continue
        ts = sorted(d["ts"]); fr = sorted(d["fr"])
        t5 = win_count(ts, refRh, 300); t60 = win_count(ts, refRh, 3600); t1440 = win_count(ts, refRh, 86400)
        u60 = unique_from_in(fr, refRh, 3600)
        accel = (t5 / 300.0 - t60 / 3600.0) * 3600.0
        score = S["wT5m"] * t5 + S["wT1h"] * t60 + S["wU1h"] * (u60 ** S["uPow"]) + S["wAccel"] * max(0.0, accel)
        items.append({"chain": "robinhood", "key": tok, "sym": sym, "n": len(ts),
                      "first": ts[0], "last": ts[-1], "t5": t5, "t60": t60, "t1440": t1440,
                      "u60": u60, "accel": round(accel, 3), "score": round(score, 2),
                      "migrated": False, "venues": ["asset_transfer"]})
    # solana coins (mint bursts + pump->raydium migration)
    cmap = {}
    for r in s:
        for m in (r.get("tokens") or []):
            t = chain_ts(r)
            if not m or t is None or m in qm:
                continue
            d = cmap.setdefault(m, {"ts": [], "ven": {}})
            d["ts"].append(t)
            d["ven"].setdefault(r.get("venue"), []).append(t)
    refSol = now
    if cmap:
        refSol = min(now, max(max(v["ts"]) for v in cmap.values()) + 5)
    for mint, d in cmap.items():
        ts = sorted(d["ts"])
        t5 = win_count(ts, refSol, 300); t60 = win_count(ts, refSol, 3600); t1440 = win_count(ts, refSol, 86400)
        accel = (t5 / 300.0 - t60 / 3600.0) * 3600.0
        score = S["wT5m"] * t5 + S["wT1h"] * t60 + S["wAccel"] * max(0.0, accel)
        pf = d["ven"].get("pumpfun"); rd1 = d["ven"].get("raydium_v4"); rd2 = d["ven"].get("raydium_clmm")
        migrated = bool((pf and (rd1 or rd2)) and 0 <= (min(min(rd1 or [1e18]), min(rd2 or [1e18])) - min(pf)) <= T["migWindowSec"])
        items.append({"chain": "solana", "key": mint, "sym": None, "n": len(ts),
                      "first": ts[0], "last": ts[-1], "t5": t5, "t60": t60, "t1440": t1440,
                      "u60": 0, "accel": round(accel, 3), "score": round(score, 2),
                      "migrated": migrated, "venues": sorted(d["ven"].keys())})
    # percentiles per chain among ACTIVE coins
    for chain in ("robinhood", "solana"):
        lst = [i for i in items if i["chain"] == chain]
        active = sorted([i for i in lst if i["t60"] >= SC["minT1h"] or i["migrated"]],
                        key=lambda x: x["score"], reverse=True)
        pool = max(len(active) - 1, 1)
        for i, it in enumerate(active):
            it["pct"] = round(100 * (1 - i / pool), 1)
        for it in lst:
            it.setdefault("pct", 0.0)
    symcnt = {}
    for it in items:
        if it["sym"]:
            symcnt[it["sym"].upper()] = symcnt.get(it["sym"].upper(), 0) + 1
    cats, top = {}, {"robinhood": [], "solana": []}
    for it in items:
        age = now - it["first"]
        it["ageSec"] = int(age)
        it["dupSize"] = symcnt.get((it["sym"] or "").upper(), 0) or 1
        tags = []
        if it["migrated"]:
            tags.append("migrated")
        if it["t60"] >= SC["minT1h"] and it["pct"] >= T["trendPct"] and it["t5"] >= 1 and it["accel"] >= T["accelFloor"]:
            tags.append("trending")
        if it["t1440"] >= T["gainerMinT24"] and (it["t60"] / max(1, it["t1440"])) >= T["gainerRecentShare"]:
            tags.append("gainer")
        if age <= T["newMaxAgeSec"] and it["t60"] >= 1:
            tags.append("new")
        elif it["t60"] >= SC["minT1h"] and it["pct"] >= T["watchPct"]:
            tags.append("watch")
        order = ["trending", "gainer", "migrated", "new", "watch"]
        it["topTier"] = next((x for x in order if x in tags), None)
        it["tags"] = tags
        if it["topTier"]:
            cats.setdefault(it["chain"], {}).setdefault(it["topTier"], []).append(
                {"key": it["key"], "sym": it["sym"], "t5": it["t5"], "t60": it["t60"],
                 "accel": it["accel"], "score": it["score"], "pct": it["pct"], "ageSec": it["ageSec"]})
            top[it["chain"]].append(it)
    for chain in top:
        top[chain].sort(key=lambda x: x["score"], reverse=True)
        top[chain] = [{"key": it["key"], "sym": it["sym"], "score": it["score"], "topTier": it["topTier"],
                       "t5": it["t5"], "t60": it["t60"], "u60": it["u60"], "accel": it["accel"],
                       "pct": it["pct"], "dupSize": it["dupSize"], "venues": it["venues"]}
                      for it in top[chain][:SC["topN"]]]
    iso = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
    return {"asOf": NOW, "chainRefTime": {"robinhood": iso(refRh), "solana": iso(refSol)},
            "categories": cats, "top": top,
            "counts": {"robinhood": len([i for i in items if i["chain"] == "robinhood"]),
                       "solana": len([i for i in items if i["chain"] == "solana"]),
                       "migrated": len([i for i in items if i["migrated"]])}}


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
    reg = registry(s, h)
    with open(COINS, "w") as f:
        json.dump(reg, f, indent=2)
    print("   COIN REGISTRY -> %s | rh=%d sol=%d migrated=%d" % (COINS,
          reg["counts"]["robinhood"], reg["counts"]["solana"], reg["counts"]["migrated"]))
    print("🛰️ UNIFIED FEED @ %s | rows: sol=%d rh=%d unified=%d" % (NOW[:19], len(s), len(h), len(uniq)))
    for k, v in cnt.items():
        print("   %s/%s -> %d" % (k[0], k[1], v))
    print("metrics saved ->", METRICS)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("feedmerge error:", e)
