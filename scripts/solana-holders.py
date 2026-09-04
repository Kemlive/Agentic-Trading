#!/usr/bin/env python3
"""Holder & whale analyzer via Helius. Usage:
  python3 scripts/solana-holders.py <mint>
Reads Helius key from ~/.config/agentic-trading/helius.key (0600). No secrets printed."""
import json
import os
import sys
import urllib.request

KEY_FILE = os.path.expanduser("~/.config/agentic-trading/helius.key")


def key():
    with open(KEY_FILE) as f:
        return f.read().strip()


def rpc(method, params):
    req = urllib.request.Request(
        "https://mainnet.helius-rpc.com/?api-key=" + key(),
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main():
    mint = sys.argv[1]
    sup = rpc("getTokenSupply", [mint])["result"]["value"]["uiAmount"]
    top = rpc("getTokenLargestAccounts", [mint])["result"]["value"][:10]
    print(f"mint {mint}  supply={sup:,.0f}")
    rows = []
    for ta in top:
        acc = rpc("getAccountInfo", [ta["address"], {"encoding": "jsonParsed"}])
        owner = ((acc.get("result") or {}).get("value") or {}).get("data", {}).get("parsed", {}).get("info", {}).get("owner")
        amt = ta.get("uiAmount") or 0
        pct = amt / sup * 100 if sup else 0
        rows.append((amt, owner, pct))
        print(f"  rank#{len(rows)} amt={amt:,.0f} ({pct:.2f}%) owner={(owner or '?')[:12]}")
    t10 = sum(r[2] for r in rows)
    print(f"TOP10 CONCENTRATION: {t10:.1f}% of supply")
    # A single >20% account is usually the AMM pool PDA or creator/dev - report both views
    if rows and rows[0][2] >= 20:
        rest = sum(r[2] for r in rows[1:])
        print(f"  excl. largest ({rows[0][2]:.1f}% - likely pool/dev): real top-9 = {rest:.1f}%")
        print(f"  largest owner={rows[0][1]} <- compare vs route-plan ammKey / known pool")
    if t10 > 40 and not (rows and rows[0][2] >= 20):
        print("  RUG-RISK RED FLAG (>40% held outside a single pool-sized account)")


if __name__ == "__main__":
    main()
