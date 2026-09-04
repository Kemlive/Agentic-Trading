#!/usr/bin/env python3
"""Read-only Solana verifier v2. Usage:
  python3 scripts/solana-verify.py <wallet> [token-mint]
Prints SOL balance and any token balance for the mint in the wallet."""
import json
import sys
import urllib.request

RPC = "https://api.mainnet-beta.solana.com"
wallet = sys.argv[1] if len(sys.argv) > 1 else ""
mint = sys.argv[2] if len(sys.argv) > 2 else ""


def rpc(method, params):
    req = urllib.request.Request(
        RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


b = rpc("getBalance", [wallet])
print("walletSOL:", (b.get("result") or {}).get("value", 0) / 1e9)
if mint:
    ta = rpc("getTokenAccountsByOwner", [wallet, {"mint": mint}, {"encoding": "jsonParsed"}])
    arr = (ta.get("result") or {}).get("value") or []
    if not arr:
        print("token accounts for mint:", ta.get("error") or "none found")
    for acc in arr:
        info = (acc.get("account") or {}).get("data") or {}
        parsed = info.get("parsed") or {}
        amt = parsed.get("info", {}).get("tokenAmount", {})
        print("tokenBalance:", amt.get("uiAmount"), "decimals:", amt.get("decimals"),
              "state:", parsed.get("info", {}).get("state"))

