#!/usr/bin/env python3
"""gecko-feed.py - independent market-data cross-check via GeckoTerminal (public API, no key).

Usage:
  python3 scripts/gecko-feed.py <solana-mint>     # print token + top-pool metrics as JSON
  python3 scripts/gecko-feed.py <mint> --json-file /tmp/x.json

Returns price, fdv, liq (top pool reserve), h24 vol, and m5/h1/h6/h24 % changes so the
scanner/autopilot can cross-check DexScreener instead of trusting one provider.
"""
import json
import sys
import urllib.request

BASE = "https://api.geckoterminal.com/api/v2/networks/solana"


def gget(path):
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": "agentic-trading/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def token_metrics(mint):
    d = gget("/tokens/" + mint)
    a = (d.get("data") or {}).get("attributes") or {}
    return {
        "gecko_found": True,
        "price_usd": f(a.get("price_usd")),
        "fdv_usd": f(a.get("fdv_usd")),
        "mcap_usd": f(a.get("market_cap_usd")),
        "reserve_usd": f(a.get("total_reserve_in_usd")),
        "chg": {k: f(a.get("price_change_percentage") or {}).get(k) for k in ("m5", "h1", "h6", "h24")} if isinstance(a.get("price_change_percentage"), dict) else None,
    }


def top_pool(mint):
    d = gget("/tokens/" + mint + "/pools?page=1")
    pools = d.get("data") or []
    best = None
    for p in pools:
        at = p.get("attributes") or {}
        r = f(at.get("reserve_in_usd")) or 0
        if best is None or r > best[0]:
            best = (r, at)
    if best is None:
        return None
    at = best[1]
    return {
        "liq_usd": best[0],
        "vol_h24_usd": f((at.get("volume_usd") or {}).get("h24")),
        "pool": at.get("address"),
        "pool_chg": {k: f((at.get("price_change_percentage") or {}).get(k)) for k in ("m5", "h1", "h6", "h24")} if isinstance(at.get("price_change_percentage"), dict) else None,
    }


def main():
    mint = sys.argv[1] if len(sys.argv) > 1 else None
    if not mint:
        print("usage: python3 scripts/gecko-feed.py <solana-mint>")
        return 1
    out = {"mint": mint}
    try:
        out.update(token_metrics(mint))
    except Exception as e:
        out = {"mint": mint, "gecko_found": False, "error": str(e)[:200]}
        print(json.dumps(out))
        return 0
    try:
        tp = top_pool(mint)
        if tp:
            out.update(tp)
    except Exception:
        pass
    jf = "--json-file" in sys.argv
    if jf:
        path = sys.argv[sys.argv.index("--json-file") + 1]
        json.dump(out, open(path, "w"))
    print(json.dumps(out))


if __name__ == "__main__":
    raise SystemExit(main())
