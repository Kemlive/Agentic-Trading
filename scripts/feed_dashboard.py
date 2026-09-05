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
            out[a] = {"symbol": (best.get("baseToken") or {}).get("symbol") or a[:6],
                      "liq": float((best.get("liquidity") or {}).get("usd") or 0),
                      "h1": float(chg.get("h1")) if chg.get("h1") is not None else None}
    except Exception:
        pass
    return out


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
    rh_tokens = [{"symbol": (t.get("sym") or t.get("key", "")[:8]),
                  "transfers": t.get("t60") or 0, "chg_h1": None,
                  "category": (t.get("topTier") or "OTHER").upper()} for t in rh_top]
    dex = _dex_for([t["key"] for t in sol_top if t.get("key")])
    sol_queue = [{"s": (dex.get(t["key"]) or {}).get("symbol") or t.get("key", "")[:6],
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
    d["lane"] = {"open": len(openp),
                 "symbols": [p.get("symbol") for p in openp[:4]]}
    fst_lane = read(os.path.join(LIVE, "fastlane-state.json"), {})
    d["lane"]["spentToday"] = fst_lane.get("spentToday")
    d["lane"]["realizedToday"] = fst_lane.get("realizedToday")
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
        html += ("<div class='intel-badge'><span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s'>%s</span>"
                 "<span class='meta-tag tag-purple'>%s</span>"
                 "<span class='vol-indicator'>📊 1h tx: %s</span></div>"
                 % (str(token.get("symbol", "UNKN"))[:6], cls, label,
                    str(token.get("category", "OTHER"))[:10], format(token.get("transfers", 0), ",")))
    html += '</div>'
    # SOL visual cluster (top 4 by dex liquidity)
    html += '<div class="chain-card sol-card"><h4>🟢 SOLANA CANDIDATES</h4>'
    sol_candidates = sorted(sol_data.get("queue", []), key=lambda x: float(x.get("liq", 0) or 0), reverse=True)[:4]
    if not sol_candidates:
        html += '<div class="empty-badge">Searching meme pool layers...</div>'
    for token in sol_candidates:
        label, cls = _trend_pct(token.get("h1"))
        html += ("<div class='intel-badge'><span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s'>%s</span>"
                 "<span class='meta-tag tag-green'>%s</span>"
                 "<span class='vol-indicator'>💧 Liq: $%s</span></div>"
                 % (str(token.get("s", "UNKN"))[:6], cls, label,
                    str(token.get("category", "WATCH"))[:10], format(float(token.get("liq", 0)), ",.0f")))
    html += '</div></div>'
    return html


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
    h.append("<style>body{font-family:ui-monospace,Menlo,monospace;background:#0b1020;color:#e6edf3;margin:0;padding:16px}")
    h.append("h1{font-size:16px;color:#7ee787}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin-top:12px}")
    h.append(".card{background:#111a2e;border:1px solid #26324a;border-radius:10px;padding:12px}")
    h.append(".k{color:#8b98b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em}.v{font-size:22px;font-weight:700}")
    h.append(".ok{color:#7ee787}.bad{color:#ff7b72}.sub{color:#8b98b8;font-size:11px}")
    h.append("table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:4px 6px;border-bottom:1px solid #1f2a44;text-align:left}</style></head><body>")
    h.append("<h1>📡 MULTI-CHAIN FEED WATCHER — PERFORMANCE SUMMARY</h1>")
    h.append("<div class='sub'>as of %s · auto-refresh 20s · our own chain data, no subscriptions</div>" % d["asOf"][:19])

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
    # lane
    ln = d["lane"]
    h.append("<div class='card'><div class='k'>Real-coin lane</div>")
    h.append("<div>open positions <b class='v %s'>%d</b></div>" % ("ok" if ln["open"] == 0 else "bad", ln["open"]))
    h.append("<div class='sub'>today spent $%s · realized $%s</div>" % (ln.get("spentToday"), ln.get("realizedToday")))
    h.append("<div class='sub'>%s</div>" % ", ".join(ln.get("symbols", [])))
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
        h.append("<div class='intel-badge'><span class='ticker-badge font-mono'>%s</span>"
                 "<span class='trend-pct %s %s'>%s</span>"
                 "<span class='meta-tag tag-purple'>%s</span>"
                 "<span class='vol-indicator'>💧 $%s</span></div>"
                 % (str(e.get("chain", "?"))[:2] + ":" + str(e.get("mint", ""))[:10], cls, flag, label,
                    str(e.get("deltaSec", "")) if False else "EDGE", format(float(e.get("liqUsd") or 0), ",.0f")))
    h.append("</div>")
    h.append("</body></html>")
    return "\n".join(h)


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
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

