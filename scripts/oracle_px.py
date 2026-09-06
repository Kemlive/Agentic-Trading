#!/usr/bin/env python3
"""oracle_px.py — ON-CHAIN POOL PRICE ORACLE v2 (prototype, read-only).

v1 lesson: generic getTokenAccountsByOwner(pool) fails on Meteora DLMM and
PumpSwap AMM (their vaults are not owned by the pool pubkey).

v2 method (layout-independent):
  1. Discover the main pair for a mint via DexScreener METADATA only (cached).
  2. Fetch the pool account bytes; scan every 8-byte-aligned window for embedded
     pubkeys; resolve them with getMultipleAccounts(jsonParsed).
  3. Keep token accounts that are real vaults: they hold {base mint, or
     WSOL/USDC}, share the SAME authority (owner), and have a balance.
  4. price = quote-vault uiAmount / base-vault uiAmount. No reserve layout used.

Usage:  python3 scripts/oracle_px.py <mint> [mint ...]
"""
import base64
import datetime
import json
import os
import struct
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")
CACHE = os.path.join(FD, "poolmap.json")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "application/json"}
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WSOL = "So11111111111111111111111111111111111111112"

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(b):
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    pad = 0
    for x in b:
        if x == 0:
            pad += 1
        else:
            break
    return "1" * pad + s


def _rpc_url():
    key = open(os.path.expanduser("~/.config/agentic-trading/helius.key")).read().strip()
    return "https://mainnet.helius-rpc.com/?api-key=" + key


def rpc(method, params):
    req = urllib.request.Request(
        _rpc_url(),
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=25).read())
    if out.get("error"):
        raise RuntimeError(str(out["error"])[:200])
    return out.get("result")


def _get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read())


def load_cache():
    try:
        return json.load(open(CACHE))
    except Exception:
        return {}


def save_cache(c):
    try:
        with open(CACHE, "w") as fh:
            json.dump(c, fh, indent=1)
    except Exception:
        pass


RAY_CPMM = "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C"
RAY_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
DLMM_PROG = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
CONSTANT_PRODUCT = {RAY_CPMM, RAY_AMM_V4}
# validated constant-product SOL/USDC pool (on-chain price source for USD conversion)
SOL_USDC_POOL = "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2"


def sol_usd():
    pair = hunt_vaults(SOL_USDC_POOL, WSOL)
    if pair:
        return pair[1]["ui"] / pair[0]["ui"]
    return None


def mint_decimals(mint):
    try:
        r = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        data = ((r or {}).get("value") or {}).get("data") or {}
        if isinstance(data, dict):
            return int(data.get("parsed", {}).get("info", {}).get("decimals"))
    except Exception:
        pass
    return 9


def token_account_ui(addr):
    try:
        r = rpc("getAccountInfo", [addr, {"encoding": "jsonParsed"}])
        data = ((r or {}).get("value") or {}).get("data") or {}
        if isinstance(data, dict):
            return float((data.get("parsed", {}).get("info", {}).get("tokenAmount") or {}).get("uiAmount") or 0)
    except Exception:
        pass
    return 0.0


def pumpswap_price(pool, base_mint):
    """PumpSwap AMM (packed struct, from open-source PumpPool parser):
    raw pool bytes -> base_mint@43, quote_mint@75, base vault@139, quote vault@171.
    Price = vault balance ratio; USD via SOL/USDC when quote is WSOL."""
    raw = pool_bytes(pool)
    if not raw or len(raw) < 180:
        return None, "short pool data"
    base = b58(raw[43:75])
    quote = b58(raw[75:107])
    bv = b58(raw[139:171])
    qv = b58(raw[171:203])
    if base_mint not in (base, quote):
        return None, "mint not in pumpswap pool"
    b_ui = token_account_ui(bv)
    q_ui = token_account_ui(qv)
    if not b_ui or not q_ui:
        return None, "vault balances unreadable"
    if base == WSOL:
        px_sol = b_ui / q_ui          # SOL per unit of quote-token
    else:
        px_sol = q_ui / b_ui          # quote (SOL/USDC) per unit of base
    if quote == WSOL or base == WSOL:
        su = sol_usd()
        if su:
            return px_sol * su, "PumpSwap vault ratio (USD via SOL/USDC)"
    return px_sol, "PumpSwap vault ratio (USDC quote)"


