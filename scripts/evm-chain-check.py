#!/usr/bin/env python3
"""EVM chain health check for the six-network lane. Read-only.
Usage: python3 scripts/evm-chain-check.py [address]
Verifies each registry network: chainId matches, native balance readable,
and for Robinhood Chain also pulls recent tx history from its Blockscout."""
import json
import sys
import urllib.request

REG = "/Users/earn/Agentic-Trading/data/live/evm-networks.json"
ADDR = sys.argv[1] if len(sys.argv) > 1 else None

UA = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def rpc(url, method, params):
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"content-type": "application/json", "user-agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode()).get("result")
    except Exception as e:
        return "ERR: " + str(e)[:60]


def main():
    reg = json.load(open(REG))
    addr = ADDR or reg.get("unifiedWallet")
    print("unified EVM wallet:", addr)
    for n in reg["networks"]:
        cid = rpc(n["rpc"][0], "eth_chainId", [])
        bal = None
        if addr:
            bal = rpc(n["rpc"][0], "eth_getBalance", [addr, "latest"])
        ok = "OK" if str(cid) == hex(n["chainId"]) else "MISMATCH"
        bal_eth = (int(bal, 16) / 1e18) if isinstance(bal, str) and bal.startswith("0x") else None
        print(f"  {n['name']:12s} chainId {n['chainId']:>7} -> rpc says {cid} [{ok}]"
              + (f" | balance {bal_eth:.6f} {n['native']}" if bal_eth is not None else ""))
    # Robinhood chain deeper check (tx history + tokens) via its Blockscout
    rh = next(n for n in reg["networks"] if n["name"] == "ROBINHOOD")
    if addr:
        try:
            u = rh["explorerApi"] + "?module=account&action=txlist&address=" + addr + "&page=1&offset=5"
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20).read())
            res = d.get("result") or []
            print("  Robinhood tx history:", len(res), "txs (recent shown)")
            for t in res[:5]:
                print("    ", t.get("timeStamp"), t.get("from", "")[:12], "->", (t.get("to") or "")[:12],
                      "value", int(t.get("value") or 0) / 1e18, t.get("methodId", ""))
        except Exception as e:
            print("  Robinhood history read error:", str(e)[:120])


if __name__ == "__main__":
    main()
