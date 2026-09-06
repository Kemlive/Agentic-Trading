#!/usr/bin/env python3
"""Autopilot v1 - keeps capital working while the boss is away.
Runs via launchd (com.agentic-trading.autopilot) every ~45 min while the Mac is ON.

CONSERVATIVE RAILS (v1):
- max 1 open live position at a time, size $1.50
- buy ONLY if: clean flags, liq >= $15k, fdv $30-150k, age > 0.15h, m5 buys:sells >= 1.3
- sell via snatcher rules (bank/trail/stop/time) using live behavior
- reserve: never let USDC fall below $15; daily loss guard -10% stops the autopilot
- every action -> Telegram + logs/trades.jsonl
Off switch: create data/live/autopilot.off (any content) -> exits silently.
"""
import json, os, sys, glob, time, datetime, subprocess, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "data", "live", "autopilot.json")
HOLD = os.path.join(ROOT, "data", "live", "holdings.json")
OFF = os.path.join(ROOT, "data", "live", "autopilot.off")
SIGNER = os.path.expanduser("~/.local/share/solagent-signer")
WALLET = "GHojAXGEY8DrcDNTjCJcA5hjNt5NBXS4j2dfsxsJKxJM"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
DAY_START = 20.3357
SIZE_USDC = 2.5
RESERVE_MIN = 12.0
MAX_OPEN = 2

# VAULT-CAP TRADING (boss 2026-09-04, pilot PASSED): vault 8ZGuiQZ owns the USDC
# reserve; the agent hot wallet only spends under the SPL delegate cap (on-chain
# allowance). Flow per cycle: pull exact trade size vault->hot (delegate), swap,
# auto push-back proceeds hot->vault. Set VAULT_MODE=0 to fall back to hot-owned cash.
VAULT = "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4"
VAULT_USDC_ACC = "GRiCEHnTyfNHKvCXpkcxqHwHmkFFxhHz5Yjhq4MxGJK8"  # vault USDC token account
HOT_USDC_ACC = "BcapBLNuagcBXo5UWUC5zxYumAEQAWDXtU1ssQWLiQRj"    # hot wallet USDC token account
VAULT_MODE = os.getenv("VAULT_MODE", "1") == "1"
HOT_KEEP_USDC = 0.10  # tiny hot buffer; everything else lives in the vault

# Market PHASE entry tactics (Meme Profit Snatcher - auto-switch, NOT CEX rules).
# Autopilot mirrors the scanner's SNATCHER_PHASES. Single source of truth: the latest
# pump-scan file carries regime.bar; the label->phase map below is only the fallback.
PHASE_LABELS = {"Extreme Fear": "bear", "Fear": "bear", "Neutral": "neutral",
                "Greed": "bull", "Extreme Greed": "bull"}
SNATCHER_FLOORS = {
    "bear":    {"minFdv": 40000, "minLiq": 15000, "minVol": 15000, "minAge": 0.35, "maxAge": 24.0,
                "maxH1": 120, "maxH6": 300, "maxH24": 800, "bsMin": 1.2, "m5Max": 0.0, "mode": "BEAR_SNATCH"},
    "neutral": {"minFdv": 40000, "minLiq": 20000, "minVol": 20000, "minAge": 0.25, "maxAge": 8.0,
                "maxH1": 100, "maxH6": 200, "maxH24": 500, "bsMin": 0.0, "m5Max": 0.0, "mode": "NEUTRAL_SNATCH"},
    "bull":    {"minFdv": 45000, "minLiq": 25000, "minVol": 25000, "minAge": 0.5, "maxAge": 8.0,
                "maxH1": 80, "maxH6": 150, "maxH24": 400, "bsMin": 1.1, "m5Max": 0.0, "mode": "BULL_SNATCH"},
}
# DRY-TAPE RELIEF: after 5 consecutive scans with no clean entry we widen age +
# thin-liq tolerance and allow a hair of green (+2% m5) so a slow tape can never
# silence the desk for hours again. Never sub-$40k FDV, never a real top.
RELIEF_BAR = {"minFdv": 40000, "minLiq": 12000, "minVol": 12000, "minAge": 0.1, "maxAge": 24.0,
              "maxH1": 120, "maxH6": 300, "maxH24": 800, "bsMin": 0.0, "m5Max": 2.0, "mode": "RELIEF"}
_BAR = dict(SNATCHER_FLOORS["neutral"])