def dlmm_price(pool, base_mint):
    """Meteora DLMM: spot = active-bin boundary price.
    LbPair body (after 8-byte discriminator): active_id i32@68, bin_step u16@72,
    token_x_mint@80, token_y_mint@112. USD = quote/unit * SOL|USDC price."""
    raw = pool_bytes(pool)
    if not raw or len(raw) < 180:
        return None, "short pool data"
    d = raw[8:]
    aid = struct.unpack_from("<i", d, 68)[0]
    bstep = struct.unpack_from("<H", d, 72)[0]
    tx = b58(d[80:112])
    ty = b58(d[112:144])
    base = 1 + bstep / 10000.0
    if base_mint == tx:
        q_per_b = base ** aid          # quote (ty) per unit of tx
    elif base_mint == ty:
        q_per_b = 1.0 / (base ** aid)  # quote (tx) per unit of ty
    else:
        return None, "base mint not in pool"
    # decimal normalization (both sides usually 9)
    q_per_b *= 10 ** (mint_decimals(ty) - mint_decimals(tx)) if base_mint == tx \
        else 10 ** (mint_decimals(tx) - mint_decimals(ty))
    if ty == WSOL or tx == WSOL:
        su = sol_usd()
        if su:
            return q_per_b * su, "DLMM active-bin (USD via SOL/USDC)"
    return q_per_b, "DLMM active-bin (quote is USDC)"



def owner_program(addr):
    try:
        r = rpc("getAccountInfo", [addr, {"encoding": "base64"}])
        v = (r or {}).get("value") or {}
        return v.get("owner")
    except Exception:
        return None


