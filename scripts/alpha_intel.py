#!/usr/bin/env python3
"""alpha_intel.py — TERMINAL-FUNNEL ALPHA INTELLIGENCE over OUR OWN feed streams.

Applies what Phantom/Robinhood-chain terminals do to rank + funnel tokens, but
computed only from our own data (recon: research/2026-09-04-terminal-trending-recon.md).
Signals: rolling transfer/event windows (5m/1h/24h), holder velocity (uniqueFrom),
acceleration, pump->raydium MIGRATION, quote-token exclusion, PvP-style dup
ticker grouping. Emits ranked tiers per chain (NEW/TRENDING/MIGRATED/GAINER/WATCH).

Outputs: data/live/feed/alpha-intel.json  (+ alpha-intel.jsonl history)
Tunables: data/live/alpha-intel.json (never in code). No execution, no keys.
"""
import os
import sys
import json
import math
import bisect
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "data", "live", "feed")
LIVE = os.path.join(ROOT, "data", "live")
CFG_PATH = os.path.join(LIVE, "alpha-intel.json")


def load_cfg():
    default = {
        "scan": {"topN": 40, "minT1h": 1},
        "score": {"wT5m": 2.0, "wT1h": 1.0, "wU1h": 1.5, "wAccel": 0.5, "uPow": 0.5},
        "tiers": {"newMaxAgeSec": 1800, "migWindowSec": 7200, "trendPct": 90, "watchPct": 70,
                  "accelFloor": 0.0, "gainerMinT24": 24, "gainerRecentShare": 0.3},
        "quotes": {"solMints": ["So11111111111111111111111111111111111111112",
                                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                                "Es9vMFrzaCwm7JwkzdQonNupPga3jTdp9NyDqW9R4yRz"]},
        "note": "terminal-funnel-inspired alpha intel (recon 2026-09-04). Tunables live here, never in code."}
    try:
        return {**default, **json.load(open(CFG_PATH))}
    except Exception:
        with open(CFG_PATH, "w") as fh:
            json.dump(default, fh, indent=2)
        return default


CFG = load_cfg()
NOW = datetime.datetime.now(datetime.timezone.utc)
NOWT = NOW.timestamp()
WINDOWS = ((300, "5m"), (3600, "1h"), (86400, "24h"))

# quote tokens (Robinscan excludes these from top-token rankings)
RH_CFG = json.load(open(os.path.join(LIVE, "rh-assets.json"))) if os.path.exists(os.path.join(LIVE, "rh-assets.json")) else {}
QUOTE_SYMS = set((RH_CFG.get("natives") or []) + (RH_CFG.get("stables") or []))


def rows(p):
    try:
        return [json.loads(l) for l in open(p)]
    except Exception:
        return []


def parse_ts(s, fallback=None):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return float(fallback or NOWT)


def collect():
    """Return token activity maps: rh and sol structures."""
    # ---- symbol metadata for RH from rh_alpha tokenMeta ----
    meta = {}
    try:
        a = json.load(open(os.path.join(FD, "rh_alpha.json")))
        meta = {k.lower(): v for k, v in (a.get("tokenMeta") or {}).items()}
    except Exception:
        pass
    # RH: per token -> ts list, unique from sets (window-aware), symbol
    rh = {}
    for r in rows(os.path.join(FD, "robinhood.jsonl")):
        tok = (r.get("token") or "").lower()
        if not tok or r.get("venue") != "asset_transfer":
            continue
        ts = parse_ts(r.get("ts"))
        fr = (r.get("from") or "").lower()
        d = rh.setdefault(tok, {"ts": [], "from": [], "venues": set(), "sym": None})
        d["ts"].append(ts)
        if fr and fr != "0x0000000000000000000000000000000000000000":
            d["from"].append((ts, fr))
        d["venues"].add(r.get("venue"))
        if d["sym"] is None and tok in meta:
            d["sym"] = meta[tok].get("symbol")
    # SOL: per mint -> ts list + venue first-seen map (migration detection)
    sol = {}
    for r in rows(os.path.join(FD, "solana.jsonl")):
        for m in (r.get("mints") or []):
            ts = parse_ts(r.get("ts"), r.get("blockTime"))
            v = r.get("venue")
            d = sol.setdefault(m, {"ts": [], "venues": {}, "sym": None})
            d["ts"].append(ts)
            d["venues"].setdefault(v, []).append(ts)
    return rh, sol


def counts(ts_sorted, now, window):
    i = bisect.bisect_left(ts_sorted, now - window)
    return len(ts_sorted) - i


def unique_from_in(fr_sorted, now, window):
    lo = bisect.bisect_left(fr_sorted, (now - window, ""))
    return len({a for _, a in fr_sorted[lo:]})


