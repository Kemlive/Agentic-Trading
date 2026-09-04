#!/usr/bin/env python3
"""Drive the solana-mcp server over stdio and call one tool.
Usage:
  python3 scripts/solana-mcp-call.py <toolName> '<json-args>'   [--net mainnet|devnet]
Prints the tool result JSON. No secrets here - key handled by the launcher."""
import json
import subprocess
import sys
import time

LAUNCHER = ["/bin/bash", "/Users/earn/.local/bin/solana-mcp-launcher"]
tool = sys.argv[1] if len(sys.argv) > 1 else "GET_WALLET_ADDRESS"
try:
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
except Exception:
    args = {}
if "--net" in sys.argv:
    net = sys.argv[sys.argv.index("--net") + 1]
    open("/Users/earn/.config/agentic-trading/network", "w").write(net + "\n")

p = subprocess.Popen(LAUNCHER, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)

def send(obj):
    p.stdin.write(json.dumps(obj) + "\n")
    p.stdin.flush()

def wait_for(want_id, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        line = p.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == want_id:
            return msg
    return None

t0 = time.time()
send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "agent-call", "version": "1.0"}}})
r1 = wait_for(1)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
time.sleep(0.3)
send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
      "params": {"name": tool, "arguments": args}})
r2 = wait_for(2)
dt = time.time() - t0
print("elapsed_s: %.1f" % dt)
if r2:
    print(json.dumps(r2.get("result", r2), indent=1)[:2500])
else:
    print("no response for tool", tool)
p.kill()
