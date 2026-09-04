#!/bin/bash
# High-frequency real-coin scanner (launchd every 30s).
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/fast-scan.out"
{
  echo "=== fast-scan $(date -u +%FT%TZ) ==="
  python3 scripts/fast-watch.py
} >> "$OUT" 2>&1