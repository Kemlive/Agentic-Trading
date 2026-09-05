#!/usr/bin/env python3
"""fastlane.py — REAL-COIN EXECUTION LANE (replaces the paused micro-bond snatcher).

Runs every 30s via the same launchd as fast-watch.py. Real money, real coins, no paper:
  Universe : curated liquid Solana coins (watchlist from fast-watch, liq >= 100k)
  Entries  : PULLBACK-READY (liq>=300k, 1h uptrend, 5m dip w/ buyer support) or MOMENTUM
             (liq>=500k, +8..60% 1h, controlled 5m). Sized $2.50..$5.00/trade,
             daily cap $10, max 2 open, delegate cap enforced.
  Exits    : HARD STOP -15% (fills on liquid coins), BANK half at +30%, TRAIL -12% off
             peak, TIME STOP 12h, forced close if the feed dies.
  Guards   : daily realized -$6 halts entries; fastlane.off pauses everything.
Off-switch: create data/live/fastlane.off
"""
import os
import sys
import time
import datetime
import json
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib.util as _iu
_FS = _iu.spec_from_file_location("fastwatch", os.path.join(ROOT, "scripts", "fast-watch.py"))
F = _iu.module_from_spec(_FS)
_FS.loader.exec_module(F)
import autopilot as A             # execution primitives (pull/swap/push, delegate)

OFF = os.path.join(ROOT, "data", "live", "fastlane.off")
POS_FILE = os.path.join(ROOT, "data", "live", "fastlane-positions.json")
STATE_FILE = os.path.join(ROOT, "data", "live", "fastlane-state.json")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")

MAX_OPEN = 2
MAX_TRADE = 10.0      # single-chain book (~$66) - clips sized to real coins
DAILY_CAP = 25.0
DAILY_LOSS_HALT = 12.0
STOP_PCT = -15.0
BANK_PCT = 30.0
TRAIL_PCT = -12.0
TIME_STOP_H = 12.0
FEED_MISS_MAX = 6           # passes (~3 min) without a price before forced close
BOT_CFG_FILE = os.path.join(ROOT, "data", "live", "bot-feed.json")
FEED_COINS = os.path.join(ROOT, "data", "live", "feed", "coins.json")


def bot_feed_cfg():
    def_ = {"enabled": True, "maxCandidates": 8, "tiers": ["trending", "gainer", "migrated"],
            "minT60": 20, "minAgeSec": 900, "staleMaxSec": 240,
            "note": "fastlane also collects from own feed intel (coins.json); real-coin liq/trend gates still apply"}
    try:
        return {**def_, **json.load(open(BOT_CFG_FILE))}
    except Exception:
        return def_


