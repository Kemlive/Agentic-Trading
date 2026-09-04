#!/usr/bin/env python3
"""
portfolio_manager.py - Portfolio Manager for the Meme Profit Snatcher system.

Pure, state-driven module (NO hardcoded balances). Risk / Execution / Rebalance
agents feed it the CURRENT portfolio state as a dict and receive clear, actionable
recommendations (dicts) for:

  1. Position / cluster / total-meme / cash-reserve limits
  2. Regime-aware entry sizing (Fear -> bigger, Greed -> smaller)
  3. Profit-taking tiers (+50% / +100% / +200%+)
  4. Rebalancing triggers (single > 15%, cluster > 30%, meme > 85%, cash < 15%)
  5. Risk kill switches (daily -10% loss, single -45% drawdown -> hard review)

State schema accepted (extra fields are ignored; missing ones get defaults):

    {
      "asOf": "2026-09-04T00:00:00Z",        # optional
      "cash": 20.0,                          # USD value of ALL cash + stablecoins
      "dayStartEquity": 66.0,                # optional - daily -10% kill switch
      "realizedToday": -1.2,                 # optional - derived if omitted
      "positions": [
        {
          "id": "pos-1", "symbol": "PEPE", "chain": "solana",
          "narrative": "frogs",              # cluster tag (omit = "unclustered")
          "qty": 12345.0, "costUsdc": 6.0,   # entry cost in USD
          "marketValueUsd": 9.0,             # OPTIONAL live value; otherwise:
          "currentPriceUsd": 0.0006,         #   used with qty to derive value
          "openedAt": "...", "status": "open"
        },
        # closed positions are fine too - they only feed realized-TODAY PnL for
        # the daily kill switch and never count toward exposure.
      ]
    }

Quick usage (Risk & Execution agents import this):

    import portfolio_manager as pm
    pm.set_state(snapshot)                  # cache it once
    recs = pm.all_recommendations(snapshot) # full advisory bundle
    size = pm.sizing_for_regime("Greed", equity=66.0)
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# POLICY (boss-approved rules, 2026-09-04)
# ---------------------------------------------------------------------------
# Hard limits (must never be exceeded while the kill switches are off).
POSITION_MAX_PCT = 0.12      # 1) max per single meme
CLUSTER_MAX_PCT = 0.25       # 2) max per narrative cluster
MEME_MAX_PCT = 0.80          # 3) max total meme exposure
CASH_MIN_PCT = 0.20          # 4) minimum cash/stable reserve

# Rebalancing TRIGGERS (crossing these fires a rebalance recommendation).
TRIGGER_POSITION_PCT = 0.15
TRIGGER_CLUSTER_PCT = 0.30
TRIGGER_MEME_PCT = 0.85
TRIGGER_CASH_PCT = 0.15

# Regime-aware ENTRY SIZING ceilings (max % of portfolio for ONE new meme).
#   Extreme Fear / Fear   -> up to 12% (cheap names, few crowds -> bigger bites)
#   Neutral               -> 8-10%    (mid risk)
#   Greed / Extreme Greed -> max 5-7% (crowded tape -> smaller, faster bites)
REGIME_SIZING = {
    "Extreme Fear":  {"maxPct": 0.12, "suggestedPct": 0.10},
    "Fear":          {"maxPct": 0.12, "suggestedPct": 0.10},
    "Neutral":       {"maxPct": 0.10, "suggestedPct": 0.08},
    "Greed":         {"maxPct": 0.07, "suggestedPct": 0.05},
    "Extreme Greed": {"maxPct": 0.07, "suggestedPct": 0.05},
}

# Profit-taking tiers.
PROFIT_TIERS = [
    {"minPct": 50,  "trimPct": 0.25, "action": "take 25-30% off the table",
     "note": "first bank - cover 25% of the position into strength"},
    {"minPct": 100, "trimPct": 0.30, "action": "take another 25-30% off",
     "note": "second bank - position now ~50-60% out; set a trailing stop"},
    {"minPct": 200, "trimPct": 0.40, "action": "aggressive scale-out / trailing",
     "note": "runner territory - scale hard or trail -20% off peak"},
]

# Risk kill switches.
DAILY_LOSS_LIMIT_PCT = -0.10     # -10% of day-start equity -> pause new entries
DRAWDOWN_HARD_FLAG_PCT = -0.45   # single position -45% from entry -> hard review

# Buffer so recommendations restore a little INSIDE the hard limit, not on the
# edge (slippage / price moves happen between advice and fill).
REBALANCE_BUFFER_PCT = 0.02


def policy() -> Dict[str, Any]:
    """Return the full policy table as a dict (single source for docs/UIs)."""
    return {
        "positionMaxPct": POSITION_MAX_PCT,
        "clusterMaxPct": CLUSTER_MAX_PCT,
        "memeMaxPct": MEME_MAX_PCT,
        "cashMinPct": CASH_MIN_PCT,
        "rebalanceTriggers": {
            "positionPct": TRIGGER_POSITION_PCT,
            "clusterPct": TRIGGER_CLUSTER_PCT,
            "memePct": TRIGGER_MEME_PCT,
            "cashPct": TRIGGER_CASH_PCT,
        },
        "regimeSizing": REGIME_SIZING,
        "profitTiers": PROFIT_TIERS,
        "killSwitches": {
            "dailyLossPct": DAILY_LOSS_LIMIT_PCT,
            "drawdownFlagPct": DRAWDOWN_HARD_FLAG_PCT,
        },
    }


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------
def _usd(x: Any) -> float:
    """Parse a value that may be None, int, float, or a comma string."""
    try:
        if x is None:
            return 0.0
        return float(str(x).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def _pct(part: float, whole: float) -> float:
    return round((part / whole) * 100.0, 2) if whole > 0 else 0.0


def _round(x: float, n: int = 2) -> float:
    return round(x + 1e-9, n)


def _is_open(p: Dict[str, Any]) -> bool:
    return str(p.get("status", "open")).lower() != "closed"


def _position_value(p: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort USD value of one position. Returns (value, source)."""
    if _usd(p.get("marketValueUsd")) > 0:
        return _usd(p["marketValueUsd"]), "marketValueUsd"
    qty = _usd(p.get("qty"))
    px = _usd(p.get("currentPriceUsd"))
    if qty > 0 and px > 0:
        return qty * px, "qty*currentPriceUsd"
    for key in ("valueUsd", "costUsdEst", "costUsdc"):
        if _usd(p.get(key)) > 0:
            return _usd(p[key]), "%s (assumed)" % key
    return 0.0, "unknown"


