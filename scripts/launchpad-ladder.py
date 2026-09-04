#!/usr/bin/env python3
"""launchpad-ladder.py — TRUSTED-LAUNCHPAD LADDER SCANNER (boss 2026-09-04).

Reads Moonit (ex-Moonshot, audited) directly — BEFORE DexScreener/CMC even list a
coin. Ranks launchpad tokens by potential, not dust:
  TIER A  GRADUATED-LIQUID      - graduated to Raydium/Meteora, real volume
  TIER B  GRADUATION-READY      - curve >90% + momentum (next to graduate)
  TIER C  CURVE-MOMENTUM        - curve <90% but real buys/volume RIGHT NOW
  TIER D  ACTIVE-CURVE          - any on-curve volume (early, watch)
  WATCH   FRESH-DUST            - zero volume new mints (listed, never bought)
Trust flags: isCTO, migrationDex, 9GAG-viral origin, name/symbol in focus list
(PONS / ANSEM / LONG / ... set via --focus or defaults).
Sources: api.mintlp.io/v1/fun (Moonit public endpoints, vanityExtension=moon, SOL).
Usage:
  python3 scripts/launchpad-ladder.py [--focus PONS ANSEM] [--json]
"""
import json
import os
import sys
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "data", "live", "launchpads.json")
OUT = os.path.join(ROOT, "data", "live", "launchpad-ladder.json")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
DEX_BATCH = "https://api.dexscreener.com/latest/dex/tokens/{}"


def load_config():
    """All pads, endpoints, thresholds and focus live in config (no hardcoded assets/
    numbers in code). Written once with defaults if missing."""
    default = {
        "pads": {
            "moonit": {
                "base": "https://api.mintlp.io/v1/fun",
                "params": "vanityExtension=moon&blockchainSymbol=SOL",
                "views": [["NEW", "NOT_GRADUATED"], ["MARKET_CAP", "NOT_GRADUATED"],
                          ["TRENDING", "NOT_GRADUATED"], ["NEW", "GRADUATED"],
                          ["MARKET_CAP", "GRADUATED"], ["TRENDING", "GRADUATED"]]},
            "longyourlongs": {"status": "research",
                              "note": "Solana curve launchpad (we trade the TOKEN only, USDC/SOL on Solana); indexer API pending JS recon"},
            "ansem": {"status": "research", "note": "ansem.io bot-walled (403); recon needed"},
            "pons": {"status": "research", "note": "pons.money bot-walled (403); recon needed"}},
        "ladder": {"tierA_minVol24": 25000, "tierA_minLiq": 100000,
                   "tierA2_minVol24": 5000, "tierA2_minLiq": 40000,
                   "gradA_vol24": 20000, "gradA_vol1": 2000,
                   "gradB2_vol24": 2000, "gradB2_vol1": 500,
                   "curveReadyPct": 9000, "curveMinVol1": 500, "curveMinTx": 3,
                   "buyShareFloor": 0.5, "focus": []}}
    try:
        return json.load(open(CONFIG_FILE))
    except Exception:
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(default, fh, indent=2)
        os.replace(tmp, CONFIG_FILE)
        return default


CFG = load_config()
MOON = CFG["pads"]["moonit"]
BASE = MOON["base"] + "?"
VIEWS = [tuple(v) for v in MOON["views"]]
TH = CFG["ladder"]
FOCUS = list(TH.get("focus") or [])


def dex_pair(pairs):
    best = None
    for p in (pairs or []):
        if str(p.get("chainId")) != "solana":
            continue
        try:
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
        except Exception:
            liq = 0
        if best is None or liq > best[0]:
            best = (liq, p)
    return best[1] if best else None


def dex_enrich(mints):
    """Live DEX stats for graduated/curve coins via DexScreener batch (chunks of 25)."""
    out = {}
    for i in range(0, len(mints), 25):
        chunk = mints[i:i + 25]
        try:
            d = get_json(DEX_BATCH.format(",".join(chunk)))
        except Exception:
            continue
        seen = {}
        for p in (d or {}).get("pairs") or []:
            bt = (p.get("baseToken") or {}).get("address")
            if bt and bt not in seen:
                seen[bt] = []
            if bt:
                seen[bt].append(p)
        for m, pairs in seen.items():
            pr = dex_pair(pairs)
            if not pr:
                continue
            chg = pr.get("priceChange") or {}
            vol = pr.get("volume") or {}
            tx = pr.get("txns") or {}
            try:
                out[m] = {"liq": float((pr.get("liquidity") or {}).get("usd") or 0),
                          "vol1": float(vol.get("h1") or 0),
                          "vol24": float(vol.get("h24") or 0),
                          "px": float(pr.get("priceUsd")),
                          "m5": chg.get("m5"), "h1": chg.get("h1")}
            except Exception:
                continue
    return out


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())


