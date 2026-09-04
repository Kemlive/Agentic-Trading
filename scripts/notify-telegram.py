#!/usr/bin/env python3
"""Telegram notifier for the trading squad.
Usage:
  python3 scripts/notify-telegram.py report     # full status (balance/open/recent/watchlist)
  python3 scripts/notify-telegram.py msg "text" # send arbitrary alert

Config: ~/.config/agentic-trading/telegram.json  {"token": "...", "chat_id": "..."}  (0600)
If no config: prints the report to the console instead of sending (preview mode).
"""
import json
import os
import sys
import glob
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.expanduser("~/.config/agentic-trading/telegram.json")
WALLET = "GHojAXGEY8DrcDNTjCJcA5hjNt5NBXS4j2dfsxsJKxJM"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def load_tg():
    if os.path.exists(CFG):
        d = json.load(open(CFG))
        if d.get("token") and d.get("chat_id"):
            return d
    return None


def send(text, tg=None, mode=None):
    if not tg:
        print(text)
        return False
    body = {"chat_id": tg["chat_id"], "text": text,
            "disable_web_page_preview": True}
    if mode:
        body["parse_mode"] = mode
    req = urllib.request.Request("https://api.telegram.org/bot" + tg["token"] + "/sendMessage",
                                 data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
        print("telegram sent")
        return True
    except Exception as e:
        body = b""
        try:
            body = e.read() if hasattr(e, "read") else b""
        except Exception:
            pass
        print("telegram send failed:", e, body.decode(errors="replace")[:300])
        return False


def helius_rpc(method, params):
    key = open(os.path.expanduser("~/.config/agentic-trading/helius.key")).read().strip()
    req = urllib.request.Request("https://mainnet.helius-rpc.com/?api-key=" + key,
                                 data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def token_price(mint):
    try:
        req = urllib.request.Request("https://api.dexscreener.com/latest/dex/tokens/" + mint,
                                     headers={"User-Agent": "agentic-trading/0.1"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        pairs = [p for p in (d.get("pairs") or []) if p.get("chainId") == "solana" and (p.get("liquidity") or {}).get("usd")]
        pairs.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
        return float(pairs[0]["priceUsd"]) if pairs else None
    except Exception:
        return None


def get_balances():
    b = helius_rpc("getBalance", [WALLET])
    sol = (b.get("result") or {}).get("value", 0) / 1e9
    tb = helius_rpc("getTokenAccountsByOwner", [WALLET, {"mint": USDC}, {"encoding": "jsonParsed"}])
    usdc = 0.0
    for a in ((tb.get("result") or {}).get("value") or []):
        usdc += (a.get("account", {}).get("data", {}).get("parsed", {}).get("info", {}).get("tokenAmount", {}) or {}).get("uiAmount") or 0
    return sol, usdc


def _usd(x):
    try:
        return "${:,.2f}".format(float(x))
    except Exception:
        return "$0.00"


def _num(x, sig=4):
    try:
        f = float(x)
    except Exception:
        return "?"
    if abs(f) >= 100000:
        return "{:,.0f}".format(f)
    if abs(f) >= 1:
        return "{:,.2f}".format(f)
    return ("{:." + str(sig) + "g}").format(f)


def _pct(x):
    try:
        return "{:+.1f}%".format(float(x))
    except Exception:
        return "?"


def _tx(short):
    return short[:8] + "…" if short else ""


def _evm_balances():
    """Read Safe USDC/AERO balances on Base (read-only; multi-RPC fallback; never blocks)."""
    try:
        safe = "0x203FD7cefb443672ef5700A1E27521c22A6E7B3A"
        usdc_c = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
        aero_c = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"
        data = "0x70a08231000000000000000000000000" + safe[2:].lower()
        rpcs = ["https://base-rpc.publicnode.com", "https://mainnet.base.org",
                "https://base.llamarpc.com", "https://1rpc.io/base", "https://base.drpc.org"]

        def call(token, url):
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                                               "params": [{"to": token, "data": data}, "latest"]}).encode(),
                                          headers={"content-type": "application/json", "user-agent": "Mozilla/5.0"})
            res = json.loads(urllib.request.urlopen(req, timeout=8).read())
            return int(res["result"], 16)

        usdc = aero = None
        for url in rpcs:  # one healthy RPC answers both calls
            try:
                usdc = call(usdc_c, url) / 1e6
                aero = call(aero_c, url) / 1e18
                break
            except Exception:
                continue
        if usdc is None or aero is None:  # final fallback: portfolio_state multi-RPC reader
            import portfolio_state as _ps
            ps_b = _ps._owner_evm_usdc("base", safe)
            if ps_b is not None:
                usdc = ps_b
        if usdc is None or aero is None:
            return None
        return {"usdc": usdc, "aero": aero}
    except Exception:
        return None


def _aero_price():
    try:
        req = urllib.request.Request("https://api.coingecko.com/api/v3/simple/price?ids=aerodrome-finance&vs_currencies=usd",
                                     headers={"User-Agent": "agentic-trading/0.1"})
        return float(json.loads(urllib.request.urlopen(req, timeout=8).read())["aerodrome-finance"]["usd"])
    except Exception:
        return None


_BUYS = {"entry_filled", "live_fill", "autopilot_buy", "evm_auto_buy_entry"}
_SELLS = {"live_close", "exit_closed", "autopilot_sell", "evm_auto_sell_all", "evm_auto_bank_half"}


def format_action(e):
    ev = e.get("event")
    t = (e.get("ts") or "")[11:16] + "Z"
    sym = e.get("symbol") or e.get("asset") or "?"
    if ev == "capital_received":
        return "💰 CAPITAL +%s @ %s" % (_usd(e.get("amountUsdc")), t)
    if ev in _BUYS:
        if ev == "autopilot_buy":
            return "🟢 AUTO BUY %s %s tx %s @ %s" % (sym, _usd(e.get("sizeUsdc") or e.get("costUsdc")), _tx(e.get("tx") or ""), t)
        if ev == "evm_auto_buy_entry":
            return "🟢 EVM BUY AERO %s tx %s @ %s" % (_usd(1.0), _tx(e.get("txHash") or ""), t)
        return "🟢 BUY %s %s tx %s @ %s" % (sym, _usd(e.get("costUsdc") or e.get("costUsdEst")), _tx(e.get("txSignature") or e.get("tx") or ""), t)
    if ev in _SELLS:
        if ev == "autopilot_sell":
            return "🔴 AUTO SELL %s (%s) %s tx %s @ %s" % (sym, e.get("reason") or "", _pct(e.get("pct")), _tx(e.get("tx") or ""), t)
        if ev in ("evm_auto_sell_all", "evm_auto_bank_half"):
            return "🔴 EVM EXIT %s %s tx %s @ %s" % (sym, ev.replace("evm_auto_", "").upper(), _tx(e.get("txHash") or ""), t)
        rl = e.get("realizedUsdc")
        if rl is None:
            rl = e.get("realizedUsd") or e.get("pnlUsd")
        pnl = (" %s" % _pct(e.get("realizedPct") or e.get("pct"))) if e.get("realizedPct") is not None or e.get("pct") is not None else ""
        return "🔴 SELL %s %s%s @ %s" % (sym, _usd(rl) if isinstance(rl, (int, float)) else "", pnl, t)
    if ev == "evm_trade_executed":
        return "🟢 EVM SWAP %s→%s tx %s @ %s" % (e.get("tokenIn"), e.get("tokenOut"), _tx(e.get("swapTx") or ""), t)
    return None



def recent_events(n=6):
    out = []
    logf = os.path.join(ROOT, "logs", "trades.jsonl")
    if os.path.exists(logf):
        for line in open(logf):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            f = format_action(e)
            if f:
                out.append(f)
    return out[-n:]



def report():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["🤖 <b>AGENTIC-TRADING STATUS</b>", now, ""]

    # ---- BALANCES: Solana hot wallet ----
    sol = usdc = None
    try:
        sol, usdc = get_balances()
    except Exception:
        pass
    L.append("💰 <b>BALANCES</b>")
    try:
        solpx = json.loads(urllib.request.urlopen(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=8)
            .read()).get("solana", {}).get("usd", 100)
    except Exception:
        solpx = None
    if usdc is None:
        L.append("  Solana: <i>unverified</i>")
    else:
        soltxt = ("%.4f SOL (~%s)" % (sol, _usd(sol * solpx))) if solpx else ("%.4f SOL" % sol)
        L.append("  • Solana hot wallet: USDC %s · %s" % (_usd(usdc), soltxt))
    # EVM Safe lane
    evm = _evm_balances()
    if evm is not None:
        apx = _aero_price()
        aero_usd = _usd(evm["aero"] * apx) if apx else ""
        L.append("  • EVM Safe (Base): USDC %s · AERO %s %s" % (_usd(evm["usdc"]), _num(evm["aero"], 5), aero_usd))
    else:
        L.append("  • EVM Safe (Base): <i>unverified</i>")

    # ---- OPEN POSITIONS ----
    L.append("")
    L.append("📂 <b>OPEN POSITIONS</b>")
    holdings = json.load(open(os.path.join(ROOT, "data", "live", "holdings.json")))
    opens = [p for p in holdings.get("positions", []) if p["status"] == "open" and (p.get("qty") or 0) > 0 and p.get("mint") not in (USDC, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")]
    if not opens:
        L.append("  (none)")
    for p in opens:
        px = token_price(p["mint"])
        entry = p.get("entryImpliedUsd") or p.get("entryUsd") or 0
        pct = ((px / entry - 1) * 100) if px and entry else None
        pnltxt = _pct(pct) if pct is not None else "?"
        L.append("  🟢 %s · %s tok · entry %s · now %s · %s" % (p["symbol"], _num(p["qty"]), _num(entry), _num(px), pnltxt))

    # ---- RECENT ACTIONS ----
    L.append("")
    L.append("🕘 <b>RECENT ACTIONS</b>")
    acts = recent_events(6)
    for a in acts:
        L.append("  " + a)
    if not acts:
        L.append("  (no recent trades)")

    # ---- WATCHLIST ----
    scans = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
    if scans:
        cands = json.load(open(scans[-1])).get("candidates", [])
        top = sorted(cands, key=lambda x: x.get("liqUsd") or 0, reverse=True)[:4]
        if top:
            L.append("")
            L.append("🔭 <b>WATCHLIST</b>")
            for r in top:
                L.append("  %s · liq %s · fdv %s" % (r.get("symbol"), _usd(r.get("liqUsd") or 0), _usd(r.get("fdv") or 0)))

    return "\n".join(L)



# ---------------------------------------------------------------------------
# RICH CARDS (Telegram Markdown) — Unified balance, open, profit-close, loss-close
# ---------------------------------------------------------------------------
def _m(x, d=2):
    try:
        return ("{:,.%df}" % d).format(float(x))
    except Exception:
        return "0"


def _price(x):
    """Precision-aware USD: >=$1 two decimals, else significant figures (microcaps)."""
    try:
        f = float(x)
    except Exception:
        return "$0.00"
    if abs(f) >= 1:
        return _usd(f)
    if f == 0:
        return "$0.00"
    return ("$%.8g" % f)


def _mc(s):
    """Clean a string for Telegram Markdown (escape _ * [ ] ` and keep unicode)."""
    out = []
    for ch in str(s or ""):
        out.append("\\" + ch if ch in "_*[]()`" else ch)
    return "".join(out)


def _fmt_dur(seconds):
    try:
        s = int(float(seconds))
    except Exception:
        return "?"
    h, m = divmod(s // 60, 60)
    if h:
        return "%dh %02dm" % (h, m)
    return "%dm %02ds" % (m, s % 60)


def _sol_split():
    """Live vault + hot USDC split (reuses portfolio_state multi-RPC reads)."""
    try:
        import portfolio_state as _ps
        vault = _ps._read_sol_usdc_any(_ps.SOL_VAULT_WALLET)
        hot = _ps._read_sol_usdc_any(_ps.SOL_HOT_WALLET)
        return (float(vault or 0.0), float(hot or 0.0))
    except Exception:
        return (None, None)


def _delegate_rem():
    try:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "solana-check-delegate.py")],
                           capture_output=True, text=True, timeout=30)
        for ln in (r.stdout or "").splitlines():
            if ln.startswith("delegatedAmount"):
                return float(ln.split(":", 1)[1].strip())
    except Exception:
        pass
    return None


def balance_card():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y %H:%M UTC")
    vault, hot = _sol_split()
    evm_raw = _evm_balances()
    evm = evm_raw if evm_raw is not None else {"usdc": 0.0, "aero": 0.0}
    base_ok = evm_raw is not None
    apx = _aero_price()
    aero_usd = evm["aero"] * apx if apx else 0.0
    cash = (vault or 0.0) + (hot or 0.0) + evm["usdc"]
    equity = cash + aero_usd
    base_eq = 0.0
    try:
        uj = json.load(open(os.path.join(ROOT, "data", "live", "unified.json")))
        base_eq = float(uj.get("dayStartEquity") or 0.0)
    except Exception:
        pass
    pnl_usd = equity - base_eq if base_eq else 0.0
    pnl_pct = (pnl_usd / base_eq * 100.0) if base_eq else 0.0
    realized7 = 0.0
    try:
        hh = json.load(open(os.path.join(ROOT, "data", "live", "holdings.json")))
        cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
        for p in (hh.get("positions") or []):
            if str(p.get("closedAt") or "") >= cut:
                realized7 += float(p.get("realizedUsdc") or p.get("realizedUsd") or 0.0)
    except Exception:
        pass
    dd = min(0.0, (equity - base_eq) / base_eq * 100.0) if base_eq else 0.0
    drem = _delegate_rem()
    L = []
    L.append("📊 **DESK PORTFOLIO & PNL REPORT**")
    L.append("─── Unified Balance Sheet ───")
    L.append("")
    L.append("💰 **CASH LIQUIDITY**")
    L.append(("├ 🟦 Solana Vault : %s USDC" % _usd(vault)) if vault is not None else "├ 🟦 Solana Vault : (unverified)")
    L.append("├ 🟦 Solana Hot   : %s USDC" % _usd(hot or 0.0))
    L.append(("├ 🟪 Base Safe    : %s USDC" % _usd(evm["usdc"])) if base_ok else "├ 🟪 Base Safe    : (unverified)")
    L.append("└ 🔘 Other EVM     : $0.00 USDC")
    L.append("")
    L.append("📈 **DESK VALUATION**")
    L.append("├ Net Cash   : %s USDC" % _usd(cash))
    L.append("├ Asset Value: %s USD (AERO)" % _usd(aero_usd))
    L.append("└ 💎 **UNIFIED EQUITY: %s USD**" % _usd(equity))
    L.append("")
    L.append("🏁 **PERFORMANCE OVERVIEW**")
    arrow = "🟩" if pnl_usd >= 0 else "🟥"
    L.append("├ Today's P&L : %s %s (%s)" % (arrow, _usd(pnl_usd), _pct(pnl_pct)))
    r7 = ("%s%s" % ("+" if realized7 >= 0 else "-", _usd(abs(realized7)))) if realized7 else "n/a"
    L.append("├ 7-Day Real : %s" % r7)
    L.append("└ Desk Drawdown: 🛡️ %s (Vs %s Baseline)" % (_pct(dd), _usd(base_eq)))
    L.append("")
    L.append("⚙️ **ENGINE STATUS**")
    L.append("├ SOL Snatcher: 🟢 ARMED (Cap: %s, Rem: %s)" % (_usd(15.0), _usd(drem or 0.0)))
    hold = "🟢 HOLD" if evm["aero"] > 0.000001 else "🟡 FLAT"
    L.append("└ Base Engine : %s (AERO %s)" % (hold, _num(evm["aero"], 5)))
    L.append("──────────────────────────────")
    L.append("[🟢 ALL PIPELINES SECURE & ONLINE] `%s`" % now)
    return "\n".join(L)


def open_card(p):
    engine = _mc(p.get("engine", "Solana Snatcher"))
    symbol = _mc(p.get("symbol", "?"))
    L = ["🚀 **NEW POSITION OPENED**", "─── %s ───" % engine, "",
         "🎫 **TOKEN:** $%s" % symbol]
    if p.get("ca"):
        L.append("📝 **CA:** `%s`" % _mc(p["ca"]))
    L.append("⏱️ **Entry Time:** %s" % _mc(p.get("entryTime", "?")))
    L.append("")
    L.append("📊 **TRADE DETAILS**")
    L.append("├ 💳 Entry Size : %s USDC" % _usd(p.get("sizeUsdc", 0)))
    L.append("├ 🪙 Tokens Got  : %s %s" % (_m(p.get("qty", 0), 6), symbol))
    if p.get("entryPrice"):
        L.append("├ 🏷️ Entry Price : $%s" % _mc(p.get("entryPrice")))
    if p.get("delegatedLeft") is not None:
        L.append("└ 🛡️ Delegated   : %s Left%s" % (_usd(p["delegatedLeft"]),
                                                  " (Refill Ready)" if float(p["delegatedLeft"]) < 2.0 else ""))
    L.append("")
    L.append("⚠️ **RISK SLOTS**")
    L.append("├ Max Slip Guard: %s" % _mc(p.get("slip", "Auto")))
    if p.get("hardStopPct"):
        L.append("├ Hard Stop Loss: 🛑 %s (%s)" % (_mc(p["hardStopPct"]), _price(p.get("hardStopPrice", 0))))
    if p.get("targetPct"):
        L.append("└ Trailing Take : 🎯 Target Active (%s)" % _mc(p["targetPct"]))
    L.append("──────────────────────────────")
    L.append("[⚡ Sized via %s]" % _mc(p.get("regime", "Risk Cycle")))
    return "\n".join(L)


def close_card(p):
    win = bool(p.get("win", False))
    engine = _mc(p.get("engine", "Engine"))
    symbol = _mc(p.get("symbol", "?"))
    head = "🎉 **POSITION CLOSED: TAKE PROFIT**" if win else "🛑 **POSITION CLOSED: STOP LOSS HIT**"
    L = [head, "─── %s ───" % engine, "",
         "🎫 **TOKEN:** $%s" % symbol,
         "⏱️ **Duration:** %s (%s)" % (_mc(p.get("duration", "?")), _mc(p.get("reason", "")))]
    L.append("")
    L.append("💸 **SETTLEMENT**")
    L.append("├ Initial Cost : %s USDC" % _usd(p.get("costUsdc", 0)))
    L.append("├ Gross Return : %s USDC" % _usd(p.get("grossUsdc", 0)))
    L.append("└ 🏦 Vault Destination: %s" % _mc(p.get("dest", "")))
    L.append("")
    pnl = float(p.get("netPnl", 0) or 0)
    pctv = _mc(p.get("pnlPct", ""))
    L.append("💰 **NET REALIZED %s**" % ("PROFIT" if win else "LOSS"))
    L.append("%s **%s%s (%s)**" % ("🟩" if win else "🟥",
                                   "+" if pnl >= 0 else "", _usd(abs(pnl)), pctv))
    L.append("")
    if p.get("fees"):
        L.append("⛽ **FEE AUDIT**")
        for k, v in p["fees"].items():
            L.append("├ %s: %s" % (_mc(k), _mc(v)))
        L.append("")
    if win:
        L.append("──────────────────────────────")
        L.append("[✅ Funds returned directly to %s — EOA balance: $0.00]" % _mc(p.get("destLane", "Safe")))
    else:
        L.append("⚠️ **DESK PROTECTIONS TRIPPED**")
        L.append("├ Loss Streak   : 🔥 %s / 3 (Consecutive)" % _mc(p.get("lossStreak", "?")))
        L.append("├ Cooldown Block: ⏳ %s Lock Active" % _mc(p.get("cooldown", "?")))
        L.append("└ System Status : 🛡️ Monitoring Next Tick")
        L.append("──────────────────────────────")
        L.append("[⚠️ Autopilot remains ONLINE. Sizing preserved.]")
    return "\n".join(L)


def main():
    tg = load_tg()
    args = sys.argv[1:]
    cmd = args[0] if args else "report"
    mode = None
    if cmd == "report":
        text = report()
        mode = "HTML"
    elif cmd == "card":
        kind = args[1] if len(args) > 1 else "balance"
        if kind == "balance":
            text = balance_card()
        else:
            payload = {}
            if len(args) > 2 and os.path.exists(args[2]):
                payload = json.load(open(args[2]))
            if kind == "open":
                text = open_card(payload)
            elif kind in ("profit", "loss"):
                payload["win"] = (kind == "profit")
                text = close_card(payload)
            else:
                text = "unknown card type: " + kind
        mode = "Markdown"
    else:
        text = " ".join(args)
    send(text, tg, mode)
    if not tg:
        print("\n[no telegram.json yet -> preview above. Setup: BotFather token + chat id]")


if __name__ == "__main__":
    main()
