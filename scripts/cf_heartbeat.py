#!/usr/bin/env python3
"""cf_heartbeat.py — Cloudflare 24/7 maintainer heartbeat.

Every ~60s (launchd) this posts a read-only snapshot of the LOCAL desk to the
Cloudflare worker's /ping endpoint (agentic-snatcher). The worker stores it in
KV and serves it 24/7 at <worker>/status and <worker>/state so the boss can see
"is the desk alive, what is open, are feeds fresh" from any device.

NO secrets / signing keys ever leave this machine. Payload is status only.
"""
import datetime
import json
import os
import socket
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")
CFG = os.path.join(LIVE, "cf-worker.json")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p, default=None):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return default


def tail_ts_sec(path):
    """Seconds since the last jsonl row's ts (lightweight tail read). None if empty."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            chunk = b""
            readback = min(size, 2048)
            fh.seek(size - readback)
            chunk = fh.read()
        line = chunk.split(b"\n")[-2] if chunk.endswith(b"\n") else chunk.split(b"\n")[-1]
        if not line:
            line = chunk.split(b"\n")[-1]
        row = json.loads(line)
        t = row.get("ts")
        if not t:
            return None
        t = datetime.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return max(0, int((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()))
    except Exception:
        return None


def pid_alive(name):
    try:
        pid = int(open(os.path.join(ROOT, "logs", "feed", name + ".pid")).read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def main():
    cfg = read(CFG, {}) or {}
    url = (cfg.get("url") or "").rstrip("/")
    token = cfg.get("pingToken") or ""
    if not url:
        print("%s no cf-worker url configured — skipping" % now_iso())
        return 0

    feed_age = {}
    for name in ("solana.jsonl", "robinhood.jsonl", "unified.jsonl"):
        feed_age[name.split(".")[0]] = tail_ts_sec(os.path.join(FD, name))

    lane_st = read(os.path.join(LIVE, "fastlane-state.json"), {}) or {}
    pos = read(os.path.join(LIVE, "fastlane-positions.json"), {"positions": []}) or {}
    openp = [p for p in pos.get("positions", []) if p.get("status") == "open"]
    lane = {
        "open": len(openp),
        "positions": [{"symbol": p.get("symbol") or str(p.get("mint", ""))[:8]} for p in openp],
        "spentToday": lane_st.get("spentToday"),
        "realizedToday": lane_st.get("realizedToday"),
    }

    payload = {
        "ts": now_iso(),
        "host": socket.gethostname(),
        "pids": {n: pid_alive(n) for n in ("sol", "rh", "merge", "bench")},
        "feedAgeSec": feed_age,
        "lane": lane,
        "pingToken": token,
    }
    ok = False
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            url + "/ping",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "cf-heartbeat/1"},
            method="POST"), timeout=20).read())
        if r.get("ok"):
            ok = True
            print("%s posted — worker recv %s" % (now_iso(), r.get("ts")))
        else:
            print("%s worker rejected ping: %s" % (now_iso(), r))
    except Exception as e:
        print("%s ping failed: %s" % (now_iso(), e))

    # Mirror the FULL local PM dashboard (:8127) so workers.dev shows the same desk.
    try:
        page = urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:8127/",
            headers={"User-Agent": "cf-heartbeat/1"}), timeout=30).read().decode("utf-8", "replace")
        if len(page) > 1000:
            r2 = json.loads(urllib.request.urlopen(urllib.request.Request(
                url + "/page",
                data=json.dumps({"ts": now_iso(), "html": page, "pingToken": token}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "cf-heartbeat/1"},
                method="POST"), timeout=30).read())
            print("%s page mirrored (%d bytes) %s" % (now_iso(), len(page), r2))
        else:
            print("%s page fetch too small, skipping mirror" % now_iso())
    except Exception as e:
        print("%s page mirror failed: %s" % (now_iso(), e))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
