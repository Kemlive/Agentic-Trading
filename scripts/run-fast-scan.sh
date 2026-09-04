#!/bin/bash
# High-frequency real-coin scanner + REAL-COIN EXECUTION LANE (launchd every 30s).
# fastlane trades real money on the real-coin signals - this is the desk now.
# Off-switch: touch data/live/fastlane.off
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/fast-scan.out"
{
  echo "=== fast-scan $(date -u +%FT%TZ) ==="
  python3 scripts/fast-watch.py
  python3 scripts/fastlane.py
} >> "$OUT" 2>&1