#!/usr/bin/env python3
"""capital-guard.py — REAL-TIME CAPITAL GUARDIAN (boss 2026-09-04, post-STOCKCAT).

Runs every 30s after fastlane. SINGLE OWNER of all exits/monitoring for open
real-coin positions. Multi-source pricing; if a price can't be found for ~60s the
position is FORCE-CLOSED (the STOCKCAT rule). If an exit won't fill, it retries and
ESCALATES. Sends Telegram + board alerts the moment anything trips.

Config (teeth of the guard):
  STOP_PCT      -15   hard stop (fills on liquid coins)
  BANK_PCT      +30   sell half at +30%, then stop = entry
  TRAIL_PCT     -12   trail off peak after bank
  TIME_STOP_H   12    force flat
  FEED_MISS_MAX 2     passes (~60s) without any price -> forced close
  SELL_RETRY    3     exit attempts before ACTION-REQUIRED escalation
  WARN_PCT      -10   one-time Telegram warning approaching the stop
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
import fastlane as FL
import autopilot as A

STOP_PCT = -15.0
BANK_PCT = 30.0
TRAIL_PCT = -12.0
TIME_STOP_H = 12.0
FEED_MISS_MAX = 2
SELL_RETRY = 3
WARN_PCT = -10.0
WATCH_FILE = os.path.join(ROOT, "data", "live", "fast-watchlist.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def log_event(rec):
    rec["ts"] = NOW
    with open(os.path.join(ROOT, "logs", "trades.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def notify(text):
    try:
        import subprocess
        subprocess.run(["python3", os.path.join(ROOT, "scripts", "notify-telegram.py"),
                        "msg", text], timeout=20)
    except Exception:
        pass


def board_escalate(msg):
    try:
        import subprocess
        subprocess.run(["python3", os.path.join(ROOT, "scripts", "team_ops.py"),
                        "post", "--from", "guard", "--to", "boss", "--msg", msg], timeout=20)
    except Exception:
        pass


def price_sources(mint):
    """Multi-source price: DexScreener token endpoint, then Jupiter price v2."""
    try:
        d = F.get("https://api.dexscreener.com/latest/dex/tokens/" + mint)
        pr = F.best_pair((d or {}).get("pairs"))
        if pr:
            return float(pr.get("priceUsd"))
    except Exception:
        pass
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.jup.ag/price/v2?ids=" + mint,
            headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read())
        p = ((d.get("data") or {}).get(mint) or {}).get("price")
        if p:
            return float(p)
    except Exception:
        pass
    return None


def fetch_batch_px():
    """Batch DexScreener prices for the whole watchlist (primary source)."""
    px = {}
    try:
        tokens = F.load(WATCH_FILE, {}).get("tokens", [])
        d = F.get(F.DEX_BATCH.format(",".join(tokens)))
        for addr, pairs in F.group((d or {}).get("pairs") or []):
            pr = F.best_pair(pairs)
            if pr:
                try:
                    px[addr] = float(pr.get("priceUsd"))
                except Exception:
                    pass
    except Exception:
        pass
    return px

def guard_positions():
    """Manage every open real-coin position. Returns (open_count, acted)."""
    obj = FL.load_positions()
    px_map = fetch_batch_px()
    st = FL.reset_day(F.load(FL.STATE_FILE, {}))
    acted = False
    for pos in obj.get("positions", []):
        if pos.get("status") != "open":
            continue
        mint = pos.get("mint")
        sym = pos.get("symbol")
        pos.setdefault("failCount", 0)
        pos.setdefault("feedMiss", 0)
        px = px_map.get(mint)
        if px is None:  # fallback source, then forced-close path
            px = price_sources(mint)
        if px is None:
            pos["feedMiss"] = int(pos.get("feedMiss") or 0) + 1
            last = float(pos.get("lastSeen") or pos.get("openedAtEpoch") or 0)
            if pos["feedMiss"] >= FEED_MISS_MAX or (time.time() - last) > 90:
                r = FL.do_sell(pos, None, "feed-dead forced close")
                if r is None:
                    pos["failCount"] = int(pos.get("failCount") or 0) + 1
                    if pos["failCount"] >= SELL_RETRY:
                        notify("🚨 ACTION REQUIRED: feed-dead close FAILED for %s (%s) - manual review" % (sym, mint[:10]))
                        board_escalate("ACTION REQUIRED: capital guard cannot close %s (%s) - feed dead, sell failing" % (sym, mint[:10]))
                        log_event({"event": "capital_guard_escalation", "symbol": sym, "mint": mint, "why": "feed-dead close failed"})
                else:
                    st["realizedToday"] = float(st.get("realizedToday") or 0) + r
                    acted = True
                    log_event({"event": "capital_guard_forced_close", "symbol": sym, "mint": mint, "realized": round(r, 4)})
            continue
        pos["feedMiss"] = 0
        pos["lastSeen"] = time.time()
        entry = float(pos.get("entryUsd") or 0)
        stop = float(pos.get("stopUsd") or 0) or entry * (1 + STOP_PCT / 100)
        peak = max(float(pos.get("peakUsd") or entry), px)
        pos["peakUsd"] = peak
        pct = (px / entry - 1) * 100 if entry else 0
        if pct <= WARN_PCT and not pos.get("warned"):
            pos["warned"] = True
            notify("⚠️ CAPITAL GUARD: %s mark %+.1f%% (approaching %s%% stop) px=$%.8g" % (sym, pct, STOP_PCT, px))
        reason = None
        frac = 1.0
        if px <= stop:
            reason = "HARD STOP %.0f%%" % STOP_PCT
        elif not pos.get("banked") and pct >= BANK_PCT:
            reason = "BANK_HALF +%d%%" % int(BANK_PCT)
            frac = 0.5
        elif pos.get("banked") and px <= peak * (1 + TRAIL_PCT / 100):
            reason = "TRAIL %.0f%% off peak" % TRAIL_PCT
        elif time.time() - float(pos.get("openedAtEpoch") or 0) > TIME_STOP_H * 3600:
            reason = "TIME_STOP %.0fh" % TIME_STOP_H
        if not reason:
            continue
        r = FL.do_sell(pos, px, reason, frac=frac)
        if r is None:
            pos["failCount"] = int(pos.get("failCount") or 0) + 1
            if pos["failCount"] >= SELL_RETRY:
                notify("🚨 ACTION REQUIRED: %s exit FAILED (%s) %d tries - manual review" % (sym, reason, SELL_RETRY))
                board_escalate("ACTION REQUIRED: exit failing for %s (%s) reason %s" % (sym, mint[:10], reason))
                log_event({"event": "capital_guard_escalation", "symbol": sym, "mint": mint, "why": reason})
        else:
            pos["failCount"] = 0
            if frac < 1.0:
                pos["banked"] = True
                pos["stopUsd"] = entry
            st["realizedToday"] = float(st.get("realizedToday") or 0) + r
            acted = True
    FL.save_positions(obj)
    F.save(FL.STATE_FILE, st)
    return FL.lane_open_count(), acted


def main():
    open_n, acted = guard_positions()
    print("capital-guard @ %s | open=%d | acted=%s" % (NOW[:19], open_n, acted))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("capital-guard error:", e)
        log_event({"event": "capital_guard_error", "err": str(e)[:200]})

