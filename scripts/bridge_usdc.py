#!/usr/bin/env python3
"""
bridge_usdc.py - Agentic Trading AUTO-BRIDGE orchestrator (cross-lane top-up executor).

Sits on top of lane_funding.py. Provider layer:

  AUTO  providers (source leg signed by OUR keys; destination completed by relayer):
    - mayan-swift : Solana->Base (sign SOL leg w/ agent key) and Base->Solana (sign EVM
                    leg w/ evm-signer). Endpoint calibration in progress (sia/price-api
                    reachable; exact order schema pending docs) - DRY/no-op until
                    PROVERS["mayan"]["ready"]=True.
  MANUAL provider (always ready, never silence):
    - dexbridge-ticket : exact bridge ticket (amount/from/to + destination address) for
                         boss/Phantom DexBridge, auto-retried each tick by the resolver.

NEVER executes without --go; DRY by default. Logs decisions to Team HQ channel.
Usage:
  python3 scripts/bridge_usdc.py plan --need base --usd 4.0        # decision only
  python3 scripts/bridge_usdc.py ticket --need base --usd 4.0      # manual ticket
  python3 scripts/bridge_usdc.py providers                         # provider status
"""
import argparse
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import lane_funding  # noqa: E402

DEST_BASE_USDC = "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A"   # Base Safe (lane holder)
DEST_SOL_USDC = "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4"  # SOL vault (lane holder)

PROVIDERS = {
    "mayan": {"ready": True, "note": "SOL->BASE LIVE (MCTP $1 test COMPLETED, Safe +0.995001, ~0.5% all-in); BASE->SOLANA reverse leg = T-6 pending"},
    "rubic": {"ready": False, "note": "SVM build sim previously failed; retry gated on green sim"},
    "dexbridge_ticket": {"ready": True, "note": "manual Phantom DexBridge ticket (auto-retried)"},
}

MAYAN_SDK_VERSION = "15.2.2"
MAYAN_USDC = {"solana": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
              "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"}


def mayan_quote(amount_usd, from_chain="solana", to_chain="base", destination=None, slippage_bps=300):
    """Live Mayan quote (read-only). Returns best quote or None on any failure."""
    import urllib.request
    import urllib.parse
    p = {"amountIn": str(amount_usd),
         "fromToken": MAYAN_USDC[from_chain], "fromChain": from_chain,
         "toToken": MAYAN_USDC[to_chain], "toChain": to_chain,
         "slippageBps": str(slippage_bps),
         "swift": "true", "mctp": "true", "fastMctp": "true", "wormhole": "true",
         "sdkVersion": MAYAN_SDK_VERSION}
    if destination:
        p["destinationAddress"] = destination
    url = "https://price-api.mayan.finance/v3/quote?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading-bridge/0.1"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    qs = d.get("quotes") or []
    if not qs:
        return {"ok": False, "error": "no routes: %s" % str(d)[:200]}
    best = min(qs, key=lambda q: float(q.get("protocolBps") or 0)) if len(qs) > 1 else qs[0]
    return {"ok": True, "quotes": len(qs), "best": {k: best.get(k) for k in
            ("type", "expectedAmountOut", "minReceived", "etaSeconds", "protocolBps", "gasless")}}

LANE_HOLDER = {"solana": DEST_SOL_USDC, "base": DEST_BASE_USDC}


def _live_cash():
    try:
        import portfolio_state
        st = portfolio_state.build_portfolio_state(live=True)
        lanes = st.get("cashByLane") or {}
        return {k: float(v or 0) for k, v in lanes.items() if k in ("solana", "base")}
    except Exception:
        return {}


def plan(need, usd, cash=None, auto=False):
    cash = cash if cash is not None else _live_cash()
    return lane_funding.resolve(need, usd, cash, auto_provider=auto)


def make_ticket(decision):
    """Human/agent-actionable ticket from a BRIDGE_TICKET / AUTO_BRIDGE decision."""
    br = decision.get("bridge") or {}
    frm, to, amt = br.get("from"), br.get("to"), br.get("amountUsd")
    if not (frm and to and amt):
        return {"ok": False, "reason": "no bridge to ticket", "decision": decision["decision"]}
    if frm == "solana":
        src_holder = "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4"  # SOL vault (owner)
        url = ("https://app.rubic.exchange/?fromChain=SOLANA&from=USDC&to=USDC"
               "&toChain=%s&amount=%.2f") % ("BASE" if to == "base" else "SOLANA", amt)
    else:
        src_holder = DEST_BASE_USDC
        url = ("https://app.rubic.exchange/?fromChain=BASE&from=USDC&to=USDC"
               "&toChain=%s&amount=%.2f") % ("SOLANA" if to == "solana" else "BASE", amt)
    t = {"ok": True, "kind": "bridge_ticket", "from": frm, "to": to, "amountUsd": amt,
         "sourceUsdcHeldBy": src_holder, "destUsdcAddress": LANE_HOLDER.get(to),
         "reason": decision.get("action"), "url": url,
         "note": "execute via Phantom DexBridge or Rubic app; paste tx here; resolver auto-retries until done"}
    return t


def log_to_hq(text):
    try:
        import team_ops
        team_ops.post("execution", "chief", text)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan"); a.add_argument("--need", required=True); a.add_argument("--usd", type=float, required=True)
    a.add_argument("--auto", action="store_true")
    t = sub.add_parser("ticket"); t.add_argument("--need", required=True); t.add_argument("--usd", type=float, required=True)
    mq = sub.add_parser("mayan-quote"); mq.add_argument("--usd", type=float, required=True)
    mq.add_argument("--from", dest="frm", default="solana")
    mq.add_argument("--to", default=None)
    p = sub.add_parser("providers")
    args = ap.parse_args()

    if args.cmd == "providers":
        print(json.dumps(PROVIDERS, indent=2))
        return 0
    if args.cmd == "mayan-quote":
        if args.to is None:
            args.to = "base" if args.frm == "solana" else "solana"
        dst = DEST_BASE_USDC if args.to == "base" else DEST_SOL_USDC
        q = mayan_quote(args.usd, args.frm, args.to, destination=dst)
        if q.get("ok"):
            exp = float(q["best"].get("expectedAmountOut") or 0)
            q["allInPct"] = round((1 - exp / args.usd) * 100, 2)
        print(json.dumps(q, indent=2))
        return 0
    if args.cmd in ("plan", "ticket"):
        cash = _live_cash()
        # NOTE: 'executable' solana liquidity includes the vault pull under the delegate cap;
        # for a plain plan view we report raw lane cash so decisions match the ledger.
        dec = plan(args.need, args.usd, cash=cash, auto=args.auto)
        print(json.dumps(dec, indent=2))
        if args.cmd == "ticket" and dec.get("decision") in ("BRIDGE_TICKET", "AUTO_BRIDGE"):
            tk = make_ticket(dec)
            print(json.dumps(tk, indent=2))
            log_to_hq("execution -> chief: bridge ticket $%.2f %s->%s (%s)" %
                      (tk.get("amountUsd", 0), tk.get("from"), tk.get("to"), dec["decision"]))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
