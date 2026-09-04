#!/usr/bin/env python3
"""Paper trading engine for Pump.fun candidates (hypothetical $5 entries).

Opens paper positions from the latest pump-scan report, then on every run
evaluates open positions against LIVE prices and applies the exit rules:
  - Take-profit 1: sell 50% at +50%
  - Stop-loss: close all at -30%
  - Trailing rule: after TP1, close rest if price falls back to entry
  - Take-profit 2: close rest at +150% from entry (after TP1)
  - Time-stop: close all after 24h

NO real money, NO signing. State under data/paper/. Logs to logs/trades.jsonl.
"""
import json
import time
import glob
import datetime
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "data", "paper")
SEEN = os.path.join(PAPER, "seen.json")
POS = os.path.join(PAPER, "positions.json")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")

SIZE_USD = 5.0
MAX_OPEN = 5
NEW_PER_RUN = 2
TP1_MULT = 1.5          # +50%  -> sell half
TP2_MULT = 2.5          # +150% -> close rest
STOP_MULT = 0.7         # -30%  -> close all
TIME_STOP_H = 24.0

TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{}"


def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading-paper/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, indent=2)


def log_event(rec):
    rec["ts"] = now_iso()
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def live_price(token_addr, chain="solana"):
    d = http_get(TOKEN.format(token_addr))
    best = None
    for pr in d.get("pairs") or []:
        if pr.get("chainId") != chain:
            continue
        try:
            v = float((pr.get("volume") or {}).get("h24") or 0)
        except Exception:
            v = 0
        if best is None or v > best[0]:
            best = (v, pr)
    if not best:
        return None
    try:
        return float(best[1].get("priceUsd"))
    except Exception:
        return None


def close(pos, price, reason, now):
    shares = pos["remainingShares"]
    if shares <= 0 or not price:
        return 0.0
    proceeds = shares * price
    basis = shares * pos["entryUsd"]
    pnl = proceeds - basis
    pos["remainingShares"] = 0.0
    pos["status"] = "closed"
    pos["closedAt"] = now
    pos["closeReason"] = reason
    pos["exitPriceUsd"] = price
    pos["realizedUsd"] = round((pos.get("realizedUsd") or 0.0) + pnl, 4)
    pos["closedPnlUsd"] = round(pnl, 4)
    return pnl


def evaluate(pos, now):
    if pos["status"] != "open":
        return 0.0, []
    price = None
    events = []
    try:
        price = live_price(pos["token"], pos.get("chain", "solana"))
    except Exception:
        pass
    if not price or price <= 0:
        return 0.0, ["price fetch failed, position kept open"]
    entry = pos["entryUsd"]
    mult = price / entry
    age_h = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.datetime.fromisoformat(pos["openedAt"])).total_seconds() / 3600.0
    pnl = 0.0
    if mult <= STOP_MULT:
        pnl = close(pos, price, "stop_loss_-30%", now)
        events.append(f"CLOSE {pos['symbol']} stop -30% pnl=${pnl:.2f} @ {price:.10g}")
    elif age_h >= TIME_STOP_H:
        pnl = close(pos, price, "time_stop_24h", now)
        events.append(f"CLOSE {pos['symbol']} time-stop pnl=${pnl:.2f} @ {price:.10g}")
    elif not pos.get("tp1Hit") and mult >= TP1_MULT:
        half = pos["remainingShares"] / 2.0
        proceeds = half * price
        basis = half * entry
        gain = proceeds - basis
        pos["remainingShares"] -= half
        pos["realizedUsd"] = round((pos.get("realizedUsd") or 0.0) + gain, 4)
        pos["tp1Hit"] = True
        events.append(f"TP1 {pos['symbol']} sold 50% gain=${gain:.2f} @ {price:.10g} (entry {entry:.10g})")
        if mult >= TP2_MULT:
            pnl = close(pos, price, "take_profit_+150%", now)
            events.append(f"CLOSE {pos['symbol']} TP2 pnl=${pnl:.2f}")
    elif pos.get("tp1Hit") and mult >= TP2_MULT:
        pnl = close(pos, price, "take_profit_+150%", now)
        events.append(f"CLOSE {pos['symbol']} TP2 pnl=${pnl:.2f} @ {price:.10g}")
    elif pos.get("tp1Hit") and mult <= 1.0:
        pnl = close(pos, price, "trail_to_entry", now)
        events.append(f"CLOSE {pos['symbol']} trail-to-entry pnl=${pnl:.2f} @ {price:.10g}")
    return pnl, events


