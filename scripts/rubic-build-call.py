#!/usr/bin/env python3
"""Drive the rubic MCP over stdio to build a swap tx and save FULL output to a file.
Usage: python3 scripts/rubic-build-call.py <params.json>
Writes: /tmp/rubic-build.json (full tool result) and /tmp/evmtx.json {to,data,value}
No truncation - file-based, so long calldata is preserved exactly."""
import json
import subprocess
import sys
import time

LAUNCHER = ["/bin/bash", "/Users/earn/.local/bin/rubic-mcp-launcher"]
params = json.load(open(sys.argv[1]))


def send(p, o):
    p.stdin.write(json.dumps(o) + "\n")
    p.stdin.flush()


def wait_for(p, want_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        line = p.stdout.readline()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("id") == want_id:
            return m
    return None


p = subprocess.Popen(LAUNCHER, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)
send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "evm-engine", "version": "1.0"}}})
wait_for(p, 1)
send(p, {"jsonrpc": "2.0", "method": "notifications/initialized"})
time.sleep(0.3)
send(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "rubic_build_swap_tx", "arguments": params}})
r = wait_for(p, 2)
p.kill()
if not r:
    print("no response")
    sys.exit(1)
content = r.get("result", {}).get("content") or []
text = content[0].get("text", "") if content else ""
open("/tmp/rubic-build.json", "w").write(text)
try:
    d = json.loads(text).get("data") or {}
    tx = d.get("transaction") or {}
    out = {"to": tx.get("to"), "data": tx.get("data"), "value": tx.get("value"),
           "route": d.get("providerType"), "estimateTo": d.get("estimate", {}).get("destinationTokenAmount"),
           "approvalAddress": tx.get("approvalAddress")}
    json.dump(out, open("/tmp/evmtx.json", "w"), indent=2)
    print("ok to=%s dataLen=%d value=%s estOut=%s approval=%s"
          % (out["to"], len(out["data"] or "") // 2 - 1, out["value"], out["estimateTo"], out.get("approvalAddress")))
except Exception as e:
    print("parse err:", e, "| text head:", text[:300])
