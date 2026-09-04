#!/usr/bin/env python3
"""mcp_gateway.py — OUR OWN "secondary-gateway" MCP server (read-only desk status).

Companion to the local wallet-signer MCP. Speaks stdio JSON-RPC and exposes
read-only audit tools over the live desk so agents/dashboards can ask "what is
the desk doing" without any signing or sending capability.
Tools: get_desk_status, get_feed_status, get_diagnostics, get_recent_events.
"""
import os
import sys
import json
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "live")


def _read(p, default=None):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return default


def _last_log_line(p):
    try:
        lines = [l for l in open(p) if l.strip()]
        return lines[-1].strip()[:220] if lines else None
    except Exception:
        return None


def _alive(pid_path):
    try:
        os.kill(int(open(pid_path).read().strip()), 0)
        return True
    except Exception:
        return False


def desk_status():
    out = {"asOf": datetime.datetime.now(datetime.timezone.utc).isoformat(), "lanes": {}}
    evm = _read(os.path.join(LIVE, "evm-autopilot.json"), {})
    out["lanes"]["base"] = {"enabled": evm.get("enabled", False),
                            "dipStagedPct": (evm.get("autoEntry") or {}).get("dipPct"),
                            "lastTick": _last_log_line(os.path.join(ROOT, "logs", "evm-autopilot.out"))}
    rh = _read(os.path.join(LIVE, "rh-exec.json"), {})
    out["lanes"]["robinhood"] = {"execEnabled": rh.get("enabled", False), "router": rh.get("router"),
                                 "lastFeed": _last_log_line(os.path.join(ROOT, "logs", "feed", "rh.log"))}
    fl = _read(os.path.join(LIVE, "fastlane-state.json"), {})
    out["lanes"]["solana"] = {"day": fl.get("day"), "spentToday": fl.get("spentToday"),
                              "realizedToday": fl.get("realizedToday"),
                              "lastScan": _last_log_line(os.path.join(ROOT, "logs", "fast-scan.out"))}
    out["paused"] = {"microSnatcher": os.path.exists(os.path.join(LIVE, "autopilot.off"))}
    return json.dumps(out, indent=1)


def feed_status():
    out = {"asOf": datetime.datetime.now(datetime.timezone.utc).isoformat(), "files": {}}
    for f in ("solana.jsonl", "robinhood.jsonl", "unified.jsonl", "bench.jsonl"):
        p = os.path.join(LIVE, "feed", f)
        try:
            n = sum(1 for _ in open(p))
        except Exception:
            n = 0
        last = None
        for l in open(p):
            try:
                last = json.loads(l).get("ts")
            except Exception:
                pass
        age = None
        if last:
            try:
                t = datetime.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                age = max(0, int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()))
            except Exception:
                pass
        out["files"][f] = {"rows": n, "ageSec": age}
    out["daemons"] = {n: _alive(os.path.join(ROOT, "logs", "feed", n + ".pid"))
                      for n in ("sol", "rh", "merge", "bench")}
    return json.dumps(out, indent=1)


def diagnostics():
    import subprocess
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "alpha-queue-diag.py")],
                           capture_output=True, text=True, timeout=90)
        return "exit=%d\n%s" % (r.returncode, (r.stdout or r.stderr)[-1500:])
    except Exception as e:
        return "diag failed: %s" % e


def recent_events(n=10):
    p = os.path.join(ROOT, "logs", "trades.jsonl")
    try:
        rows = [json.loads(l) for l in open(p)]
    except Exception:
        rows = []
    return json.dumps(rows[-int(n):], indent=1) if rows else "no events yet"


TOOLS = [
    {"name": "get_desk_status", "description": "Read-only lane + pause + last-tick status for Base/Solana/Robinhood.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_feed_status", "description": "Feed file rows/recency + daemon liveness.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_diagnostics", "description": "Run the alpha-queue tolerance diagnostic (read-only, exit code included).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_recent_events", "description": "Tail of logs/trades.jsonl.",
     "inputSchema": {"type": "object", "properties": {"n": {"type": "number", "default": 10}}}},
]
HANDLERS = {"get_desk_status": desk_status, "get_feed_status": feed_status,
            "get_diagnostics": diagnostics, "get_recent_events": recent_events}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        mid = req.get("id")
        method = req.get("method")
        if method == "initialize":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": (req.get("params") or {}).get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentic-secondary-gateway", "version": "1.0.0"}}}) + "\n")
        elif method in ("notifications/initialized", "notifications/cancelled"):
            pass
        elif method == "ping":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {}}) + "\n")
        elif method == "tools/list":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}) + "\n")
        elif method == "tools/call":
            name = (req.get("params") or {}).get("name")
            args = (req.get("params") or {}).get("arguments") or {}
            try:
                if name not in HANDLERS:
                    raise ValueError("unknown tool %s" % name)
                out = HANDLERS[name](**args) if name == "get_recent_events" else HANDLERS[name]()
                res = {"content": [{"type": "text", "text": str(out)}]}
            except Exception as e:
                res = {"content": [{"type": "text", "text": "ERROR: %s" % e}], "isError": True}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}) + "\n")
        else:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                         "error": {"code": -32601, "message": "not found: " + method}}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


