#!/usr/bin/env python3
"""rh_potential.py — ROBINHOOD-CHAIN POTENTIAL-COIN SHORTLIST (research only).

Boss directive 2026-09-05: the hunter is blind to RH's many coins. This module
wires RH trending/gainers/new (+ holder/volume data) into the dashboard as a
potential-coin shortlist. NO auto-trade: it only reads and republishes.

Source of truth = the fresh feed registry (feedmerge already scores every RH
token: t5/t60 windows, u60 = unique holders/1h, accel, score, tier). Quotes
(stables/natives) excluded. Output -> data/live/feed/rh-potential.json
"""
import datetime
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "data", "live", "feed")
LIVE = os.path.join(ROOT, "data", "live")
OUT = os.path.join(FD, "rh-potential.json")
TIERS = ["trending", "gainer", "new", "watch"]
CAP = {"trending": 12, "gainer": 12, "new": 12, "watch": 8}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def main():
    coins = load(os.path.join(FD, "coins.json"), {}) or {}
    reg_age = None
    try:
        t = datetime.datetime.fromisoformat(str(coins.get("asOf")).replace("Z", "+00:00"))
        reg_age = int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds())
    except Exception:
        pass
    meta = (load(os.path.join(FD, "rh_alpha.json"), {}) or {}).get("tokenMeta") or {}
    assets = load(os.path.join(LIVE, "rh-assets.json"), {}) or {}
    quotes = set((assets.get("natives") or []) + (assets.get("stables") or []))
    equities = set(assets.get("equities") or [])
    out = {"asOf": now_iso(), "registryAgeSec": reg_age, "source": "feed registry (robinhood)",
           "note": "RESEARCH ONLY - potential RH coins shortlist. NO auto-trade.",
           "tiers": {}, "count": 0}
    top = (coins.get("top") or {}).get("robinhood") or []
    seen = set()
    for it in top:
        tier = it.get("topTier")
        if tier not in TIERS or it.get("key") in seen:
            continue
        sym = (it.get("sym") or "").upper()
        if sym in quotes:
            continue
        seen.add(it.get("key"))
        row = {
            "key": it.get("key"),
            "sym": it.get("sym"),
            "type": "equity" if sym in equities else "coin",
            "topTier": tier,
            "t5": it.get("t5"),
            "t60": it.get("t60"),
            "u60": it.get("u60"),
            "accel": it.get("accel"),
            "score": it.get("score"),
            "pct": it.get("pct"),
            "decimals": (meta.get(str(it.get("key")).lower()) or {}).get("decimals"),
        }
        out["tiers"].setdefault(tier, []).append(row)
        out["count"] += 1
    for tier in TIERS:
        rows = out["tiers"].get(tier) or []
        rows.sort(key=lambda x: x.get("score") or 0, reverse=True)
        out["tiers"][tier] = rows[: CAP.get(tier, 12)]

    # Pons v2 live-fillable PASS candidates -> extra research tier (fresh scan preferred).
    # Fillability_scan ignores this tier (its gate stays with scripts/pons_live_fill.cjs).
    pl = []
    fresh_ref = None
    ff = os.path.join(FD, "pons-live-fresh.json")
    if os.path.exists(ff):
        try:
            fj = json.load(open(ff))
            fresh_ref = fj.get("asOf")
            for c in fj.get("rows") or []:
                tk = str(c.get("token") or "")
                if not tk.lower().startswith("0x"):
                    continue
                pl.append({"key": tk.lower(), "sym": tk[:6] + "…", "type": c.get("type") or "pons-native",
                           "topTier": "pons-live", "curve": c.get("curve"), "native": c.get("type") != "pons-usdg",
                           "tokensOut5": c.get("t5"), "t20": c.get("t20"), "impactPct": c.get("impactPct"),
                           "t5": None, "t60": None, "u60": None, "accel": None, "score": 0, "pct": None})
        except Exception:
            pl = []
    if not pl:
        # fallback: cached research scans (native pass list + USDG real-holder replay)
        try:
            cf = max(glob.glob(os.path.join(ROOT, "research", "pons-live-pass-candidates-*.json")))
            cands = json.load(open(cf))
            for c in (cands or {}).get("passCandidates") or []:
                tk = str(c.get("token") or "")
                if not tk.lower().startswith("0x"):
                    continue
                pl.append({"key": tk.lower(), "sym": tk[:6] + "…", "type": "pons-native", "topTier": "pons-live",
                           "curve": c.get("curve"), "native": True, "tokensOut5": c.get("tokensOut"),
                           "t5": None, "t60": None, "u60": None, "accel": None, "score": 0, "pct": None})
            try:
                uf = max(glob.glob(os.path.join(ROOT, "research", "pons-usdg-pair-replay-*.json")))
                for c in (json.load(open(uf)).get("rows") or []):
                    if c.get("verdict") != "PASS":
                        continue
                    tk = str(c.get("token") or "")
                    d = c.get("detail") or {}
                    if not tk.lower().startswith("0x"):
                        continue
                    pl.append({"key": tk.lower(), "sym": tk[:6] + "…", "type": "pons-usdg", "topTier": "pons-live",
                               "curve": c.get("curve"), "native": False, "tokensOut5": d.get("tokensOut"),
                               "t5": None, "t60": None, "u60": None, "accel": None, "score": 0, "pct": None})
            except Exception:
                pass
        except Exception:
            pass
    if pl:
        pl.sort(key=lambda x: -(int(x.get("tokensOut5") or 0)))
        pl = pl[:80]
        out["tiers"]["pons-live"] = pl
        out["count"] += len(pl)
        out["ponsLive"] = {"n": len(pl),
                           "refreshedAt": fresh_ref or now_iso(),
                           "note": "sim PASS (real eth_call, zero funds); freshness re-scan via node scripts/pons_size_scan.cjs"}

    with open(OUT + ".tmp", "w") as f:
        json.dump(out, f, indent=1)
    os.replace(OUT + ".tmp", OUT)
    print("rh-potential @ %s | registryAge=%s | trending=%d gainer=%d new=%d watch=%d" % (
        now_iso()[:19], reg_age,
        len(out["tiers"].get("trending") or []), len(out["tiers"].get("gainer") or []),
        len(out["tiers"].get("new") or []), len(out["tiers"].get("watch") or [])))


if __name__ == "__main__":
    main()
