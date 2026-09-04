#!/usr/bin/env python3
"""solfeed.py — STEP 1: OWN SOLANA DATA FEED (one thing at a time: build the feed).

Collects launch/trade activity DIRECTLY from Solana hub programs (verified on-chain)
into a normalized local feed. No third-party data, no trading logic here.
Venues (config-driven, verified program ids):
  pumpfun · raydium_v4 · raydium_clmm · meteora_dlmm
Output : data/live/feed/solana.jsonl (one normalized event per tx) + coverage counters
Run    : python3 scripts/solfeed.py --secs 30   (windowed demo)
         python3 scripts/solfeed.py             (run until Ctrl-C -> future daemon)
"""
import os
import sys
import json
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPC = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
VENUE_FILE = os.path.join(ROOT, "data", "live", "feed-venues.json")
STATE_FILE = os.path.join(ROOT, "data", "live", "feed-state.json")
FEED_DIR = os.path.join(ROOT, "data", "live", "feed")
FEED = os.path.join(FEED_DIR, "solana.jsonl")


def rpc(method, params):
    last = None
    for u in RPC:
        try:
            req = urllib.request.Request(u, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                                             "params": params}).encode(),
                                         headers={"content-type": "application/json", "User-Agent": "Mozilla/5.0"})
            res = json.loads(urllib.request.urlopen(req, timeout=15).read())
            if res.get("result") is not None or method in ("getSignaturesForAddress", "getTransaction"):
                return res.get("result")
        except Exception as e:
            last = e
    if last:
        raise last
    return None


def load_venues():
    default = {"venues": {
        "pumpfun": {"program": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "enabled": True},
        "raydium_v4": {"program": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", "enabled": True},
        "raydium_clmm": {"program": "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK", "enabled": True},
        "meteora_dlmm": {"program": "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo", "enabled": True}},
        "pollSecs": 5, "maxTxPerVenue": 6}
    try:
        return json.load(open(VENUE_FILE))
    except Exception:
        tmp = VENUE_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(default, fh, indent=2)
        os.replace(tmp, VENUE_FILE)
        return default


def load_state():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {"lastSeen": {}, "counts": {}}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(st, fh, indent=2)
    os.replace(tmp, STATE_FILE)


def append_event(ev):
    with open(FEED, "a") as fh:
        fh.write(json.dumps(ev) + "\n")


def normalize_tx(venue, sig):
    try:
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    except Exception:
        return None
    if not tx:
        return None
    meta = tx.get("meta") or {}
    msg = tx.get("transaction", {}).get("message") or {}
    accts = [a.get("pubkey") for a in msg.get("accountKeys", [])]
    mints = set()
    for b in (meta.get("postTokenBalances") or []) + (meta.get("preTokenBalances") or []):
        if b.get("mint"):
            mints.add(b["mint"])
    return {
        "venue": venue, "tx": sig, "slot": tx.get("slot"),
        "blockTime": tx.get("blockTime"),
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "err": bool(meta.get("err")),
        "acctCount": len(accts),
        "mints": sorted(list(mints))[:6],
        "logLines": len(meta.get("logMessages") or []),
    }

def collect_venue(name, cfg, st):
    prog = cfg["program"]
    last = (st["lastSeen"].get(name) or {}).get("sig")
    sigs = rpc("getSignaturesForAddress", [prog, {"limit": 30}]) or []
    new = []
    for s in sigs:
        if last is None or s["signature"] == last:
            if last is not None:
                break
        new.append(s)
        if s["signature"] == last:
            break
    new.reverse()
    got = 0
    for s in new[:cfg.get("maxTxPerVenue", 6)]:
        rec = normalize_tx(name, s["signature"])
        if rec:
            append_event(rec)
            got += 1
    if new:
        st["lastSeen"][name] = {"sig": new[-1]["signature"], "slot": new[-1]["slot"]}
    st["counts"][name] = int(st["counts"].get(name, 0)) + got
    return len(new), got


def main():
    args = sys.argv[1:]
    secs = 30
    if "--secs" in args:
        secs = int(args[args.index("--secs") + 1])
    cfgd = load_venues()
    st = load_state()
    os.makedirs(FEED_DIR, exist_ok=True)
    print("🟢 SOLANA FEED ONLINE @ %s | venues: %s"
          % (datetime.datetime.now(datetime.timezone.utc).isoformat()[:19],
             ",".join(cfgd["venues"].keys())))
    t0 = time.time()
    passes = 0
    while time.time() - t0 < secs:
        p0 = time.time()
        for name, vc in cfgd["venues"].items():
            if not vc.get("enabled", True):
                continue
            try:
                n_new, n_got = collect_venue(name, vc, st)
                if n_new:
                    print("   [%s] new=%d recorded=%d total=%d" % (name, n_new, n_got, st["counts"][name]))
            except Exception as e:
                print("   [%s] err %s" % (name, str(e)[:80]))
        passes += 1
        save_state(st)
        dt = time.time() - p0
        time.sleep(max(0.5, float(cfgd.get("pollSecs", 5)) - dt))
    rows = _rows()
    print("DONE %d passes in %.0fs | totals %s | feed rows: %d" % (passes, time.time() - t0, json.dumps(st["counts"]), rows))


def _rows():
    try:
        with open(FEED) as fh:
            return sum(1 for _ in fh)
    except Exception:
        return 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
    except Exception as e:
        print("solfeed error:", e)

