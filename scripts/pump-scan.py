#!/usr/bin/env python3
"""Pump.fun multi-chain paper scanner (READ-ONLY).

Fetches fresh candidates from DexScreener (token boosts + profiles) across
Pump.fun-served networks, pulls live pair metrics per chain, applies the Pump
Trader Agent checklist heuristics, and writes a paper watchlist + report.
NO signing, NO money movement.

Usage:
  python3 scripts/pump-scan.py                # auto: scan all chains present
  python3 scripts/pump-scan.py --chains solana,base,ethereum
  python3 scripts/pump-scan.py 25             # max tokens to enrich
"""
import json
import sys
import time
import os
import urllib.request
import datetime

LIMIT = 25
CHAIN_SPEC = None  # None => auto (all chainIds surfaced by the feeds)
AS_JSON = "--json" in sys.argv
args = sys.argv[1:]
for a in args:
    if a.isdigit():
        LIMIT = int(a)
    elif a == "--all":
        CHAIN_SPEC = "auto"
    elif a.startswith("--chains="):
        CHAIN_SPEC = a.split("=", 1)[1]

BOOSTS = "https://api.dexscreener.com/token-boosts/latest/v1"
PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{}"
TOP_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"
SOL_PAIRS = "https://api.dexscreener.com/latest/dex/pairs/solana"


# ---------------------------------------------------------------------------
# MARKET PHASE ENGINE (Meme Profit Snatcher mindset - NOT CEX rules)
# ---------------------------------------------------------------------------
# One rule: never stop hunting, never chase tops. Everything else auto-switches
# with the tape. CMC Fear&Greed is the phase clock, but each phase runs a
# DIFFERENT snatcher tactic (we never run one static bar):
#   bear  (Fear)      -> hunt RESILIENT SURVIVORS that hold up in the dump and
#                        show buyer support (bs ratio) during the dip.
#   neutral           -> balanced pullback snatch on the standard bar.
#   bull  (Greed)     -> everyone is in = crowded: only CLEAN liquid dips with
#                        buyer support pass; banks happen fast (short exits).
# Trending/narratives stay SOFT context - never the entry reason.
SNATCHER_PHASES = {
    "bear": {"mode": "BEAR_SNATCH", "minFdv": 40000, "minLiq": 15000, "minVol": 15000,
             "minAge": 0.35, "maxAge": 24.0, "maxH1": 120, "maxH6": 300, "maxH24": 800,
             "bsMin": 1.2, "note": "bear hunt - resilient survivors w/ buyer support"},
    "neutral": {"mode": "NEUTRAL_SNATCH", "minFdv": 40000, "minLiq": 20000, "minVol": 20000,
                "minAge": 0.25, "maxAge": 8.0, "maxH1": 100, "maxH6": 200, "maxH24": 500,
                "bsMin": 0.0, "note": "neutral - balanced pullback snatch"},
    "bull": {"mode": "BULL_SNATCH", "minFdv": 45000, "minLiq": 25000, "minVol": 25000,
             "minAge": 0.5, "maxAge": 8.0, "maxH1": 80, "maxH6": 150, "maxH24": 400,
             "bsMin": 1.1, "note": "bull/crowded - clean liq + buyer-supported dips only"},
}
_REGIME_CACHE = {"t": 0, "v": None}
_REGIME_TTL = 300  # seconds - don't hammer CMC every scan

