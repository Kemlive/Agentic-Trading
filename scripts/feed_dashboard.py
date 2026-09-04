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

def render(d):
    on = lambda b: ("🟢" if b else "🔴")
    h = []
    h.append("<!doctype html><html><head><meta charset='utf-8'>")
    h.append("<meta http-equiv='refresh' content='20'><title>Multi-Chain Feed Dashboard</title>")
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

    # benchmark sample table
    h.append("<div class='card' style='margin-top:12px'><div class='k'>Benchmark sample (latest)</div><table><tr><th>chain</th><th>mint</th><th>delta</th><th>liq$</th></tr>")
    for e in (bm.get("liquidityVsDelta") or [])[-10:]:
        h.append("<tr><td>%s</td><td>%s…</td><td>%s</td><td>%.0f</td></tr>" % (e.get("chain"), e.get("mint", "")[:12], e.get("deltaSec"), e.get("liqUsd") or 0))
    h.append("</table></div>")
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

