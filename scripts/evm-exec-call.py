#!/usr/bin/env python3
"""EVM execution engine: send a saved swap tx through wallet-signer (Rabby approval).
Usage: python3 scripts/evm-exec-call.py <tx.json> <chainId>
tx.json: {"to": "...", "data": "0x...", "value": "wei"}  (full, file-based - no truncation)
Waits up to ~180s for the human to approve in Rabby. Prints the tx hash."""
import json
import subprocess
import sys
import time

tx = json.load(open(sys.argv[1]))
chain_id = int(sys.argv[2]) if len(sys.argv) > 2 else 8453
cmd = ["npx", "-y", "mcp-wallet-signer"]


def send(p, o):
    p.stdin.write(json.dumps(o) + "\n")
    p.stdin.flush()


def wait_for(p, want_id, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        line = p.stdout.readline()
        if not line:
            time.sleep(0.2)
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("id") == want_id:
            return m
    return None


p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)
send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "evm-engine", "version": "1.0"}}})
wait_for(p, 1, 90)
send(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "connect_wallet", "arguments": {"address": "0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8", "chainId": chain_id}}})
r = wait_for(p, 2, 120)
if r:
    c = (r.get("result", {}).get("content") or [])
    print("CONNECT:", (c[0].get("text") if c else json.dumps(r))[:300])
send(p, {"jsonrpc": "2.0", "method": "notifications/initialized"})
time.sleep(1.5)
params = {"to": tx.get("to"), "chainId": chain_id}
if tx.get("value"):
    params["value"] = str(tx["value"])
if tx.get("data"):
    params["data"] = tx["data"]
send(p, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "send_transaction", "arguments": params}})
r = wait_for(p, 3, 180)
p.kill()
if not r:
    print("TIMEOUT waiting for Rabby approval (may still broadcast - verify on explorer)")
    sys.exit(2)
res = r.get("result", {})
content = res.get("content") or []
print("RESULT:", (content[0].get("text") if content else json.dumps(res))[:500])