def _position_cost(p: Dict[str, Any]) -> float:
    for key in ("costUsdc", "costUsdEst", "costUsd"):
        if _usd(p.get(key)) > 0:
            return _usd(p[key])
    val, _ = _position_value(p)
    return val  # unknown cost -> treat current value as cost (flat)



# ---------------------------------------------------------------------------
# State: cache + normalization
# ---------------------------------------------------------------------------
_STATE: Dict[str, Any] = {"cash": 0.0, "positions": []}


def set_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Cache a portfolio snapshot and return its computed metrics.
    Agents call this once at the start of a decision cycle."""
    global _STATE
    _STATE = dict(state or {})
    return portfolio_snapshot(_STATE)


def current_state() -> Dict[str, Any]:
    """Return the last cached raw state (or an empty one)."""
    return dict(_STATE)


def update_position(position_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Patch one open position by id (e.g. new marketValueUsd / narrative) and
    refresh the cached snapshot. No-op returns the raw cached state unchanged."""
    global _STATE
    for p in _STATE.get("positions", []):
        if str(p.get("id")) == str(position_id):
            p.update(patch)
            break
    return portfolio_snapshot(_STATE)


def portfolio_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize ANY state dict into a measured snapshot:
    equity, cash %, meme %, per-position weight, cluster weights + warnings.
    This is the base every other function reasons on."""
    cash = _usd(state.get("cash"))
    rows: List[Dict[str, Any]] = []
    cluster_val: Dict[str, float] = {}
    for p in (state.get("positions") or []):
        if not _is_open(p):
            continue
        val, src = _position_value(p)
        cost = _position_cost(p)
        row = {
            "id": p.get("id") or p.get("symbol") or "unknown",
            "symbol": p.get("symbol") or "?",
            "chain": p.get("chain") or "?",
            "narrative": (p.get("narrative") or p.get("cluster") or "unclustered").lower(),
            "valueUsd": _round(val),
            "valueSource": src,
            "costUsd": _round(cost),
            "pnlPct": _round(((val / cost) - 1.0) * 100.0, 1) if cost > 0 else None,
            "offPeakPct": _round(((val / max(_usd(p.get("peakUsd")), 1e-12)) - 1.0) * 100.0, 1)
                          if _usd(p.get("peakUsd")) > 0 else None,
        }
        rows.append(row)
        cl = row["narrative"]
        cluster_val[cl] = cluster_val.get(cl, 0.0) + val

    meme_val = sum(r["valueUsd"] for r in rows)
    # UNIFIED ACCOUNT (boss 2026-09-04): non-meme assets from other lanes (e.g. EVM
    # AERO) count toward total equity and reserve math, but never toward MEME caps.
    other_val = _usd(state.get("nonMemeValueUsd"))
    equity = cash + meme_val + other_val

    enriched = []
    for r in rows:
        r["weightPct"] = _pct(r["valueUsd"], equity)
        enriched.append(r)
    clusters = [{"narrative": k, "valueUsd": _round(v),
                 "weightPct": _pct(v, equity)} for k, v in sorted(
                 cluster_val.items(), key=lambda kv: -kv[1])]

    warnings = []
    for r in enriched:
        if r["weightPct"] > POSITION_MAX_PCT * 100:
            warnings.append("position %s = %.1f%% > %.0f%% max"
                            % (r["symbol"], r["weightPct"], POSITION_MAX_PCT * 100))
    for c in clusters:
        if c["weightPct"] > CLUSTER_MAX_PCT * 100:
            warnings.append("cluster '%s' = %.1f%% > %.0f%% max"
                            % (c["narrative"], c["weightPct"], CLUSTER_MAX_PCT * 100))
    if meme_val and equity > 0 and meme_val / equity > MEME_MAX_PCT:
        warnings.append("total meme exposure %.1f%% > %.0f%% max"
                        % (meme_val / equity * 100, MEME_MAX_PCT * 100))
    if equity > 0 and cash / equity < CASH_MIN_PCT:
        warnings.append("cash reserve %.1f%% < %.0f%% minimum"
                        % (cash / equity * 100, CASH_MIN_PCT * 100))

    return {
        "asOf": state.get("asOf") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cashUsd": _round(cash),
        "memeUsd": _round(meme_val),
        "otherUsd": _round(other_val),       # EVM/non-meme lane value (unified equity)
        "equityUsd": _round(equity),
        "cashPct": _pct(cash, equity),
        "memePct": _pct(meme_val, equity),
        "otherPct": _pct(other_val, equity),
        "positionCount": len(enriched),
        "positions": enriched,
        "clusters": clusters,
        "warnings": warnings,
        "ok": not warnings,
    }



# ---------------------------------------------------------------------------
# 2) Regime-aware entry sizing
# ---------------------------------------------------------------------------
def sizing_for_regime(regime_label: str,
                      equity: Optional[float] = None,
                      state: Optional[Dict[str, Any]] = None,
                      cash_to_keep_reserve: bool = True) -> Dict[str, Any]:
    """Max USD + pct for ONE new meme entry given the current market regime.

    Ceilings (regime): Fear 12% / Neutral 8-10% / Greed 5-7%. The result is the
    MINIMUM of every constraint that applies:
      - regime ceiling (max AND a suggested 'safer' number)
      - free cash available
      - remaining single-position headroom
      - remaining cluster headroom (pass 'narrative' of the intended cluster)
      - remaining total-meme headroom + cash-reserve protection (keeps >= 20%
        cash if cash_to_keep_reserve=True)

    Returns a recommendation dict (no side effects).
    """
    snap = portfolio_snapshot(state) if state else portfolio_snapshot(_STATE)
    eq = equity if equity is not None else snap["equityUsd"]
    if eq <= 0:
        return {"ok": False, "reason": "portfolio equity is 0 - nothing to size"}

    sizing = REGIME_SIZING.get(regime_label, REGIME_SIZING["Neutral"])
    max_pct = sizing["maxPct"]
    suggested_pct = sizing["suggestedPct"]

    # available dry powder AFTER keeping the 20% cash reserve intact
    cash = snap["cashUsd"]
    if cash_to_keep_reserve:
        cash_headroom = max(0.0, cash - eq * CASH_MIN_PCT)
    else:
        cash_headroom = cash

    # total-meme exposure headroom (don't let one buy break the 80% meme cap)
    meme_headroom = max(0.0, eq * MEME_MAX_PCT - snap["memeUsd"])

    max_pct_bounded = min(max_pct,
                          cash_headroom / eq if eq else 0,
                          meme_headroom / eq if eq else 0)
    suggested_pct_bounded = min(suggested_pct, max_pct_bounded)

    return {
        "ok": True,
        "regime": regime_label,
        "regimeMaxPct": max_pct,
        "regimeSuggestedPct": suggested_pct,
        "portfolioEquityUsd": _round(eq),
        "freeCashUsd": _round(cash_headroom),
        "memeHeadroomUsd": _round(meme_headroom),
        "maxUsd": _round(max_pct_bounded * eq),
        "maxPct": _round(max_pct_bounded * 100, 2),
        "suggestedUsd": _round(suggested_pct_bounded * eq),
        "suggestedPct": _round(suggested_pct_bounded * 100, 2),
        "reason": ("min(regime %.0f%%, cash headroom %.0f%%, meme headroom %.0f%%)"
                   % (max_pct * 100,
                      cash_headroom / eq * 100 if eq else 0,
                      meme_headroom / eq * 100 if eq else 0)),
    }


# ---------------------------------------------------------------------------
# 3) Profit-taking recommendations
# ---------------------------------------------------------------------------
def profit_taking(position: Dict[str, Any]) -> Dict[str, Any]:
    """Given one position (raw or enriched), return tiered take-profit advice."""
    val, src = _position_value(position)
    cost = _position_cost(position)
    if cost <= 0:
        return {"ok": False, "reason": "position cost unknown", "actions": []}
    pnl_pct = (val / cost - 1.0) * 100.0

    actions = []
    for tier in PROFIT_TIERS:
        if pnl_pct >= tier["minPct"]:
            actions.append({
                "tier": ">= +%d%%" % tier["minPct"],
                "action": tier["action"],
                "trimPctOfPosition": tier["trimPct"],
                "estSellUsd": _round(val * tier["trimPct"]),
                "note": tier["note"],
                "priority": 1,
            })
    if pnl_pct >= 200:
        actions.append({"tier": "runner", "action": "activate trailing stop -20% off peak",
                        "trimPctOfPosition": None, "estSellUsd": None,
                        "note": "let a runner run only with a hard trailing stop",
                        "priority": 1})
    # a deep loser is a RISK event, handled by risk_kill_switches, not here
    if not actions:
        actions.append({"tier": "below +50%% (pnl %+.1f%%)" % pnl_pct,
                        "action": "hold - not at the first bank tier yet",
                        "trimPctOfPosition": 0.0, "estSellUsd": 0.0,
                        "note": "keep the snatcher exit rules active (stop/trail)",
                        "priority": 0})

    return {"ok": True,
            "symbol": position.get("symbol"),
            "pnlPct": _round(pnl_pct, 1),
            "positionValueUsd": _round(val),
            "valueSource": src,
            "actions": actions}



# ---------------------------------------------------------------------------
# 4) Rebalancing triggers + recommended actions
# ---------------------------------------------------------------------------
def rebalance(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Detect breaches of the rebalancing triggers and propose concrete sells.

    Trigger set (boss rules): single position > 15% | cluster > 30% |
    total meme > 85% | cash < 15%. Each action sells down to a target INSIDE the
    hard policy limit (12/25/80/20) minus a small buffer, largest exposure first.
    """
    snap = portfolio_snapshot(state) if state else portfolio_snapshot(_STATE)
    equity = snap["equityUsd"]
    if equity <= 0:
        return {"ok": False, "reason": "no equity to rebalance", "actions": []}

    triggers: List[str] = []
    actions: List[Dict[str, Any]] = []
    sell_map: Dict[str, float] = {}          # position id -> usd to sell

    def _want(pid: str, usd: float, reason: str, priority: int) -> None:
        sell_map[pid] = max(sell_map.get(pid, 0.0), usd)
        actions.append({"kind": "sell", "positionId": pid, "sellUsd": _round(usd),
                        "reason": reason, "priority": priority,
                        "note": "executor should size the order in small slices"})

    # --- single-position breach: sell down to hard cap (12%) - 2% buffer ---
    for r in snap["positions"]:
        if r["weightPct"] > TRIGGER_POSITION_PCT * 100:
            triggers.append("single %s %.1f%% > %.0f%%" % (r["symbol"], r["weightPct"],
                                                           TRIGGER_POSITION_PCT * 100))
            target_usd = equity * (POSITION_MAX_PCT - REBALANCE_BUFFER_PCT)
            _want(r["id"], max(0.0, r["valueUsd"] - target_usd),
                  "single position > 15%% (now %.1f%%)" % r["weightPct"], 1)

    # --- cluster breach: reduce the biggest names inside the cluster first ---
    for c in snap["clusters"]:
        if c["weightPct"] > TRIGGER_CLUSTER_PCT * 100:
            triggers.append("cluster %s %.1f%% > %.0f%%" % (c["narrative"], c["weightPct"],
                                                            TRIGGER_CLUSTER_PCT * 100))
            members = [r for r in snap["positions"] if r["narrative"] == c["narrative"]]
            members.sort(key=lambda r: -r["valueUsd"])
            target = equity * (CLUSTER_MAX_PCT - REBALANCE_BUFFER_PCT)
            excess = c["valueUsd"] - target
            for r in members:
                if excess <= 0:
                    break
                share = r["valueUsd"] / c["valueUsd"] if c["valueUsd"] > 0 else 0.0
                cut = min(r["valueUsd"], excess * share + excess * 0.1)
                _want(r["id"], cut, "cluster %s > 30%% (cut %.1f%%)"
                      % (c["narrative"], c["weightPct"]), 2)
                excess -= cut


    # --- total meme breach: sell across the largest names to get meme <= 78% ---
    if snap["memePct"] > TRIGGER_MEME_PCT * 100:
        triggers.append("total meme %.1f%% > %.0f%%" % (snap["memePct"], TRIGGER_MEME_PCT * 100))
        target = equity * (MEME_MAX_PCT - REBALANCE_BUFFER_PCT)
        excess = snap["memeUsd"] - target
        for r in sorted(snap["positions"], key=lambda r: -r["valueUsd"]):
            if excess <= 0:
                break
            cut = min(r["valueUsd"] * 0.5, excess)
            _want(r["id"], cut, "total meme exposure > 85%% (cut %.1f%%)" % snap["memePct"], 3)
            excess -= cut

    # --- cash below trigger: top up reserve by trimming the largest position ---
    if snap["cashPct"] < TRIGGER_CASH_PCT * 100 and snap["positions"]:
        triggers.append("cash reserve %.1f%% < %.0f%%" % (snap["cashPct"], TRIGGER_CASH_PCT * 100))
        need = equity * (CASH_MIN_PCT + REBALANCE_BUFFER_PCT) - snap["cashUsd"]
        biggest = max(snap["positions"], key=lambda r: -r["valueUsd"])
        _want(biggest["id"], min(need, biggest["valueUsd"] * 0.5),
              "cash reserve < 15%% (top up from %s)" % biggest["symbol"], 4)

    return {"ok": not triggers, "equityUsd": _round(equity),
            "triggers": triggers,
            "actions": sorted(actions, key=lambda a: a["priority"])}


