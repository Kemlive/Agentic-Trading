#!/bin/bash
# run-live-feed.sh — FEED-ONLY live capture loop (no keys, no balances, no trading).
# Starts: solfeed daemon, rhfeed daemon, merge every 30s, benchmark watcher loop.
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
mkdir -p logs/feed data/live/feed
export PATH="/opt/homebrew/opt/node@20/bin:/usr/bin:/bin"

start() {  # start <name> <cmd...>
  local name="$1"; shift
  if ! kill -0 "$(cat "logs/feed/$name.pid" 2>/dev/null)" 2>/dev/null; then
    nohup "$@" >> "logs/feed/$name.log" 2>&1 &
    echo $! > "logs/feed/$name.pid"
    echo "started $name pid $(cat logs/feed/$name.pid)"
  else
    echo "$name already running (pid $(cat logs/feed/$name.pid))"
  fi
}

start sol python3 scripts/solfeed.py
start rh  bash -c 'cd evm-signer && node src/rhfeed.mjs'

# merge + benchmark watcher (lightweight supervisors)
if ! kill -0 "$(cat logs/feed/merge.pid 2>/dev/null)" 2>/dev/null; then
  ( while true; do python3 scripts/feedmerge.py >> logs/feed/merge.log 2>&1; sleep 30; done ) &
  echo $! > logs/feed/merge.pid; echo "started merge pid $(cat logs/feed/merge.pid)"
fi
if ! kill -0 "$(cat logs/feed/bench.pid 2>/dev/null)" 2>/dev/null; then
  ( while true; do python3 scripts/feed_benchmark.py --watch 600 >> logs/feed/bench.log 2>&1; sleep 2; done ) &
  echo $! > logs/feed/bench.pid; echo "started bench pid $(cat logs/feed/bench.pid)"
fi
echo "live feed loop up"