def analyze(rh, sol):
    S = CFG["score"]
    T = CFG["tiers"]
    items = []

    # ---- Robinhood assets (quotes excluded, like Robinscan top-tokens) ----
    for tok, d in rh.items():
        sym = d["sym"]
        if sym and sym.upper() in QUOTE_SYMS:
            continue
        ts = sorted(d["ts"])
        fr = sorted(d["from"])
        t5 = counts(ts, NOWT, 300); t60 = counts(ts, NOWT, 3600); t1440 = counts(ts, NOWT, 86400)
        u60 = unique_from_in(fr, NOWT, 3600); u1440 = unique_from_in(fr, NOWT, 86400)
        accel = (t5 / 300.0 - t60 / 3600.0) * 3600.0
        score = (S["wT5m"] * t5 + S["wT1h"] * t60 + S["wU1h"] * (u60 ** S["uPow"])
                 + S["wAccel"] * max(0.0, accel))
        items.append({"chain": "robinhood", "key": tok, "sym": sym,
                      "first": ts[0], "last": ts[-1], "n": len(ts),
                      "t5": t5, "t60": t60, "t1440": t1440,
                      "u60": u60, "u1440": u1440, "accel": round(accel, 3),
                      "score": round(score, 2), "venues": sorted(d["venues"]),
                      "migrated": False})

    # ---- Solana mints (event bursts + pump->raydium migration) ----
    QUOTE_MINTS = set(CFG.get("quotes", {}).get("solMints", []))
    for mint, d in sol.items():
        if mint in QUOTE_MINTS:
            continue
        ts = sorted(d["ts"])
        t5 = counts(ts, NOWT, 300); t60 = counts(ts, NOWT, 3600); t1440 = counts(ts, NOWT, 86400)
        accel = (t5 / 300.0 - t60 / 3600.0) * 3600.0
        score = (S["wT5m"] * t5 + S["wT1h"] * t60 + S["wAccel"] * max(0.0, accel))
        pf = min((d["venues"].get("pumpfun") or [NOWT]))
        rd = min(min(d["venues"].get("raydium_v4") or [NOWT]),
                 min(d["venues"].get("raydium_clmm") or [NOWT]))
        migrated = (d["venues"].get("pumpfun") and d["venues"].get("raydium_v4")
                    or d["venues"].get("pumpfun") and d["venues"].get("raydium_clmm")
                    ) and 0 <= (rd - pf) <= T["migWindowSec"]
        items.append({"chain": "solana", "key": mint, "sym": None,
                      "first": ts[0], "last": ts[-1], "n": len(ts),
                      "t5": t5, "t60": t60, "t1440": t1440,
                      "u60": 0, "u1440": 0, "accel": round(accel, 3),
                      "score": round(score, 2),
                      "venues": sorted(d["venues"].keys()),
                      "migrated": bool(migrated)})
    return items


def finalize(items):
    SC = CFG["scan"]
    T = CFG["tiers"]
    # per-chain percentile ranks among ACTIVE tokens (recent events or migrated)
    by = {}
    for it in items:
        by.setdefault(it["chain"], []).append(it)
    out_items = []
    for chain, lst in by.items():
        active = [it for it in lst if it["t60"] >= SC["minT1h"] or it["migrated"]]
        ranked = sorted(active, key=lambda x: x["score"], reverse=True)
        pool = max(len(ranked) - 1, 1)
        for i, it in enumerate(ranked):
            it["pct"] = round(100 * (1 - i / pool), 1)
        out_items.extend(lst)

    sym_count = {}
    for it in out_items:
        if it["sym"]:
            sym_count[it["sym"].upper()] = sym_count.get(it["sym"].upper(), 0) + 1

    for it in out_items:
        age = NOWT - it["first"]
        it["ageSec"] = int(age)
        it["dupSize"] = sym_count.get((it["sym"] or "").upper(), 0) or 1
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
    return out_items


def emit(items):
    cats = {}
    tops = {}
    for it in items:
        if it["topTier"] is None:
            continue
        cats.setdefault(it["chain"], {}).setdefault(it["topTier"], []).append({
            "key": it["key"], "sym": it["sym"], "t5": it["t5"], "t60": it["t60"],
            "accel": it["accel"], "score": it["score"], "pct": it["pct"],
            "dupSize": it["dupSize"], "ageSec": it["ageSec"]})
    for chain in ("robinhood", "solana"):
        ch = sorted([i for i in items if i["chain"] == chain and i["topTier"]],
                    key=lambda x: x["score"], reverse=True)[:CFG["scan"]["topN"]]
        tops[chain] = [{"key": it["key"], "sym": it["sym"], "score": it["score"],
                        "topTier": it["topTier"], "t5": it["t5"], "t60": it["t60"],
                        "u60": it["u60"], "accel": it["accel"], "pct": it["pct"],
                        "dupSize": it["dupSize"], "venues": it["venues"]} for it in ch]
    doc = {"asOf": NOW.isoformat(), "scan": CFG["scan"], "categories": cats, "top": tops,
           "counts": {"robinhood": len([i for i in items if i["chain"] == "robinhood"]),
                      "solana": len([i for i in items if i["chain"] == "solana"]),
                      "migrated": len([i for i in items if i["migrated"]])}}
    p = os.path.join(FD, "alpha-intel.json")
    with open(p + ".tmp", "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(p + ".tmp", p)
    with open(os.path.join(FD, "alpha-intel.jsonl"), "a") as f:
        f.write(json.dumps({k: doc[k] for k in ("asOf", "counts")}) + "\n")
    return doc


def main():
    rh, sol = collect()
    items = analyze(rh, sol)
    items = finalize(items)
    doc = emit(items)
    c = doc["counts"]
    print("🧠 ALPHA INTEL @ %s | rh=%d sol=%d migrated=%d" % (
        NOW.isoformat()[:19], c["robinhood"], c["solana"], c["migrated"]))
    for chain in ("robinhood", "solana"):
        top = doc["top"].get(chain) or []
        if not top:
            continue
        print("  %s TOP:" % chain)
        for it in top[:8]:
            print("    [%s] %s %s score=%s t5=%s t60=%s u60=%s accel=%s dup=%s" % (
                it["topTier"], it["sym"] or it["key"][:10],
                (it["key"][:12] if it["sym"] else ""),
                it["score"], it["t5"], it["t60"], it["u60"], it["accel"], it["dupSize"]))
    print("  saved ->", os.path.join(FD, "alpha-intel.json"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("alpha_intel error:", e)
        sys.exit(1)