def open_positions(candidates, seen, positions, now):
    opened = []
    open_count = len([p for p in positions if p["status"] == "open"])
    room = max(0, MAX_OPEN - open_count)
    picks = 0
    for c in sorted(candidates, key=lambda r: (r.get("buy_sell_m5") or 0), reverse=True):
        if picks >= min(NEW_PER_RUN, room):
            break
        addr = c["token"]
        chain = c.get("chain") or "solana"
        flags = c.get("flags") or []
        if f"{chain}:{addr}" in seen:
            continue
        if any(f in flags for f in ("PAID BOOST - extra scrutiny", "thin liquidity <$2k",
                                    "old (>48h)", "m5 pump >150% (chase risk)")):
            continue
        try:
            liq = float(c.get("liqUsd") or 0)
            price = float(c.get("priceUsd") or 0)
            fdv = float(c.get("fdv") or 0)
        except Exception:
            continue
        if liq < 2000 or price <= 0 or not (20000 <= fdv <= 300000):
            continue
        qty = SIZE_USD / price
        pos = {"token": addr, "chain": chain, "symbol": c.get("symbol", "?"),
               "openedAt": now, "entryUsd": price, "sizeUsd": SIZE_USD,
               "remainingShares": qty, "remainingCost": SIZE_USD, "realizedUsd": 0.0,
               "tp1Hit": False, "status": "open", "url": c.get("url"), "fdvUsd": fdv}
        positions.append(pos)
        seen[f"{chain}:{addr}"] = now
        opened.append(pos)
        picks += 1
        log_event({"event": "paper_open", "symbol": pos["symbol"], "chain": chain,
                   "token": addr, "entryUsd": price, "sizeUsd": SIZE_USD,
                   "url": c.get("url")})
    return opened


def latest_scan():
    files = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
    if not files:
        return None
    with open(files[-1]) as f:
        return json.load(f)


def daily_summary(positions, events, opened, now, realized_total):
    today = now[:10]
    fn = os.path.join(ROOT, "research", f"paper-daily-{today}.md")
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    opens = [p for p in positions if p["status"] == "open"]
    equity = sum(p["remainingShares"] * p["entryUsd"] for p in opens)
    total_realized = sum(float(p.get("realizedUsd") or 0.0) for p in positions)
    lines = [f"# Paper Trading — {today}", "",
             f"_Auto run {now} | hypothetical $5 positions | rule engine v1_", "",
             f"**Realized all-time: ${total_realized:.2f}** | this run ${realized_total:.2f} | "
             f"Open: {len(opens)} (cost ~${equity:.2f})", ""]
    if opened:
        lines.append(f"Opened {len(opened)} this run: " + ", ".join(f"{p['symbol']}@{p['entryUsd']:.6g}" for p in opened))
    if events:
        lines.append("### Events")
        lines += [f"- {e}" for e in events]
    with open(fn, "w") as f:
        f.write("\n".join(lines) + "\n")
    return fn


def main():
    os.makedirs(PAPER, exist_ok=True)
    seen = load(SEEN, {})
    # migrate legacy keys (pre-multichain entries were all solana)
    seen = {(k if ":" in k else "solana:" + k): v for k, v in seen.items()}
    positions = load(POS, [])
    for p in positions:
        p.setdefault("chain", "solana")
    now = now_iso()
    events = []
    opened = []
    realized = 0.0
    for p in positions:
        pnl, evs = evaluate(p, now)
        realized += pnl
        events += evs
        for e in evs:
            if e.startswith("CLOSE"):
                log_event({"event": "paper_close", "symbol": p["symbol"], "token": p["token"],
                           "reason": p["closeReason"], "pnlUsd": p["closedPnlUsd"],
                           "exitUsd": p["exitPriceUsd"]})
    scan = latest_scan()
    if scan:
        opened = open_positions(scan.get("candidates") or [], seen, positions, now)
    save(SEEN, seen)
    save(POS, positions)
    fn = daily_summary(positions, events, opened, now, realized)
    print(f"paper-track | opened={len(opened)} | events={len(events)} | realized=${realized:.2f}")
    for e in events:
        print("  " + e)
    print(f"summary: {fn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


