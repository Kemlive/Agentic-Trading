#!/usr/bin/env python3
"""
portfolio_state.py - Agentic Trading (Meme Profit Snatcher) portfolio state adapter.

Builds the REAL current portfolio state dict consumed by `portfolio_manager.py`:

    from portfolio_state import build_portfolio_state
    import portfolio_manager as pm

    state = build_portfolio_state()          # fresh local snapshot + optional live marks
    recs  = pm.all_recommendations(state)    # full advisory bundle
    size  = pm.sizing_for_regime(state["regime"])   # next-entry USD size

State schema (matches portfolio_manager.py):
    {
      "cash": float,                 # USD of all cash/stablecoins (SOL-lane USDC + Base USDC)
      "dayStartEquity": float|None,  # only when autopilot.json day == today (else None)
      "realizedToday": float,        # sum of realized USD on positions closed today
      "regime": str,                 # CMC Fear&Greed label from the newest scan (or live)
      "positions": [ { id, symbol, chain, narrative, qty, costUsdc,
                       marketValueUsd|currentPriceUsd, status:"open" } ... ]
    }

DATA SOURCES (all best-effort; the adapter NEVER crashes on a missing source):
  1. data/live/holdings.json      - canonical open meme positions (id/symbol/qty/costUsdc).
  2. data/live/autopilot.json     - day + dayStartEquity for the daily -10% kill switch.
  3. data/live/evm-autopilot.json - Base Safe address + USDC/AERO token addresses.
  4. data/live/config.json        - last-known snapshot balances (fallback for cash).
  5. data/pump-scan-*.json        - newest regime label (source: CMC Fear & Greed).
  6. Optional LIVE reads (on by default via --live): public-RPC USDC balances
     (Solana hot wallet + Base Safe) and DexScreener spot prices for open mints.
     Any failure falls back to snapshot/cost figures - never a crash.

Branding note (boss rule 2026-09-04): this is Agentic Trading code; no third-party
names/brands appear in outputs, logs, or subagent-facing text.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = datetime.datetime.now(datetime.timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")

# Canonical token/wallet ids (kept in sync with scripts/autopilot.py + data/live/*).
SOL_HOT_WALLET = "GHojAXGEY8DrcDNTjCJcA5hjNt5NBXS4j2dfsxsJKxJM"
# Vault owner = config walletPublicKey; the vault owns the USDC reserve and the hot
# wallet only spends under its SPL delegate cap -> SOL-lane cash = vault + hot.
SOL_VAULT_WALLET = "8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4"
SOL_RPCS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com",
            "https://rpc.ankr.com/solana"]
USDC_SOL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_RPC = "https://api.mainnet-beta.solana.com"
BASE_RPC = "https://mainnet.base.org"


# ---------------------------------------------------------------------------
# Tiny robust helpers (no external deps; stdlib only)
# ---------------------------------------------------------------------------
def _f(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        return float(str(x).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def _read_json(path: str) -> Dict[str, Any]:
    """Read a JSON file; returns {} on any error (never raises)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 4.0) -> Optional[Dict[str, Any]]:
    """Small JSON-RPC/HTTP POST used for read-only public-node queries."""
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "agentic-trading-pm/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _get_json(url: str, timeout: float = 4.0) -> Optional[Any]:
    """Small GET used for DexScreener spot prices."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading-pm/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cash / stable reads (best-effort; file snapshot first, live RPC on --live)
# ---------------------------------------------------------------------------
def _snapshot_cash() -> Dict[str, float]:
    """Fallback per-lane cash from the last persisted snapshots (config.json).
    Never raises. Lanes: 'solana' (SOL-lane USDC), 'base' (Base USDC = EVM
    settlement lane), 'other' (any other EVM USDC pockets)."""
    cfg = _read_json(os.path.join(ROOT, "data", "live", "config.json"))
    lanes = {"solana": 0.0, "base": 0.0, "other": 0.0}
    try:
        lanes["solana"] = _f((cfg.get("onChain") or {}).get("usdcHeld"))   # SOL-lane USDC
    except Exception:
        pass
    try:
        bals = ((cfg.get("evmLane") or {}).get("balances")) or {}
        lanes["base"] = _f(bals.get("usdc_base"))          # Base USDC (settlement lane)
        lanes["other"] = _f(bals.get("usdc_ethereum"))      # ETH-pocket USDC (rare)
    except Exception:
        pass
    lanes["snapshotUsd"] = lanes["solana"] + lanes["base"] + lanes["other"]
    return lanes


def _read_sol_usdc_any(address: str) -> Optional[float]:
    """Read an owner's USDC (sum over its token accounts) across fallback RPCs."""
    for url in SOL_RPCS:
        res = _post_json(url, {"jsonrpc": "2.0", "id": 1, "method": "getTokenAccountsByOwner",
                               "params": [address, {"mint": USDC_SOL_MINT}, {"encoding": "jsonParsed"}]})
        try:
            if res and "result" in res:
                total = 0.0
                for item in res["result"].get("value", []):
                    total += _f(((item.get("account") or {}).get("data") or {})
                                .get("parsed", {}).get("info", {}).get("tokenAmount", {}).get("uiAmount"))
                return total
        except Exception:
            continue
    return None