def load_regime_bar():
    """Sync the phase tactic from the latest scanner file (regime.bar is the single
    source of truth). Falls back to the label->phase map, then to neutral."""
    global _BAR
    try:
        files = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
        reg = (json.load(open(files[-1])) or {}).get("regime") or {}
        bar = reg.get("bar")
        if bar:
            _BAR = dict(SNATCHER_FLOORS.get(reg.get("phase") or "neutral", SNATCHER_FLOORS["neutral"]))
            _BAR.update({k: bar[k] for k in bar if k != "mode"})
            _BAR["mode"] = reg.get("mode") or _BAR.get("mode")
        else:  # old scan files w/o bar meta -> map by label
            phase = PHASE_LABELS.get(reg.get("label") or "Neutral", "neutral")
            _BAR = dict(SNATCHER_FLOORS[phase])
    except Exception:
        _BAR = dict(SNATCHER_FLOORS["neutral"])


def tg(text):
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "notify-telegram.py"), "msg", text],
                   capture_output=True, timeout=40)


def tg_card(kind, payload):
    """Send a rich card (open/profit/loss) via notify-telegram.py (best-effort)."""
    try:
        with open("/tmp/autopilot_card.json", "w") as f:
            json.dump(payload, f)
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "notify-telegram.py"),
                        "card", kind, "/tmp/autopilot_card.json"],
                       capture_output=True, timeout=40)
    except Exception:
        pass


