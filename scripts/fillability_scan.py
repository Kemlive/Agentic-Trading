#!/usr/bin/env python3
"""fillability_scan.py v2 — RH SHORTLIST FILL-ABILITY SCAN (simulation only, zero funds).

Venues:
  uniswap-v3 : Factory + QuoterV2 (RH)            -> real revert-sim (eth_call)
  ramses-v3  : Factory + QuoterV2 (RH, docs.locked)-> real revert-sim (same v3 ABI)
  uniswap-v2 : Factory + Router02 (RH)            -> real revert-sim (getAmountsOut)
  uniswap-v4 / pons-v2 : need-PoolKey-build       -> NOT simulated, never PASS

PASS rule: $5/$25/$50 quote fills (no revert) with impact <= 5%.
Results -> research/fillability_scan_<ts>.md/.json
"""
import datetime
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RHRPC = "https://rpc.mainnet.chain.robinhood.com"
# RH official deployments (locked, no guesses)
V3_FACTORY = "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"
QUOTER_V2 = "0x33e885eD0Ec9bF04EcfB19341582aADCb4c8A9E7"      # Uniswap v3 QuoterV2
V2_FACTORY = "0x8bcEaA40B9AcdfAedF85AdF4FF01F5Ad6517937f"      # Uniswap v2 factory
V2_ROUTER = "0x89e5DB8B5aA49aA85AC63f691524311AEB649eba"       # Uniswap v2 Router02
R_FACTORY = "0xE0c4ceb92d08CA985bB70fe0a22fEb121A9854A8"       # Ramses V3 factory (RH)
R_QUOTER = "0x4730e03EB4a58A5e20244062D5f9A99bCf5770a6"        # Ramses V3 QuoterV2 (RH)
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
FEES = (100, 500, 3000, 10000)
SIZES = (5.0, 25.0, 50.0)
MAX_IMPACT = 0.05
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
      "Content-Type": "application/json", "Accept": "application/json"}
Q_SEL = "0xc6a5026a"          # quoteExactInputSingle((addr,addr,uint24,uint,uint160))
GET_PAIR = "0xe6a43905"       # factory.getPair(addr,addr)
GET_POOL = "0x1698ee82"       # factory.getPool(addr,addr,uint24)
GET_RES = "0x0902f1ac"        # pair.getReserves()
AMTS_OUT = "0xd06ca61f"       # router.getAmountsOut(uint,addr[])


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc)