def _cmc_module():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("cmc_feed", os.path.join(here, "cmc-feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def get_regime():
    """Fear & Greed snapshot from CMC. Falls back to NEUTRAL if CMC is down
    (scanner must never die because one feed is unavailable)."""
    now = time.time()
    if _REGIME_CACHE["v"] and now - _REGIME_CACHE["t"] < _REGIME_TTL:
        return _REGIME_CACHE["v"]
    try:
        fg = _cmc_module().fear_greed()
        idx = int(fg.get("index"))
    except Exception:
        fg = {"index": None, "value": ""}
        idx = None
    if idx is None:
        reg = {"index": None, "label": "Neutral", "source": "fallback"}
    elif idx <= 25:
        reg = {"index": idx, "label": "Extreme Fear", "source": "cmc"}
    elif idx <= 45:
        reg = {"index": idx, "label": "Fear", "source": "cmc"}
    elif idx <= 54:
        reg = {"index": idx, "label": "Neutral", "source": "cmc"}
    elif idx <= 75:
        reg = {"index": idx, "label": "Greed", "source": "cmc"}
    else:
        reg = {"index": idx, "label": "Extreme Greed", "source": "cmc"}
    _REGIME_CACHE.update({"t": now, "v": reg})
    return reg


def regime_policy(label):
    """CMC label -> market phase -> SNATCHER TACTIC (auto-switches with the tape).
    Never static: bear hunts survivors, neutral pulls back, bull demands clean
    liquid dips. 'no chasing tops / no green m5' holds in EVERY phase."""
    phase = {"Extreme Fear": "bear", "Fear": "bear",
             "Neutral": "neutral", "Greed": "bull", "Extreme Greed": "bull"}.get(label, "neutral")
    pol = dict(SNATCHER_PHASES[phase])
    pol["phase"] = phase
    return pol


def regime_mode_note(mode):
    return {"BEAR_SNATCH": "bear/washout - resilient survivors w/ buyer support",
            "NEUTRAL_SNATCH": "neutral - balanced pullback snatch",
            "BULL_SNATCH": "bull/crowded - clean liq + buyer-supported dips only"}.get(mode, mode)


def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading-paper/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def addr_from_url(u):
    if not u:
        return None
    return u.rstrip("/").split("/")[-1]


def collect_addresses(chains):
    boosted = set()
    boosted_why = {}
    addrs = {}
    try:
        for b in http_get(BOOSTS) or []:
            ch = b.get("chainId")
            a = b.get("tokenAddress")
            if not ch or not a:
                continue
            if chains is not None and ch not in chains:
                continue
            key = (ch, a)
            boosted.add(key)
            boosted_why[key] = (b.get("description") or "")[:80]
    except Exception:
        pass
    try:
        for p in http_get(PROFILES) or []:
            ch = p.get("chainId")
            a = p.get("tokenAddress") or addr_from_url(p.get("url"))
            if not ch or not a:
                continue
            if chains is not None and ch not in chains:
                continue
            key = (ch, a)
            if key not in addrs:
                addrs[key] = {"chain": ch, "boosted": key in boosted,
                              "why": boosted_why.get(key, "")}
    except Exception:
        pass
    # boosts that never appeared in profiles also count as candidates
    for (ch, a) in boosted:
        key = (ch, a)
        if key not in addrs:
            addrs[key] = {"chain": ch, "boosted": True, "why": boosted_why.get(key, "")}
    # top-voted boosts (second discovery list) - same boost payload shape
    try:
        for b in http_get(TOP_BOOSTS) or []:
            ch = b.get("chainId")
            a = b.get("tokenAddress")
            if not ch or not a:
                continue
            if chains is not None and ch not in chains:
                continue
            key = (ch, a)
            if key not in addrs:
                addrs[key] = {"chain": ch, "boosted": True,
                              "why": "top-voted:" + (b.get("description") or "")[:60]}
    except Exception:
        pass
    # GECKO VOLUME-RANKED POOLS (real-liquidity discovery) - micro-cap band only.
    # Base token address lives in relationships.base_token.data.id ("solana/<addr>").
    if chains is None or "solana" in chains:
        try:
            extras = 0
            for page in ("1", "2"):
                if extras >= 60:
                    break
                g = http_get("https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=h24_volume_usd_desc&include=base_token&page=" + page)
                for pool in (g or {}).get("data") or []:
                    if extras >= 60:
                        break
                    rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
                    a = str(rel.get("id") or "").split("/")[-1]
                    if not a or a == "None":
                        continue
                    key = ("solana", a)
                    if key in addrs:
                        continue
                    at = pool.get("attributes") or {}
                    try:
                        liq = float(at.get("reserve_in_usd") or 0)
                        vol = float(((at.get("volume_usd") or {}).get("h24")) or 0)
                        fdv = float(at.get("fdv_usd") or 0)
                        h1 = float(((at.get("price_change_percentage") or {}).get("h1")) or 0)
                    except Exception:
                        continue
                    if liq < 12000 or vol < 10000 or not (20000 <= fdv <= 600000) or not (-40 <= h1 <= 200):
                        continue
                    addrs[key] = {"chain": "solana", "boosted": False, "why": "gecko-vol($%.0f)" % vol,
                                  "liq_est": liq}
                    extras += 1
        except Exception:
            pass
    return addrs


def pick_pair(pairs, chain):
    best = None
    for pr in pairs or []:
        if pr.get("chainId") != chain:
            continue
        try:
            v = float((pr.get("volume") or {}).get("h24") or 0)
        except Exception:
            v = 0
        if best is None or v > best[0]:
            best = (v, pr)
    return best[1] if best else None


def age_hours(ms):
    try:
        return (time.time() * 1000 - int(ms)) / 3600000.0
    except Exception:
        return None


def fnum(x):
    try:
        x = float(x)
        if x >= 1000:
            return f"{x:,.0f}"
        return f"{x:.6g}"
    except Exception:
        return "n/a"


def analyze(addr, meta):
    chain = meta.get("chain") or "unknown"
    row = {"token": addr, "chain": chain, "boosted": meta.get("boosted"), "why": meta.get("why")}
    try:
        d = http_get(TOKEN.format(addr))
    except Exception:
        row["error"] = "no dex data"
        return row
    pr = pick_pair(d.get("pairs"), chain)
    if not pr:
        row["error"] = "no solana pair"
        return row
    base = pr.get("baseToken") or {}
    row["symbol"] = base.get("symbol")
    row["name"] = base.get("name")
    row["dex"] = pr.get("dexId")
    row["url"] = pr.get("url")
    try:
        row["priceUsd"] = float(pr.get("priceUsd"))
    except Exception:
        row["priceUsd"] = None
    try:
        row["fdv"] = float(pr.get("fdv") or 0)
    except Exception:
        row["fdv"] = None
    try:
        row["liqUsd"] = float((pr.get("liquidity") or {}).get("usd") or 0)
    except Exception:
        row["liqUsd"] = None
    vol = pr.get("volume") or {}
    chg = pr.get("priceChange") or {}
    txns = pr.get("txns") or {}
    for k in ("m5", "h1", "h6", "h24"):
        try:
            row[f"vol_{k}"] = float(vol.get(k)) if vol.get(k) is not None else None
        except Exception:
            row[f"vol_{k}"] = None
        row[f"chg_{k}"] = chg.get(k)
    try:
        b = (txns.get("h1") or {}).get("buys") or 0
        s = (txns.get("h1") or {}).get("sells") or 0
        row["buy_sell_h1"] = round(b / s, 2) if s else None
        bm = (txns.get("m5") or {}).get("buys") or 0
        sm = (txns.get("m5") or {}).get("sells") or 0
        row["buy_sell_m5"] = round(bm / sm, 2) if sm else None
    except Exception:
        pass
    row["ageH"] = age_hours(pr.get("pairCreatedAt"))
    row["created"] = pr.get("pairCreatedAt")
    # checklist heuristics
    flags = []
    age = row["ageH"]
    if age is None:
        flags.append("age unknown")
    elif age < 0.25:
        flags.append("VERY NEW (<15m) - wait for pattern")
    elif age > 48:
        flags.append("old (>48h)")
    if row.get("buy_sell_m5") is not None and row["buy_sell_m5"] < 0.4:
        flags.append("sell pressure (m5)")
    try:
        v1 = float(vol.get("h1") or 0)
        if row.get("fdv") and row["fdv"] > 0 and v1 / row["fdv"] < 0.03:
            flags.append("weak h1 volume vs mcap")
    except Exception:
        pass
    if row.get("chg_m5") is not None and row["chg_m5"] > 150:
        flags.append("m5 pump >150% (chase risk)")
    if row.get("liqUsd") is not None and row["liqUsd"] < 2000:
        flags.append("thin liquidity <$2k")
    if row.get("boosted"):
        flags.append("PAID BOOST - extra scrutiny")
    row["flags"] = flags
    if "error" in row:
        row["verdict"] = "SKIP (no data)"
    elif any("VERY NEW" in f for f in flags) and any("chase" in f for f in flags):
        row["verdict"] = "SKIP (fomo)"
    elif row.get("buy_sell_m5") is not None and row["buy_sell_m5"] < 0.5:
        row["verdict"] = "SKIP (dumping)"
    elif age is not None and age < 0.25:
        row["verdict"] = "WATCH (too new)"
    elif any("chase" in f for f in flags):
        row["verdict"] = "WATCH (chase risk)"
    else:
        row["verdict"] = "PAPER CANDIDATE"
    return row


def phase_label(r):
    dex = r.get("dex") or ""
    fdv = r.get("fdv") or 0
    liq = r.get("liqUsd") or 0
    age = r.get("ageH")
    chg1 = r.get("chg_h1")
    bs = r.get("buy_sell_m5") or 0
    try:
        chg1 = float(chg1)
    except Exception:
        chg1 = None
    pool = (liq and liq > 0) or dex in ("pumpswap", "raydium")
    if pool:
        if age is not None and age < 24:
            if 50000 <= fdv <= 90000:
                main = "GRADUATING/NEW-POOL"
            elif fdv > 90000:
                main = "MIGRATED"
            else:
                main = "EARLY-MIGRATED"
        else:
            main = "MIGRATED"
    else:
        main = "ON-CURVE climbing" if fdv >= 20000 else "ON-CURVE early"
    alpha = " | ALPHA-MOMENTUM" if (chg1 is not None and chg1 > 80 and bs > 1.5 and liq and liq > 10000) else ""
    return main + alpha


def main():
    chains = None
    if CHAIN_SPEC == "auto":
        chains = None
    elif CHAIN_SPEC:
        chains = {c.strip() for c in CHAIN_SPEC.split(",") if c.strip()}
    addrs = collect_addresses(chains)
    if not addrs:
        print("no candidates found right now")
        return
    # bias enrichment: core (profiles/boosts) first, then feed tokens ranked by est.
    # liquidity/volume desc (they are the most likely to pass the liq floors), cap total requests
    def _enrich_key(kv):
        est = (kv[1] or {}).get("liq_est")
        return (0 if est is None else 1, -(float(est or 0.0)))
    rows = []
    for (ch_addr, meta) in sorted(addrs.items(), key=_enrich_key)[:LIMIT]:
        addr = ch_addr[1]
        rows.append(analyze(addr, meta))
        time.sleep(0.15)
    rows = [r for r in rows if "error" not in r]
    # --- apply market regime to the scan results (Meme Profit Snatcher gate) ---
    regime = get_regime()
    pol = regime_policy(regime["label"])
    for r in rows:
        r["regime"] = regime["label"]
        r["regimeMode"] = pol["mode"]
        r["regimePhase"] = pol.get("phase")
        r["regimeBar"] = {k: pol[k] for k in ("minFdv", "minLiq", "minVol", "minAge", "maxAge",
                                              "maxH1", "maxH6", "maxH24", "bsMin")}
    cands = [r for r in rows if r.get("verdict") == "PAPER CANDIDATE"]
    cands.sort(key=lambda r: (r.get("fdv") or 0), reverse=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    chains_seen = sorted({r.get("chain") for r in rows})
    report = {"scannedAt": stamp, "regime": {"label": regime["label"], "index": regime.get("index"),
                                             "phase": pol.get("phase"), "mode": pol["mode"],
                                             "note": regime_mode_note(pol["mode"]),
                                             "bar": {k: pol[k] for k in ("minFdv", "minLiq", "minVol", "minAge",
                                                                          "maxAge", "maxH1", "maxH6", "maxH24", "bsMin")}},
              "count": len(rows), "chains": chains_seen,
              "candidates": cands, "all": rows}
    if AS_JSON:
        print(json.dumps(report, indent=2))
        return
    print(f"PAPER SCAN {stamp} | {len(addrs)} tokens on {len(chains_seen)} chains "
          f"({', '.join(chains_seen)}) | {len(cands)} paper candidates\n")
    print(f"PHASE: {regime['label']} (idx {regime.get('index')}) -> {pol['mode']} | {pol['note']}\n")
    for r in cands[:20]:
        print(f"{r.get('symbol','?'):12s} @{r.get('chain','?'):10s} fdv=${fnum(r.get('fdv')):>12s} "
              f"liq=${fnum(r.get('liqUsd')):>10s} h1vol=${fnum(r.get('vol_h1')):>10s} "
              f"chg1h={r.get('chg_h1')} bs_m5={r.get('buy_sell_m5')} "
              f"age={None if r.get('ageH') is None else round(r['ageH'],2)}h")
        print(f"    flags: {', '.join(r['flags']) or 'none'} | {r['url']}")
    # phase map: group candidates by lifecycle + flag alpha
    groups = {}
    for r in cands:
        lab = phase_label(r)
        main = lab.split(" | ")[0]
        groups.setdefault(main, []).append(r)
    print("\n=== PHASE MAP (candidates) ===")
    for main, rs in sorted(groups.items()):
        syms = ", ".join(f"{r.get('symbol')}" for r in rs[:8])
        alpha_n = sum(1 for r in rs if "ALPHA" in phase_label(r))
        print(f"  {main}: {len(rs)}  [{syms}]  alpha={alpha_n}")
    # coin comparison (keyless proxies; true holder counts need an indexer API key)
    liquid = sorted([r for r in cands if (r.get("liqUsd") or 0) >= 5000],
                    key=lambda r: r["liqUsd"], reverse=True)
    active = sorted([r for r in cands if (r.get("buy_sell_h1") or 0) is not None],
                    key=lambda r: (r.get("buy_sell_h1") or 0), reverse=True)
    print("\n=== COIN COMPARISON ===")
    if liquid:
        print("MOST HELD/LIQUID (value locked in pool): " + ", ".join(
            f"{r['symbol']}@{r.get('chain')} ${r['liqUsd']:,.0f}" for r in liquid[:5]))
    if active:
        print("MOST TRADED (h1 buy:sell participation proxy): " + ", ".join(
            f"{r['symbol']}@{r.get('chain')} bs={r.get('buy_sell_h1')}" for r in active[:5]))
    fn = f"data/pump-scan-{stamp}.json"
    with open(fn, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nsaved: {fn}")


if __name__ == "__main__":
    main()

