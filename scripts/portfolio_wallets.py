#!/usr/bin/env python3
"""
portfolio_wallets.py - Agentic Trading: multi-portfolio wallet registry ("Add Wallet").

Lets the Portfolio Manager track/manage MORE than one portfolio. Each portfolio is a
named group of wallets; the registry lives in data/live/portfolios.json (money source
of truth for wallet IDENTITY stays data/live/config.json + evm-autopilot.json; this
file only lists which wallets belong to which managed portfolio).

  python3 scripts/portfolio_wallets.py list                       # show portfolios
  python3 scripts/portfolio_wallets.py add --portfolio primary \
      --label "Alt SOL hot" --chain solana --type hot --address <addr>
  python3 scripts/portfolio_wallets.py add --label "New portfolio" --address <addr> \
      --chain base --type safe --new-portfolio

Rules: addresses are validated by shape; 'primary' already contains the unified
account. Solana addresses = base58 len 32-44; EVM addresses = 0x + 40 hex.
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "data", "live", "portfolios.json")
EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
CHAINS = ("solana", "base", "ethereum", "bsc", "hyperevm", "robinhood")


def _load():
    try:
        return json.load(open(REG))
    except Exception:
        return {"portfolios": [], "updatedAt": ""}


def _save(d):
    d["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(d, open(REG, "w"), indent=2)


def list_portfolios():
    return [p["id"] for p in _load()["portfolios"]]


def add_wallet(label, chain, wtype, address, portfolio="primary", new_portfolio=None):
    d = _load()
    chain = chain.lower()
    if chain not in CHAINS:
        raise ValueError("chain must be one of %s" % ", ".join(CHAINS))
    if chain == "solana" and not SOL_RE.match(address):
        raise ValueError("invalid Solana address")
    if chain != "solana" and not EVM_RE.match(address):
        raise ValueError("invalid EVM address (need 0x + 40 hex)")
    pid = new_portfolio or portfolio
    port = next((p for p in d["portfolios"] if p["id"] == pid), None)
    if port is None:
        port = {"id": pid, "label": pid, "wallets": []}
        d["portfolios"].append(port)
    wid = "w-%s-%d" % (pid, len(port["wallets"]) + 1)
    port["wallets"].append({"id": wid, "label": label, "chain": chain,
                            "type": wtype or "other", "address": address})
    _save(d)
    return {"portfolio": pid, "walletId": wid}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list")
    a = sub.add_parser("add")
    a.add_argument("--label", required=True)
    a.add_argument("--chain", required=True)
    a.add_argument("--address", required=True)
    a.add_argument("--type", dest="wtype", default="other")
    a.add_argument("--portfolio", default="primary")
    a.add_argument("--new-portfolio", dest="new_portfolio", default=None)
    args = ap.parse_args()
    if args.cmd == "list":
        for p in _load()["portfolios"]:
            print("%s (%s):" % (p["id"], p.get("label", p["id"])))
            for w in p["wallets"]:
                print("  - %s [%s/%s] %s %s" % (w["id"], w["chain"], w["type"], w["label"], w["address"]))
    elif args.cmd == "add":
        r = add_wallet(args.label, args.chain, args.wtype, args.address,
                       args.portfolio, args.new_portfolio)
        print("ADDED wallet %s to portfolio %s" % (r["walletId"], r["portfolio"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("ERR", e)
        sys.exit(1)