def _iso_secs(iso):
    """Seconds since epoch for an ISO-8601 UTC ts (best-effort)."""
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def atomic_write(path, obj):
    """Crash-safe state write: tmp file + atomic rename (no truncation on races)."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def log(rec):
    rec["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(os.path.join(ROOT, "logs", "trades.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def rpc(method, params):
    key = open(os.path.expanduser("~/.config/agentic-trading/helius.key")).read().strip()
    req = urllib.request.Request("https://mainnet.helius-rpc.com/?api-key=" + key,
                                 data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def balances():
    sol = (rpc("getBalance", [WALLET]).get("result") or {}).get("value", 0) / 1e9
    usdc = 0.0
    tb = rpc("getTokenAccountsByOwner", [WALLET, {"mint": USDC}, {"encoding": "jsonParsed"}])
    for a in ((tb.get("result") or {}).get("value") or []):
        usdc += (a.get("account", {}).get("data", {}).get("parsed", {}).get("info", {}).get("tokenAmount", {}) or {}).get("uiAmount") or 0
    return sol, usdc


def token_balance(mint):
    tb = rpc("getTokenAccountsByOwner", [WALLET, {"mint": mint}, {"encoding": "jsonParsed"}])
    for a in ((tb.get("result") or {}).get("value") or []):
        return (a.get("account", {}).get("data", {}).get("parsed", {}).get("info", {}).get("tokenAmount", {}) or {}).get("uiAmount") or 0
    return 0.0


def token_balance_retry(mint, tries=6, wait=2.0):
    """Poll the post-buy token balance; the ATA can lag a few seconds after the swap."""
    for _ in range(tries):
        b = token_balance(mint)
        if b and b > 0:
            return b
        time.sleep(wait)
    return token_balance(mint)


def spl_transfer(src_ata, dst_ata, amount_micros, outfile):
    """Build a plain SPL USDC transfer (src->dst, authority/signer = agent hot key),
    sign via solagent-signer, broadcast. Works for delegate pulls (src owned by vault)
    and owner pushes (src owned by hot). Returns sig or None."""
    node = "/opt/homebrew/opt/node@20/bin/node"
    env = dict(os.environ)
    env["PATH"] = "/opt/homebrew/opt/node@20/bin:" + env.get("PATH", "")
    b = subprocess.run([node, os.path.join(SIGNER, "spl-transfer.cjs"), src_ata, dst_ata,
                        str(amount_micros), outfile],
                       cwd=SIGNER, capture_output=True, text=True, timeout=60, env=env)
    if b.returncode != 0:
        return None
    return exec_tx(outfile)


def vault_usdc():
    """USDC balance inside the vault token account (vault is the reserve owner)."""
    try:
        r = rpc("getAccountInfo", [VAULT_USDC_ACC, {"encoding": "jsonParsed"}])
        a = (r.get("result") or {}).get("value")
        if not a:
            return 0.0
        return float(a["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
    except Exception:
        return 0.0


def delegate_remaining():
    """Remaining SPL delegated allowance on the vault USDC account (None if no cap)."""
    try:
        r = rpc("getAccountInfo", [VAULT_USDC_ACC, {"encoding": "jsonParsed"}])
        a = (r.get("result") or {}).get("value")
        if not a:
            return None
        info = a["data"]["parsed"]["info"]
        da = info.get("delegatedAmount") or {}
        if not info.get("delegate"):
            return None
        return float(da.get("uiAmount") or 0)
    except Exception:
        return None


def vault_pull(usd):
    """Pull exactly `usd` from the vault into the hot wallet under the delegate cap."""
    micros = int(round(usd * 1e6))
    rem = delegate_remaining()
    vault = vault_usdc()
    if rem is None:
        tg("🚫 VAULT: delegate cap not set - approve via safe/solana-delegate-approve.html")
        return False
    if rem < usd:
        tg("⛔ VAULT CAP: remaining $%.2f < pull $%.2f - boss: top up the delegate cap" % (rem, usd))
        return False
    if vault < usd:
        tg("⛔ VAULT: balance $%.2f < pull $%.2f" % (vault, usd))
        return False
    sig = spl_transfer(VAULT_USDC_ACC, HOT_USDC_ACC, micros, "/tmp/vault_pull.b64")
    if not sig:
        tg("⚠️ VAULT PULL FAILED - buy skipped")
        return False
    log({"event": "vault_pull", "amountUsdc": round(usd, 4), "tx": sig})
    tg("🏦 VAULT PULL $%.2f vault->hot tx %s (cap rem ~$%.2f)" % (usd, sig[:12], rem - usd))
    return True


def hot_to_vault(usd=None):
    """Push hot USDC back to the vault (default: everything above the tiny buffer)."""
    bal = token_balance(USDC)
    amt = min(bal, usd) if usd else max(0.0, bal - HOT_KEEP_USDC)
    if amt < 0.01:
        return None
    sig = spl_transfer(HOT_USDC_ACC, VAULT_USDC_ACC, int(round(amt * 1e6)), "/tmp/hot_push.b64")
    if sig:
        log({"event": "vault_push", "amountUsdc": round(amt, 6), "tx": sig})
        tg("🏦 VAULT PUSH hot->vault $%.2f tx %s" % (amt, sig[:12]))
    return sig


def exec_tx(outfile):
    node = "/opt/homebrew/opt/node@20/bin/node"
    env = dict(os.environ)
    env["PATH"] = "/opt/homebrew/opt/node@20/bin:" + env.get("PATH", "")
    r = subprocess.run([node, os.path.join(SIGNER, "sign-broadcast.cjs"), outfile,
                        "https://api.mainnet-beta.solana.com"],
                       cwd=SIGNER, capture_output=True, text=True, timeout=120, env=env)
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("TX_SIGNATURE"):
            return ln.split()[-1]
    return None


def build_and_send(inmint, outmint, amount_raw, slip, txfile):
    node = "/opt/homebrew/opt/node@20/bin/node"
    env = dict(os.environ)
    env["PATH"] = "/opt/homebrew/opt/node@20/bin:" + env.get("PATH", "")
    b = subprocess.run([node, os.path.join(SIGNER, "jup-swap.cjs"), inmint, outmint,
                        str(amount_raw), str(slip), txfile],
                       cwd=SIGNER, capture_output=True, text=True, timeout=60, env=env)
    if b.returncode != 0:
        return None, (b.stderr or b.stdout or "")[:300]
    return exec_tx(txfile), None


def pair_live(mint):
    req = urllib.request.Request("https://api.dexscreener.com/latest/dex/tokens/" + mint,
                                 headers={"User-Agent": "agentic-trading/0.1"})
    d = json.loads(urllib.request.urlopen(req, timeout=12).read())
    best = None
    for p in d.get("pairs") or []:
        if p.get("chainId") != "solana":
            continue
        try:
            v = float((p.get("liquidity") or {}).get("usd") or 0)
        except Exception:
            v = 0
        if best is None or v > best[0]:
            best = (v, p)
    return best[1] if best else None


def snatcher_decision(pos):
    pr = pair_live(pos["mint"])
    if not pr:
        return None
    st = {}
    if os.path.exists(STATE):
        st = json.load(open(STATE))
    pid = pos.get("id") or pos.get("mint") or "?"
    peaks = st.setdefault("peaks", {})
    price = float(pr["priceUsd"])
    entry = float(pos.get("entryImpliedUsd") or 0)
    pct = (price / entry - 1) * 100 if entry else 0
    peak = max(peaks.get(pid, 0), price)
    peaks[pid] = peak
    atomic_write(STATE, st)
    txn = pr.get("txns") or {}
    chg = pr.get("priceChange") or {}
    try:
        b5 = (txn.get("m5") or {}).get("buys") or 0
        s5 = (txn.get("m5") or {}).get("sells") or 0
    except Exception:
        b5 = s5 = 0
    bp = (b5 / s5) if s5 else (999 if b5 else None)
    age_h = None
    try:
        age_h = (datetime.datetime.now(datetime.timezone.utc) -
                 datetime.datetime.fromisoformat(pos["openedAt"])).total_seconds() / 3600.0
    except Exception:
        pass
    if price <= entry * 0.70:
        return {"action": "SELL_ALL", "reason": "hard stop -30%", "price": price, "pct": pct}
    if age_h and age_h >= 24:
        return {"action": "SELL_ALL", "reason": "time stop 24h", "price": price, "pct": pct}
    if pct >= 30 and (chg.get("m5") or 0) <= 0:
        return {"action": "SELL_ALL", "reason": "bank: +%.0f%% & momentum fading" % pct, "price": price, "pct": pct}
    if pct >= 5 and price <= peak * 0.85:
        return {"action": "SELL_ALL", "reason": "trail: -15%% off peak", "price": price, "pct": pct}
    return {"action": "HOLD", "reason": "momentum %s" % ("OK" if (bp or 0) >= 1 else "watching"), "price": price, "pct": pct}


def gecko_check(mint):
    """Independent cross-check via GeckoTerminal. Returns {} if unavailable/not found."""
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gecko-feed.py"), mint],
                           capture_output=True, text=True, timeout=25)
        d = json.loads((r.stdout or "{}"))
    except Exception:
        return {}
    if not d.get("gecko_found"):
        return {}
    return d


def latest_scan_candidates():
    files = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
    if not files:
        return []
    return json.load(open(files[-1])).get("candidates", [])


def eligible(c, bar=None):
    """Phase-tactic gate. bar = the ACTIVE snatcher tactic (bear/neutral/bull/relief),
    so the same code switches behavior with the market. Never-buy-real-tops holds via
    h1/h6/h24 caps; chasing holds via m5 cap (relief allows a hair of green)."""
    bar = bar or _BAR
    flags = c.get("flags") or []
    if flags:
        return False
    def f(x):
        try:
            if x is None:
                return 0.0
            return float(str(x).replace(",", "").replace(" ", ""))
        except Exception:
            return 0.0
    liq, fdv, age, m5, h1, h6, h24, v24, px, bs = (f(c.get("liqUsd")), f(c.get("fdv")), f(c.get("ageH")),
                                                   f(c.get("chg_m5")), f(c.get("chg_h1")), f(c.get("chg_h6")),
                                                   f(c.get("chg_h24")), f(c.get("vol_h24")), f(c.get("priceUsd")),
                                                   f(c.get("buy_sell_h1")))
    if fdv < bar.get("minFdv", 40000):
        return False
    if liq < bar.get("minLiq", 20000):
        return False
    if v24 < bar.get("minVol", 20000):
        return False
    if not (bar.get("minAge", 0.25) <= age <= bar.get("maxAge", 8.0)):
        return False
    if m5 > bar.get("m5Max", 0.0):      # chasing (relief allows small green on dry tapes)
        return False
    if h1 <= 0 or h1 > bar.get("maxH1", 100):  # no uptrend, or already vertical
        return False
    if h6 > bar.get("maxH6", 200) or h24 > bar.get("maxH24", 500):  # ran too far = top risk
        return False
    if bar.get("bsMin", 0.0) > 0 and c.get("buy_sell_h1") is not None and bs < bar["bsMin"]:
        return False  # bear/bull demand BUYER SUPPORT during the dip
    return px > 0


def save_position(pos):
    h = json.load(open(HOLD))
    h["positions"].insert(0, pos)
    h["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    atomic_write(HOLD, h)


def prune_banned(banned):
    """Drop expired mint bans. banned: {mint: untilUnix}."""
    now = time.time()
    out = {}
    for m, until in (banned or {}).items():
        try:
            if float(until) > now:
                out[str(m)] = float(until)
        except Exception:
            continue
    return out


def blocked_mints(holdings=None, banned=None):
    """Mints we must not re-enter: open + recent closes + explicit bans."""
    blocked = set()
    now = time.time()
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        h = holdings if holdings is not None else json.load(open(HOLD))
    except Exception:
        h = {"positions": []}
    for p in (h.get("positions") or []):
        mint = str(p.get("mint") or p.get("token") or "").strip()
        if not mint:
            continue
        st = str(p.get("status", "open")).lower()
        if st == "open":
            blocked.add(mint)
            continue
        if st != "closed":
            continue
        closed = str(p.get("closedAt") or "")
        ts = _iso_secs(closed)
        if ts is not None and (now - ts) < 24 * 3600:
            blocked.add(mint)
        try:
            realized = float(p.get("realizedUsdc") or p.get("realizedUsd") or 0)
        except Exception:
            realized = 0.0
        if closed[:10] == today and realized < 0:
            blocked.add(mint)
    for m, until in (banned or {}).items():
        try:
            if float(until) > now:
                blocked.add(str(m))
        except Exception:
            continue
    return blocked


def ban_mint(prev, mint, hours=24.0, reason=""):
    """Record a durable mint ban in autopilot state."""
    if not mint:
        return prev
    banned = prune_banned(prev.get("bannedMints") or {})
    until = time.time() + float(hours) * 3600.0
    prev_until = float(banned.get(mint) or 0)
    banned[mint] = max(prev_until, until)
    prev["bannedMints"] = banned
    log({"event": "mint_banned", "mint": mint, "hours": hours, "reason": reason, "until": until})
    return prev


def rank_key(c, tried_set, blocked_set):
    """Higher liq first; deprioritize tried/blocked."""
    mint = str(c.get("token") or "")
    liq = float(c.get("liqUsd") or 0)
    penalty = 0.0
    if mint in tried_set:
        penalty += 1e12
    if mint in blocked_set:
        penalty += 1e15
    return (penalty, -liq)


def main():
    if os.path.exists(OFF):
        return 0
    sol, usdc = balances()
    # VAULT MODE (boss 2026-09-04): the vault owns the reserve; the hot wallet only
    # spends under the delegate cap. Consolidate idle hot USDC into the vault first.
    vault = 0.0
    if VAULT_MODE:
        vault = vault_usdc() or 0.0
        if usdc > HOT_KEEP_USDC + 0.5:
            pb = hot_to_vault()
            if pb:
                sol, usdc = balances()
                vault = vault_usdc() or 0.0
    cash_total = usdc + vault          # owner basis = hot + vault (reserve for guards)
    cash_disp = cash_total if VAULT_MODE else usdc

    # daily loss guard (EQUITY-based: reserve incl. vault + open positions at market)
    def equity_now(u, s):
        eq = cash_total + s * 100.0
        try:
            hq = json.load(open(HOLD))
        except Exception:
            return eq
        for pos in hq.get("positions", []):
            if pos.get("status") != "open" or not (pos.get("qty") or 0):
                continue
            try:
                pr = pair_live(pos["mint"])
                if pr:
                    eq += float(pos.get("qty") or 0) * float(pr["priceUsd"])
            except Exception:
                pass
        return eq

    try:
        prev = json.load(open(STATE))
    except Exception:
        prev = {}
    if not prev.get("day"):
        prev = {"day": datetime.date.today().isoformat(), "dayStartEquity": equity_now(usdc, sol), "peak": 0}
    if prev["day"] != datetime.date.today().isoformat():
        prev = {"day": datetime.date.today().isoformat(), "dayStartEquity": equity_now(usdc, sol), "peak": 0}
    if not prev.get("dayStartEquity"):
        prev["dayStartEquity"] = equity_now(usdc, sol)
    prev.setdefault("lossStreak", 0)
    prev.setdefault("cooldownUntil", 0)
    if prev.get("dayStartEquity") and (equity_now(usdc, sol) - prev["dayStartEquity"]) / prev["dayStartEquity"] <= -0.10:
        open(OFF, "w").write("daily loss guard")
        tg("⛔ AUTO PAUSED: daily loss guard (<= -10%%). Equity $%.2f" % equity_now(usdc, sol))
        return 0
    atomic_write(STATE, prev)
    h = json.load(open(HOLD))
    opens = [p for p in h.get("positions", []) if p["status"] == "open"]
    # 1) manage ALL open positions - each exits on its own snatcher triggers (independent peaks)
    for pos in opens:
        try:
            dec = snatcher_decision(pos)
        except Exception as e:
            continue
        if not dec or dec["action"] != "SELL_ALL":
            continue
        qty_raw = int(float(pos.get("qty") or 0) * 1e6)
        if qty_raw <= 0:
            pos["status"] = "closed"
            pos["closedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            pos["closeReason"] = "autopilot:dust_zero_qty"
            prev = ban_mint(prev, pos.get("mint") or "", hours=24.0, reason="dust_zero_qty")
            atomic_write(STATE, prev)
            atomic_write(HOLD, h)
            continue
        usdc_before_sell = token_balance(USDC)
        sig, err = build_and_send(pos["mint"], USDC, qty_raw, 1000, "/tmp/auto_sell.b64")
        if sig:
            pos["status"] = "closed"
            pos["closedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cost = float(pos.get("costUsdc") or 0)
            proceeds = token_balance(USDC) - usdc_before_sell
            realized = proceeds - cost
            pos["realizedUsdc"] = round(realized, 6)
            pos["realizedPct"] = round(realized / cost * 100, 1) if cost else None
            pos["closeReason"] = "autopilot:" + dec["reason"]
            # honest streak + circuit breaker: 2 straight losing closes -> 6h entry cooldown
            if realized < 0:
                prev["lossStreak"] = prev.get("lossStreak", 0) + 1
                prev = ban_mint(prev, pos.get("mint") or "", hours=24.0, reason="closed_loss")
            else:
                prev["lossStreak"] = 0
                prev = ban_mint(prev, pos.get("mint") or "", hours=24.0, reason="closed_win")
            if prev["lossStreak"] >= 2 and time.time() >= float(prev.get("cooldownUntil") or 0):
                prev["cooldownUntil"] = time.time() + 6 * 3600
                tg("🧊 AUTO COOLDOWN: %d straight stop-outs -> no new entries for 6h" % prev["lossStreak"])
            atomic_write(STATE, prev)
            atomic_write(HOLD, h)
            log({"event": "autopilot_sell", "symbol": pos["symbol"], "reason": dec["reason"], "tx": sig, "pct": round(dec["pct"], 1)})
            tg("🔴 AUTO SELL %s (%s) pnl %.1f%% realized $%.2f tx %s" % (pos["symbol"], dec["reason"], dec["pct"], realized, sig[:12]))
            try:  # rich close card (never blocks the engine)
                _t0 = _iso_secs(pos.get("openedAt")); _t1 = _iso_secs(pos.get("closedAt"))
                _secs = int(_t1 - _t0) if (_t0 and _t1) else 0
                _dur = "%dh %02dm" % (_secs // 3600, (_secs % 3600) // 60) if _secs else "?"
                _rem = delegate_remaining()
                _cp = {"engine": "Solana Snatcher Engine", "symbol": pos.get("symbol"),
                       "duration": _dur, "reason": dec.get("reason") or "",
                       "costUsdc": cost, "grossUsdc": proceeds, "dest": "SOL ATA (GRiCE…) — vault",
                       "destLane": "Solana Vault", "netPnl": realized,
                       "pnlPct": ("%+.1f%%" % ((realized / cost * 100) if cost else 0.0))}
                if realized >= 0:
                    tg_card("profit", _cp)
                else:
                    _cooldown = float(prev.get("cooldownUntil") or 0)
                    _mins = max(0, int((_cooldown - time.time()) / 60) + 1) if _cooldown else 0
                    _cp["lossStreak"] = prev.get("lossStreak", 1)
                    _cp["cooldown"] = ("%d-Min" % _mins) if _mins else "n/a"
                    _cp["delegatedLeft"] = _rem
                    tg_card("loss", _cp)
            except Exception:
                pass
            if VAULT_MODE:  # auto push sale proceeds back to the vault (vault owns reserve)
                time.sleep(1.5)
                hot_to_vault()
        else:
            tg("⚠️ AUTO sell FAILED for %s: %s" % (pos["symbol"], err))
    opens = [p for p in h.get("positions", []) if p["status"] == "open"]
    if len(opens) >= MAX_OPEN:
        log({"event": "autopilot_no_entry", "reason": "max_open", "open": len(opens)})
        return 0
    # refresh balances after any sells (owner basis incl. vault)
    sol, usdc = balances()
    vault = (vault_usdc() or 0.0) if VAULT_MODE else 0.0
    cash_total = usdc + vault
    cash_disp = cash_total if VAULT_MODE else usdc
    # 2) find an entry
    if time.time() < float(prev.get("cooldownUntil") or 0):
        log({"event": "autopilot_no_entry", "reason": "cooldown", "until": prev.get("cooldownUntil")})
        tg("🛑 NO-ENTRY reason=cooldown - no new entries (2 straight stop-outs). Reserve $%.2f ready." % cash_disp)
        return 0
    if cash_total < RESERVE_MIN:
        log({"event": "autopilot_no_entry", "reason": "reserve", "reserve": cash_disp})
        tg("🛑 NO-ENTRY reason=reserve - cash $%.2f below floor %.2f" % (cash_disp, RESERVE_MIN))
        return 0
    # PORTFOLIO MANAGER (T-1): full advisory once per tick - Risk cycle + Execution sizing.
    pm_size = SIZE_USDC
    try:
        import portfolio_state as _ps
        import portfolio_manager as _pm
        st = _ps.build_portfolio_state(live=True)
        pm_recs = _pm.all_recommendations(st)
        ks = pm_recs.get("killSwitches") or {}
        if ks.get("haltNewEntries"):  # PM daily-loss kill switch pauses the desk
            tg("⛔ PORTFOLIO MANAGER: daily loss halt - no new entries")
            open(OFF, "w").write("pm daily-loss halt")
            return 0
        sizing = pm_recs.get("entrySizing") or {}
        if sizing.get("ok"):
            sug = float(sizing.get("suggestedUsd") or 0)
            if sug > 0:  # Execution sizes from the manager; never exceed the fixed cap
                pm_size = round(max(1.0, min(SIZE_USDC, sug)), 2)
        log({"event": "portfolio_manager_advisory",
             "equity": (pm_recs.get("snapshot") or {}).get("equityUsd"),
             "memePct": (pm_recs.get("snapshot") or {}).get("memePct"),
             "halt": bool(ks.get("haltNewEntries")), "pmSize": pm_size,
             "summary": (pm_recs.get("summary") or [])[:3]})
    except Exception as e:
        log({"event": "portfolio_manager_advisory_error", "err": str(e)[:200]})
    # keep execution aligned with the scanner's market regime (fear->greed bar)
    load_regime_bar()
    tried = prev.get("tried", [])
    dry_runs = int(prev.get("emptyRuns", 0))
    prev["bannedMints"] = prune_banned(prev.get("bannedMints") or {})
    try:
        holdings_snap = json.load(open(HOLD))
    except Exception:
        holdings_snap = {"positions": []}
    blocked = blocked_mints(holdings_snap, prev.get("bannedMints"))
    tried_set = set(tried)
    raw = latest_scan_candidates()
    pool = [c for c in raw if c.get("token") and c.get("token") not in tried_set
            and c.get("token") not in blocked]
    pool.sort(key=lambda c: rank_key(c, tried_set, blocked))
    cands = pool
    bar, entry_note = _BAR, _BAR.get("mode", "NEUTRAL_SNATCH")
    strict = [c for c in cands if eligible(c, bar)]
    relief = [c for c in cands if eligible(c, RELIEF_BAR)] if (not strict and dry_runs >= 2) else []
    queue = (strict or relief)[:3]
    log({"event": "autopilot_hunt", "mode": entry_note,
         "queue": [{"s": c.get("symbol"), "liq": c.get("liqUsd"), "fdv": c.get("fdv"),
                    "h1": c.get("chg_h1"), "m5": c.get("chg_m5")} for c in queue],
         "strict": len(strict), "relief": len(relief),
         "blocked": len(blocked), "rawScan": len(raw)})
    if not queue:
        prev["emptyRuns"] = dry_runs + 1
        atomic_write(STATE, prev)
        reason = "zero_eligible"
        if not raw:
            reason = "no_scan_file_or_empty"
        elif not pool and (tried_set or blocked):
            reason = "all_blocked_or_tried"
        elif not strict and dry_runs < 2:
            reason = "zero_eligible_strict_relief_pending"
        open_n = len([p for p in holdings_snap.get("positions", []) if str(p.get("status")) == "open"])
        diag = ("🛑 NO-ENTRY reason=%s mode=%s emptyRuns=%d open=%d blocked=%d scanned=%d "
                "strict=0 relief=%d reserve=$%.2f barLiq=%s" %
                (reason, entry_note, dry_runs + 1, open_n, len(blocked), len(raw),
                 len(relief), cash_disp, _BAR.get("minLiq")))
        log({"event": "autopilot_no_entry", "reason": reason, "detail": diag})
        tg(diag)
        return 0
    # MULTI-SHOT HUNT (boss 2026-09-04): try up to 3 eligible candidates per tick.
    # A gecko / USDC-gate / swap rejection falls through to the NEXT candidate instead
    # of ending the whole tick (was: one shot, tick over).
    for cand in queue:
        shot_mode = ("RELIEF(dry-tape)" if cand in relief else entry_note)
        tried.append(cand["token"])
        # INDEPENDENT CROSS-CHECK (GeckoTerminal) - reject when the second provider disagrees
        ck = gecko_check(cand["token"])
        if ck:
            gl = float(ck.get("liq_usd") or 0)
            gf = float(ck.get("fdv_usd") or 0)
            pc = ck.get("pool_chg") or {}
            gh1 = float(pc.get("h1") or 0)
            gh24 = float(pc.get("h24") or 0)
            if gl < 10000 or gf < 30000 or gh1 > 150 or gh24 > 800:
                log({"event": "autopilot_shot", "symbol": cand.get("symbol"), "outcome": "gecko_reject",
                     "gl": gl, "gf": gf, "gh1": gh1, "gh24": gh24})
                tg("🚫 SKIP %s: GeckoTerminal disagrees (liq $%.0f, fdv $%.0f, h1 %+.0f%%, h24 %+.0f%%) -> next shot"
                   % (cand.get("symbol"), gl, gf, gh1, gh24))
                continue
        # cleared cross-check -> persist rotation + reset dry counter
        prev["tried"] = tried[-40:]
        prev["emptyRuns"] = 0
        atomic_write(STATE, prev)
        # VAULT FUNDING (Safe-style): pull the PM-sized amount from the vault under the
        # SPL delegate cap (if hot doesn't already hold it), then swap as usual.
        size = pm_size
        if VAULT_MODE and token_balance(USDC) < size * 0.99:
            if not vault_pull(size):
                return 0
        amt_raw = int(size * 1e6)
        # USDC-ONLY GATE (UNIFIED USDC desk): the lane always SPENDS USDC and opens a
        # position in the target token. Two checks: (1) input asset must be USDC,
        # (2) the target must NOT be USDC (never open a position in the settlement mint).
        if str(cand.get("inputAsset") or "USDC").upper() != "USDC":
            log({"event": "autopilot_shot", "symbol": cand.get("symbol"), "outcome": "not_usdc_input",
                 "inputAsset": cand.get("inputAsset")})
            tg("🚫 USDC-ONLY GATE: refusing %s buy - input asset must be USDC (got %s)" %
               (cand.get("symbol"), cand.get("inputAsset")))
            continue
        if str(cand.get("token") or "").lower() == USDC.lower():
            log({"event": "autopilot_shot", "symbol": cand.get("symbol"), "outcome": "target_is_usdc"})
            tg("🚫 USDC-ONLY GATE: refusing %s - cannot open a position in the settlement mint USDC" %
               cand.get("symbol"))
            continue
        sig, err = build_and_send(USDC, cand["token"], amt_raw, 1500, "/tmp/auto_buy.b64")
        if not sig:
            log({"event": "autopilot_shot", "symbol": cand.get("symbol"), "outcome": "swap_error", "err": str(err)[:200]})
            tg("⚠️ AUTO buy FAILED %s: %s -> next shot" % (cand.get("symbol"), err))
            continue
        qty = token_balance_retry(cand["token"])
        if not qty:  # fill tx landed but token balance unread/zero (RPC lag or bad fill)
            time.sleep(3)
            qty = token_balance_retry(cand["token"])
        if not qty:
            log({"event": "autopilot_shot", "symbol": cand.get("symbol"), "outcome": "qty_unread_after_fill",
                 "tx": sig, "sizeUsdc": size})
            tg("🚨 FILLED %s BUT QTY UNREADABLE (tx %s, $%.2f) - NO $0 entry recorded; human review" %
               (cand.get("symbol"), sig[:16], size))
            return 0  # stop the tick: unaccounted exposure must be resolved, not compounded
        entry = size / qty
        pos = {"id": "auto-" + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S"),
               "ticket": "autopilot", "status": "open", "chain": "solana", "wallet": WALLET,
               "symbol": cand.get("symbol"), "mint": cand["token"],
               "settleToUsdcLane": "solana-usdc", "inputAsset": "USDC",
               "fundedFrom": "vault-delegate" if VAULT_MODE else "hot",
               "openedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "txSignature": sig, "qty": qty, "costUsdc": size,
               "entryImpliedUsd": round(entry, 12), "exitStrategy": "snatcher autopilot"}
        save_position(pos)
        log({"event": "autopilot_buy", "symbol": pos["symbol"], "mint": pos["mint"], "qty": qty,
             "sizeUsdc": size, "entry": entry, "tx": sig})
        tg("🟢 AUTO BUY %s [%s] $%.2f -> %s tokens @ $%.8g | hot USDC left $%.2f | tx %s" %
           (pos["symbol"], shot_mode, size, qty, entry, token_balance(USDC), sig[:12]))
        try:  # rich open card (never blocks the engine)
            _rem = delegate_remaining()
            tg_card("open", {"engine": "Solana Snatcher Engine", "symbol": pos.get("symbol"),
                             "ca": pos.get("mint", "")[:8] + "…",
                             "entryTime": pos.get("openedAt", "").replace("T", " ")[:16] + " UTC",
                             "sizeUsdc": size, "qty": qty, "entryPrice": "%.8g" % entry,
                             "delegatedLeft": _rem, "slip": "≤15% guard (Jupiter route)",
                             "hardStopPct": "-30.00%", "hardStopPrice": (entry * 0.70) if entry else 0,
                             "targetPct": "+50% rung / trail", "regime": shot_mode})
        except Exception:
            pass
        return 0
    # queue exhausted without a fill
    prev["emptyRuns"] = dry_runs + 1
    atomic_write(STATE, prev)
    tg("🎯 %d eligible shot(s) attempted, none filled this tick (reserve $%.2f). Continuing hunt."
       % (len(queue), cash_disp))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        tg("AUTOPILOT error: %s" % e)
        raise


