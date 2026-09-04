#!/bin/bash
# Autopilot heartbeat (launchd every ~45 min while Mac is on).
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/autopilot.out"
{
  echo "=== autopilot $(date -u +%FT%TZ) ==="
  python3 scripts/pump-scan.py --chains=solana 10
  python3 scripts/autopilot.py
} >> "$OUT" 2>&1
