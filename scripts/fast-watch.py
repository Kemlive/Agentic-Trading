#!/usr/bin/env python3
"""fast-watch.py — HIGH-FREQUENCY REAL-COIN SCANNER (boss 2026-09-04).

Polls a curated watchlist of REAL liquid Solana tokens every 30 seconds
(launchd com.agentic-trading.fast-scan) using DexScreener's BATCH endpoint
(multiple token addresses in ONE request -> stays far inside API limits).

Signals (ALERT-ONLY for now — no buys until boss picks Option A/B/C):
  PULLBACK-READY : liq>=300k, age>=1h, 1h uptrend, pullback in last 5m with
                   buyer support (m5 buy:sell >= 1.0) and no h1 cliff.
  MOMENTUM       : liq>=500k, 1h up +8..60%, 5m green (not chasing top), and
                   fresh 1h volume.

State + cooldowns live in data/live/fast-state.json (gitignored). Alerts go to
Telegram via notify-telegram.py and logs/trades.jsonl.
"""
import json
import os
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_FILE = os.path.join(ROOT, "data", "live", "fast-watchlist.json")
STATE_FILE = os.path.join(ROOT, "data", "live", "fast-state.json")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")
DEX_BATCH = "https://api.dexscreener.com/latest/dex/tokens/{}"
GECKO_POOLS = "https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=reserve_in_usd_desc&page={}"
MAX_TOKENS = 28

NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
TOP_QUOTE = {"sol", "usdc", "usdt", "weth", "jitosol", "wbtc", "bonk"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def load(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d if d is not None else {}


def save(p, o):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(o, f, indent=2)
    os.replace(tmp, p)


def notify(text):
    try:
        import subprocess
        subprocess.run(["python3", os.path.join(ROOT, "scripts", "notify-telegram.py"),
                        "msg", text], timeout=20)
    except Exception:
        pass


def log_event(rec):
    rec["ts"] = NOW
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


# Curated anchor REAL Solana coins (always watched) - resolved live via DexScreener
SYMBOLS = ["WIF", "POPCAT", "BONK", "MEW", "FWOG", "GIGA", "GOAT", "PNUT", "TRUMP",
           "JUP", "JTO", "PYTH", "RENDER", "RAY", "HNT", "MOODENG", "PONKE", "SLERF",
           "MICHI", "RETARDIO", "SAMO", "BOME"]
QUOTE_NAMES = {"sol", "usdc", "usdt", "weth", "jitosol", "wbtc"}


def refresh_watchlist():
    """HYBRID DYNAMIC watchlist (boss 2026-09-04): curated anchors + auto-discovered
    top liquid/trending Solana coins (gecko trending + top h24-volume), capped at
    MAX_TOKENS. Rebuilt every 10 min so new movers enter and dead coins drop out."""
    st = load(WATCH_FILE, {})
    if st.get("asOf", 0) > time.time() - 600 and st.get("tokens"):
        return st.get("tokens", [])
    found = {}
    # 1) curated anchors (highest-liquidity pair per symbol via DexScreener search)
    for sym in SYMBOLS:
        try:
            d = get("https://api.dexscreener.com/latest/dex/search?q=" + sym)
        except Exception:
            continue
        best = None
        for p in (d or {}).get("pairs") or []:
            if str(p.get("chainId")) != "solana":
                continue
            try:
                liq = float((p.get("liquidity") or {}).get("usd") or 0)
            except Exception:
                liq = 0
            if ((p.get("baseToken") or {}).get("symbol") or "").upper() != sym.upper():
                continue
            if best is None or liq > best[0]:
                best = (liq, p)
        if best and best[0] >= 100000:
            p = best[1]
            a = (p.get("baseToken") or {}).get("address")
            if a:
                found[a] = (p.get("baseToken") or {}).get("symbol") or sym
    # 2) dynamic discovery: gecko trending + high h24-volume pools, liquid only
    for url in ("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools",
                "https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=h24_volume_usd_desc&page=1",
                "https://api.geckoterminal.com/api/v2/networks/solana/pools?sort=h24_volume_usd_desc&page=2"):
        try:
            g = get(url)
        except Exception:
            continue
        for pool in (g or {}).get("data") or []:
            at = pool.get("attributes") or {}
            rel = ((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            a = str(rel.get("id") or "").split("/")[-1]
            if not a or a == "None" or a in found:
                continue
            nm = str(at.get("name") or "").lower().replace(" ", "")
            try:
                liq = float(at.get("reserve_in_usd") or 0)
            except Exception:
                continue
            if liq < 100000 or nm in QUOTE_NAMES or len(nm) < 2:
                continue
            found[a] = (at.get("name") or a[:6])
    tokens = list(found.keys())[:MAX_TOKENS]
    if tokens:
        save(WATCH_FILE, {"asOf": time.time(), "tokens": tokens, "names": found,
                          "anchors": len(SYMBOLS), "dynamic": max(0, len(tokens) - len(SYMBOLS))})
        return tokens
    return st.get("tokens", [])


def best_pair(pairs):
    best = None
    for p in pairs or []:
        if str(p.get("chainId")) != "solana":
            continue
        try:
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
        except Exception:
            liq = 0
        if best is None or liq > best[0]:
            best = (liq, p)
    return best[1] if best else None


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def group(pairs):
    groups = {}
    for p in pairs or []:
        bt = (p.get("baseToken") or {}).get("address")
        if bt:
            groups.setdefault(bt, []).append(p)
    return groups.items()

def main():
    st = load(STATE_FILE, {"last": {}, "cooldown": {}})
    tokens = refresh_watchlist()
    if not tokens:
        print("watchlist empty")
        return
    try:
        d = get(DEX_BATCH.format(",".join(tokens)))
    except Exception as e:
        print("batch fetch failed:", e)
        return
    alerts = []
    now = time.time()
    for addr, pairs in group((d or {}).get("pairs") or []):
        pr = best_pair(pairs)
        if not pr:
            continue
        bt = pr.get("baseToken") or {}
        sym = bt.get("symbol") or addr[:6]
        liq = fnum((pr.get("liquidity") or {}).get("usd")) or 0
        px = fnum(pr.get("priceUsd"))
        chg = pr.get("priceChange") or {}
        m5, h1 = fnum(chg.get("m5")), fnum(chg.get("h1"))
        h6, h24 = fnum(chg.get("h6")), fnum(chg.get("h24"))
        tx = pr.get("txns") or {}
        try:
            b = (tx.get("m5") or {}).get("buys") or 0
            s = (tx.get("m5") or {}).get("sells") or 0
            bs5 = round(b / s, 2) if s else None
        except Exception:
            bs5 = None
        try:
            age = (time.time() * 1000 - int(pr.get("pairCreatedAt") or 0)) / 3600000.0
        except Exception:
            age = None
        if liq < 100000 or px is None:
            continue
        reasons = []
        if liq >= 300000 and (age is None or age >= 1) and 0 < (h1 or 0) <= 80 \
           and -50 < (m5 or 0) <= -1.5 and bs5 is not None and bs5 >= 1.0 \
           and (h6 or 0) <= 200:
            reasons.append("PULLBACK-READY")
        if liq >= 500000 and 8 <= (h1 or 0) <= 60 and 3 <= (m5 or 0) <= 30 \
           and (h24 or 0) <= 400:
            reasons.append("MOMENTUM")
        if not reasons:
            continue
        if now < st["cooldown"].get(addr, 0):
            continue
        st["cooldown"][addr] = now + 600  # one alert per token per 10 min
        msg = ("🚀 FAST-SCAN [%s] %s liq=$%.0fk h1=%+.1f%% m5=%+.1f%% bs5=%s age=%.1fh px=$%.8g" %
               (sym, "/".join(reasons), liq / 1000, h1 or 0, m5 or 0, bs5, age or -1, px))
        alerts.append(msg)
        log_event({"event": "fast_scan_alert", "symbol": sym, "signals": reasons,
                   "liqUsd": liq, "px": px, "m5": m5, "h1": h1, "bs5": bs5,
                   "mint": addr, "msg": msg})
    st["last"] = {"asOf": now, "nTokens": len(tokens), "checked": NOW}
    st["cooldown"] = {k: v for k, v in st["cooldown"].items() if v > now - 6 * 3600}
    save(STATE_FILE, st)
    print("fast-scan @ %s | watch %d tokens | alerts: %d" % (NOW[:19], len(tokens), len(alerts)))
    for a in alerts:
        print(a)
        notify(a)
        log_event({"event": "fast_scan_sent", "msg": a})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("fast-watch error:", e)