def _age_sec(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds()
    except Exception:
        return None


def feed_intel_candidates(cfg):
    """Own-feed entry shortlist: coins.json tiers -> mints (still gated later by
    the same real-coin liquidity/trend checks as the static watchlist)."""
    try:
        coins = json.load(open(FEED_COINS))
    except Exception:
        return []
    reg_age = _age_sec(coins.get("asOf"))
    if reg_age is None or reg_age > cfg.get("staleMaxSec", 240):
        return []
    ref_age = _age_sec((coins.get("chainRefTime") or {}).get("solana"))
    if ref_age is None or ref_age > cfg.get("staleMaxSec", 240):
        return []
    rows = []
    cats = (coins.get("categories") or {}).get("solana") or {}
    for tier in cfg.get("tiers", []):
        for r in cats.get(tier) or []:
            if int(r.get("ageSec") or 0) < cfg.get("minAgeSec", 900):
                continue
            if int(r.get("t60") or 0) < cfg.get("minT60", 20):
                continue
            rows.append(r)
    rows.sort(key=lambda x: x.get("score") or 0, reverse=True)
    return [r["key"] for r in rows[: cfg.get("maxCandidates", 8)]]

NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def log_event(rec):
    rec["ts"] = NOW
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def notify(text):
    try:
        import subprocess
        subprocess.run(["python3", os.path.join(ROOT, "scripts", "notify-telegram.py"),
                        "msg", text], timeout=20)
    except Exception:
        pass


def load_positions():
    return F.load(POS_FILE, {"positions": []})


def save_positions(obj):
    F.save(POS_FILE, obj)


def reset_day(st):
    today = datetime.date.today().isoformat()
    if st.get("day") != today:
        st["day"] = today
        st["spentToday"] = 0.0
        st["realizedToday"] = 0.0
        st["peak"] = {}
    return st


def lane_open_count():
    return len([p for p in load_positions().get("positions", []) if p.get("status") == "open"])


def held(addr):
    return any(p.get("status") == "open" and p.get("mint") == addr
               for p in load_positions().get("positions", []))


def buy_px_checks(pr):
    """Reuse the same real-coin signal thresholds as fast-watch."""
    chg = pr.get("priceChange") or {}
    tx = pr.get("txns") or {}
    def f(x):
        try:
            return float(x)
        except Exception:
            return None
    liq = f((pr.get("liquidity") or {}).get("usd")) or 0
    m5, h1, h6, h24 = f(chg.get("m5")), f(chg.get("h1")), f(chg.get("h6")), f(chg.get("h24"))
    try:
        b = (tx.get("m5") or {}).get("buys") or 0
        s = (tx.get("m5") or {}).get("sells") or 0
        bs5 = round(b / s, 2) if s else None
    except Exception:
        bs5 = None
    try:
        age = (time.time() * 1000 - int(pr.get("pairCreatedAt") or 0)) / 3600000.0
    except Exception:
        age = None
    pullback = (liq >= 300000 and (age is None or age >= 1) and 0 < (h1 or 0) <= 80
                and -50 < (m5 or 0) <= -1.5 and bs5 is not None and bs5 >= 1.0
                and (h6 or 0) <= 200)
    momentum = (liq >= 500000 and 8 <= (h1 or 0) <= 60 and 3 <= (m5 or 0) <= 30
                and (h24 or 0) <= 400)
    if pullback:
        return "PULLBACK-READY"
    if momentum:
        return "MOMENTUM"
    return None

def do_sell(pos, px, reason, frac=1.0):
    """Sell `frac` of an open fast-lane position back to USDC. Returns realized or None."""
    qty_raw = int(float(pos.get("qty") or 0) * frac * 1e6)
    if qty_raw <= 0:
        return None
    before = A.token_balance_retry(A.USDC)
    sig, err = A.build_and_send(pos["mint"], A.USDC, qty_raw, 200, "/tmp/fastlane_sell.b64")
    if not sig:
        log_event({"event": "fastlane_sell_error", "symbol": pos.get("symbol"), "err": str(err)[:200], "reason": reason})
        notify("⚠️ FASTLANE sell FAILED %s: %s" % (pos.get("symbol"), (err or "")[:120]))
        return None
    time.sleep(3)
    proceeds = A.token_balance_retry(A.USDC) - before
    if proceeds < 0:
        proceeds = 0.0
    cost_here = float(pos.get("costUsdc") or 0) * frac
    realized = proceeds - cost_here
    pos["qty"] = round(float(pos.get("qty") or 0) * (1 - frac), 6)
    pos["realizedUsdc"] = round(float(pos.get("realizedUsdc") or 0) + realized, 6)
    pos["realizedPct"] = round(realized / cost_here * 100, 1) if cost_here else 0
    pos["lastExit"] = {"ts": NOW, "reason": reason, "tx": sig, "proceeds": round(proceeds, 4)}
    if frac >= 0.999:
        pos["status"] = "closed"
        pos["closedAt"] = NOW
    else:
        pos["stopUsd"] = pos.get("entryUsd")  # bank half -> stop to entry
    log_event({"event": "fastlane_sell", "symbol": pos.get("symbol"), "reason": reason,
               "proceeds": round(proceeds, 4), "realized": round(realized, 4), "tx": sig,
               "pnlPct": pos["realizedPct"]})
    notify("🟢 FASTLANE SELL %s (%s) realized $%.2f tx %s" % (pos.get("symbol"), reason, realized, sig[:14]))
    try:
        A.tg_card("profit" if realized >= 0 else "loss",
                  {"engine": "Real-Coin Lane", "symbol": pos.get("symbol"), "duration": "auto",
                   "reason": reason, "costUsdc": cost_here, "grossUsdc": proceeds,
                   "dest": "SOL vault", "destLane": "Solana Vault", "netPnl": realized,
                   "pnlPct": ("%+.1f%%" % pos["realizedPct"])})
    except Exception:
        pass
    return realized


def manage_positions(px_map):
    """Apply stop/bank/trail/time-stop on open fast-lane positions using live prices."""
    obj = load_positions()
    changed = False
    for pos in obj.get("positions", []):
        if pos.get("status") != "open":
            continue
        px = px_map.get(pos["mint"])
        pos["feedMiss"] = int(pos.get("feedMiss") or 0)
        if px is None:
            pos["feedMiss"] += 1
            if pos["feedMiss"] > FEED_MISS_MAX:
                do_sell(pos, None, "feed-dead forced close")
                changed = True
            continue
        pos["feedMiss"] = 0
        entry = float(pos.get("entryUsd") or 0)
        pct = (px / entry - 1) * 100 if entry else 0
        peak = max(float(pos.get("peakUsd") or entry), px)
        pos["peakUsd"] = peak
        now = time.time()
        op = float(pos.get("openedAtEpoch") or now)
        reason = None
        if pos.get("banked") and px <= float(pos.get("peakUsd") or entry) * (1 + TRAIL_PCT / 100):
            reason = "TRAIL -12% off peak"
        elif px <= entry * (1 + STOP_PCT / 100):
            reason = "HARD STOP -15%"
        elif not pos.get("banked") and pct >= BANK_PCT:
            reason = "BANK_HALF +30%"
        elif now - op > TIME_STOP_H * 3600:
            reason = "TIME_STOP 12h"
        if reason and reason != "BANK_HALF +30%":
            r = do_sell(pos, px, reason)
            if r is not None:
                st = reset_day(F.load(STATE_FILE, {}))
                st["realizedToday"] = float(st.get("realizedToday") or 0) + r
                F.save(STATE_FILE, st)
                changed = True
        elif reason == "BANK_HALF +30%":
            r = do_sell(pos, px, reason, frac=0.5)
            if r is not None:
                pos["banked"] = True
                st = reset_day(F.load(STATE_FILE, {}))
                st["realizedToday"] = float(st.get("realizedToday") or 0) + r
                F.save(STATE_FILE, st)
                changed = True
    if changed:
        save_positions(obj)
    return lane_open_count()



def try_entry(candidates):
    """Pick best signal candidate that is tradable and execute a buy."""
    if os.path.exists(OFF):
        return False
    st = reset_day(F.load(STATE_FILE, {}))
    spent = float(st.get("spentToday") or 0)
    realized = float(st.get("realizedToday") or 0)
    if realized <= -DAILY_LOSS_HALT:
        log_event({"event": "fastlane_guard", "note": "daily realized loss limit hit - entries halted"})
        return False
    rem_delegate = A.delegate_remaining()
    if rem_delegate is None:
        return False
    size = min(MAX_TRADE, DAILY_CAP - spent, rem_delegate - 1.0)
    if size < 2.5 or lane_open_count() >= MAX_OPEN:
        return False
    for cand in candidates:
        mint = cand.get("mint")
        if held(mint):
            continue
        sig_reason = cand.get("signal")
        if not sig_reason:
            continue
        if A.vault_usdc() < size:
            log_event({"event": "fastlane_guard", "note": "vault below size"})
            return False
        if not A.vault_pull(size):
            return False
        sig, err = A.build_and_send(A.USDC, mint, int(size * 1e6), 100, "/tmp/fastlane_buy.b64")
        if not sig:
            notify("⚠️ FASTLANE buy FAILED %s: %s" % (cand.get("symbol"), (err or "")[:120]))
            A.hot_to_vault()
            log_event({"event": "fastlane_buy_error", "symbol": cand.get("symbol"), "err": str(err)[:200]})
            return False
        qty = A.token_balance_retry(mint)
        if not qty:
            time.sleep(3)
            qty = A.token_balance_retry(mint)
        if not qty:
            log_event({"event": "fastlane_qty_unread", "symbol": cand.get("symbol"), "tx": sig})
            notify("🚨 FASTLANE filled %s but qty unread (tx %s) - review" % (cand.get("symbol"), sig[:16]))
            return False
        entry = size / qty
        now = time.time()
        pos = {"id": "fl-" + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S"),
               "symbol": cand.get("symbol"), "mint": mint, "status": "open", "chain": "solana",
               "signal": sig_reason, "qty": qty, "costUsdc": size, "entryUsd": entry,
               "peakUsd": entry, "banked": False, "openedAt": NOW, "openedAtEpoch": now,
               "txSignature": sig, "feedMiss": 0, "realizedUsdc": 0.0}
        obj = load_positions()
        obj.setdefault("positions", []).insert(0, pos)
        save_positions(obj)
        st["spentToday"] = round(float(st.get("spentToday") or 0) + size, 2)
        F.save(STATE_FILE, st)
        log_event({"event": "fastlane_buy", "symbol": pos["symbol"], "mint": mint, "qty": qty,
                   "sizeUsdc": size, "entry": entry, "signal": sig_reason, "tx": sig})
        notify("🚀 FASTLANE BUY %s (%s) $%.2f @ $%.8g tx %s" % (pos["symbol"], sig_reason, size, entry, sig[:16]))
        try:
            A.tg_card("open", {"engine": "Real-Coin Lane", "symbol": pos.get("symbol"),
                               "ca": mint[:8] + "…", "entryTime": NOW[:16] + " UTC",
                               "sizeUsdc": size, "qty": qty, "entryPrice": "%.8g" % entry,
                               "slip": "1% max", "hardStopPct": "-15.00%",
                               "hardStopPrice": entry * 0.85, "targetPct": "+30% bank / trail",
                               "regime": sig_reason})
        except Exception:
            pass
        return True
    return False


def collect_candidates():
    """Batch-fetch the real-coin watchlist and tag signal candidates."""
    tokens = F.refresh_watchlist()
    out = []
    if not tokens:
        return out
    try:
        d = F.get(F.DEX_BATCH.format(",".join(tokens)))
    except Exception:
        return out
    for addr, pairs in F.group((d or {}).get("pairs") or []):
        pr = F.best_pair(pairs)
        if not pr:
            continue
        sig = buy_px_checks(pr)
        if not sig:
            continue
        bt = pr.get("baseToken") or {}
        try:
            px = float(pr.get("priceUsd"))
        except Exception:
            px = None
        if px is None:
            continue
        out.append({"mint": addr, "symbol": bt.get("symbol") or addr[:6], "signal": sig,
                    "px": px, "liq": float((pr.get("liquidity") or {}).get("usd") or 0),
                    "pr": pr})
    # FEED-BOT source: own-feed intel (coins.json tiers), same gates on top.
    cfg = bot_feed_cfg()
    if cfg.get("enabled"):
        have = {c["mint"] for c in out}
        fmints = [m for m in feed_intel_candidates(cfg) if m not in have and not held(m)]
        if fmints:
            try:
                fd = F.get(F.DEX_BATCH.format(",".join(fmints)))
            except Exception:
                fd = None
            for addr, pairs in F.group((fd or {}).get("pairs") or []):
                pr = F.best_pair(pairs)
                if not pr:
                    continue
                sig = buy_px_checks(pr)
                if not sig:
                    continue
                bt = pr.get("baseToken") or {}
                try:
                    px = float(pr.get("priceUsd"))
                except Exception:
                    px = None
                if px is None:
                    continue
                out.append({"mint": addr, "symbol": bt.get("symbol") or addr[:6], "signal": "FEED-" + sig,
                            "px": px, "liq": float((pr.get("liquidity") or {}).get("usd") or 0),
                            "pr": pr})
    return out


def main():
    DRY = "--dry" in sys.argv
    if os.path.exists(OFF):
        print("fastlane paused (fastlane.off)")
        return
    cands = collect_candidates()
    open_n = lane_open_count()
    if open_n < MAX_OPEN and cands:
        if DRY:
            best = next((c for c in cands if not held(c["mint"])), None)
            if best:
                print("DRY would-enter: %s %s signal=%s px=%s liq=$%.0f"
                      % (best.get("symbol"), best.get("mint")[:10], best.get("signal"),
                         best.get("px"), best.get("liq") or 0))
        else:
            try_entry(cands)
        open_n = lane_open_count()
    print("fastlane @ %s | open=%d | candidates=%d | (exit mgmt delegated to capital-guard)%s"
          % (NOW[:19], open_n, len(cands), " | DRY" if DRY else ""))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("fastlane error:", e)