def _live_sol_usdc() -> Optional[float]:
    """SOL-lane USDC = vault reserve + hot wallet (VAULT_MODE owner basis)."""
    vault = _read_sol_usdc_any(SOL_VAULT_WALLET)
    hot = _read_sol_usdc_any(SOL_HOT_WALLET)
    if vault is None and hot is None:
        return None
    return float(vault or 0.0) + float(hot or 0.0)


def _live_base_usdc() -> Optional[float]:
    """Public-RPC eth_call balanceOf(USDC) summed across BOTH Base lane holders:
    the Safe (0x203FD7...) and the unified owner EOA (0xB1AC...) - a DexBridge
    delivery may land on either. Read-only."""
    evm = _read_json(os.path.join(ROOT, "data", "live", "evm-autopilot.json"))
    cfg = _read_json(os.path.join(ROOT, "data", "live", "config.json"))
    usdc = (evm.get("usdc") or "").strip()
    addrs = []
    if evm.get("safe"):
        addrs.append(str(evm["safe"]).strip())
    eoa = (((cfg.get("evmLane") or {}).get("walletAccounts")) or {}).get("evm")
    if eoa:
        addrs.append(str(eoa).strip())
    addrs = list(dict.fromkeys(a for a in addrs if a))  # dedupe, drop empties
    if not usdc or not addrs:
        return None
    total = 0.0
    for holder in addrs:
        data = "0x70a08231000000000000000000000000" + holder[2:].lower()
        res = _post_json(BASE_RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                    "params": [{"to": usdc, "data": data}, "latest"]})
        try:
            total += int((res or {}).get("result", "0x0"), 16) / 1e6  # USDC = 6 decimals
        except Exception:
            continue
    return total




def _live_base_aero() -> Optional[float]:
    """Public-RPC eth_call balanceOf(AERO) for the Base Safe (read-only, 18 decimals)."""
    evm = _read_json(os.path.join(ROOT, "data", "live", "evm-autopilot.json"))
    safe = (evm.get("safe") or "").strip()
    aero = (evm.get("aero") or "").strip()
    if not safe or not aero:
        return None
    data = "0x70a08231000000000000000000000000" + safe[2:].lower()
    res = _post_json(BASE_RPC, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                "params": [{"to": aero, "data": data}, "latest"]})
    try:
        return int((res or {}).get("result", "0x0"), 16) / 1e18  # AERO = 18 decimals
    except Exception:
        return None