def rawrpc(method, params):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(RHRPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception as e:
            last = e
            time.sleep(1 + attempt)
    raise last


def call(to, data):
    try:
        r = rawrpc("eth_call", [{"to": to, "data": data}, "latest"])
        return r.get("result") if "result" in r else None
    except Exception:
        return None


def word(hexv, idx):
    h = hexv[2:]
    if len(h) < (idx + 1) * 64:
        return 0
    return int(h[idx * 64:(idx + 1) * 64], 16)


def decimals(addr):
    r = call(addr, "0x313ce567")
    return int(r, 16) if r else None


def addrz(hexv):
    return "0x" + (hexv or "")[2:].rjust(64, "0")[-40:]


def mid_from_raw_ratio(raw, t0_is_usdg, tok_dec):
    """USDG per token (ui) from raw token1/token0 ratio."""
    if not raw:
        return None
    if t0_is_usdg:
        return (1.0 / raw) * (10.0 ** (tok_dec - 6))
    return raw * (10.0 ** (6 - tok_dec))


def quote_v3(quoter, fee, token, amt_usdg):
    amt = int(amt_usdg * 10 ** 6)
    data = (Q_SEL + USDG[2:].lower().rjust(64, "0") + token[2:].lower().rjust(64, "0")
            + hex(fee)[2:].rjust(64, "0") + hex(amt)[2:].rjust(64, "0") + "0".rjust(64, "0"))
    r = rawrpc("eth_call", [{"to": quoter, "data": data}, "latest"])
    return word(r["result"], 0) if "result" in r else None


def quote_v2(token, amt_usdg):
    amt = int(amt_usdg * 10 ** 6)
    path = USDG + token
    off = "0" * 62 + "40"
    ln = "0" * 62 + "02"
    elems = path[0:40].lower().rjust(64, "0") + path[40:].lower().rjust(64, "0")
    data = AMTS_OUT + hex(amt)[2:].rjust(64, "0") + off + ln + elems
    r = rawrpc("eth_call", [{"to": V2_ROUTER, "data": data}, "latest"])
    if "result" in r:
        # returns uint[] -> word0 offset, word1 len, word2 amountOut
        return word(r["result"], 2)
    return None


def resolve_v3(factory, token, fee):
    args = token[2:].lower().rjust(64, "0") + USDG[2:].lower().rjust(64, "0") + hex(fee)[2:].rjust(64, "0")
    p = call(factory, GET_POOL + args)
    if not p or word(p, 0) == 0:
        return None
    return addrz(p)


def mid_v3(pool, tok_dec):
    r = call(pool, "0x3850c7bd")
    if not r:
        return None
    sp = word(r, 0)
    t0 = call(pool, "0x0dfe1681")
    return mid_from_raw_ratio((sp / 2.0 ** 96) ** 2, addrz(t0).lower() == USDG.lower(), tok_dec)


def resolve_v2(token):
    args = token[2:].lower().rjust(64, "0") + USDG[2:].lower().rjust(64, "0")
    p = call(V2_FACTORY, GET_PAIR + args)
    if not p or word(p, 0) == 0:
        return None
    return addrz(p)


def mid_v2(pair, tok_dec):
    r = call(pair, GET_RES)
    if not r:
        return None
    r0, r1 = word(r, 0), word(r, 1)
    t0 = call(pair, "0x0dfe1681")
    raw = r1 / r0 if r0 else 0.0
    return mid_from_raw_ratio(raw, addrz(t0).lower() == USDG.lower(), tok_dec)


def gecko_pools(token):
    try:
        url = "https://api.geckoterminal.com/api/v2/networks/robinhood/tokens/" + token + "/pools?page=1"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read())
        out = []
        for p in (d.get("data") or [])[:8]:
            a = p.get("attributes") or {}
            dex = ((p.get("relationships") or {}).get("dex") or {}).get("data") or {}
            out.append({"pool": a.get("address"), "dex": (dex.get("id") or ""), "liqUsd": a.get("reserve_in_usd")})
        return out
    except Exception:
        return []


def test_sizes(quote_fn, mid, tok_dec):
    """Return (max_ok, impact5_pct, fail_at) for the $5/$25/$50 ladder."""
    max_ok, fail_at = 0.0, None
    for usd in SIZES:
        out = quote_fn(usd)
        if out is None:
            fail_at = "revert@$%g" % usd
            break
        fill_px = usd / (out / 10.0 ** tok_dec)
        impact = (fill_px / mid - 1) if (mid and fill_px) else None
        if impact is None or abs(impact) > MAX_IMPACT:
            fail_at = "impact@$%g" % usd
            break
        max_ok = usd
    imp5 = None
    if max_ok >= 5.0:
        out5 = quote_fn(5.0)
        if out5:
            fpx = 5.0 / (out5 / 10.0 ** tok_dec)
            imp5 = (fpx / mid - 1) if mid else None
    return max_ok, imp5, fail_at


def best_or(best, cand):
    if best is None:
        return cand
    if cand.get("status") == "PASS" and (best.get("status") != "PASS" or cand["maxFillUsd"] > best["maxFillUsd"]):
        return cand
    return best