# ---------------------------------------------------------------------------
# 5) Risk kill switches
# ---------------------------------------------------------------------------
def _realized_today(state: Dict[str, Any]) -> float:
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    total = 0.0
    for p in (state.get("positions") or []):
        if str(p.get("status", "open")).lower() != "closed":
            continue
        closed = str(p.get("closedAt") or p.get("closedAtTs") or "")
        if closed[:10] != today:
            continue
        total += _usd(p.get("realizedUsdc") or p.get("realizedUsd"))
    return total


def risk_kill_switches(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate the two kill switches:
      a) DAILY LOSS  - equity (cash + open marks) is -10% vs dayStartEquity,
                       OR realizedToday is <= -10% of dayStartEquity (whichever
                       is provided). Breach => halt new entries for the day.
      b) DRAWDOWN    - any open position <= -45% from entry => HARD REVIEW flag
                       (never an auto-sell: a -45% meme can be dust; a human or
                       agent decision is required before touching it).
    """
    state = state or _STATE
    snap = portfolio_snapshot(state)
    day_start = _usd(state.get("dayStartEquity"))
    flags: List[str] = []
    out: Dict[str, Any] = {"dailyLoss": {"armed": False}, "drawdownFlags": [],
                           "haltNewEntries": False, "flags": flags}

    if day_start > 0:
        equity_now = snap["equityUsd"]
        pnl_from_start = (equity_now - day_start) / day_start
        if state.get("realizedToday") is not None:
            realized = _usd(state.get("realizedToday"))
        else:
            realized = _realized_today(state)
        breached = pnl_from_start <= DAILY_LOSS_LIMIT_PCT or \
                   (day_start > 0 and realized / day_start <= DAILY_LOSS_LIMIT_PCT)
        out["dailyLoss"] = {"armed": True, "dayStartEquityUsd": _round(day_start),
                            "equityNowUsd": _round(equity_now),
                            "pnlVsStartPct": _round(pnl_from_start * 100, 2),
                            "realizedTodayUsd": _round(realized),
                            "limitPct": DAILY_LOSS_LIMIT_PCT * 100,
                            "breached": bool(breached)}
        if breached:
            out["haltNewEntries"] = True
            flags.append("DAILY LOSS LIMIT -10% breached: halt new entries today")
    else:
        out["dailyLoss"]["reason"] = "no dayStartEquity in state - switch unarmed"

    for r in snap["positions"]:
        if r.get("pnlPct") is not None and r["pnlPct"] <= DRAWDOWN_HARD_FLAG_PCT * 100:
            out["drawdownFlags"].append({
                "positionId": r["id"], "symbol": r["symbol"], "chain": r["chain"],
                "pnlPct": r["pnlPct"], "valueUsd": r["valueUsd"],
                "severity": "HARD REVIEW",
                "action": "no auto-sell: review liquidity, holders, narrative decay now"})
            flags.append("position %s is -%.0f%%: HARD REVIEW" % (r["symbol"], -r["pnlPct"]))
    out["flags"] = flags
    return out



# ---------------------------------------------------------------------------
# One-call advisory bundle for Risk / Execution agents
# ---------------------------------------------------------------------------
def all_recommendations(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run every manager check on the current state and return one bundle:

        {
          "ok": bool,            # False if ANY red flag / trigger / breach exists
          "asOf": iso,
          "snapshot": {...},     # normalized metrics (see portfolio_snapshot)
          "entrySizing": {...},  # regime-aware size for the next meme
          "profitTaking": [ ... per open position ... ],
          "rebalance": {...},    # triggers + concrete sell actions
          "killSwitches": {...}, # daily-loss + drawdown flags
          "summary": [ human-readable one-liners ... ],
        }
    """
    state = state or _STATE
    snap = portfolio_snapshot(state)
    regime = str(state.get("regime") or state.get("phase") or "Neutral")

    pt = []
    for r in snap["positions"]:
        raw = next((p for p in state.get("positions") or []
                    if str(p.get("id")) == str(r["id"])), r)
        pt.append(profit_taking(raw))

    rb = rebalance(state)
    ks = risk_kill_switches(state)

    summary = list(snap["warnings"]) + list(rb["triggers"]) + list(ks["flags"])
    if not summary:
        summary.append("within limits: cash %.0f%% / meme %.0f%%" % (snap["cashPct"], snap["memePct"]))

    sizing = sizing_for_regime(regime, equity=snap["equityUsd"], state=state)
    if not sizing.get("ok"):
        summary.append(sizing.get("reason"))

    return {
        "ok": snap["ok"] and rb["ok"] and not ks["flags"] and not ks["haltNewEntries"],
        "asOf": snap["asOf"],
        "snapshot": snap,
        "entrySizing": sizing,
        "profitTaking": pt,
        "rebalance": rb,
        "killSwitches": ks,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Example usage (no real balances are hardcoded anywhere in this module)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    demo = {
        "asOf": "2026-09-04T00:00:00Z",
        "regime": "Greed",
        "cash": 34.0,                       # 34% cash after the demo buys below
        "dayStartEquity": 100.0,
        "positions": [
            {"id": "p1", "symbol": "PEPE", "chain": "solana", "narrative": "frogs",
             "qty": 5_000_000, "costUsdc": 12.0, "currentPriceUsd": 0.0000042,
             "marketValueUsd": 21.0, "status": "open", "openedAt": "2026-09-04T08:00:00Z"},
            {"id": "p2", "symbol": "FROGE", "chain": "solana", "narrative": "frogs",
             "qty": 2_000_000, "costUsdc": 10.0, "marketValueUsd": 12.0,
             "status": "open", "openedAt": "2026-09-04T08:10:00Z"},
            {"id": "p3", "symbol": "DOGE2", "chain": "solana", "narrative": "dogs",
             "qty": 1_000_000, "costUsdc": 15.0, "marketValueUsd": 33.0,
             "status": "open", "openedAt": "2026-09-04T08:20:00Z"},
            {"id": "p4", "symbol": "DUSTY", "chain": "solana", "narrative": "dogs",
             "qty": 500_000, "costUsdc": 9.0, "marketValueUsd": 4.0,   # -55% drawdown demo
             "status": "open", "openedAt": "2026-09-04T08:30:00Z"},
        ],
    }
    set_state(demo)
    print(json.dumps(all_recommendations(demo), indent=2))

