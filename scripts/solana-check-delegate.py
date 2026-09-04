#!/usr/bin/env python3
"""
solana-check-delegate.py - Agentic Trading: verify the vault USDC delegate-cap state.

Reads the vault's USDC token account and reports owner / delegate / delegated amount.
Usage: python3 scripts/solana-check-delegate.py
"""
import json
import urllib.request

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
VAULT = "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4"
SRC = "GRiCEHnTyfNHKvCXpkcxqHwHmkFFxhHz5Yjhq4MxGJK8"  # vault USDC account (RPC-verified)
RPC = "https://api.mainnet-beta.solana.com"

body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                   "params": [SRC, {"encoding": "jsonParsed"}]}).encode()
req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=15))
acc = (r.get("result") or {}).get("value")
if not acc:
    print("account not found:", SRC)
    raise SystemExit(1)
info = acc["data"]["parsed"]["info"]
amt = info["tokenAmount"]
print("account :", SRC)
print("owner   :", info.get("owner"))
print("mint    :", info.get("mint"))
print("balance :", amt["uiAmount"], amt.get("decimals"), "decimals")
print("delegate:", info.get("delegate"))
print("delegatedAmount:", (info.get("delegatedAmount") or {}).get("uiAmount"))
if info.get("delegate"):
    print("CAP ACTIVE: hot wallet may spend up to $%s" % (info["delegatedAmount"]["uiAmount"]))
else:
    print("NO DELEGATE YET - approve via safe/solana-delegate-approve.html (vault owner)")
