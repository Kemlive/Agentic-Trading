#!/usr/bin/env python3
"""Adaptive snatcher monitor for OPEN live positions.

Reads data/live/holdings.json (open positions), pulls LIVE pair behavior from
DexScreener (price, volume, buy/sell pressure, liquidity) and decides like a
snatcher - not a fixed CEX %:
  - BANK when profit >= +30% AND momentum fades (sells rising / m5 flat-red)
  - TRAIL after banking: exit rest if price falls >=15% from the peak we saw
  - HARD STOP -30% from entry (capital protection, never negotiable)
  - TIME STOP 24h unless boss extends
  - HOLD while buys > sells and price is pressing higher (let winners run on house money)

Tracks a per-position peak in data/live/snatcher-state.json. Read-only: NO execution.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOLDINGS = os.path.join(ROOT, "data", "live", "holdings.json")
STATE = os.path.join(ROOT, "data", "live", "snatcher-state.json")
TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{}"
TRAIL_DROP = 0.85      # exit rest if price < peak * 0.85
BANK_FLOOR = 1.30      # bank half once +30% AND momentum fades
STOP = 0.70            # -30%
TIME_STOP_H = 24.0


def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading-paper/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pair_live(mint):
    d = http_get(TOKEN.format(mint))
    best = None
    for pr in d.get("pairs") or []:
        if pr.get("chainId") != "solana":
            continue
        try:
            v = float((pr.get("volume") or {}).get("h24") or 0)
        except Exception:
            v = 0
        if best is None or v > best[0]:
            best = (v, pr)
    return best[1] if best else None


def main():
    if not os.path.exists(HOLDINGS):
        print("no holdings file")
        return 1
    holdings = json.load(open(HOLDINGS))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"peaks": {}}
    opens = [p for p in holdings.get("positions", []) if p["status"] == "open"]
    if not opens:
        print("no open live positions")
        return 0
    print("=== SNATCHER MONITOR ===")
    for pos in opens:
        pid = pos["id"]
        entry = float(pos.get("entryImpliedUsd") or pos.get("entryUsd") or 0)
        print(f"\n[{pid}] {pos['symbol']}  entry=${entry:.8g}")
        try:
            pr = pair_live(pos["mint"])
        except Exception as e:
            print("  pair fetch failed:", e)
            continue
        if not pr:
            print("  no live pair")
            continue
        price = float(pr.get("priceUsd"))
        pct = (price / entry - 1) * 100 if entry else 0
        chg = pr.get("priceChange") or {}
        vol = pr.get("volume") or {}
        txn = pr.get("txns") or {}
        try:
            b5 = (txn.get("m5") or {}).get("buys") or 0
            s5 = (txn.get("m5") or {}).get("sells") or 0
            b1 = (txn.get("h1") or {}).get("buys") or 0
            s1 = (txn.get("h1") or {}).get("sells") or 0
        except Exception:
            b5 = s5 = b1 = s1 = 0
        buy_pressure = (b5 / s5) if s5 else (999 if b5 else None)
        peak = max(state["peaks"].get(pid, 0), price)
        state["peaks"][pid] = peak
        peak_pct = (price / peak - 1) * 100 if peak else 0
        print(f"  price=${price:.8g}  pnl={pct:+.1f}%  peakSeen=${peak:.8g} (now {peak_pct:+.1f}% vs peak)")
        print(f"  buys/sells m5={b5}/{s5} (ratio {buy_pressure if buy_pressure is None else round(buy_pressure,2)}) h1={b1}/{s1}")
        print(f"  chg m5/h1/h6 = {chg.get('m5')}%/{chg.get('h1')}%/{chg.get('h6')}%  vol h1=${(vol.get('h1') or 0):,.0f}")
        age_h = None
        import datetime
        try:
            age_h = (datetime.datetime.now(datetime.timezone.utc) -
                     datetime.datetime.fromisoformat(pos["openedAt"])).total_seconds() / 3600.0
        except Exception:
            pass
        actions = []
        reason = []
        if price <= entry * STOP:
            actions.append("SELL 100% (hard stop -30%)")
            reason.append("capital protection")
        elif age_h and age_h >= TIME_STOP_H:
            actions.append("SELL 100% (time stop 24h)")
            reason.append(f"age {age_h:.1f}h")
        elif not pos.get("tp1Hit") and pct >= 30 and (chg.get("m5") or 0) <= 0:
            actions.append("BANK ~50% (snatcher grab: profit >= +30% & momentum fading)")
            pos["tp1Hit"] = True
            reason.append(f"momentum fading after +{pct:.0f}%")
        elif pos.get("tp1Hit") and peak_pct <= -15:
            actions.append("SELL REST (trail stop: -15% off the peak we saw)")
            reason.append("trail hit")
        else:
            if pct > 0 and buy_pressure is not None and buy_pressure >= 1.2 and (chg.get("m5") or 0) > 0:
                actions.append("HOLD (buyers pressing, let it run on house money)")
                reason.append("momentum strong")
            elif pct > 0:
                actions.append("HOLD (in profit; watching behavior - bank if m5 turns red)")
                reason.append("watch mode")
            else:
                actions.append("HOLD (underwater but > -30%; watch for stop)")
                reason.append("in tolerance")
        print("  ACTION:", "; ".join(actions))
        print("  WHY:", ", ".join(reason))
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
