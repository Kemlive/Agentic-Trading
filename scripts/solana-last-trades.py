#!/usr/bin/env python3
"""Read-only: list recent Solana transactions for a wallet (debug-friendly)."""
import json
import sys
import urllib.request

RPC = "https://api.mainnet-beta.solana.com"
W = sys.argv[1] if len(sys.argv) > 1 else ""


def rpc(method, params):
    req = urllib.request.Request(
        RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


items = (rpc("getSignaturesForAddress", [W, {"limit": 8}]).get("result") or [])
print("sigs:", len(items))
for it in items:
    print("sig:", it["signature"], "len:", len(it["signature"]),
          "err:", it.get("err"), "slot:", it.get("slot"),
          "time:", it.get("blockTime"))
if items:
    sig = items[0]["signature"]
    print("--- parsing most recent:", sig)
    try:
        raw = rpc("getParsedTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        r = raw.get("result")
        if not r:
            print("result is null/None; raw keys:", list(raw.keys()), "error:", (raw.get("error") or {}).get("message"))
        else:
            m = r.get("meta") or {}
            print("meta keys:", sorted(m.keys()))
            pre = m.get("preBalances") or []
            post = m.get("postBalances") or []
            print("signer SOL pre/post:", (pre[0] / 1e9 if pre else None), (post[0] / 1e9 if post else None))
            print("log msgs:", [l for l in (m.get("logMessages") or []) if "Program" in l][:6])
            print("num postTokenBalances:", len(m.get("postTokenBalances") or []))
            for tb in (m.get("postTokenBalances") or []):
                print("  mint:", tb.get("mint"), "owner:", (tb.get("owner") or "")[:8], "amt:", (tb.get("uiTokenAmount") or {}).get("uiAmount"))
    except Exception as e:
        print("parse error:", repr(e))