def _base_aero_price() -> Optional[float]:
    """DexScreener spot price for AERO on Base (best-effort)."""
    evm = _read_json(os.path.join(ROOT, "data", "live", "evm-autopilot.json"))
    aero = (evm.get("aero") or "").strip()
    if not aero:
        return None
    data = _get_json("https://api.dexscreener.com/latest/dex/tokens/" + aero)
    try:
        for pair in (data or {}).get("pairs") or []:  # prefer a real Base/USDC pool
            if str(pair.get("chainId")) == "base" and (pair.get("quoteToken") or {}).get("symbol") == "USDC":
                return _f(pair.get("priceUsd")) or None
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Regime (CMC Fear & Greed): newest scan file is the local source of truth;
# fall back to a live CMC read when the newest scan is stale (> 90 min).
# ---------------------------------------------------------------------------
_SCAN_FRESH_SECONDS = 90 * 60


def _scan_regime() -> Optional[Dict[str, Any]]:
    try:
        files = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
        if not files:
            return None
        scan = _read_json(files[-1])
        reg = scan.get("regime") or {}
        scanned = str(scan.get("scannedAt") or "")
        try:
            ts = datetime.datetime.strptime(scanned, "%Y-%m-%dT%H%MZ").replace(tzinfo=datetime.timezone.utc)
            if (NOW - ts).total_seconds() > _SCAN_FRESH_SECONDS:
                return None  # stale -> let the live CMC read take over
        except Exception:
            return None
        return reg if reg.get("label") else None
    except Exception:
        return None


