#!/usr/bin/env python3
"""
usdc-topup-advisor.py - Agentic Trading (Meme Profit Snatcher) cross-lane USDC top-up.

UNIFIED USDC DESK helper (fomo.family-style "one balance" behavior): the account's
cash lives as USDC per lane (solana-usdc in the SOL hot wallet, base-usdc in the EVM
Safe). When one lane drops below its operating floor and another has surplus, this
advisor RECOMMENDS a Rubic bridge to rebalance. It NEVER sends anything - boss GO +
Execution (via wallet-signer / Rubic URL) does that.

Usage:
    python3 scripts/usdc-topup-advisor.py                    # live reads, default floors
    python3 scripts/usdc-topup-advisor.py --no-live          # snapshot files only
    python3 scripts/usdc-topup-advisor.py --floor-solana 12 --floor-base 5 --json

Defaults (floors):
    solana: 12.0 USDC   (matches autopilot reserve floor in scripts/autopilot.py)
    base:    5.0 USDC   (EVM desk wants dry powder for entries on Base)

Output: recommendation dict; exit 0 (advisory only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# Keep import local so a missing feed can never crash the CLI.
import portfolio_state  # noqa: E402

BUFFER_USD = 1.0  # bridge a little extra so the receiving lane lands INSIDE the floor


def recommend(state: Dict[str, Any], floor_solana: float, floor_base: float) -> Dict[str, Any]:
    lanes = state.get("cashByLane") or {}
    sol = float(lanes.get("solana") or 0.0)
    base = float(lanes.get("base") or 0.0)
    sol_deficit = max(0.0, floor_solana - sol)
    base_deficit = max(0.0, floor_base - base)
    actions: list = []

    # Only the two real trading lanes move USDC between each other. A lane may only
    # SEND its surplus (above its own floor), so no bridge ever starves the sender.
    if sol_deficit > 0 and base > base_deficit:
        avail = max(0.0, base - floor_base)          # base surplus above ITS floor
        amount = min(sol_deficit + BUFFER_USD, avail)
        if amount >= 1.0:
            actions.append({
                "kind": "bridge_usdc",
                "from": "base-usdc", "to": "solana-usdc", "amountUsd": round(amount, 2),
                "reason": "solana lane $%.2f < floor $%.2f" % (sol, floor_solana),
                "execute": "boss GO -> Rubic bridge Base USDC -> Solana USDC (rubic_get_swap_url)",
            })
    if base_deficit > 0 and sol > sol_deficit:
        avail = max(0.0, sol - floor_solana)         # solana surplus above ITS floor
        amount = min(base_deficit + BUFFER_USD, avail)
        if amount >= 1.0:
            actions.append({
                "kind": "bridge_usdc",
                "from": "solana-usdc", "to": "base-usdc", "amountUsd": round(amount, 2),
                "reason": "base lane $%.2f < floor $%.2f" % (base, floor_base),
                "execute": "boss GO -> Rubic bridge Solana USDC -> Base USDC (rubic_get_swap_url)",
            })

    out = {
        "asOf": state.get("asOf"),
        "cashByLane": {k: round(float(v or 0), 2) for k, v in lanes.items() if k != "other"},
        "floors": {"solana": floor_solana, "base": floor_base},
        "deficits": {"solana": round(sol_deficit, 2), "base": round(base_deficit, 2)},
        "recommendations": actions,
        "note": "ADVISORY ONLY - never executes. Boss GO + Execution (wallet-signer/Rubic) required.",
    }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Unified USDC desk - cross-lane top-up advisor")
    ap.add_argument("--no-live", action="store_true", help="use snapshot files (offline)")
    ap.add_argument("--floor-solana", type=float, default=float(os.getenv("SOLANA_USDC_FLOOR", "12.0")))
    ap.add_argument("--floor-base", type=float, default=float(os.getenv("BASE_USDC_FLOOR", "5.0")))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    st = portfolio_state.build_portfolio_state(live=not a.no_live)
    out = recommend(st, a.floor_solana, a.floor_base)
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        print("USDC top-up advisor  %s" % (out["asOf"] or ""))
        print("  lanes : %s" % out["cashByLane"])
        print("  floors: %s" % out["floors"])
        if out["recommendations"]:
            for r in out["recommendations"]:
                print("  BRIDGE %s -> %s : $%.2f (%s)" % (r["from"], r["to"], r["amountUsd"], r["reason"]))
        else:
            print("  all lanes at/above floor - no top-up recommended")
