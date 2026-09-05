#!/usr/bin/env python3
"""feed_dashboard.py — AUTOMATED PERFORMANCE SUMMARY DASHBOARD (multi-chain feed).

Renders live metrics from our own feed watchers + desk state on http://127.0.0.1:8127
(auto-refresh every 20s). Data sources are our local files only:
  feed/solana.jsonl · robinhood.jsonl · unified.jsonl · metrics.json ·
  bench-matrix.json · rh_alpha.json · feed-state.json · fastlane-positions.json
Plus live balance reads via portfolio_state (read-only).
Run : python3 scripts/feed_dashboard.py [--port 8127]
"""
import os
import sys
import json
import glob
import time
import datetime
import http.server
import socketserver
import urllib.request
import threading
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, "data", "live", "feed")
LIVE = os.path.join(ROOT, "data", "live")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p, default=None):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return default


def rows(p):
    try:
        return [json.loads(l) for l in open(p)]
    except Exception:
        return []


def count_rows(p):
    try:
        return sum(1 for _ in open(p))
    except Exception:
        return 0


def last_ts(p):
    last = None
    for l in open(p):
        try:
            last = json.loads(l).get("ts")
        except Exception:
            pass
    if not last:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        return max(0, int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()))
    except Exception:
        return None


def proc_alive(name):
    try:
        pid = int(open(os.path.join(ROOT, "logs", "feed", name + ".pid")).read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _dex_for(mints):
    """Single DexScreener batch call -> per-mint {symbol, liq, h1} for display. Best-pair by liquidity."""
    import urllib.request
    out = {}
    if not mints:
        return out
    try:
        url = "https://api.dexscreener.com/latest/dex/tokens/" + ",".join(mints)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=12).read())
        groups = {}
        for p in data.get("pairs") or []:
            bt = (p.get("baseToken") or {}).get("address") or ""
            groups.setdefault(bt, []).append(p)
        for a, ps in groups.items():
            best = max(ps, key=lambda x: float((x.get("liquidity") or {}).get("usd") or 0))
            chg = best.get("priceChange") or {}
            vol = best.get("volume") or {}
            out[a] = {"symbol": (best.get("baseToken") or {}).get("symbol") or a[:6],
                      "name": (best.get("baseToken") or {}).get("name"),
                      "liq": float((best.get("liquidity") or {}).get("usd") or 0),
                      "h1": float(chg.get("h1")) if chg.get("h1") is not None else None,
                      "price": float(best.get("priceUsd")) if best.get("priceUsd") is not None else None,
                      "volH1": float(vol.get("h1")) if vol.get("h1") is not None else None,
                      "image": ((best.get("info") or {}).get("imageUrl")) if best.get("info") else None,
                      "pool": best.get("pairAddress"), "dex": best.get("dexId")}
    except Exception:
        pass
    return out


BLOCKSCOUT = "https://robinhoodchain.blockscout.com/api/v2"
MARKS = os.path.join(FD, "position-marks.jsonl")
RH_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
META_PROGRAM = "metaqbxxUerqRkFfnyLcQvZuWfvo4F1jQsm8Yk5cXU5qWmS8"


def _post_json(url, payload, timeout=12):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": RH_UA})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": RH_UA, "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _sol_rpc_url():
    try:
        k = open(os.path.expanduser("~/.config/agentic-trading/helius.key")).read().strip()
        if k:
            return "https://mainnet.helius-rpc.com/?api-key=" + k
    except Exception:
        pass
    return "https://api.mainnet-beta.solana.com"


def _sol_rpc(method, params):
    return _post_json(_sol_rpc_url(), {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})["result"]


def _sol_das(mint):
    """Official on-chain metadata (DAS on Helius/public RPC) — avatar/name/authorities."""
    try:
        r = _post_json(_sol_rpc_url(),
                       {"jsonrpc": "2.0", "id": 1, "method": "getAsset", "params": {"id": mint}})
        return r.get("result") or {}
    except Exception:
        return {}


def _rh_explorer(path, tries=3):
    last = None
    for i in range(tries):
        try:
            raw = _get_json(BLOCKSCOUT + path, timeout=15)
            if isinstance(raw, dict):
                return raw
            last = "non-json response"
        except Exception as e:
            last = e
        time.sleep(2 * (i + 1))
    return None


def _tail_lines(path, maxlines=6000):
    try:
        with open(path, "r", errors="ignore") as f:
            lines = f.readlines()
        return lines[-maxlines:]
    except Exception:
        return []


def _feed_context(address, chain):
    """Benchmark earliness deltas + feed tier history for one tracked token."""
    a = str(address or "").lower()
    bench, hist = [], []
    try:
        for l in _tail_lines(os.path.join(FD, "bench.jsonl"), 4000):
            r = json.loads(l)
            if str(r.get("mint") or "").lower() == a and r.get("chain") == chain:
                bench.append(r)
    except Exception:
        pass
    try:
        for l in _tail_lines(os.path.join(FD, "tier-history.jsonl"), 8000):
            r = json.loads(l)
            if str(r.get("key") or "").lower() == a and r.get("chain") == chain:
                hist.append(r)
    except Exception:
        pass
    bl = bench[-6:]
    return {"benchmark": {"samples": [{"ts": r.get("ts"), "deltaSec": r.get("deltaSec"),
                                       "liqUsd": r.get("liqUsd")} for r in bl],
                          "lastDeltaSec": (bl[-1].get("deltaSec") if bl else None),
                          "liqUsd": (bl[-1].get("liqUsd") if bl else None)},
            "history": [{"ts": r.get("ts"), "tier": r.get("tier"), "t60": r.get("t60"),
                         "score": r.get("score")} for r in hist[-12:]]}


TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _token_holdings(owner):
    """All non-zero SPL token balances for an owner wallet (our own RPC read)."""
    try:
        r = _post_json(_sol_rpc_url(),
                       {"jsonrpc": "2.0", "id": 1, "method": "getTokenAccountsByOwner",
                        "params": [owner, {"programId": TOKEN_PROGRAM}, {"encoding": "jsonParsed"}]}, timeout=15)
        out = []
        for acc in ((r or {}).get("result") or {}).get("value", []):
            info = ((((acc.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {})
            mint = info.get("mint")
            amt = info.get("tokenAmount") or {}
            ui = float(amt.get("uiAmount") or 0)
            if not mint or ui <= 0:
                continue
            out.append({"mint": mint, "ui": ui, "decimals": int(amt.get("decimals") or 0)})
        return out
    except Exception:
        return []


def _wallet_holdings():
    """Trading hot-wallet SPL balances (executor wallet, spends under delegate cap)."""
    try:
        import importlib.util as _iu
        s = _iu.spec_from_file_location("autow", os.path.join(ROOT, "scripts", "autopilot.py"))
        au = _iu.module_from_spec(s)
        s.loader.exec_module(au)
        return _token_holdings(au.WALLET)
    except Exception:
        return []


def _vault_cfg():
    def_ = {"solVault": "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4",
            "solVaultUsdcAcc": "GRiCEHnTyfNHKvCXpkcxqHwHmkFFxhHz5Yjhq4MxGJK8",
            "evm": {"base": {"rpc": ["https://base-rpc.publicnode.com"],
                             "safe": "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A",
                             "owner": "0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8",
                             "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                             "aero": "0x940181a94A35A4569E4529A3CDfB74e38FD98631"}}}
    try:
        return {**def_, **json.load(open(os.path.join(LIVE, "vaults.json")))}
    except Exception:
        return def_


def _sol_native_sol(owner):
    try:
        r = _post_json(_sol_rpc_url(), {"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                                        "params": [owner]}, timeout=12)
        return (r.get("result") or {}).get("value", 0) / 1e9
    except Exception:
        return 0.0


def _evm_call(rpcs, to, data):
    for u in rpcs:
        try:
            r = _post_json(u, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                               "params": [{"to": to, "data": data}, "latest"]}, timeout=12)
            return r.get("result")
        except Exception:
            continue
    return None


def _evm_native_eth(addr, rpcs):
    try:
        for u in rpcs:
            try:
                r = _post_json(u, {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance",
                                   "params": [addr, "latest"]}, timeout=12)
                if r:
                    return int(r["result"], 16) / 1e18
            except Exception:
                continue
    except Exception:
        pass
    return 0.0


def _evm_erc20_ui(addr, who, decimals, rpcs):
    data = "0x70a08231000000000000000000000000" + who.lower()[2:]
    res = _evm_call(rpcs, addr, data)
    if not res:
        return None
    try:
        return int(res, 16) / (10 ** decimals)
    except Exception:
        return None


def _vault_snapshot():
    """Read-only view of the Vault / Safe capital-owner wallets (multi-chain)."""
    v = _vault_cfg()
    rows = []
    # Solana vault
    try:
        sol = _sol_native_sol(v["solVault"])
        lines = [{"k": "SOL", "v": "%.4f" % sol}]
        hld = _token_holdings(v["solVault"])
        usdc = next((h for h in hld if h["mint"] == USDC_MINT), None)
        if usdc:
            lines.append({"k": "USDC", "v": "$%.2f" % usdc["ui"], "usd": True})
        for h in hld:
            if h["mint"] != USDC_MINT:
                lines.append({"k": h["mint"][:6], "v": "%.4g" % h["ui"]})
        rows.append({"label": "SOL VAULT", "addr": v["solVault"], "lines": lines})
    except Exception:
        rows.append({"label": "SOL VAULT", "addr": v["solVault"], "lines": [{"k": "?", "v": "unreadable"}]})
    # Base EVM safe + owner
    b = (v.get("evm") or {}).get("base") or {}
    if b:
        rpcs = b.get("rpc") or []
        for label, who in (("EVM OWNER", b.get("owner")), ("EVM SAFE", b.get("safe"))):
            if not who:
                continue
            lines = [{"k": "ETH", "v": "%.6f" % _evm_native_eth(who, rpcs)}]
            u = _evm_erc20_ui(b.get("usdc"), who, 6, rpcs)
            if u is not None:
                lines.append({"k": "USDC", "v": "$%.2f" % u, "usd": True})
            a = _evm_erc20_ui(b.get("aero"), who, 18, rpcs)
            if a is not None:
                lines.append({"k": "AERO", "v": "%.4g" % a})
            rows.append({"label": label, "addr": who, "lines": lines})
    return rows


PM_CFG_FILE = os.path.join(LIVE, "pm.json")


def _pm_cfg():
    def_ = {"baseAsset": "USDC", "baseTargetPct": 50, "maxCoinWeightPct": 25,
            "minSellUsd": 0.5, "slippageBps": 500,
            "note": "Bybit/Nexo-style target allocation. Rebalance is BOSS-TRIGGERED: preview -> confirm -> execute. Tune here."}
    try:
        return {**def_, **json.load(open(PM_CFG_FILE))}
    except Exception:
        with open(PM_CFG_FILE, "w") as f:
            json.dump(def_, f, indent=2)
        return def_


def _pm_snapshot():
    """Current wallet equity split: base asset vs every held coin (fresh read)."""
    cfg = _pm_cfg()
    hld = _wallet_holdings()
    lane = set()
    try:
        import importlib.util as _iu
        s = _iu.spec_from_file_location("flpm", os.path.join(ROOT, "scripts", "fastlane.py"))
        fl = _iu.module_from_spec(s)
        s.loader.exec_module(fl)
        lane = {p.get("mint") for p in fl.load_positions().get("positions", []) if p.get("status") == "open"}
    except Exception:
        pass
    dex = _dex_for([h["mint"] for h in hld if h["mint"] != USDC_MINT][:40])
    usdc = 0.0
    coins = []
    for h in hld:
        if h["mint"] == USDC_MINT:
            usdc = h["ui"]
            continue
        d = dex.get(h["mint"]) or {}
        price = d.get("price")
        val = round(h["ui"] * price, 2) if price else None
        coins.append({"mint": h["mint"], "ui": h["ui"], "symbol": d.get("symbol") or h["mint"][:6],
                      "decimals": h["decimals"], "value": val, "lane": h["mint"] in lane})
    total = usdc + sum(c["value"] for c in coins if c.get("value"))
    base_pct = round(usdc / total * 100, 1) if total else 0.0
    for c in coins:
        c["weightPct"] = round((c["value"] or 0) / total * 100, 2) if total and c.get("value") else 0.0
    return {"usdc": usdc, "equity": round(total, 2), "basePct": base_pct,
            "targetPct": cfg["baseTargetPct"], "maxWeightPct": cfg["maxCoinWeightPct"],
            "coins": coins}


def _rebalance_plan(snap):
    """Coins to sell to restore base target: overweight first, whole positions,
    lane coins included (closed guard-managed). Sells only priced coins >= minSellUsd."""
    cfg = _pm_cfg()
    need = max(0.0, snap["equity"] * cfg["baseTargetPct"] / 100.0 - snap["usdc"]) if snap["equity"] > 0 else 0.0
    plan = []
    cands = sorted([c for c in snap["coins"] if c.get("value") is not None and c["value"] >= cfg["minSellUsd"]],
                   key=lambda c: c["value"], reverse=True)
    shortfall = need
    for c in cands:
        over = c["weightPct"] > snap["maxWeightPct"]
        if not over and shortfall <= 0:
            break
        plan.append({"mint": c["mint"], "symbol": c["symbol"], "value": round(c["value"], 2),
                     "kind": "lane" if c["lane"] else "free",
                     "reason": "over max weight (%.1f%% > %.0f%%)" % (c["weightPct"], snap["maxWeightPct"]) if over
                     else "base shortfall"})
        shortfall = round(shortfall - c["value"], 2)
    return {"plan": plan, "needUsd": round(need, 2), "totalSellUsd": round(sum(p["value"] for p in plan), 2),
            "targetUsd": round(snap["equity"] * snap["targetPct"] / 100.0, 2)}


def _pm_rebalance_execute(plan):
    results = []
    for p in plan:
        if p["kind"] == "lane":
            res = _close_position(p["mint"])
        else:
            res = _sell_token(p["mint"])
        results.append({"symbol": p["symbol"], "ok": bool(res.get("ok")), "err": res.get("error"),
                        "realized": res.get("realized")})
    try:
        _sweep_usdc()
    except Exception:
        pass
    return results


def collect():
    d = {}
    d["asOf"] = now_iso()
    d["daemons"] = {n: proc_alive(n) for n in ("sol", "rh", "merge", "bench")}
    d["rows"] = {f: count_rows(os.path.join(FD, f)) for f in
                 ("solana.jsonl", "robinhood.jsonl", "unified.jsonl", "bench.jsonl")}
    d["recency"] = {"sol": last_ts(os.path.join(FD, "solana.jsonl")),
                    "rh": last_ts(os.path.join(FD, "robinhood.jsonl"))}
    met = read(os.path.join(FD, "metrics.json"), {})
    d["metrics"] = met
    # Earliness computed LIVE from bench.jsonl (single source of truth) so the
    # dashboard reflects forward deltas immediately after any purge/reset.
    br = [json.loads(l) for l in open(os.path.join(FD, "bench.jsonl"))] if os.path.exists(os.path.join(FD, "bench.jsonl")) else []
    with_d = [r for r in br if r.get("deltaSec") is not None]
    avg = (sum(r["deltaSec"] for r in with_d) / len(with_d)) if with_d else None
    d["bench"] = {"benchmarks": len(br), "withDelta": len(with_d),
                  "avgDeltaSec": round(avg, 1) if avg is not None else None,
                  "note": "live from bench.jsonl — forward capture only after purge",
                  "liquidityVsDelta": [{"liqUsd": r.get("liqUsd"), "deltaSec": r.get("deltaSec"),
                                        "chain": r.get("chain"), "mint": (r.get("mint") or "")[:10]}
                                       for r in with_d[-12:]]}
    ai = read(os.path.join(FD, "coins.json"), {})
    rh_top = (ai.get("top") or {}).get("robinhood", [])[:8]
    sol_top = (ai.get("top") or {}).get("solana", [])[:8]
    rh_tokens = [{"address": t.get("key"),
                  "symbol": (t.get("sym") or t.get("key", "")[:8]),
                  "transfers": t.get("t60") or 0, "chg_h1": None,
                  "category": (t.get("topTier") or "OTHER").upper()} for t in rh_top]
    dex = _dex_for([t["key"] for t in sol_top if t.get("key")])
    sol_queue = [{"address": t.get("key"),
                  "s": (dex.get(t["key"]) or {}).get("symbol") or t.get("key", "")[:6],
                  "liq": (dex.get(t["key"]) or {}).get("liq", 0),
                  "h1": (dex.get(t["key"]) or {}).get("h1"),
                  "category": (t.get("topTier") or "WATCH").upper(),
                  "t60": t.get("t60") or 0, "accel": t.get("accel") or 0} for t in sol_top]
    d["intel"] = {"counts": ai.get("counts", {}),
                  "chainRefTime": ai.get("chainRefTime", {}),
                  "topRH": rh_top, "topSOL": sol_top,
                  "rh_data": {"tokens": rh_tokens},
                  "sol_data": {"queue": sol_queue}}

    alpha = read(os.path.join(FD, "rh_alpha.json"), {})
    clusters = alpha.get("clusters", {}) if alpha else {}
    d["alpha"] = {k: len(v) for k, v in clusters.items()}
    d["alphaTop"] = {k: [{"symbol": c.get("symbol"), "transfers": c.get("transfers"),
                          "token": (c.get("token") or "")[:10]}
                          for c in clusters.get(k, [])[:4]] for k in clusters}
    fst = read(os.path.join(LIVE, "feed-state.json"), {})
    counts = {}
    for v in (fst.get("counts") or {}).items():
        counts[v[0]] = v[1]
    d["feedCounts"] = counts
    fp = read(os.path.join(LIVE, "fastlane-positions.json"), {"positions": []})
    openp = [p for p in fp.get("positions", []) if p.get("status") == "open"]
    d["lane"] = {"open": len(openp), "positions": []}
    fst_lane = read(os.path.join(LIVE, "fastlane-state.json"), {})
    d["lane"]["spentToday"] = fst_lane.get("spentToday")
    d["lane"]["realizedToday"] = fst_lane.get("realizedToday")
    try:
        px_map = _dex_for([p.get("mint") for p in openp if p.get("mint")])
        for p in openp:
            mint = p.get("mint")
            entry = float(p.get("entryUsd") or 0)
            cost = float(p.get("costUsdc") or 0)
            qty = float(p.get("qty") or 0)
            px = (px_map.get(mint) or {}).get("price")
            pct = round((px / entry - 1) * 100, 2) if entry and px else None
            val = px * qty if px is not None else None
            pnl = round(val - cost, 2) if val is not None else None
            d["lane"]["positions"].append({
                "symbol": p.get("symbol"), "mint": mint, "signal": p.get("signal"),
                "openedAt": str(p.get("openedAt") or ""), "openedAtEpoch": p.get("openedAtEpoch"),
                "entryUsd": entry, "qty": qty, "costUsdc": cost,
                "peakUsd": float(p.get("peakUsd") or entry), "banked": bool(p.get("banked")),
                "tx": str(p.get("txSignature") or "")[:18], "price": px, "pct": pct, "value": val, "pnl": pnl})
    except Exception:
        pass
    for i, p in enumerate(d["lane"]["positions"]):
        trail = _mark_trail(p.get("mint"))
        d["lane"]["positions"][i]["spark"] = ",".join("%.6f" % v for v in trail) if len(trail) >= 2 else None
        d["lane"]["positions"][i]["monitor"] = _monitor_for(p.get("mint"))
    d["portfolio"] = {"coins": [], "usdcHot": None, "estNonUsdc": 0.0}
    try:
        hld = _wallet_holdings()
        lane_mints = {p.get("mint") for p in openp}
        dex = _dex_for([h["mint"] for h in hld if h["mint"] != USDC_MINT][:40])
        coins, est = [], 0.0
        for h in hld:
            m = h["mint"]
            if m == USDC_MINT:
                d["portfolio"]["usdcHot"] = h["ui"]
                continue
            di = dex.get(m) or {}
            price = di.get("price")
            value = round(h["ui"] * price, 2) if price else None
            if value:
                est += value
            coins.append({"mint": m, "ui": h["ui"], "symbol": di.get("symbol") or m[:6],
                          "name": di.get("name"), "price": price, "value": value,
                          "lane": m in lane_mints})
        coins.sort(key=lambda x: x.get("value") or 0, reverse=True)
        d["portfolio"]["coins"] = coins
        d["portfolio"]["estNonUsdc"] = round(est, 2)
    except Exception:
        pass
    try:
        d["vaults"] = _vault_snapshot()
    except Exception:
        d["vaults"] = []
    d["paused"] = os.path.exists(os.path.join(LIVE, "autopilot.off"))
    try:  # live balances
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import portfolio_state as PS
        vault = PS._read_sol_usdc_any(PS.SOL_VAULT_WALLET)
        hot = PS._read_sol_usdc_any(PS.SOL_HOT_WALLET)
        safe = PS._owner_evm_usdc("base", "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A")
        d["balances"] = {"vault": round(vault or 0, 2), "hot": round(hot or 0, 2),
                         "safe": round(safe or 0, 2)}
    except Exception:
        d["balances"] = {}
    return d


def _mark_trail(mint, n=90):
    vals = []
    try:
        for l in _tail_lines(MARKS, 4000):
            r = json.loads(l)
            if r.get("mint") == mint and r.get("px") is not None:
                vals.append(float(r["px"]))
    except Exception:
        pass
    return vals[-n:]


def _persist_marks(d):
    pos = (d.get("lane") or {}).get("positions") or []
    rows = []
    for p in pos:
        if p.get("price") is None:
            continue
        rows.append(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                "mint": p.get("mint"), "symbol": p.get("symbol"), "px": p["price"]}))
    if not rows:
        return
    try:
        with open(MARKS, "a") as f:
            f.write("\n".join(rows) + "\n")
        lines = open(MARKS, errors="ignore").readlines()
        if len(lines) > 3000:
            open(MARKS, "w").writelines(lines[-3000:])
    except Exception:
        pass


def _monitor_for(mint, chain="solana"):
    """Own-feed watch around a held coin: recent event count + latest events + tier trail."""
    src = os.path.join(FD, "solana.jsonl") if chain == "solana" else os.path.join(FD, "robinhood.jsonl")
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    rows_all, hits = [], []
    try:
        rows_all = [json.loads(l) for l in _tail_lines(src, 9000)]
    except Exception:
        return {"n30": 0, "latest": [], "tiers": []}
    for r in rows_all:
        toks = r.get("mints") if chain == "solana" else [r.get("token")]
        if not toks or str(mint) not in toks:
            continue
        bt = r.get("blockTime")
        try:
            t = float(bt) if bt is not None else datetime.datetime.fromisoformat(str(r.get("ts")).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        hits.append((t, r.get("venue"), r.get("tx") or ""))
    n30 = sum(1 for t, _, _ in hits if now - t <= 1800)
    latest = []
    for t, v, tx in sorted(hits, reverse=True)[:4]:
        age = max(0, int(now - t))
        latest.append({"venue": v, "tx": str(tx)[:14], "ageSec": age})
    tiers = []
    try:
        for l in _tail_lines(os.path.join(FD, "tier-history.jsonl"), 8000):
            r = json.loads(l)
            if str(r.get("key") or "").lower() == str(mint).lower():
                tiers.append({"tier": r.get("tier"), "ts": str(r.get("ts") or "")[11:19]})
    except Exception:
        pass
    return {"n30": n30, "latest": latest, "tiers": tiers[-5:]}


def _trend_pct(v):
    if v is None:
        return ("—", "trend-flat")
    cls = "trend-up" if v >= 0 else "trend-down"
    sign = "+" if v >= 0 else ""
    return ("%s%.1f%%" % (sign, v), cls)


def _delta_badge(delta):
    """Delta styling: green when comfortably ahead, ⚠️ flag when <15s, red when aggregator beat us."""
    if delta is None:
        return ("…", "trend-flat", "")
    if delta < 0:
        return ("%ss" % delta, "trend-down", "")
    if delta < 15:
        return ("⚠️ %ss" % delta, "trend-warn", "delta-mismatch")
    return ("+%ss" % delta, "trend-up", "")


def _sol_account_owner(addr):
    try:
        r = _sol_rpc("getAccountInfo", [addr, {"encoding": "jsonParsed"}])
        info = (r or {}).get("value") or {}
        parsed = (info.get("data") or {}).get("parsed") or {}
        return (parsed.get("info") or {}).get("owner")
    except Exception:
        return None


def _token_details_sol(mint):
    out = {"chain": "solana", "address": mint, "avatar": None, "name": None, "symbol": None,
           "price": None, "liqUsd": None, "pool": None, "dex": None, "topHolders": [],
           "totalSupply": None, "decimals": None, "devFlags": [], "benchmark": None, "history": []}
    out.update(_feed_context(mint, "solana"))
    meta = _sol_das(mint)
    cm = ((meta.get("content") or {}).get("metadata") or {})
    out["name"] = cm.get("name")
    out["symbol"] = cm.get("symbol") or (meta.get("symbol") or "")
    out["avatar"] = ((meta.get("content") or {}).get("links") or {}).get("image") or cm.get("image")
    raw_auth = meta.get("authorities")
    auth = {}
    if isinstance(raw_auth, list):
        for it in raw_auth:
            ad = (it or {}).get("address")
            if ad:
                auth[ad] = (it or {}).get("scopes") or "authority"
    elif isinstance(raw_auth, dict):
        auth = {k: v for k, v in raw_auth.items() if v}
    out["authorities"] = auth
    dev = set(auth.keys())
    try:
        sp = (_sol_rpc("getTokenSupply", [mint]) or {}).get("value") or {}
        out["decimals"] = int(sp.get("decimals") or 0)
        out["totalSupply"] = float(sp.get("uiAmount") or 0)
        raw_supply = int(sp.get("amount") or 0)
    except Exception:
        raw_supply = 0
    dex = _dex_for([mint]).get(mint, {})
    out["price"] = dex.get("price")
    out["liqUsd"] = dex.get("liq")
    out["pool"] = dex.get("pool")
    out["dex"] = dex.get("dex")
    if dex.get("image") and not out["avatar"]:
        out["avatar"] = dex["image"]   # public CDN fallback only when no on-chain image
    try:
        for h in (_sol_rpc("getTokenLargestAccounts", [mint]) or {}).get("value", [])[:10]:
            raw = int(h.get("amount") or 0)
            ui = float(h.get("uiAmount") or 0)
            owner = _sol_account_owner(h.get("address"))
            tag = None
            if dev and owner and owner in dev:
                tag = "DEV-AUTH ⚠️"
                out["devFlags"].append(h.get("address"))
            out["topHolders"].append({"address": h.get("address"), "pct": round(raw / raw_supply * 100, 2) if raw_supply else None,
                                      "amount": ui, "owner": owner, "tag": tag})
    except Exception:
        pass
    return out


def _token_details_rh(address):
    if not (isinstance(address, str) and address.lower().startswith("0x") and len(address) == 42):
        return {"chain": "robinhood", "error": "invalid RH address"}
    t = _rh_explorer("/tokens/" + address)
    if not t:
        return {"chain": "robinhood", "address": address, "error": "explorer unreachable / token unknown"}
    dec = int(t.get("decimals") or 0)
    tot_raw = int(t.get("total_supply") or 0)
    out = {"chain": "robinhood", "address": address, "symbol": t.get("symbol"), "name": t.get("name"),
           "avatar": t.get("icon_url"), "decimals": dec,
           "totalSupply": round(tot_raw / (10 ** dec), 6) if tot_raw else None,
           "holdersCount": t.get("holders_count"),
           "price": float(t.get("exchange_rate")) if t.get("exchange_rate") is not None else None,
           "vol24h": float(t.get("volume_24h")) if t.get("volume_24h") is not None else None,
           "topHolders": [], "devFlags": [], "benchmark": None, "history": []}
    out.update(_feed_context(address, "robinhood"))
    hs = _rh_explorer("/tokens/" + address + "/holders") or {}
    for it in (hs.get("items") or [])[:12]:
        ah = it.get("address") or {}
        addr = ah.get("hash")
        raw = float(it.get("value") or 0)
        pct = round(raw / tot_raw * 100, 2) if tot_raw else None
        nm = (ah.get("name") or "").lower()
        tag = "CONTRACT" if ah.get("is_contract") else "EOA"
        if ah.get("is_contract") and any(k in nm for k in ("multisig", "vest", "timelock", "lock", "treasury", "gnosissafe")):
            tag = "RISK " + tag
            out["devFlags"].append(addr)
        out["topHolders"].append({"address": addr, "pct": pct, "amount": raw / (10 ** dec) if dec else None,
                                  "isContract": bool(ah.get("is_contract")), "tag": tag})
    return out


def token_details(chain, address):
    try:
        if chain == "solana":
            return _token_details_sol(address)
        if chain == "robinhood":
            return _token_details_rh(address)
        return {"error": "unknown chain " + str(chain)}
    except Exception as e:
        return {"chain": chain, "address": address, "error": str(e)[:200]}


def _render_alpha_intel(rh_data, sol_data):
    """
    Transforms intel rows into component-styled UI cards.
    Caps visibility to the top 4 highest-velocity candidates per chain.
    """
    html = '<div class="alpha-intel-grid">'
    # RH visual cluster (top 4 by 1h event velocity)
    html += '<div class="chain-card rh-card"><h4>🟣 ROBINHOOD CANDIDATES</h4>'
    rh_candidates = sorted(rh_data.get("tokens", []), key=lambda x: x.get("transfers", 0), reverse=True)[:4]
    if not rh_candidates:
        html += '<div class="empty-badge">No active assets in current feed window</div>'
    for token in rh_candidates:
        label, cls = _trend_pct(token.get("chg_h1"))
        html += ("<div class='intel-badge clickable' data-chain='robinhood' data-address='%s' title='View on-chain'>"
                 "<span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s'>%s</span>"
                 "<span class='meta-tag tag-purple'>%s</span>"
                 "<span class='vol-indicator'>📊 1h tx: %s</span></div>"
                 % (str(token.get("address") or ""), str(token.get("symbol", "UNKN"))[:6], cls, label,
                    str(token.get("category", "OTHER"))[:10], format(token.get("transfers", 0), ",")))
    html += '</div>'
    # SOL visual cluster (top 4 by dex liquidity)
    html += '<div class="chain-card sol-card"><h4>🟢 SOLANA CANDIDATES</h4>'
    sol_candidates = sorted(sol_data.get("queue", []), key=lambda x: float(x.get("liq", 0) or 0), reverse=True)[:4]
    if not sol_candidates:
        html += '<div class="empty-badge">Searching meme pool layers...</div>'
    for token in sol_candidates:
        label, cls = _trend_pct(token.get("h1"))
        html += ("<div class='intel-badge clickable' data-chain='solana' data-address='%s' title='View on-chain'>"
                 "<span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s'>%s</span>"
                 "<span class='meta-tag tag-green'>%s</span>"
                 "<span class='vol-indicator'>💧 Liq: $%s</span></div>"
                 % (str(token.get("address") or ""), str(token.get("s", "UNKN"))[:6], cls, label,
                    str(token.get("category", "WATCH"))[:10], format(float(token.get("liq", 0)), ",.0f")))
    html += '</div></div>'
    return html


def _render_live_positions(positions):
    if not positions:
        return "<div class='empty-badge'>No open positions — lane flat</div>"
    cards = []
    for p in positions:
        opened = (str(p.get("openedAt") or "")[:19]).replace("T", " ") + "Z"
        px = p.get("price"); pct = p.get("pct"); pnl = p.get("pnl"); val = p.get("value")
        qty = p.get("qty"); entry = p.get("entryUsd") or 0; cost = p.get("costUsdc") or 0
        peak = p.get("peakUsd") or entry
        sig = str(p.get("signal") or "OPEN")
        pct_s = ("%+.2f%%" % pct) if pct is not None else "—"
        pnl_s = ("%+.2f" % pnl) if pnl is not None else "—"
        val_s = ("$%.4f" % val) if val is not None else "—"
        px_s = ("$%.8g" % px) if px is not None else "—"
        qty_s = ("%.6g" % qty) if qty is not None else "—"
        pct_cls = "trend-up" if (pct or 0) >= 0 else "trend-down"
        pnl_cls = "trend-up" if (pnl or 0) >= 0 else "trend-down"
        sig_cls = "tag-green" if sig.startswith("FEED") else "tag-gold"
        mint_s = p.get("mint") or ""
        btn = "<button class='close-pos' type='button' data-mint='%s' title='Guard-managed manual close'>✕ CLOSE</button>" % mint_s
        head = ("<div class='pos-head'><span class='ticker-badge font-mono'>%s</span>"
                "<span class='trend-pct %s'>%s</span>"
                "<span class='meta-tag %s'>%s</span>"
                "<span class='vol-indicator'>%s</span>%s</div>"
                % (str(p.get("symbol") or "?"), pct_cls, pct_s, sig_cls, sig,
                   "🔒 BANKED" if p.get("banked") else "⚙️ GUARD-MANAGED", btn))
        grid = ("<div class='pos-grid'>"
                "<div><span>Opened (UTC)</span><b>%s</b></div>"
                "<div><span>Size</span><b>$%.2f</b></div>"
                "<div><span>Entry</span><b>%s</b></div>"
                "<div><span>Qty</span><b>%s</b></div>"
                "<div><span>Live mark</span><b>%s</b></div>"
                "<div><span>Value</span><b>%s</b></div>"
                "<div><span>PnL</span><b class='%s'>%s</b></div>"
                "<div><span>Peak</span><b>$%.6g</b></div>"
                "<div><span>Tx</span><b class='font-mono'>%s…</b></div></div>"
                % (opened, cost, ("$%.8g" % entry), qty_s, px_s, val_s, pnl_cls, pnl_s, peak, str(p.get("tx") or "")))
        spk = ""
        if p.get("spark"):
            spk = ("<div class='spark-label'>LIVE MARK · own-tick trail</div>"
                   "<div class='spark pos-spark' data-v='%s' data-h='26'></div>" % p["spark"])
        # stop-distance ruler (guard exit line)
        ruler = ""
        if px is not None and entry:
            banked = bool(p.get("banked"))
            stop = entry if banked else entry * 0.85      # banked -> stop to entry, else HARD -15%
            stop_kind = "ENTRY FLOOR (BANKED)" if banked else "HARD -15% STOP"
            cushion = (px / stop - 1) * 100
            top = max(peak, px, entry)
            if top <= stop:
                top = stop * 1.1
            norm = max(0.0, min(100.0, (px - stop) / (top - stop) * 100))
            col = "#4ade80" if cushion > 8 else ("#fbbf24" if cushion > 3 else "#f87171")
            cush_s = ("%+.1f%%" % cushion) if cushion >= 0 else ("%.1f%% below stop" % -cushion)
            ruler = ("<div class='stop-ruler' title='guard exit: %s · cushion %s'>"
                     "<div class='ruler-top'><span class='ruler-kind'>%s</span>"
                     "<span class='ruler-cush' style='color:%s'>%s to stop</span></div>"
                     "<div class='ruler-track'><div class='ruler-marker' style='left:%d%%'></div></div>"
                     "<div class='ruler-scale'><span>$%.4g STOP</span><span>NOW $%.4g</span><span>PEAK $%.4g</span></div>"
                     "</div>" % (stop_kind, cush_s, stop_kind, col, cush_s, round(norm), stop, px, top))
        # on-chain watch (our own feed activity around the held coin)
        mon_html = ""
        m = p.get("monitor") or {}
        tcol = {"TRENDING": "tag-green", "GAINER": "tag-gold", "MIGRATED": "tag-purple",
                "NEW": "tag-grey", "WATCH": "tag-gold"}
        chips = "".join("<span class='meta-tag %s'>%s@%s</span>" % (tcol.get(t.get("tier"), "tag-grey"),
                                                                    t.get("tier"), t.get("ts"))
                        for t in (m.get("tiers") or []))
        rows_l = "".join("<li><span class='mon-venue'>%s</span><span class='mon-tx'>%s</span>"
                         "<span class='mon-age'>%ss ago</span></li>"
                         % (e.get("venue"), e.get("tx"), e.get("ageSec"))
                         for e in (m.get("latest") or []))
        if not rows_l:
            rows_l = "<li class='mon-empty'>no feed events in last window</li>"
        mon_html = ("<details class='pos-mon'><summary>🔍 ON-CHAIN WATCH · %s events/30m%s</summary>"
                    "<ul>%s</ul><div class='mon-tiers'>%s</div></details>"
                    % (m.get("n30", 0), " · feed-tier trail below" if chips else "", rows_l, chips))
        cards.append("<div class='pos-card clickable' data-chain='solana' data-address='%s' title='View on-chain'>%s%s%s%s%s</div>"
                     % (mint_s, head, grid, spk, ruler, mon_html))
    return "".join(cards)


def _render_portfolio(pf):
    coins = pf.get("coins") or []
    usdc = pf.get("usdcHot")
    rows = []
    if usdc is not None and usdc > 0:
        rows.append("<div class='pf-row'><span class='ticker-badge font-mono'>USDC</span>"
                    "<span class='pf-bal'>%.6g</span><span class='pf-val'>$%.2f</span>"
                    "<span class='meta-tag tag-gold'>BASE ASSET</span>"
                    "<button class='act act-sweep' data-url='/api/sweep-usdc' data-label='SWEEP → VAULT'>SWEEP → VAULT</button></div>" % (usdc, usdc))
    for c in coins:
        val = c.get("value")
        ui = c.get("ui")
        val_s = "$%.2f" % val if val is not None else "—"
        bal = "%.6g" % ui
        name = c.get("name")
        tick = "%s%s" % (c.get("symbol"), ("" if not name else "·" + str(name)[:12]))
        if c.get("lane"):
            act = "<span class='meta-tag tag-gold'>LANE OPEN — use ✕ CLOSE</span>"
        elif val is None:
            act = "<span class='meta-tag tag-grey'>NO PRICE</span>"
        else:
            act = "<button class='act act-sell' data-url='/api/sell-token?mint=%s' data-label='SELL %s → USDC'>SELL → USDC</button>" % (c.get("mint"), c.get("symbol"))
        rows.append("<div class='pf-row clickable' data-chain='solana' data-address='%s' title='View on-chain'>"
                    "<span class='ticker-badge font-mono'>%s</span><span class='pf-bal'>%s</span>"
                    "<span class='pf-val'>%s</span>%s</div>" % (c.get("mint"), tick, bal, val_s, act))
    if not rows:
        return "<div class='empty-badge'>No token holdings in hot wallet</div>"
    return "".join(rows)


def _render_vaults(rows):
    if not rows:
        return "<div class='empty-badge'>No vault/safe addresses configured</div>"
    cards = []
    for r in rows:
        chips = "".join("<span class='meta-tag %s'>%s %s</span>"
                        % ("tag-green" if l.get("usd") else "tag-grey", l.get("k"), l.get("v"))
                        for l in (r.get("lines") or []))
        cards.append("<div class='pf-row'><span class='ticker-badge font-mono'>%s</span>"
                     "<span class='pf-bal'>%s</span>%s"
                     "<span class='meta-tag tag-grey'>READ-ONLY</span></div>"
                     % (r.get("label"), str(r.get("addr", ""))[:18] + "…", chips))
    return "".join(cards)


def render(d):
    on = lambda b: ("🟢" if b else "🔴")
    h = []
    h.append("<!doctype html><html><head><meta charset='utf-8'>")
    h.append("<meta http-equiv='refresh' content='20'><title>Multi-Chain Feed Dashboard</title>")
    h.append("<style>.alpha-intel-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:8px}")
    h.append(".chain-card h4{margin:0 0 8px;font-size:13px}.rh-card{border-top:3px solid #a855f7}.sol-card{border-top:3px solid #22c55e}")
    h.append(".intel-badge{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:6px}")
    h.append(".ticker-badge{background:#0f172a;padding:2px 8px;border-radius:4px;font-weight:bold;color:#f8fafc}")
    h.append(".trend-up{color:#4ade80;font-weight:600}.trend-down{color:#f87171;font-weight:600}.trend-flat{color:#94a3b8}.trend-warn{color:#fbbf24;font-weight:600}")
    h.append(".meta-tag{font-size:.7rem;padding:2px 6px;border-radius:4px;text-transform:uppercase;letter-spacing:.03em}")
    h.append(".tag-purple{background:#581c87;color:#e9d5ff}.tag-green{background:#064e3b;color:#a7f3d0}")
    h.append(".vol-indicator{color:#94a3b8;font-size:.8rem}.empty-badge{background:#111a2e;border:1px dashed #334155;border-radius:6px;padding:8px;color:#64748b;font-size:.85rem;text-align:center}")
    h.append(".font-mono{font-family:ui-monospace,Menlo,monospace}.delta-mismatch{animation:flashwarn 1.6s infinite}")
    h.append("@keyframes flashwarn{0%,100%{opacity:1}50%{opacity:.35}}@media(max-width:720px){.alpha-intel-grid{grid-template-columns:1fr}}</style>")
    h.append("<style>.clickable{cursor:pointer}.clickable:hover{border-color:#4ade80!important}")
    h.append(".modal-overlay{position:fixed;inset:0;background:rgba(2,6,23,.78);display:flex;align-items:center;justify-content:center;z-index:50}")
    h.append(".modal{background:#0f172a;border:1px solid #334155;border-radius:14px;width:min(680px,94vw);max-height:88vh;overflow:auto;padding:18px 20px;box-shadow:0 20px 60px #000a}")
    h.append(".modal h2{display:flex;align-items:center;gap:10px;margin:0 0 12px;font-size:18px;color:#f8fafc}")
    h.append(".modal img.avatar{width:44px;height:44px;border-radius:10px;border:1px solid #334155;background:#1e293b}")
    h.append(".modal .ca{color:#64748b;font-size:.75rem;word-break:break-all}")
    h.append(".modal .vit{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0}")
    h.append(".modal .vit .cell{background:#111a2e;border:1px solid #26324a;border-radius:8px;padding:8px 10px}")
    h.append(".modal .vit .cell b{display:block;font-size:1.02rem;color:#e6edf3}.modal .vit .cell span{font-size:.68rem;color:#8b98b8;text-transform:uppercase}")
    h.append(".modal .holder{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 10px;margin:5px 0;background:#111a2e;border:1px solid #26324a;border-radius:8px;font-size:.85rem}")
    h.append(".risk{color:#f87171;border-color:#7f1d1d!important}.tag-red{background:#7f1d1d;color:#fecaca}.tag-grey{background:#334155;color:#e2e8f0}.tag-gold{background:#78350f;color:#fde68a}")
    h.append(".modal .close{float:right;cursor:pointer;color:#94a3b8;font-size:20px;line-height:1}</style>")
    h.append("<style>.pos-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 14px;margin:8px 0}")
    h.append(".pos-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}")
    h.append(".pos-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}")
    h.append(".pos-grid>div{background:#111a2e;border:1px solid #26324a;border-radius:8px;padding:6px 9px}")
    h.append(".pos-grid span{display:block;font-size:.62rem;color:#8b98b8;text-transform:uppercase;letter-spacing:.04em}")
    h.append(".pos-grid b{font-size:.95rem;color:#e6edf3;word-break:break-all}</style>")
    h.append("<style>.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding-bottom:10px;border-bottom:1px solid #1f2a44}")
    h.append("h1{font-size:20px;letter-spacing:.02em;margin:0;background:linear-gradient(90deg,#7ee787,#38bdf8);-webkit-background-clip:text;background-clip:text;color:transparent}")
    h.append(".pill{border:1px solid #334155;border-radius:999px;padding:3px 10px;font-size:.72rem;background:#111a2e;color:#94a3b8;font-weight:600;letter-spacing:.04em}")
    h.append(".pill.green{color:#7ee787;border-color:#14532d}.pill.bad{color:#ff7b72;border-color:#7f1d1d}.pill.grey{color:#94a3b8}")
    h.append(".pos-section{border:1px solid #14532d;background:linear-gradient(180deg,rgba(20,83,45,.14),#111a2e);margin-top:12px}")
    h.append("::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-thumb{background:#26324a;border-radius:6px}::-webkit-scrollbar-track{background:transparent}</style>")
    h.append("<style>.spark{margin:6px 0 2px}.spark svg{display:block;width:100%;height:100%;overflow:visible}")
    h.append(".sp-draw{stroke-dasharray:1;stroke-dashoffset:1;animation:spdraw .7s ease forwards}")
    h.append("@keyframes spdraw{to{stroke-dashoffset:0}}@keyframes sppulse{0%,100%{opacity:1}50%{opacity:.35}}")
    h.append(".sp-dot{animation:sppulse 1.8s infinite}</style>")
    h.append("<style>.spark-label{font-size:.62rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em;margin:8px 0 2px}")
    h.append(".pos-spark{margin:2px 0 0;background:#0f172a;border:1px solid #1f2a44;border-radius:8px;padding:4px 8px}</style>")
    h.append("<style>.stop-ruler{margin:8px 2px 0;padding:7px 9px;background:#0b1220;border:1px solid #1f2a44;border-radius:9px}")
    h.append(".ruler-top{display:flex;justify-content:space-between;align-items:center;font-size:.7rem;margin-bottom:6px;gap:8px;flex-wrap:wrap}")
    h.append(".ruler-kind{color:#8b98b8;letter-spacing:.05em}.ruler-cush{font-weight:700}")
    h.append(".ruler-track{position:relative;height:6px;border-radius:99px;background:linear-gradient(90deg,#f87171,#fbbf24 55%,#4ade80)}")
    h.append(".ruler-marker{position:absolute;top:50%;transform:translate(-50%,-50%);width:11px;height:11px;border-radius:50%;background:#f8fafc;border:2px solid #0b1220;box-shadow:0 0 0 1px #64748b}")
    h.append(".ruler-scale{display:flex;justify-content:space-between;margin-top:4px;font-size:.62rem;color:#64748b}</style>")
    h.append("<style>.close-pos{margin-left:auto;background:transparent;border:1px solid #7f1d1d;color:#f87171;border-radius:6px;padding:2px 9px;font-size:.7rem;cursor:pointer;font-weight:700;line-height:1.5}")
    h.append(".close-pos:hover,.close-pos.armed{background:#7f1d1d;color:#fecaca}")
    h.append(".pos-mon{margin-top:8px;border-top:1px dashed #1f2a44;padding-top:6px;font-size:.78rem;color:#94a3b8}")
    h.append(".pos-mon summary{cursor:pointer;color:#8b98b8;font-size:.75rem;user-select:none}")
    h.append(".pos-mon ul{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}")
    h.append(".pos-mon li{display:flex;gap:10px;align-items:center;font-size:.72rem}")
    h.append(".mon-venue{color:#7ee787;min-width:84px;text-transform:lowercase}.mon-tx{font-family:ui-monospace,Menlo,monospace;color:#e2e8f0}")
    h.append(".mon-age{color:#64748b;margin-left:auto}.mon-empty{color:#64748b;font-style:italic}")
    h.append(".mon-tiers{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}</style>")
    h.append("<style>.pf-row{display:flex;align-items:center;gap:10px;background:#111a2e;border:1px solid #26324a;border-radius:8px;padding:8px 12px;margin:5px 0;font-size:.85rem;flex-wrap:wrap}")
    h.append(".pf-bal{color:#94a3b8;font-size:.8rem}.pf-val{color:#e6edf3;font-weight:600}")
    h.append(".act{background:transparent;border:1px solid #14532d;color:#7ee787;border-radius:6px;padding:3px 10px;font-size:.72rem;font-weight:700;cursor:pointer;margin-left:auto}")
    h.append(".act.act-sell{border-color:#14532d}.act.act-sweep{border-color:#1d4ed8;color:#93c5fd}")
    h.append(".act.armed{background:#14532d;color:#052e16}.act-sweep.armed{background:#1d4ed8;color:#dbeafe}</style>")
    h.append("<style>.pf-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:6px;padding:8px 10px;background:#0b1220;border:1px solid #1f2a44;border-radius:9px}")
    h.append(".pf-tools .stat{color:#94a3b8;font-size:.78rem}.act-reb{border-color:#7c3aed;color:#d8b4fe;margin-left:0}.act-reb:disabled{opacity:.5}")
    h.append(".act-go{border-color:#7f1d1d;color:#f87171}.act-cancel{border-color:#334155;color:#94a3b8}</style>")
    h.append("<style>body{font-family:ui-monospace,Menlo,monospace;background:#0b1020;color:#e6edf3;margin:0;padding:16px}")
    h.append("h1{font-size:16px;color:#7ee787}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-top:12px}")
    h.append(".card{background:#111a2e;border:1px solid #26324a;border-radius:10px;padding:12px}")
    h.append(".k{color:#8b98b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em}.v{font-size:22px;font-weight:700}")
    h.append(".ok{color:#7ee787}.bad{color:#ff7b72}.sub{color:#8b98b8;font-size:11px}")
    h.append("table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:4px 6px;border-bottom:1px solid #1f2a44;text-align:left}</style></head><body>")
    da0 = d.get("daemons") or {}
    ln0 = d.get("lane") or {}
    pill_good = bool(da0) and all(da0.values())
    h.append("<div class='topbar'><h1>📡 MULTI-CHAIN FEED DASHBOARD</h1>"
             "<div style='display:flex;gap:8px;flex-wrap:wrap'><span class='pill %s'>● FEEDS %s</span>"
             "<span class='pill %s'>LANE OPEN %d</span></div></div>"
             % ("green" if pill_good else "bad", "LIVE" if pill_good else "DOWN",
                "green" if (ln0.get("open") or 0) > 0 else "grey", ln0.get("open") or 0))
    h.append("<div class='sub'>as of %s UTC · auto-refresh 20s · our own chain data, no subscriptions · "
             "today spent $%s · realized $%s</div>"
             % (d["asOf"][:19], ln0.get("spentToday") if ln0.get("spentToday") is not None else "0.0",
                ln0.get("realizedToday") if ln0.get("realizedToday") is not None else "0.0"))

    # LIVE POSITIONS — its own hero column (open positions live here)
    h.append("<div class='card pos-section'><div class='k'>Real-coin lane — LIVE POSITIONS (%d open)</div>" % (ln0.get("open") or 0))
    h.append(_render_live_positions(ln0.get("positions") or []))
    h.append("</div>")

    h.append("<div class='grid'>")
    # daemon health
    da = d["daemons"]
    h.append("<div class='card'><div class='k'>Feed Daemons</div>")
    for n in ("sol", "rh", "merge", "bench"):
        h.append("<div>%s <b>%s</b></div>" % (on(da.get(n, False)), n.upper()))
    h.append("</div>")
    # rows captured
    r = d["rows"]
    h.append("<div class='card'><div class='k'>Events captured</div>")
    h.append("<div>SOL <b class='v ok'>%s</b></div>" % r.get("solana.jsonl", 0))
    h.append("<div>RH&nbsp; <b class='v ok'>%s</b></div>" % r.get("robinhood.jsonl", 0))
    h.append("<div class='sub'>unified %s · benchmarked %s</div>" % (r.get("unified.jsonl", 0), r.get("bench.jsonl", 0)))
    h.append("</div>")
    # balances
    b = d.get("balances", {})
    h.append("<div class='card'><div class='k'>Desk cash (live)</div>")
    if b:
        h.append("<div>SOL vault <b>$%.2f</b></div>" % b.get("vault", 0))
        h.append("<div>SOL hot <b>$%.2f</b></div>" % b.get("hot", 0))
        h.append("<div>Base safe <b>$%.2f</b></div>" % b.get("safe", 0))
    h.append("<div class='sub'>micro snatcher %s</div>" % ("paused" if d.get("paused") else "RUNNING"))
    h.append("</div>")
    # recency
    rec = d["recency"]
    h.append("<div class='card'><div class='k'>Feed recency</div>")
    for c in ("sol", "rh"):
        age = rec.get(c)
        ok = age is not None and age <= 180
        h.append("<div>%s %s <b class='%s'>%ss</b></div>" % (on(ok), c.upper(), "ok" if ok else "bad", age if age is not None else "?"))
    h.append("</div>")
    # benchmark
    bm = d.get("bench", {})
    h.append("<div class='card'><div class='k'>Earliness benchmark</div>")
    h.append("<div>with delta <b>%s</b> · avg <b>%ss</b></div>" % (bm.get("withDelta"), bm.get("avgDeltaSec")))
    deltas = [e.get("deltaSec") for e in (bm.get("liquidityVsDelta") or []) if e.get("deltaSec") is not None][-30:]
    if len(deltas) >= 2:
        h.append("<div class='spark' data-v='%s' data-h='34' title='forward-edge trend'></div>" % ",".join("%.1f" % v for v in deltas))
    h.append("<div class='sub'>%s</div>" % (bm.get("note") or ""))
    h.append("</div>")
    # rh classification
    al = d.get("alpha", {})
    h.append("<div class='card'><div class='k'>RH classification</div>")
    for k in ("equity", "stable", "native", "other"):
        h.append("<div>%s <b>%s</b></div>" % (k, al.get(k, 0)))
    h.append("</div>")
    h.append("</div>")  # end grid

    # PORTFOLIO MANAGER — HOT / TRADING wallet (executor wallet actions)
    pf = d.get("portfolio") or {}
    h.append("<div class='card' style='margin-top:12px'><div class='k'>PORTFOLIO MANAGER — HOT / TRADING wallet</div>")
    h.append("<div class='sub'>executor wallet holdings · vault/safe is read-only below · lane positions close via their card · actions use the lane swap path + vault sweep</div>")
    _b_usd = pf.get("usdcHot") or 0
    _o_usd = pf.get("estNonUsdc") or 0
    _tot = _b_usd + _o_usd
    _bpct = round(_b_usd / _tot * 100, 1) if _tot else 0.0
    _pmc = _pm_cfg()
    h.append("<div class='pf-tools'><span class='stat'>hot USDC $%.2f · est. other $%.2f · → USDC %.1f%% · target ≥ %.0f%% · coin cap ≤ %.0f%%</span>"
             "<button class='act act-reb' type='button'>🔄 REBALANCE</button></div>"
             % (_b_usd, _o_usd, _bpct, _pmc["baseTargetPct"], _pmc["maxCoinWeightPct"]))
    h.append(_render_portfolio(pf))
    h.append("</div>")

    # VAULT / SAFE — capital owners (read-only)
    vts = d.get("vaults") or []
    h.append("<div class='card' style='margin-top:12px'><div class='k'>VAULT / SAFE — capital owners (read-only)</div>")
    h.append("<div class='sub'>these wallets own the reserve; delegate approvals + Safe module move funds — the PM only reads them here</div>")
    h.append(_render_vaults(vts))
    h.append("</div>")

    # alpha intel section (full-width visual clusters)
    it = d.get("intel", {})
    c_ = it.get("counts") or {}
    rt = it.get("chainRefTime") or {}
    h.append("<div class='card' style='margin-top:12px'><div class='k'>Alpha intel — top candidates (terminal funnel)</div>")
    h.append("<div class='sub'>RH %s · SOL %s · migrated %s · ref RH %s / SOL %s</div>" % (
        c_.get("robinhood"), c_.get("solana"), c_.get("migrated"),
        str(rt.get("robinhood", "…"))[11:19], str(rt.get("solana", "…"))[11:19]))
    h.append(_render_alpha_intel(it.get("rh_data", {}), it.get("sol_data", {})))
    h.append("</div>")

    # benchmark sample (badge-styled, flags speed-delta mismatches < 15s)
    rows = (bm.get("liquidityVsDelta") or [])[-10:]
    h.append("<div class='card' style='margin-top:12px'><div class='k'>Benchmark sample (latest) — forward edge vs DexScreener</div>")
    if not rows:
        h.append("<div class='empty-badge'>No benchmark deltas yet — waiting for live forward captures</div>")
    for e in rows:
        label, cls, flag = _delta_badge(e.get("deltaSec"))
        h.append("<div class='intel-badge clickable' data-chain='%s' data-address='%s' title='View on-chain'>"
                 "<span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s %s'>%s</span>"
                 "<span class='meta-tag tag-purple'>%s</span>"
                 "<span class='vol-indicator'>💧 $%s</span></div>"
                 % (str(e.get("chain", "")), str(e.get("mint", "")),
                    str(e.get("chain", "?"))[:2] + ":" + str(e.get("mint", ""))[:10], cls, flag, label,
                    "EDGE", format(float(e.get("liqUsd") or 0), ",.0f")))
    h.append("</div>")
    h.append("""<script>
function mdFmt(x){ if(x===null||x===undefined) return '—'; return Number(x).toLocaleString(undefined,{maximumFractionDigits:4}); }
function openTokenDetails(el){
  var chain=el.getAttribute('data-chain'), addr=el.getAttribute('data-address');
  if(!addr) return;
  var ov=document.createElement('div'); ov.className='modal-overlay';
  var m=document.createElement('div'); m.className='modal';
  m.innerHTML="<div class='ca' id='md-load'>⏳ Loading on-chain vitals…</div>";
  ov.appendChild(m); document.body.appendChild(ov);
  function close(){ if(ov.parentNode) document.body.removeChild(ov); }
  ov.addEventListener('click',function(e){ if(e.target===ov) close(); });
  fetch('/api/token-details?chain='+encodeURIComponent(chain)+'&address='+encodeURIComponent(addr))
   .then(function(r){return r.json();}).then(function(d){
    var b=document.getElementById('md-load'); b.id='';
    if(d.error){ b.textContent='⚠️ '+d.error; return; }
    var h2=document.createElement('h2');
    if(d.avatar){ var im=document.createElement('img'); im.className='avatar'; im.alt=''; im.src=d.avatar; im.onerror=function(){ this.parentNode.removeChild(this); }; h2.appendChild(im); }
    var tt=document.createElement('span'); tt.textContent='🪙 '+((d.symbol||'?')+(d.name? ' — '+d.name:''));
    var cx=document.createElement('span'); cx.className='close'; cx.textContent='×'; cx.onclick=close;
    h2.appendChild(tt); h2.appendChild(cx); b.appendChild(h2);
    var ca=document.createElement('div'); ca.className='ca'; ca.textContent='CA: '+d.address; b.appendChild(ca);
    var vit=document.createElement('div'); vit.className='vit';
    var cells=[['Current Price', d.price!=null? '$'+Number(d.price).toPrecision(6):'—'],
               ['Total Supply', d.totalSupply!=null? mdFmt(d.totalSupply):'—'],
               ['Holders', d.holdersCount!=null? mdFmt(d.holdersCount):(d.topHolders? d.topHolders.length+' top':'—')],
               ['Liquidity', d.liqUsd? '$'+mdFmt(d.liqUsd):(d.vol24h!=null? '24h vol $'+mdFmt(d.vol24h):'—')],
               ['Pool', d.pool? String(d.pool).slice(0,10)+'…':(d.dex||'—')],
               ['Decimals', d.decimals!=null? d.decimals:'—']];
    cells.forEach(function(c){ var cell=document.createElement('div'); cell.className='cell';
      var b1=document.createElement('b'); b1.textContent=c[1]; var s=document.createElement('span'); s.textContent=c[0];
      cell.appendChild(b1); cell.appendChild(s); vit.appendChild(cell); });
    b.appendChild(vit);
    var hh=document.createElement('div'); hh.style.marginTop='12px'; hh.style.fontSize='13px'; hh.textContent='👥 TOP HOLDER CONCENTRATION'; b.appendChild(hh);
    if(d.topHolders && d.topHolders.length){
      d.topHolders.forEach(function(h){ var row=document.createElement('div'); row.className='holder';
        if(h.tag && (h.tag.indexOf('RISK')>=0||h.tag.indexOf('DEV')>=0)) row.className+=' risk';
        var l=document.createElement('span'); l.textContent=(h.pct!=null? h.pct+'% · ':'')+String(h.address||'').slice(0,14)+'…';
        var tg=document.createElement('span'); tg.className='meta-tag '+(h.tag?(h.tag.indexOf('RISK')>=0||h.tag.indexOf('DEV')>=0?'tag-red':'tag-gold'):'tag-grey');
        tg.textContent=h.tag||(h.isContract?'CONTRACT':'EOA'); row.appendChild(l); row.appendChild(tg); b.appendChild(row); });
    } else b.appendChild(document.createTextNode('  no holder data returned'));
    if(d.history && d.history.length){
      var hb=document.createElement('div'); hb.style.marginTop='12px'; hb.style.fontSize='13px'; hb.textContent='📈 FEED TIER HISTORY'; b.appendChild(hb);
      var wrap=document.createElement('div'); wrap.style.display='flex'; wrap.style.flexWrap='wrap'; wrap.style.gap='6px'; wrap.style.marginTop='4px';
      var tierCol={'TRENDING':'tag-green','GAINER':'tag-gold','MIGRATED':'tag-purple','NEW':'tag-grey','WATCH':'tag-gold'};
      d.history.slice(-6).forEach(function(hh){
        var sp=document.createElement('span'); sp.className='meta-tag '+(tierCol[hh.tier]||'tag-grey');
        var hm=String(hh.ts||'').slice(11,16); sp.textContent=hh.tier+'@'+hm+' 1h:'+hh.t60; wrap.appendChild(sp);
      });
      b.appendChild(wrap);
      var hs2=document.createElement('div'); hs2.className='spark';
      hs2.setAttribute('data-v', d.history.map(function(h){ return h.t60; }).join(','));
      b.appendChild(hs2); sparkMount(hs2);
    }
    if(d.benchmark){
      var bd=d.benchmark.lastDeltaSec, brow=document.createElement('div'); brow.className='holder';
      var bl=document.createElement('span'); bl.textContent='⚡ Earliness vs DexScreener';
      var bt=document.createElement('span'); bt.className='meta-tag ';
      if(bd===null||bd===undefined){ bt.textContent='no benchmark yet'; bt.className+=' tag-grey'; }
      else if(bd<0){ bt.textContent=Number(bd).toFixed(1)+'s — aggregator beat us'; bt.className+=' trend-down'; }
      else if(bd<15){ bt.textContent='⚠️ +'+Number(bd).toFixed(1)+'s lead (<15s)'; bt.className+=' tag-red delta-mismatch'; }
      else { bt.textContent='+'+Number(bd).toFixed(1)+'s forward'; bt.className+=' tag-green'; }
      brow.appendChild(bl); brow.appendChild(bt); b.appendChild(brow);
    }
    if(d.devFlags && d.devFlags.length){ var w=document.createElement('div'); w.className='meta-tag tag-red'; w.style.marginTop='8px';
      w.textContent='⚠️ developer / vesting-linked wallet present in top holders'; b.appendChild(w); }
   }).catch(function(e){ var b=document.getElementById('md-load'); if(b){ b.textContent='fetch error'; } });
}
document.addEventListener('click',function(e){ var t=e.target;
  var ignore=t.closest?t.closest('.close-pos,.pos-mon,details,summary,button,a,input'):null;
  var el=t.closest?t.closest('.clickable[data-address]'):null;
  if(el && !ignore) openTokenDetails(el); });
document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ var o=document.querySelector('.modal-overlay'); if(o&&o.parentNode) document.body.removeChild(o); } });
window.__sparkSeq=0;
function sparkMount(el){
  if(!el) return;
  var raw=el.getAttribute('data-v')||'';
  var vals=raw.split(',').map(Number).filter(function(v){ return !isNaN(v); });
  if(vals.length<2){ el.innerHTML=''; return; }
  var W=280, H=parseInt(el.getAttribute('data-h')||'40',10)||40, pad=8;
  var mn=Math.min.apply(null,vals), mx=Math.max.apply(null,vals), rng=(mx-mn)||1;
  function X(i){ return pad+(i/(vals.length-1))*(W-2*pad); }
  function Y(v){ return pad+(1-(v-mn)/rng)*(H-2*pad); }
  var pts=vals.map(function(v,i){ return [X(i).toFixed(1),Y(v).toFixed(1)]; });
  var line=pts.map(function(p,i){ return (i?'L':'M')+p[0]+' '+p[1]; }).join(' ');
  var area=line+' L'+X(vals.length-1).toFixed(1)+' '+(H-1)+' L'+X(0).toFixed(1)+' '+(H-1)+' Z';
  var col=(vals[vals.length-1]>=vals[0])?'#4ade80':'#f87171';
  var hi=vals.indexOf(mx), lo=vals.indexOf(mn);
  var id='spk'+(++window.__sparkSeq);
  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img">';
  svg+='<defs><linearGradient id="'+id+'" x1="0" y1="0" x2="0" y2="1">';
  svg+='<stop offset="0" stop-color="'+col+'" stop-opacity="0.22"/><stop offset="1" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>';
  svg+='<path d="'+area+'" fill="url(#'+id+')"/>';
  svg+='<path d="'+line+'" fill="none" stroke="'+col+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" pathLength="1" class="sp-draw"/>';
  svg+='<circle cx="'+pts[lo][0]+'" cy="'+pts[lo][1]+'" r="2.2" fill="#fbbf24"/>';
  if(hi!==lo){ svg+='<circle cx="'+pts[hi][0]+'" cy="'+pts[hi][1]+'" r="2.2" fill="#e2e8f0"/>'; }
  svg+='<circle cx="'+pts[pts.length-1][0]+'" cy="'+pts[pts.length-1][1]+'" r="3" fill="'+col+'" class="sp-dot"/>';
  svg+='</svg>';
  el.innerHTML=svg; el.style.height=H+'px';
}
function openConfirm(o){
  var ov=document.createElement('div'); ov.className='modal-overlay';
  var m=document.createElement('div'); m.className='modal';
  m.innerHTML="<h2><span>⚠️ "+o.title+"</span><span class='close' id='mcc'>×</span></h2>"+
    "<div class='ca' style='margin:4px 0 10px' id='msub'></div>"+
    "<div id='mcl' style='max-height:200px;overflow:auto'></div>"+
    "<div style='display:flex;gap:8px;margin-top:14px;justify-content:flex-end'>"+
    "<button class='act act-cancel' id='mcan' type='button'>CANCEL</button>"+
    "<button class='act act-go' id='mgo' type='button'>"+o.okLabel+"</button></div>";
  ov.appendChild(m); document.body.appendChild(ov);
  function close(){ if(ov.parentNode) document.body.removeChild(ov); }
  document.getElementById('mcc').onclick=close;
  document.getElementById('mcan').onclick=close;
  document.getElementById('msub').textContent=o.sub||'';
  var lst=document.getElementById('mcl');
  if(o.lines && o.lines.length){ o.lines.forEach(function(l){ var d=document.createElement('div'); d.className='ca'; d.style.padding='3px 0'; d.textContent=l; lst.appendChild(d); }); }
  ov.addEventListener('click',function(e){ if(e.target===ov) close(); });
  document.getElementById('mgo').onclick=function(){
    this.disabled=true; this.textContent='EXECUTING…';
    fetch(o.url,{method:'POST'}).then(function(r){return r.json();}).then(function(res){
      if(res.error){ alert(res.error); close(); return; }
      if(res.results){ alert('Rebalance executed: '+(res.succeeded||0)+' sold · '+(res.failed||0)+' failed'); }
      else alert(o.doneMsg||'Done');
      setTimeout(function(){ location.reload(); },900);
    }).catch(function(){ alert('request error'); close(); });
  };
}
document.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('.close-pos'):null; if(!b) return;
  e.stopPropagation();
  openConfirm({title:'Close open position?', sub:'Guard-managed FULL exit of this lane position. Proceeds settle to USDC, then sweep to vault.', okLabel:'CLOSE POSITION', url:'/api/close-position?mint='+encodeURIComponent(b.getAttribute('data-mint'))});
});
document.addEventListener('click',function(e){
  var a=e.target.closest?e.target.closest('.act.act-sell, .act.act-sweep'):null; if(!a) return;
  e.stopPropagation();
  openConfirm({title:a.getAttribute('data-label')||'Execute action', sub:'Executes via the lane swap path, settles to USDC, then sweeps to the vault.', okLabel:'CONFIRM EXECUTE', url:a.getAttribute('data-url')});
});
document.addEventListener('click',function(e){
  var r=e.target.closest?e.target.closest('.act-reb'):null; if(!r) return; e.stopPropagation();
  r.disabled=true; r.textContent='…';
  fetch('/api/rebalance-preview',{method:'POST'}).then(function(rr){return rr.json();}).then(function(res){
    r.disabled=false; r.textContent='🔄 REBALANCE';
    if(res.error){ alert(res.error); return; }
    if(!res.plan || !res.plan.length){ alert('Already balanced — USDC at '+res.basePct+'% (target '+res.targetPct+'%)'); return; }
    var lines=['Equity ~$'+res.equity+' · USDC '+res.basePct+'% (target ≥ '+res.targetPct+'%)','Proposed sells ≈ $'+res.totalSellUsd+' of '+res.plan.length+' coin(s):'];
    res.plan.forEach(function(p){ lines.push((p.kind==='lane'?'🔒 LANE ':'🪙 ')+p.symbol+' — $'+p.value+' ('+p.reason+')'); });
    openConfirm({title:'Rebalance proposal', sub:'Sell overweight / excess coins to restore the target USDC allocation. Lane coins close guard-managed.', okLabel:'EXECUTE REBALANCE', url:'/api/rebalance-execute', lines:lines});
  }).catch(function(){ r.disabled=false; r.textContent='🔄 REBALANCE'; alert('preview error'); });
});
document.querySelectorAll('.spark[data-v]').forEach(function(el){ sparkMount(el); });
</script>""")
    h.append("</body></html>")
    return "\n".join(h)


def _close_position(mint):
    """Guard-managed manual close: full exit via the lane's own do_sell path."""
    if not (isinstance(mint, str) and len(mint) >= 32):
        return {"error": "bad mint"}
    try:
        import importlib.util as _iu
        s = _iu.spec_from_file_location("flc", os.path.join(ROOT, "scripts", "fastlane.py"))
        fl = _iu.module_from_spec(s)
        s.loader.exec_module(fl)
        obj = fl.load_positions()
        pos = next((x for x in obj.get("positions", []) if x.get("status") == "open" and x.get("mint") == mint), None)
        if not pos:
            return {"error": "no open position for mint"}
        px = _dex_for([mint]).get(mint, {}).get("price")
        if not px:
            return {"error": "no live price — cannot mark-to-market close"}
        r = fl.do_sell(pos, px, "BOSS MANUAL CLOSE", 1.0)
        if r is None:
            return {"error": "sell failed — see logs/trades.jsonl"}
        st = fl.reset_day(fl.F.load(fl.STATE_FILE, {}))
        st["realizedToday"] = round(float(st.get("realizedToday") or 0) + r, 2)
        fl.F.save(fl.STATE_FILE, st)
        fl.save_positions(obj)
        return {"ok": True, "symbol": pos.get("symbol"), "realized": round(r, 2),
                "tx": (pos.get("lastExit") or {}).get("tx", "")}
    except Exception as e:
        return {"error": str(e)[:240]}


def _sell_token(mint):
    """Portfolio sell: non-lane wallet coin -> USDC (decimals-correct raw via lane swap path)."""
    try:
        import importlib.util as _iu
        s = _iu.spec_from_file_location("fls", os.path.join(ROOT, "scripts", "autopilot.py"))
        au = _iu.module_from_spec(s)
        s.loader.exec_module(au)
        lane = None
        try:
            f2 = _iu.spec_from_file_location("fll", os.path.join(ROOT, "scripts", "fastlane.py"))
            fl = _iu.module_from_spec(f2)
            f2.loader.exec_module(fl)
            lane = next((x for x in fl.load_positions().get("positions", [])
                         if x.get("status") == "open" and x.get("mint") == mint), None)
        except Exception:
            pass
        if lane:
            return {"error": "that is an open LANE position — use ✕ CLOSE on its card"}
        if mint == USDC_MINT:
            return {"error": "USDC is the base asset — use SWEEP to vault"}
        held = next((h for h in _wallet_holdings() if h["mint"] == mint), None)
        if not held:
            return {"error": "no balance for that mint"}
        raw = int(held["ui"] * (10 ** held["decimals"]))
        if raw <= 0:
            return {"error": "dust below one raw unit"}
        before = au.token_balance_retry(au.USDC) or 0
        sig, err = au.build_and_send(mint, au.USDC, raw, 500, "/tmp/portfolio_sell.b64")
        if not sig:
            return {"error": (err or "sell failed")[:240]}
        time.sleep(3)
        proceeds = (au.token_balance_retry(au.USDC) or 0) - before
        if proceeds <= 0:
            proceeds = 0.0
        try:
            au.hot_to_vault()
        except Exception:
            pass
        try:
            with open(os.path.join(ROOT, "logs", "trades.jsonl"), "a") as f:
                f.write(json.dumps({"event": "portfolio_sell", "mint": mint,
                                    "ui": held["ui"], "proceedsUsdc": round(proceeds, 6),
                                    "tx": sig[:40], "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}) + "\n")
        except Exception:
            pass
        return {"ok": True, "symbol": mint[:8], "realized": round(proceeds, 6), "tx": sig[:24]}
    except Exception as e:
        return {"error": str(e)[:240]}


def _sweep_usdc():
    try:
        import importlib.util as _iu
        s = _iu.spec_from_file_location("flw", os.path.join(ROOT, "scripts", "fastlane.py"))
        fl = _iu.module_from_spec(s)
        s.loader.exec_module(fl)
        fl.A.hot_to_vault()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)[:200]}


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/close-position":
            q = parse_qs(parsed.query)
            mint = (q.get("mint") or [""])[0]
            body = json.dumps(_close_position(mint)).encode()
        elif parsed.path == "/api/sell-token":
            q = parse_qs(parsed.query)
            mint = (q.get("mint") or [""])[0]
            body = json.dumps(_sell_token(mint)).encode()
        elif parsed.path == "/api/sweep-usdc":
            body = json.dumps(_sweep_usdc()).encode()
        elif parsed.path == "/api/rebalance-preview":
            snap = _pm_snapshot()
            plan = _rebalance_plan(snap)
            body = json.dumps({"equity": snap["equity"], "basePct": snap["basePct"],
                               "targetPct": snap["targetPct"], "usdc": round(snap["usdc"], 2),
                               "needUsd": plan["needUsd"], "targetUsd": plan["targetUsd"],
                               "totalSellUsd": plan["totalSellUsd"],
                               "plan": plan["plan"]}).encode()
        elif parsed.path == "/api/rebalance-execute":
            snap = _pm_snapshot()
            plan = _rebalance_plan(snap)["plan"]
            results = _pm_rebalance_execute(plan)
            ok = sum(1 for r in results if r.get("ok"))
            body = json.dumps({"results": results, "succeeded": ok, "failed": len(results) - ok}).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/token-details":
            q = parse_qs(parsed.query)
            chain = (q.get("chain") or [""])[0]
            address = (q.get("address") or [""])[0]
            body = json.dumps(token_details(chain, address)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = render(_cached_page_data()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


_PAGE_CACHE = {}
_PAGE_LOCK = threading.Lock()


def _refresher():
    while True:
        try:
            d = collect()
            _persist_marks(d)
            with _PAGE_LOCK:
                _PAGE_CACHE["d"] = d
        except Exception:
            pass
        time.sleep(20)


def _cached_page_data():
    d = _PAGE_CACHE.get("d")
    if d is None:
        d = collect()
        _persist_marks(d)
        with _PAGE_LOCK:
            _PAGE_CACHE["d"] = d
    return d


def main():
    port = 8127
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    threading.Thread(target=_refresher, daemon=True).start()
    with S(("127.0.0.1", port), H) as srv:
        print("📊 Feed dashboard on http://127.0.0.1:%d  (ctrl-c to stop)" % port)
        srv.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")

