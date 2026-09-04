#!/usr/bin/env python3
"""
evm-eoa-sweep.py - Agentic Trading: sweep ALL Base USDC off the owner EOA into the Safe.

RULE (boss 2026-09-04): the Safe is the ONLY EVM USDC holder. Any USDC that lands on
the owner EOA (e.g. a Phantom DexBridge delivery) MUST be cleared into the Safe so the
ledger stays simple. Run this after any EOA inflow.

    python3 scripts/evm-eoa-sweep.py            # prepare only (prints command)
    python3 scripts/evm-eoa-sweep.py --sign     # prepare AND sign+broadcast via evm-signer

Safe: 0x203FD7cefb443672ef5700A1E27521c22A6E7B3A
EOA : 0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8 (evm-signer key)
USDC: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 (Base, 6 decimals)
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
EOA = "0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8"
SAFE = "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = {"Content-Type": "application/json", "User-Agent": "agentic-trading-eoa-sweep/0.1"}
RPCS = ("https://mainnet.base.org", "https://base.llamarpc.com", "https://1rpc.io/base")


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for url in RPCS:
        try:
            req = urllib.request.Request(url, data=body, headers=HEAD)
            r = json.load(urllib.request.urlopen(req, timeout=20))
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sign", action="store_true", help="also sign+broadcast via evm-signer")
    a = ap.parse_args()

    data = "0x70a08231000000000000000000000000" + EOA[2:].lower()
    raw = rpc("eth_call", [{"to": USDC, "data": data}, "latest"])
    if raw is None:
        print("ERR: no Base RPC reachable")
        return 1
    micros = int(raw, 16)
    if micros <= 0:
        print("EOA USDC = 0 - nothing to sweep (Safe-only holder rule satisfied)")
        return 0

    amount = hex(micros)[2:].rjust(64, "0")
    tx = {"to": USDC, "data": "0xa9059cbb" + SAFE[2:].lower().rjust(64, "0") + amount, "value": "0"}
    txfile = "/tmp/tx_eoa_to_safe.json"
    json.dump(tx, open(txfile, "w"))
    print("EOA USDC %.6f -> sweep tx written %s" % (micros / 1e6, txfile))
    cmd = ["node", "src/cli.mjs", "sign", txfile, "8453", "--broadcast", "--ethUsd", "2500"]
    if not a.sign:
        print("run to execute: cd %s && %s" % (os.path.join(ROOT, "evm-signer"), " ".join(cmd)))
        return 0
    return subprocess.call(cmd, cwd=os.path.join(ROOT, "evm-signer"))


if __name__ == "__main__":
    sys.exit(main())