def main():
    short = json.load(open(os.path.join(ROOT, "data/live/feed/rh-potential.json")))
    tokens = []
    for tier in ("trending", "gainer", "new"):
        for r in (short.get("tiers") or {}).get(tier, []):
            k = str(r.get("key") or "")
            if k.lower().startswith("0x") and k not in tokens:
                tokens.append(k)
    print("tokens to scan:", len(tokens))
    rows, needkey = [], []
    for tok in tokens:
        td = decimals(tok) or 18
        best = None
        for fee in FEES:  # uniswap v3
            pool = resolve_v3(V3_FACTORY, tok, fee)
            if not pool:
                continue
            mid = mid_v3(pool, td)
            max_ok, imp5, fail = test_sizes(lambda u: quote_v3(QUOTER_V2, fee, tok, u), mid, td)
            best = best_or(best, {"token": tok, "venue": "uniswap-v3", "pool": pool, "fee": fee,
                                  "q5": "OK" if max_ok >= 5 else "no-fill",
                                  "impact5": round(imp5 * 100, 2) if imp5 is not None else None,
                                  "maxFillUsd": max_ok,
                                  "status": "PASS" if (max_ok >= 5 and (imp5 is None or abs(imp5) <= MAX_IMPACT * 100)) else "no-fill",
                                  "failAt": fail})
        for fee in FEES:  # ramses v3
            pool = resolve_v3(R_FACTORY, tok, fee)
            if not pool:
                continue
            mid = mid_v3(pool, td)
            max_ok, imp5, fail = test_sizes(lambda u: quote_v3(R_QUOTER, fee, tok, u), mid, td)
            best = best_or(best, {"token": tok, "venue": "ramses-v3", "pool": pool, "fee": fee,
                                  "q5": "OK" if max_ok >= 5 else "no-fill",
                                  "impact5": round(imp5 * 100, 2) if imp5 is not None else None,
                                  "maxFillUsd": max_ok,
                                  "status": "PASS" if (max_ok >= 5 and (imp5 is None or abs(imp5) <= MAX_IMPACT * 100)) else "no-fill",
                                  "failAt": fail})
        pair = resolve_v2(tok)  # uniswap v2
        if pair:
            mid = mid_v2(pair, td)
            max_ok, imp5, fail = test_sizes(lambda u: quote_v2(tok, u), mid, td)
            best = best_or(best, {"token": tok, "venue": "uniswap-v2", "pool": pair, "fee": "-",
                                  "q5": "OK" if max_ok >= 5 else "no-fill",
                                  "impact5": round(imp5 * 100, 2) if imp5 is not None else None,
                                  "maxFillUsd": max_ok,
                                  "status": "PASS" if (max_ok >= 5 and (imp5 is None or abs(imp5) <= MAX_IMPACT * 100)) else "no-fill",
                                  "failAt": fail})
        if best is None:
            best = {"token": tok, "venue": "-", "pool": "-", "fee": "-", "q5": "no-pool",
                    "impact5": None, "maxFillUsd": 0, "status": "no-pool", "failAt": None}
        rows.append(best)
        for o in gecko_pools(tok):
            dx = o.get("dex") or ""
            if "uniswap-v4" in dx or "pons" in dx.lower():
                needkey.append({"token": tok, "venue": dx, "pool": o.get("pool"), "fee": "-",
                                "q5": "n/a", "impact5": None, "maxFillUsd": 0,
                                "status": "needs-PoolKey-build", "failAt": None})
        time.sleep(0.1)
    ts = now_iso().strftime("%Y%m%d-%H%M%S")
    res = {"asOf": now_iso().isoformat(), "quote": "USDG", "sizesTested": list(SIZES),
           "maxImpactPct": MAX_IMPACT * 100,
           "venues": ["uniswap-v3", "ramses-v3", "uniswap-v2"],
           "v4PonsStatus": "needs-PoolKey-build (not simulated)",
           "notes": "simulation only - eth_call quoters, no funds",
           "rows": rows, "needsPoolKey": needkey}
    jpath = os.path.join(ROOT, "research", "fillability_scan_%s.json" % ts)
    with open(jpath, "w") as f:
        json.dump(res, f, indent=1)
    md = ["# RH Fill-Ability Scan v2 (%s UTC)" % now_iso().isoformat(),
          "Simulation only (eth_call quoters, zero funds). Quote = USDG.",
          "Venues: uniswap-v3 / ramses-v3 / uniswap-v2. PASS = $5 fills, impact <= 5%.",
          "uniswap-v4 & pons-v2 = needs-PoolKey-build (not simulated).",
          "", "| token | venue | pool | fee | $5 | impact% | maxFill$ | status |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["token"][:10], r["venue"], (r["pool"] or "-")[:10], r["fee"], r["q5"],
            r["impact5"] if r["impact5"] is not None else "-", r["maxFillUsd"], r["status"]))
    if needkey:
        md.append("")
        md.append("## v4 / Pons pools (needs-PoolKey-build - not simulated, never PASS)")
        for r in needkey:
            md.append("- %s %s pool=%s" % (r["token"][:10], r["venue"], (r["pool"] or "")[:14]))
    mpath = os.path.join(ROOT, "research", "fillability_scan_%s.md" % ts)
    with open(mpath, "w") as f:
        f.write("\n".join(md))
    print("saved:", os.path.basename(mpath), "and", os.path.basename(jpath))
    print("\n".join(md))


if __name__ == "__main__":
    main()
