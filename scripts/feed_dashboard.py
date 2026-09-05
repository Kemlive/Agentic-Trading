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
    auth = meta.get("authorities") or {}
    out["authorities"] = {k: v for k, v in auth.items() if v}
    dev = {k: v for k, v in auth.items() if v}
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
            if dev and owner and (list(dev.values())[0] == owner or owner in dev.values()):
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
        head = ("<div class='pos-head'><span class='ticker-badge font-mono'>%s</span>"
                "<span class='trend-pct %s'>%s</span>"
                "<span class='meta-tag %s'>%s</span>"
                "<span class='vol-indicator'>%s</span></div>"
                % (str(p.get("symbol") or "?"), pct_cls, pct_s, sig_cls, sig,
                   "🔒 BANKED" if p.get("banked") else "⚙️ GUARD-MANAGED"))
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
        cards.append("<div class='pos-card clickable' data-chain='solana' data-address='%s' title='View on-chain'>%s%s</div>"
                     % (p.get("mint") or "", head, grid))
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
    h.append("<div class='sub'>%s</div>" % (bm.get("note") or ""))
    h.append("</div>")
    # rh classification
    al = d.get("alpha", {})
    h.append("<div class='card'><div class='k'>RH classification</div>")
    for k in ("equity", "stable", "native", "other"):
        h.append("<div>%s <b>%s</b></div>" % (k, al.get(k, 0)))
    h.append("</div>")
    h.append("</div>")  # end grid

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
document.addEventListener('click',function(e){ var el=e.target.closest?e.target.closest('.clickable[data-address]'):null; if(el) openTokenDetails(el); });
document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ var o=document.querySelector('.modal-overlay'); if(o&&o.parentNode) document.body.removeChild(o); } });
</script>""")
    h.append("</body></html>")
    return "\n".join(h)


class H(http.server.BaseHTTPRequestHandler):
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
        body = render(collect()).encode()
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


def main():
    port = 8127
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    with S(("127.0.0.1", port), H) as srv:
        print("📊 Feed dashboard on http://127.0.0.1:%d  (ctrl-c to stop)" % port)
        srv.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")

