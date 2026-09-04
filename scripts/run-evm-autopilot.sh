#!/bin/bash
# EVM-lane autonomous tick (launchd every 15 min). Mean-reversion on AERO/USDC via Safe SwapModule.
D=/Users/earn/Agentic-Trading
cd "$D" || exit 1
OUT="$D/logs/evm-autopilot.out"
export PATH="/opt/homebrew/opt/node@20/bin:/usr/bin:/bin"
{
  echo "=== evm-autopilot $(date -u +%FT%TZ) ==="
  cd "$D/evm-signer" && env -u EVM_KEYSTORE -u EVM_PASSPHRASE node src/autopilot.mjs --go
} >> "$OUT" 2>&1
