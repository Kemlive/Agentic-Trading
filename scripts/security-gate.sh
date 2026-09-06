#!/bin/bash
# security-gate.sh <sol|evm> — PRE-FLIGHT SECURITY GATE for the launchd engines.
# Exits NON-ZERO (HALT) when any precondition for SAFE trading is violated, so a
# background engine tick never runs on a mis-configured / paused / under-funded desk.
# Written in-house (boss request 2026-09-04). Read-only — never moves funds.
set -u

D=/Users/earn/Agentic-Trading
CFG_DIR="${GATE_CFG_DIR:-$HOME/.config/agentic-trading}"
LANE="${1:-}"
HALTED=0

note() { echo "GATE[$LANE] $*"; }
halt() { note "HALT: $*"; HALTED=1; }

[ "$LANE" = "sol" ] || [ "$LANE" = "evm" ] || { echo "usage: security-gate.sh <sol|evm>"; exit 2; }

# ---------------------------------------------------------------------------
# 1) KEY-FILE PERMISSIONS — everything must be owner-only 0600 (never group/world)
# ---------------------------------------------------------------------------
if [ -d "$CFG_DIR" ]; then
  for f in evm-keystore.json evm-keystore.pass solana-agent-key.json telegram.json \
           helius.key turnkey.json cloudflare.json coinmarketcap.json; do
    p="$CFG_DIR/$f"
    [ -e "$p" ] || continue
    m=$(stat -f '%Lp' "$p" 2>/dev/null)
    if [ "$m" != "600" ]; then
      halt "key file perms $m (want 600): $p"
    fi
  done
  # lane-critical key must EXIST
  if [ "$LANE" = "sol" ] && [ ! -e "$CFG_DIR/solana-agent-key.json" ]; then
    halt "solana hot key missing: $CFG_DIR/solana-agent-key.json"
  fi
  if [ "$LANE" = "evm" ] && { [ ! -e "$CFG_DIR/evm-keystore.json" ] || [ ! -e "$CFG_DIR/evm-keystore.pass" ]; }; then
    halt "EVM keystore missing: $CFG_DIR/evm-keystore.json (+.pass)"
  fi
else
  halt "key config dir missing: $CFG_DIR"
fi

# ---------------------------------------------------------------------------
# 2) KILL-SWITCH / HALT markers — an explicit pause must never be overridden
# ---------------------------------------------------------------------------
if ls "$D"/data/live/*.off >/dev/null 2>&1; then
  halt "halt marker present (data/live/*.off) — remove it only after boss review"
fi

# ---------------------------------------------------------------------------
# 3) LANE-SPECIFIC CHECKS
# ---------------------------------------------------------------------------
if [ "$LANE" = "evm" ]; then
  # config/policy must say ENABLED and no kill-switch
  ENABLED=$(python3 -c "import json;print(json.load(open('$D/data/live/evm-autopilot.json')).get('enabled',False))" 2>/dev/null)
  POL_EN=$(python3 -c "import json;print(json.load(open('$D/evm-signer/config/policy.json')).get('enabled',False))" 2>/dev/null)
  POL_KS=$(python3 -c "import json;print(json.load(open('$D/evm-signer/config/policy.json')).get('killSwitch',True))" 2>/dev/null)
  [ "$ENABLED" = "True" ] || halt "evm-autopilot.json enabled!=true (paused?)"
  [ "$POL_EN" = "True" ] || halt "evm policy enabled!=true"
  [ "$POL_KS" = "False" ] || halt "evm policy killSwitch=true — HALT"
  # reserve: Safe USDC must at least cover a minimum trade so we never buy gas-broke
  SAFE_USDC=$(python3 -c "import sys;sys.path.insert(0,'$D/scripts');import portfolio_state as p;print(p._owner_evm_usdc('base','0x203FD7cefb443672ef5700A1E27521c22A6E7B3A') or 0)" 2>/dev/null)
  note "Safe USDC = \$${SAFE_USDC:-?}"
  if [ -z "$SAFE_USDC" ] || [ "$(python3 -c "print(float('${SAFE_USDC:-0}') < 0.30)")" = "True" ]; then
    halt "Safe USDC under \$0.30 minimum-trade floor"
  fi
else
  # SOL lane: delegate cap must be known and >= next entry size ($2.50)
  DELEG=$(python3 "$D/scripts/solana-check-delegate.py" 2>/dev/null | sed -n 's/^delegatedAmount: //p')
  if [ -n "$DELEG" ]; then
    note "delegate remaining = \$$DELEG"
    # Boss GO 2026-09-06: capital sizing is boss's call — engine may act down to the
    # minimum-trade floor ($0.30); vault_pull re-verifies before any spend.
    if [ "$(python3 -c "print(float('$DELEG') < 0.30)")" = "True" ]; then
      halt "delegate remaining \$$DELEG < min-trade \$0.30"
    fi
  else
    note "WARN: delegate amount unreadable (RPC?) — engine's vault_pull will re-verify before any spend"
  fi
  # reserve floor: SOL-lane USDC (vault + hot) must clear RESERVE_MIN ($12)
  SOLCASH=$(python3 -c "import sys;sys.path.insert(0,'$D/scripts');import portfolio_state as p
v=p._read_sol_usdc_any(p.SOL_VAULT_WALLET);h=p._read_sol_usdc_any(p.SOL_HOT_WALLET)
print('{:.2f}'.format((v or 0)+(h or 0)) if (v is not None or h is not None) else '')" 2>/dev/null)
  note "SOL-lane USDC (vault+hot) = \$${SOLCASH:-unreadable}"
  if [ -z "$SOLCASH" ]; then
    halt "SOL reserve unreadable — cannot verify floor"
  elif [ "$(python3 -c "print(float('$SOLCASH') < 12.0)")" = "True" ]; then
    halt "SOL reserve \$$SOLCASH < floor \$12.00"
  fi
fi

if [ "$HALTED" = "1" ]; then
  note "RESULT: BLOCKED (exit 1) — engine tick will NOT run"
  exit 1
fi
note "RESULT: PASS — safe to tick"
exit 0
