#!/bin/bash
# Daily unified balance/P&L card (launchd once/day at 23:45 local).
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
export PATH="/opt/homebrew/bin:/usr/bin:/bin"
echo "=== daily card $(date -u +%FT%TZ) ==="
python3 scripts/notify-telegram.py card balance
