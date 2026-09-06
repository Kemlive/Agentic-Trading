#!/usr/bin/env python3
"""px.py — resilient token price checker (read-only).

Fixes the two failure modes seen on 2026-09-05:
  1. DexScreener 403 when no browser User-Agent is sent  -> always send UA.
  2. No single source is reliable                        -> ordered fallback chain:
        DexScreener -> GeckoTerminal -> Jupiter (price v1 legacy).

Usage:
    python3 scripts/px.py <mint> [more mints...]

Prints price + source for each mint. Only reads public APIs.
"""
import json
import sys
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}


def _get_json(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def price_dexscreener(mint):
    d = _get_json("https://api.dexscreener.com/latest/dex/tokens/" + mint)
    best = None
    for pair in d.get("pairs") or []:
        if pair.get("chainId") != "solana":
            continue
        liq = (pair.get("liquidity") or {}).get("usd") or 0
        if not best or liq > best[0]:
            best = [liq, pair]
    if best:
        return float(best[1].get("priceUsd") or 0), "dexscreener"
    return None, None


def price_gecko(mint):
    d = _get_json("https://api.geckoterminal.com/api/v2/networks/solana/tokens/" + mint)
    at = (d.get("data") or {}).get("attributes") or {}
    px = at.get("price_usd")
    if px is not None:
        return float(px), "geckoterminal"
    return None, None


def price_jup(mint):
    d = _get_json("https://quote-api.jup.ag/v6/price?ids=" + mint)
    info = ((d.get("data") or {}).get(mint)) or {}
    px = info.get("price")
    if px is not None:
        return float(px), "jupiter"
    return None, None


def get_price(mint):
    for fn in (price_dexscreener, price_gecko, price_jup):
        try:
            px, src = fn(mint)
            if px and px > 0:
                return px, src
        except Exception:
            continue
    return None, None


def main():
    mints = sys.argv[1:]
    if not mints:
        print("usage: px.py <mint> [...]")
        return 1
    for mint in mints:
        px, src = get_price(mint)
        if px:
            print("%s\t%.8f\tvia %s" % (mint, px, src))
        else:
            print("%s\tNO PRICE from any source" % mint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