def discover_pool(mint):
    try:
        d = _get("https://api.dexscreener.com/latest/dex/tokens/" + mint)
    except Exception:
        return None
    best = None
    for pair in d.get("pairs") or []:
        if pair.get("chainId") != "solana":
            continue
        liq = (pair.get("liquidity") or {}).get("usd") or 0
        if not best or liq > best[0]:
            best = [liq, pair]
    if not best:
        return None
    pr = best[1]
    bt = pr.get("baseToken") or {}
    qt = pr.get("quoteToken") or {}
    pool = pr.get("pairAddress")
    return {"pool": pool, "dexId": pr.get("dexId"),
            "baseMint": bt.get("address"), "quoteMint": qt.get("address"),
            "quoteSymbol": qt.get("symbol"), "liqUsd": best[0],
            "refPx": float(pr.get("priceUsd") or 0),
            "program": owner_program(pool) if pool else None,
            "foundAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}



def pool_bytes(pool):
    r = rpc("getAccountInfo", [pool, {"encoding": "base64"}])
    info = (r or {}).get("value") or {}
    data = info.get("data") or []
    if not data:
        return None
    return base64.b64decode(data[0])


def hunt_vaults(pool, base_mint):
    """Scan pool bytes for embedded pubkeys that are live token accounts
    holding base or quote mints, grouped by their authority."""
    raw = pool_bytes(pool)
    if not raw:
        return []
    cand = set()
    for off in range(0, len(raw) - 31, 8):
        cand.add(b58(raw[off:off + 32]))
    cand = [c for c in cand if len(c) in (43, 44)][:120]
    found = []
    for i in range(0, len(cand), 40):
        chunk = cand[i:i + 40]
        try:
            res = rpc("getMultipleAccounts", [chunk, {"encoding": "jsonParsed"}])
        except Exception:
            continue
        for pub, acc in zip(chunk, (res or {}).get("value") or []):
            if not acc:
                continue
            data = acc.get("data")
            if not isinstance(data, dict):
                continue
            parsed = data.get("parsed") or {}
            info = parsed.get("info") or {}
            ta = info.get("tokenAmount") or {}
            ui = float(ta.get("uiAmount") or 0)
            m = info.get("mint")
            if ui <= 0 or m not in (base_mint, USDC, WSOL):
                continue
            found.append({"vault": pub, "mint": m, "ui": ui,
                          "owner": info.get("owner"), "decimals": ta.get("decimals")})
    groups = {}
    for v in found:
        groups.setdefault(v["owner"], []).append(v)
    best = None
    for owner, vs in groups.items():
        base = next((x for x in vs if x["mint"] == base_mint), None)
        quote = next((x for x in vs if x["mint"] == USDC), None) or \
                next((x for x in vs if x["mint"] == WSOL), None)
        if base and quote:
            score = 2 if quote["mint"] == USDC else 1
            if not best or score > best[0]:
                best = [score, base, quote]
    return best[1:] if best else []


def constant_price(pool, base_mint, quote_mint):
    """Constant-product pools (Raydium CPMM / AMM v4): price = quote/ui / base/ui
    read straight from the pool's vault token accounts."""
    try:
        res = rpc("getTokenAccountsByOwner", [pool, {"encoding": "jsonParsed"}])
    except Exception:
        return None, []
    base = quote = None
    vaults = []
    for item in ((res or {}).get("value") or []):
        info = (((item.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
        ta = info.get("tokenAmount") or {}
        ui = float(ta.get("uiAmount") or 0)
        m = info.get("mint")
        vaults.append({"mint": m, "vault": item.get("pubkey"), "ui": ui})
        if m == base_mint and ui > 0:
            base = ui
        if m == quote_mint and ui > 0:
            quote = ui
    if not base or not quote:
        return None, vaults
    return quote / base, vaults


def price_usd(mint):
    """One-call USD price for the guard fallback: cached pool -> venue decoder."""
    cache = load_cache()
    meta = cache.get(mint)
    if not meta or not meta.get("program") or not meta.get("pool"):
        try:
            meta = discover_pool(mint)
        except Exception:
            return None
        if meta and meta.get("program"):
            cache[mint] = meta
            save_cache(cache)
    if not meta:
        return None
    prog = meta.get("program") or ""
    pool = meta.get("pool")
    try:
        if prog in CONSTANT_PRODUCT:
            pair = hunt_vaults(pool, mint)
            return (pair[1]["ui"] / pair[0]["ui"]) if pair else None
        if prog == DLMM_PROG or prog.startswith("LBUZKhRx"):
            return dlmm_price(pool, mint)[0]
        if prog.startswith("pAMMBay6"):
            return pumpswap_price(pool, mint)[0]
    except Exception:
        return None
    return None


def main():
    mints = sys.argv[1:]
    if not mints:
        print("usage: oracle_px.py <mint> [...]")
        return 1
    cache = load_cache()
    for mint in mints:
        meta = cache.get(mint)
        if not meta or not meta.get("program") or not meta.get("refPx"):
            meta = discover_pool(mint) or meta
        print("== %s ==" % mint)
        if not meta:
            print("  no pool discoverable")
            continue
        if meta.get("program"):
            cache[mint] = meta
        prog = meta.get("program") or "?"
        m2 = dict(meta)
        m2["program"] = prog[:8]
        print("  venue %(dexId)s  pool %(pool)s  program %(program)s  quote %(quoteSymbol)s liq $%(liqUsd)d refPx %(refPx)s" % m2)
        ref = float(meta.get("refPx") or 0)
        if prog in CONSTANT_PRODUCT:
            pair = hunt_vaults(meta["pool"], mint)
            px = (pair[1]["ui"] / pair[0]["ui"]) if pair else None
            method = "constant-product vault-hunt (validated)"
        elif prog == DLMM_PROG or (prog or "").startswith("LBUZKhRx"):
            px, method = dlmm_price(meta["pool"], mint)
        elif (prog or "").startswith("pAMMBay6"):
            px, method = pumpswap_price(meta["pool"], mint)
        else:
            pair = hunt_vaults(meta["pool"], mint)
            method = "pubkey-hunt (unknown/non-CP venue)"
            px = (pair[1]["ui"] / pair[0]["ui"]) if pair else None
        if not px:
            print("  NO onchain price via %s" % method)
            continue
        print("  ONCHAIN price = %.8f  [method: %s]" % (px, method))
        if ref and ref > 0:
            delta = (px / ref - 1) * 100
            status = "OK" if abs(delta) <= 15 else "MISMATCH (needs venue decoder)"
            print("  vs DexScreener ref %.8f -> %.2f%%  [%s]" % (ref, delta, status))
    save_cache(cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())


