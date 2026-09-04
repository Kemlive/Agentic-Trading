#!/bin/bash
# Daily Pump.fun paper scan + rule-engine run (3x/day via LaunchAgent).
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/pump-cron.out"
{
  echo "=== run $(date -u +%FT%TZ) ==="
  python3 scripts/pump-scan.py 20
  python3 scripts/paper-track.py
  python3 scripts/live-snatcher.py  # watchdog: behavior-read any OPEN live positions
  # Telegram heartbeat (only if a bot token+chat are configured)
  if [ -f "$HOME/.config/agentic-trading/telegram.json" ]; then
    python3 scripts/notify-telegram.py report >> "$OUT" 2>&1
  fi
} >> "$OUT" 2>&1
# Auto-expire: unload once past the paper-phase end date (boss set ~5 days).
END=$(cat "$D/data/paper/end_epoch" 2>/dev/null || echo 0)
NOW=$(date +%s)
if [ "$NOW" -gt "$END" ]; then
  launchctl bootout "gui/$(id -u)/com.agentic-trading.paper" >/dev/null 2>&1
  echo "paper scheduler expired and unloaded" >> "$OUT"
fi
