#!/bin/bash
# feed-supervisor.sh — foreground supervisor for the whole feed stack (launchd KeepAlive).
# Owns: solfeed, rhfeed, merge (30s), benchmark watcher (10s).
# Children are this script's own job -> survive; loop wrapper auto-restarts on crash.
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
mkdir -p logs/feed data/live/feed
export PATH="/opt/homebrew/opt/node@20/bin:/usr/bin:/bin"
PIDS=()

loop() { # loop <name> <interval> <cmd...>
  local name="$1" iv="$2"; shift 2
  ( while true; do "$@" >> "logs/feed/$name.log" 2>&1; sleep "$iv"; done ) &
  local p=$!
  PIDS+=("$p")
  echo "$p" > "logs/feed/$name.pid"
  echo "feed-supervisor: started $name (pid $p, every ${iv}s)"
}

cleanup() { kill "${PIDS[@]}" 2>/dev/null; }
trap cleanup EXIT INT TERM

loop sol 3 python3 scripts/solfeed.py
loop rh 3 bash -c 'cd evm-signer && node src/rhfeed.mjs'
loop rhpot 90 python3 scripts/rh_potential.py
loop ponsfresh 420 node scripts/pons_size_scan.cjs
loop ponsauto 300 node scripts/pons_autopilot.mjs
loop subrep 3600 python3 scripts/subagent-report.py
loop merge 300 python3 scripts/feedmerge.py
loop bench 30 python3 scripts/feed_benchmark.py --watch 600

echo "feed-supervisor: all loops up"
while true; do sleep 20; done