def _live_cmc_regime_label() -> Optional[str]:
    """Direct CMC Fear&Greed read (best-effort), reusing scripts/cmc-feed.py."""
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location("cmc_feed", os.path.join(here, "cmc-feed.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        idx = int((mod.fear_greed() or {}).get("index"))
    except Exception:
        return None
    if idx <= 25:
        return "Extreme Fear"
    if idx <= 45:
        return "Fear"
    if idx <= 54:
        return "Neutral"
    if idx <= 75:
        return "Greed"
    return "Extreme Greed"


def _resolve_regime() -> str:
    reg = _scan_regime()
    if reg and reg.get("label"):
        return reg["label"]
    live = _live_cmc_regime_label()
    return live if live else "Neutral"


# ---------------------------------------------------------------------------
# Positions (canonical source: data/live/holdings.json) + best-effort spot prices
# ---------------------------------------------------------------------------
def _dex_price(mint: str) -> Optional[float]:
    """DexScreener spot price for a mint (best-effort; None on any failure)."""
    data = _get_json("https://api.dexscreener.com/latest/dex/tokens/" + mint)
    try:
        pairs = (data or {}).get("pairs") or []
        for pair in pairs:  # prefer a real USDC-quoted Solana pool
            if str(pair.get("chainId")) == "solana" and (pair.get("quoteToken") or {}).get("symbol") == "USDC":
                return _f(pair.get("priceUsd")) or None
        return _f(pairs[0].get("priceUsd")) or None if pairs else None
    except Exception:
        return None


def _open_positions(live: bool) -> List[Dict[str, Any]]:
    """Open positions from holdings.json. Price enrichment is best-effort: live
    DexScreener price when `live`, otherwise the recorded cost basis stands in as
    the valuation fallback (portfolio_manager handles that via costUsdc)."""
    holdings = _read_json(os.path.join(ROOT, "data", "live", "holdings.json"))
    out: List[Dict[str, Any]] = []
    for p in (holdings.get("positions") or []):
        if str(p.get("status", "open")).lower() != "open":
            continue
        qty = _f(p.get("qty"))
        cost = _f(p.get("costUsdc")) or _f(p.get("costUsdEst")) or 0.0
        chain = str(p.get("chain") or "solana").lower()
        # Settlement contract (UNIFIED USDC desk): buys are always USDC input, the
        # coin sits on its NATIVE chain, and selling it lands USDC on the lane below.
        settle_lane = str(p.get("settleToUsdcLane") or
                          ("solana-usdc" if chain == "solana" else "base-usdc"))
        pos = {
            "id": str(p.get("id") or p.get("symbol") or "unknown"),
            "symbol": str(p.get("symbol") or "?"),
            "chain": chain,                       # native chain the coin sits on
            "settleToUsdcLane": settle_lane,      # lane that receives USDC on sell
            "inputAsset": "USDC",                 # this desk only ever buys with USDC
            "narrative": str(p.get("narrative") or p.get("cluster") or "unclustered").lower(),
            "qty": qty,
            "costUsdc": round(cost, 6),
            "status": "open",
        }
        px = _dex_price(str(p.get("mint") or "")) if (live and p.get("mint")) else None
        if px:
            pos["marketValueUsd"] = round(qty * px, 6)
            pos["currentPriceUsd"] = px
            pos["priceSource"] = "dexscreener-live"
        else:
            pos["priceSource"] = "cost-fallback"
        out.append(pos)
    return out



# ---------------------------------------------------------------------------
# Day-start equity + realized-today (daily -10% kill switch inputs)
# ---------------------------------------------------------------------------
UNIFIED_STATE = os.path.join(ROOT, "data", "live", "unified.json")


def _day_start_equity() -> Optional[float]:
    """Unified day-start equity for the PM daily -10% kill switch.

    Prefers data/live/unified.json (the UNIFIED-account baseline captured at the start of
    the day for the whole desk). Falls back to autopilot.json's SOL-lane baseline ONLY for
    backward compatibility when the unified snapshot is absent/stale. Never uses a stale day."""
    for path in (UNIFIED_STATE, os.path.join(ROOT, "data", "live", "autopilot.json")):
        st = _read_json(path)
        if str(st.get("day") or "") != TODAY:
            continue
        eq = _f(st.get("dayStartEquity"))
        if eq > 0:
            return eq
    return None


def _realized_today() -> float:
    """Sum of realized USD for positions closed today (canonical: holdings.json)."""
    holdings = _read_json(os.path.join(ROOT, "data", "live", "holdings.json"))
    total = 0.0
    for p in (holdings.get("positions") or []):
        if str(p.get("status", "open")).lower() != "closed":
            continue
        closed = str(p.get("closedAt") or "")
        if closed[:10] != TODAY:
            continue
        total += _f(p.get("realizedUsdc") or p.get("realizedUsd"))
    return total


def _account_map() -> Dict[str, Any]:
    """UNIFIED-ACCOUNT map (boss 2026-09-04): one identity across chains.
    Reads config.json walletAccounts (Turnkey unified) + the agent execution hot
    wallet + EVM Safe. Informational only - signing stays chain-native."""
    cfg = _read_json(os.path.join(ROOT, "data", "live", "config.json"))
    evm = _read_json(os.path.join(ROOT, "data", "live", "evm-autopilot.json"))
    accounts = ((cfg.get("evmLane") or {}).get("walletAccounts")) or {}
    hot = ((cfg.get("agentHotWallet") or {}).get("publicKey")) or ""
    return {
        "identity": {  # same boss account (Turnkey 'Buon' f0fb66a4)
            "solana": accounts.get("solana") or "",
            "evm": accounts.get("evm") or "",
        },
        "execution": {  # chain-native execution keys/wallets (NOT separate accounts)
            "solanaHotWallet": hot,
            "evmSafe": (evm.get("safe") or ""),
            "evmOwnerEoa": accounts.get("evm") or "",
        },
        "note": "One portfolio/equity across lanes; chain signing paths are native per chain.",
    }


# ---------------------------------------------------------------------------
# MULTI-PORTFOLIO (boss 2026-09-04): value ANY registered portfolio from
# data/live/portfolios.json. 'primary' = the full unified account (rich state);
# others = read-only USDC valuation of their wallets so the PM can manage them.
# ---------------------------------------------------------------------------
REG_FILE = os.path.join(ROOT, "data", "live", "portfolios.json")
NETWORKS_FILE = os.path.join(ROOT, "data", "live", "evm-networks.json")
BASE_USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Verified USDC per EVM chain (ledger in research/2026-09-04-unified-usdc-desk.md).
EVM_USDC = {
    "base": BASE_USDC_BASE,
    "ethereum": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "arbitrum": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    "hyperevm": "0xb88339cb7199b77e23db6e890353e22632ba630f",
    "robinhood": None,  # PENDING verification - reads return None until confirmed
}
EVM_NET_NAME = {"base": "BASE", "ethereum": "ETHEREUM", "bsc": "BNB",
                "arbitrum": "ARBITRUM", "hyperevm": "HYPER_EVM", "robinhood": "ROBINHOOD"}
_RPC_CACHE = {}


def _owner_sol_usdc(address: str) -> Optional[float]:
    res = _post_json(SOL_RPC, {"jsonrpc": "2.0", "id": 1, "method": "getTokenAccountsByOwner",
                               "params": [address, {"mint": USDC_SOL_MINT}, {"encoding": "jsonParsed"}]})
    try:
        total = 0.0
        for item in (res or {}).get("result", {}).get("value", []):
            total += _f(((item.get("account") or {}).get("data") or {})
                        .get("parsed", {}).get("info", {}).get("tokenAmount", {}).get("uiAmount"))
        return total
    except Exception:
        return None


def _chain_rpcs(chain: str) -> list:
    """RPC endpoints for an EVM chain from data/live/evm-networks.json."""
    if chain in _RPC_CACHE:
        return _RPC_CACHE[chain]
    rpcs = []
    try:
        nets = (_read_json(NETWORKS_FILE) or {}).get("networks") or []
        name = EVM_NET_NAME.get(chain)
        n = next((x for x in nets if str(x.get("name", "")).upper() == name), None)
        rpcs = (n or {}).get("rpc") or []
    except Exception:
        rpcs = []
    if chain == "base" and not rpcs:
        rpcs = [BASE_RPC]
    _RPC_CACHE[chain] = rpcs
    return rpcs


def _owner_evm_usdc(chain: str, address: str) -> Optional[float]:
    """USDC balanceOf(address) on that chain's OWN network + contract. None = unread."""
    usdc = EVM_USDC.get(chain)
    if not usdc or not address:
        return None
    data = "0x70a08231000000000000000000000000" + address[2:].lower()
    for url in _chain_rpcs(chain):
        try:
            res = _post_json(url, {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                   "params": [{"to": usdc, "data": data}, "latest"]})
            if res and res.get("result"):
                return int(res["result"], 16) / 1e6  # USDC = 6 decimals on all listed chains
        except Exception:
            continue
    return None


def _owner_base_usdc(address: str) -> Optional[float]:
    """Back-compat wrapper: USDC on Base."""
    return _owner_evm_usdc("base", address)


def list_portfolios() -> list:
    reg = _read_json(REG_FILE)
    return [p.get("id") for p in (reg.get("portfolios") or [])]


def portfolio_state(pid: str = "primary", live: bool = True) -> Dict[str, Any]:
    """Value one portfolio from the wallet registry. 'primary' returns the FULL rich
    state (positions/non-meme/accounts); extra portfolios return their USDC cash per
    lane + regime (positions not tracked yet - read-only cash management)."""
    if pid == "primary":
        return build_portfolio_state(live=live)
    reg = _read_json(REG_FILE)
    port = next((p for p in (reg.get("portfolios") or []) if p.get("id") == pid), None)
    if not port:
        return {"ok": False, "reason": "portfolio %r not in registry" % pid, "positions": []}
    cash_map = {}
    src = []
    for w in (port.get("wallets") or []):
        chain = str(w.get("chain") or "").lower()
        addr = str(w.get("address") or "")
        if chain == "solana":
            amt = _owner_sol_usdc(addr) if live else None
            lane = "solana"
        elif chain in EVM_USDC:  # each EVM chain read on ITS OWN network + USDC contract
            amt = _owner_evm_usdc(chain, addr) if live else None
            lane = chain
        else:
            amt = None
            lane = chain
        if amt is not None:
            cash_map[lane] = cash_map.get(lane, 0.0) + amt
            src.append("%s:%s" % (lane, addr[:6]))
        else:
            src.append("%s:%s(unread)" % (lane, addr[:6]))
    cash = sum(cash_map.values())
    return {
        "portfolio": pid,
        "label": port.get("label", pid),
        "cash": round(cash, 6),
        "usdcTotal": round(cash, 6),
        "cashByLane": {k: round(v, 6) for k, v in cash_map.items()},
        "nonMemeValueUsd": 0.0,
        "dayStartEquity": None,
        "realizedToday": 0.0,
        "regime": _resolve_regime(),
        "positions": [],
        "asOf": NOW.isoformat(),
        "accounts": {"wallets": port.get("wallets") or [], "sources": src},
        "meta": {"brand": "agentic-trading", "liveReads": live,
                 "note": "extra portfolio - read-only USDC cash tracking for now",
                 "openPositionCount": 0},
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def build_portfolio_state(live: bool = True) -> Dict[str, Any]:
    """Build the current portfolio state dict for portfolio_manager.py.

    live=True  -> best-effort public-RPC balance reads + DexScreener spot prices
                  (each source individually guarded; failures fall back to files).
    live=False -> file snapshots + cost-basis only (fast, fully offline).
    Never raises: any missing file/feed degrades to usable defaults.
    """
    sources: List[str] = []
    cash_map = {"solana": 0.0, "base": 0.0, "other": 0.0}

    # 1) CASH / stables per lane (UNIFIED ACCOUNT = one USDC desk): live RPC first,
    #    persisted snapshot fallback per lane, 0 last. 'other' = non-Base EVM USDC.
    live_sol = _live_sol_usdc() if live else None
    live_base = _live_base_usdc() if live else None
    snap = _snapshot_cash()
    if live_sol is not None:
        cash_map["solana"] = live_sol
        sources.append("sol-usdc-rpc")
    if live_base is not None:
        cash_map["base"] = live_base
        sources.append("base-usdc-rpc")
    if not sources:  # full offline fallback to the persisted snapshot lanes
        for lane in ("solana", "base", "other"):
            cash_map[lane] = snap.get(lane, 0.0)
        sources.append("config-snapshot")
    cash = cash_map["solana"] + cash_map["base"] + cash_map["other"]

    # 1b) NON-MEME lane value (UNIFIED ACCOUNT): EVM AERO marked at live spot when
    #     available - it is equity, not a meme, so it never touches meme caps.
    aero_other = 0.0
    if live:
        aero_qty = _live_base_aero()
        aero_px = _base_aero_price()
        if aero_qty and aero_px:
            aero_other = aero_qty * aero_px
            sources.append("base-aero-rpc+dexscreener")
    non_meme = round(aero_other, 6)

    # 2) Day-start + realized (guarded; None/0 when not applicable today).
    day_start = _day_start_equity()
    realized = _realized_today()

    # 3) Regime (newest scan, else live CMC, else Neutral).
    regime = _resolve_regime()

    # 4) Open positions (meme lane).
    positions = _open_positions(live)

    state = {
        "cash": round(cash, 6),
        "usdcTotal": round(cash, 6),                  # UNIFIED ACCOUNT: one USDC desk total
        "cashByLane": {k: round(v, 6) for k, v in cash_map.items()},  # per-lane USDC ledger
        "nonMemeValueUsd": non_meme,          # UNIFIED ACCOUNT: EVM lane value (equity, not meme)
        "dayStartEquity": day_start,
        "realizedToday": round(realized, 6),
        "regime": regime,
        "positions": positions,
        # adapter metadata - ignored by portfolio_manager, useful for audit
        "asOf": NOW.isoformat(),
        "accounts": _account_map(),           # one identity across chains (see below)
        "meta": {
            "brand": "agentic-trading",
            "cashSources": sources,
            "liveReads": live,
            "dayStartEquityStale": day_start is None,
            "realizedSource": "holdings-closed-today",
            "regimeSource": "pump-scan" if _scan_regime() else ("cmc-live" if regime != "Neutral" else "default"),
            "openPositionCount": len(positions),
        },
    }
    return state


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Agentic Trading - print current portfolio state (JSON).")
    ap.add_argument("--no-live", action="store_true", help="offline: snapshot files + cost basis only")
    args = ap.parse_args()

    st = build_portfolio_state(live=not args.no_live)
    json.dump(st, sys.stdout, indent=2)
    print()

