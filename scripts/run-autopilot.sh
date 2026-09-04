#!/bin/bash
# Autopilot heartbeat (launchd every ~45 min while Mac is on).
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/autopilot.out"
# PRE-FLIGHT SECURITY GATE: never tick on a paused/mis-configured/under-funded desk
if ! bash "$D/scripts/security-gate.sh" sol >> "$OUT" 2>&1; then
  exit 1
fi
{
  echo "=== autopilot $(date -u +%FT%TZ) ==="
  python3 scripts/pump-scan.py --chains=solana 120
  python3 scripts/autopilot.py
} >> "$OUT" 2>&1
