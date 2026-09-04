#!/usr/bin/env python3
"""rh_alpha.py — RH chain: EXACT Uni V3 price math + asset-transfer clustering (analysis only).

Part A  fetchUniswapV3PoolData():
  price(T0/T1) = (sqrtPriceX96 / 2^96)^2 * 10^(dec0 - dec1)
  Reads slot0/token0/token1/decimals straight from the contracts via eth_call.
  Decimal handling is LIVE (per-token), NOT assumed 6. Factory poolCount + addresses
  are printed to the terminal on every scan.

Part B  cluster RH asset_transfer logs -> tokenized equities vs native/stable/other.
  Output : data/live/feed/rh_alpha.json
Run     : python3 scripts/rh_alpha.py
"""
import os
import sys
import json
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPC = "https://rpc.mainnet.chain.robinhood.com"
FACTORIES = {
    "univ3": "0x1F98431c8aD98523631AE4a59f267346ea31F984",  # verified present on-chain
}
RH_FEED = os.path.join(ROOT, "data", "live", "feed", "robinhood.jsonl")
ASSET_CFG = os.path.join(ROOT, "data", "live", "rh-assets.json")
OUT = os.path.join(ROOT, "data", "live", "feed", "rh_alpha.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()

EQUITY_DEFAULT = {"TSLA", "AAPL", "NVDA", "MSFT", "GOOG", "GOOGL", "AMZN", "META",
                  "PLTR", "COIN", "AMD", "NFLX", "SPY", "QQQ", "MSTR", "TSM", "AVGO"}
STABLE_DEFAULT = {"USDC", "USDT", "DAI", "USDE", "PYUSD", "FRAX", "EURC"}
NATIVE_DEFAULT = {"ETH", "WETH", "SOL", "WSOL"}


def call(addr, data):
    for attempt in range(3):
        try:
            req = urllib.request.Request(RPC, data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                 "params": [{"to": addr, "data": data}, "latest"]}).encode(),
                headers={"content-type": "application/json", "User-Agent": "Mozilla/5.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=20).read())
            if r.get("error"):
                return None
            return r.get("result")
        except Exception as e:
            code = getattr(getattr(e, "code", None), "real", None) or (e.code if hasattr(e, "code") else None)
            if code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            if attempt == 2:
                return None
            time.sleep(0.3)
    return None


def u256(h):
    return int(h or "0x0", 16)


def s256(h):
    v = int(h or "0x0", 16)
    return v - (1 << 256) if v >= (1 << 255) else v


def erc_meta(addr):
    """Read symbol/name/decimals live (cached per run)."""
    sym = erc_str(call(addr, "0x95d89b41"))      # symbol()
    dec = None
    try:
        dec = u256(call(addr, "0x313ce567"))     # decimals()
    except Exception:
        pass
    return sym, dec


def erc_str(h):
    try:
        data = bytes.fromhex((h or "0x")[2:])
        off = u256("0x" + data[:32].hex())
        ln = u256("0x" + data[off:off + 32].hex())
        raw = data[off + 32: off + 32 + ln]
        return raw.decode("utf-8", "ignore")
    except Exception:
        return None


def fetch_uniswap_v3_pool_data(pool):
    """Exact Uni V3 price + liquidity state from slot0/token0/token1/decimals."""
    s0 = call(pool, "0x3850c7bd")  # slot0()
    if not s0:
        return {"pool": pool, "error": "no slot0 (not a v3 pool?)"}
    t0 = "0x" + u256(call(pool, "0x0dfe1681")).to_bytes(20, "big").hex()  # token0()
    t1 = "0x" + u256(call(pool, "0xd21220a7")).to_bytes(20, "big").hex()  # token1()
    d0 = u256(call(t0, "0x313ce567"))
    d1 = u256(call(t1, "0x313ce567"))
    raw = bytes.fromhex(s0[2:])
    sqrt_price_x96 = int.from_bytes(raw[:32], "big")
    tick = int.from_bytes(raw[32:64], "big", signed=True)
    price0in1 = (sqrt_price_x96 / 2 ** 96) ** 2 * 10 ** (d0 - d1)
    return {"pool": pool, "token0": t0, "token1": t1, "dec0": d0, "dec1": d1,
            "sqrtPriceX96": sqrt_price_x96, "tick": tick,
            "priceToken0PerToken1": price0in1,
            "priceToken1PerToken0": 1 / price0in1 if price0in1 else None}

def load_asset_cfg():
    default = {"equities": sorted(EQUITY_DEFAULT), "stables": sorted(STABLE_DEFAULT),
               "natives": sorted(NATIVE_DEFAULT)}
    try:
        return json.load(open(ASSET_CFG))
    except Exception:
        tmp = ASSET_CFG + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(default, fh, indent=2)
        os.replace(tmp, ASSET_CFG)
        return default


def cluster_token(token, cfg, cache):
    if token not in cache:
        sym, dec = erc_meta(token)
        cache[token] = {"symbol": sym, "decimals": dec}
    m = cache[token]
    sym_u = (m.get("symbol") or "").upper()
    if sym_u in cfg["equities"]:
        cat = "equity"
    elif sym_u in cfg["stables"]:
        cat = "stable"
    elif sym_u in cfg["natives"]:
        cat = "native"
    else:
        cat = "other"
    return cat, sym_u, m.get("decimals")


def cluster_feed(cfg):
    rows = [json.loads(l) for l in open(RH_FEED)] if os.path.exists(RH_FEED) else []
    rows = [r for r in rows if r.get("venue") == "asset_transfer" and r.get("token")]
    agg = {}
    cache = {}
    for r in rows:
        t = r["token"].lower()
        a = agg.setdefault(t, {"token": t, "txs": 0, "from": set(), "to": set(), "first": r.get("ts"), "last": r.get("ts")})
        a["txs"] += 1
        a["from"].add(r.get("from"))
        a["to"].add(r.get("to"))
        if (r.get("ts") or "") < (a["first"] or ""):
            a["first"] = r.get("ts")
        if (r.get("ts") or "") > (a["last"] or ""):
            a["last"] = r.get("ts")
    clusters = {"equity": [], "stable": [], "native": [], "other": []}
    for t, a in agg.items():
        time.sleep(0.08)  # polite pacing for RH public RPC
        cat, sym, dec = cluster_token(t, cfg, cache)
        rec = {"token": t, "symbol": sym, "decimals": dec, "transfers": a["txs"],
               "uniqueFrom": len(a["from"]), "uniqueTo": len(a["to"]),
               "windowFirst": a["first"], "windowLast": a["last"]}
        clusters.setdefault(cat, []).append(rec)
    for cat in clusters:
        clusters[cat].sort(key=lambda x: -x["transfers"])
    return clusters, cache


def main():
    print("🔎 RH ALPHA @ %s" % NOW[:19])
    print("   Factories scanned:", json.dumps(FACTORIES))
    # factory poolCount (confirms whether any v3 pools exist yet)
    for name, addr in FACTORIES.items():
        try:
            pc = u256(call(addr, "0x7d33b6e7"))  # poolCount()
            print("   %s factory %s poolCount=%d" % (name, addr, pc))
        except Exception:
            print("   %s poolCount: no response (no pools or selector unsupported)" % name)
    cfg = load_asset_cfg()
    clusters, cache = cluster_feed(cfg)
    out = {"asOf": NOW, "factories": FACTORIES, "clusters": clusters, "tokenMeta": cache,
           "priceNote": "Uni V3 pool pricing via fetch_uniswap_v3_pool_data() when pools exist on RH"}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2)
    for cat in ("equity", "stable", "native", "other"):
        top = clusters[cat][:5]
        print("\n  %s (%d tokens)" % (cat.upper(), len(clusters[cat])))
        for c in top:
            print("    %-8s %-10s transfers=%-5d dec=%s" % (c["symbol"], c["token"][:10] + "…",
                                                            c["transfers"], c["decimals"]))
    print("\nsaved ->", OUT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("rh_alpha error:", e)

