#!/usr/bin/env python3
"""
lane_funding.py - Agentic Trading LANE FUNDING RESOLVER (auto cross-lane top-up brain).

Decision engine for: "a trade qualified on Lane X but Lane X USDC is short — what do we
do?" It NEVER says "wait for boss". Output is one of:

  READY          -> Lane X already has enough USDC; execute locally.
  AUTO_BRIDGE    -> Surplus exists on another lane above ITS floor AND an auto-bridge
                    provider is available -> bridge now, then execute in the same cycle.
  BRIDGE_TICKET  -> Surplus exists but no auto provider ready -> emit an exact,
                    actionable bridge ticket (amount/from/to) + auto-retry each tick.
  NEEDS_FUND     -> No lane has surplus above its floor -> real external top-up needed
                    (alert + Team HQ ticket). Nothing else can fund it.

Guardrails: a sending lane NEVER drops below its floor; only bridge when the deficit is
economically meaningful (>= MIN_BRIDGE_USD) and cost is a sane % of the trade.

Input `cash` = EXECUTABLE lane liquidity (e.g. solana = hot USDC + vault pullable-under-
cap; base = Safe USDC). Caller computes that; resolver stays pure/testable.
"""
import argparse
import json

FLOORS = {"solana": 12.0, "base": 5.0}   # lane floors (match usdc-topup-advisor defaults)
MIN_BRIDGE_USD = 1.50                    # below this, bridging fees are not worth it
BUFFER_USD = 0.50                        # bridge a little extra so dest lands inside floor


def resolve(need_chain, need_usd, cash, floors=None, auto_provider=False):
    """Return a decision dict for funding a trade on `need_chain`."""
    floors = dict(floors or FLOORS)
    cash = {k: float(v or 0) for k, v in (cash or {}).items()}
    have = cash.get(need_chain, 0.0)
    if have >= need_usd:
        return {"decision": "READY", "chain": need_chain, "needUsd": need_usd,
                "haveUsd": have, "action": "execute local trade"}

    deficit = need_usd - have
    # surplus of OTHER lanes above their own floors (senders never go below floor)
    surplus = {k: max(0.0, cash.get(k, 0.0) - floors.get(k, 0.0))
               for k in cash if k != need_chain}
    total_surplus = sum(surplus.values())

    if total_surplus + BUFFER_USD < deficit:
        return {"decision": "NEEDS_FUND", "chain": need_chain, "needUsd": need_usd,
                "haveUsd": have, "deficitUsd": round(deficit, 2),
                "action": "no lane surplus above floor -> alert boss + Team HQ ticket (real top-up)"}

    if deficit < MIN_BRIDGE_USD:
        return {"decision": "SKIP_BRIDGE_TOO_SMALL", "chain": need_chain,
                "needUsd": need_usd, "deficitUsd": round(deficit, 2),
                "action": "deficit below economic bridge minimum - keep watching (no silence: logged each tick)"}

    # pick sender(s): richest surplus lane first
    ordered = sorted(surplus.items(), key=lambda kv: -kv[1])
    from_lane = ordered[0][0]
    amount = round(min(deficit + BUFFER_USD, surplus[from_lane]), 2)
    route = {"from": from_lane, "to": need_chain, "amountUsd": amount,
             "provider": "auto" if auto_provider else "pending"}
    if auto_provider:
        return {"decision": "AUTO_BRIDGE", "chain": need_chain, "needUsd": need_usd,
                "haveUsd": have, "deficitUsd": round(deficit, 2), "bridge": route,
                "action": "bridge %s->%s $%.2f then execute trade in same cycle" % (from_lane, need_chain, amount)}
    return {"decision": "BRIDGE_TICKET", "chain": need_chain, "needUsd": need_usd,
            "haveUsd": have, "deficitUsd": round(deficit, 2), "bridge": route,
            "action": "emit exact bridge ticket + auto-retry each tick (no silence, no wait)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", required=True, help="lane that needs funding: solana|base")
    ap.add_argument("--usd", type=float, required=True)
    ap.add_argument("--cash-sol", type=float, default=None)
    ap.add_argument("--cash-base", type=float, default=None)
    ap.add_argument("--auto", action="store_true", help="assume auto-bridge provider available")
    args = ap.parse_args()
    if args.cash_sol is None or args.cash_base is None:
        import portfolio_state
        st = portfolio_state.build_portfolio_state(live=True)
        lanes = st.get("cashByLane") or {}
        args.cash_sol = lanes.get("solana", 0.0)
        args.cash_base = lanes.get("base", 0.0)
    cash = {"solana": args.cash_sol, "base": args.cash_base}
    out = resolve(args.need, args.usd, cash, auto_provider=args.auto)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