def get(params, page=1, size=50):
    url = BASE + params + "&" + MOON["params"] + "&page=%d&pageSize=%d" % (page, size)
    d = get_json(url)
    return (d.get("data") or []) if isinstance(d, dict) else (d or [])


def f(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def age_h(created):
    try:
        ts = datetime.datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
        return (time.time() - ts) / 3600.0
    except Exception:
        return None


def load_all():
    coins = {}
    for sort, state in VIEWS:
        try:
            items = get("sortBy=%s&state=%s" % (sort, state))
        except Exception:
            continue
        for c in items or []:
            m = c.get("mintAddress") or c.get("id")
            if not m:
                continue
            if m not in coins:  # first source wins; keep it simple
                coins[m] = c
    return list(coins.values())


def classify(c):
    """Return (tier, reasons) for a Moonit coin."""
    mc = f(c.get("marketcap"))
    vol1 = f(c.get("volumeUSD1h"))
    tx1 = f(c.get("transactionCount1h"))
    vol24 = f(c.get("volumeUSD24h"))
    tx24 = f(c.get("transactionCount24h"))
    buy1 = f(c.get("buyVolumeUSD1h"))
    sell1 = f(c.get("sellVolumeUSD1h"))
    prog = f(c.get("progressPercent"))
    grad = str(c.get("state") or "").upper() == "GRADUATED"
    cto = bool(c.get("isCTO"))
    dex = c.get("migrationDex") or ""
    nine = bool(c.get("isFirstNineGagToken"))
    age = age_h(c.get("createdAt"))
    buy_share = buy1 / (buy1 + sell1) if (buy1 + sell1) > 0 else None
    sym = str(c.get("symbol") or "").upper()
    name = str(c.get("name") or "").upper()
    focused = any(k in sym or k in name for k in FOCUS)
    reasons = []
    if focused:
        reasons.append("FOCUS:%s" % sym)
    if cto:
        reasons.append("CTO")
    if nine:
        reasons.append("9GAG-VIRAL")
    if grad:
        reasons.append("GRADUATED:%s" % dex)
    elif prog >= 9000:
        reasons.append("CURVE>90%%")
    if vol1 > 0:
        reasons.append("vol1h=$%.0f tx1h=%.0f buyshare=%s" % (vol1, tx1, ("%.2f" % buy_share) if buy_share else "n/a"))
    # tier
    if grad:
        if vol24 >= TH["gradA_vol24"] and vol1 >= TH["gradA_vol1"]:
            return "A", reasons, mc, vol1, tx1, vol24, buy_share
        if vol24 >= TH["gradB2_vol24"] or vol1 >= TH["gradB2_vol1"]:
            return "B2", reasons, mc, vol1, tx1, vol24, buy_share
        return "D", reasons, mc, vol1, tx1, vol24, buy_share
    if prog >= TH["curveReadyPct"] and (vol1 > 0 or tx1 > 0):
        return "B", reasons, mc, vol1, tx1, vol24, buy_share
    if vol1 >= TH["curveMinVol1"] and tx1 >= TH["curveMinTx"] and (buy_share is None or buy_share >= TH["buyShareFloor"]):
        return "C", reasons, mc, vol1, tx1, vol24, buy_share
    if tx1 >= 1 or vol1 > 0:
        return "D", reasons, mc, vol1, tx1, vol24, buy_share
    if not grad and vol24 == 0 and tx1 == 0 and vol1 == 0:
        return "WATCH", reasons, mc, vol1, tx1, vol24, buy_share
    return "D", reasons, mc, vol1, tx1, vol24, buy_share

def main():
    global FOCUS
    args = sys.argv[1:]
    if args and args[0] == "--pads":
        for name, pad in CFG["pads"].items():
            st = pad.get("status") if "status" in pad else ("live" if "base" in pad else "config")
            print("  %-14s %-10s %s" % (name, st, (pad.get("note") or "")[:80]))
        return
    if "--focus" in args:
        i = args.index("--focus")
        FOCUS = [a.upper() for a in args[i + 1:]]
        args = args[:i]
    coins = load_all()
    if not coins:
        print("launchpad ladder: no coins returned (API down/empty)")
        return
    rows = []
    for c in coins:
        tier, reasons, mc, vol1, tx1, vol24, bs = classify(c)
        rows.append({"symbol": c.get("symbol"), "name": c.get("name"),
                     "mint": c.get("mintAddress"), "state": c.get("state"),
                     "mc": round(mc, 2), "progress": c.get("progressPercent"),
                     "vol1h": round(vol1, 2), "tx1h": int(tx1), "vol24h": round(vol24, 2),
                     "buyShare1h": (round(bs, 3) if bs is not None else None),
                     "migrationDex": c.get("migrationDex"), "isCTO": bool(c.get("isCTO")),
                     "createdAt": c.get("createdAt"), "tier": tier, "why": reasons})
    order = {"A": 0, "A2": 1, "B": 1, "B2": 2, "C": 3, "D": 4, "WATCH": 5}
    # MERGE Moonit trust + live DEX activity (graduates trade on Raydium/Meteora)
    mints = [r["mint"] for r in rows if r["mint"]
             and (str(r["state"]).upper() in ("GRADUATED", "MIGRATED") or r["mc"] >= 30000)][:80]
    dx = dex_enrich(mints) if mints else {}
    for r in rows:
        d2 = dx.get(r["mint"])
        if not d2:
            continue
        r["dex"] = {k: (round(d2[k], 2) if isinstance(d2[k], float) else d2[k])
                    for k in ("liq", "vol1", "vol24", "px", "m5", "h1")}
        if d2["vol24"] >= TH["tierA_minVol24"] and d2["liq"] >= TH["tierA_minLiq"]:
            r["tier"] = "A"
            r["why"].append("DEX24=$%.0f liq=$%.0f" % (d2["vol24"], d2["liq"]))
        elif d2["vol24"] >= TH["tierA2_minVol24"] and d2["liq"] >= TH["tierA2_minLiq"]:
            r["tier"] = "A2"
            r["why"].append("DEX24=$%.0f liq=$%.0f" % (d2["vol24"], d2["liq"]))
        elif r["tier"] == "WATCH" and d2["vol24"] > 0:
            r["tier"] = "D"
            r["why"].append("dex-vol24=$%.0f" % d2["vol24"])
    def _rk(r):
        base = order.get(r["tier"], 9)
        d2 = r.get("dex") or {}
        key = d2.get("vol24", r.get("vol24h") or 0) if r["tier"] in ("A", "A2", "B2") else (d2.get("vol1") or r.get("vol1h") or 0)
        return (base, -float(key))
    rows.sort(key=_rk)
    out = {"asOf": NOW, "totalScanned": len(rows),
           "focus": FOCUS, "rows": rows}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, OUT)
    # console ladder (skip pure dust unless small)
    print("🌱 LAUNCHPAD LADDER (Moonit) @ %s | scanned %d" % (NOW[:19], len(rows)))
    shown = {"A": 0, "A2": 0, "B": 0, "B2": 0, "C": 0}
    for r in rows:
        if r["tier"] in shown and shown[r["tier"]] < 6:
            shown[r["tier"]] += 1
            dxn = r.get("dex") or {}
            dex_s = (" dex24=$%.0f liq=$%.0f" % (dxn["vol24"], dxn["liq"])) if dxn.get("vol24") else ""
            print("  [%s] %-12s mc=$%-10s vol1h=$%-9s tx1h=%-4s prog=%-5s %s %s| %s" %
                  (r["tier"], r["symbol"], ("%.0f" % r["mc"]), ("%.0f" % r["vol1h"]),
                   r["tx1h"], r["progress"], r["mint"][:8] + "…", dex_s,
                   ",".join(r["why"])[:60]))
    focused = [r for r in rows if any("FOCUS:" in w for w in r["why"])]
    for r in focused:
        print("  ⭐FOCUS %-12s tier=%s mc=$%.0f vol1h=$%.0f %s" %
              (r["symbol"], r["tier"], r["mc"], r["vol1h"], ",".join(r["why"])))
    with open(LOG, "a") as fh:
        fh.write(json.dumps({"event": "launchpad_ladder", "ts": NOW,
                             "scanned": len(rows), "focus": FOCUS}) + "\n")
    print("saved:", OUT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("launchpad-ladder error:", e)

