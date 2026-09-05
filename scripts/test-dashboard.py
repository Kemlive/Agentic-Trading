#!/usr/bin/env python3
"""test-dashboard.py — DRY TEST HARNESS (never moves funds).

Verifies dashboard wiring after every change, per boss directive:
  render smoke · wallet snapshot · rebalance plan math · endpoint guards ·
  token-details resolvers. NO real sells/closes execute here.
"""
import os
import sys
import json
import importlib.util as _iu

ROOT = "/Users/earn/Agentic-Trading"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
s = _iu.spec_from_file_location("fd", os.path.join(ROOT, "scripts", "feed_dashboard.py"))
fd = _iu.module_from_spec(s)
s.loader.exec_module(fd)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print("   [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))


# 1) wallet snapshot + rebalance plan (read-only network)
snap = fd._pm_snapshot()
plan = fd._rebalance_plan(snap)
check("pm.snapshot", snap.get("equity") is not None and snap.get("coins") is not None,
      "equity=%s basePct=%s coins=%d" % (snap.get("equity"), snap.get("basePct"), len(snap.get("coins") or [])))
check("pm.plan.keys", isinstance(plan, dict) and "plan" in plan,
      "needUsd=%s totalSell=%s items=%d" % (plan.get("needUsd"), plan.get("totalSellUsd"), len(plan["plan"])))
for p in plan["plan"][:5]:
    check("pm.plan.item", p.get("mint") and p.get("value") and p.get("kind") in ("lane", "free"),
          "%s %s $%s" % (p.get("symbol"), p.get("kind"), p.get("value")))

# 2) endpoint guards (must refuse BEFORE any swap)
check("close.guard.invalid", (fd._close_position("bogus") or {}).get("error"),
      "invalid mint refused")
check("sell.guard.usdc", (fd._sell_token(fd.USDC_MINT) or {}).get("error"),
      "USDC sell refused")
lane_mint = next((c.get("mint") for c in snap.get("coins", []) if c.get("lane")), None)
if lane_mint:
    check("sell.guard.lane", "LANE" in str((fd._sell_token(lane_mint) or {}).get("error", "")),
          "lane mint %s blocked from direct sell" % lane_mint[:8])
else:
    check("sell.guard.lane", True, "no open lane coin in wallet snapshot")

# 3) token-details resolvers
t = fd.token_details("solana", (snap.get("coins") or [{}])[0].get("mint") or "So11111111111111111111111111111111111111112")
check("details.sol", "topHolders" in t, "keys=%d" % len(t))
g = fd.token_details("robinhood", "0x1b0e319c6a659f002271b69db8a7df2f911c153e")
check("details.rh", g.get("symbol") == "GME", "symbol=%s holders=%s" % (g.get("symbol"), g.get("holdersCount")))

# 4) render smoke on a minimal snapshot via cached data path
try:
    d = fd._cached_page_data() if hasattr(fd, "_cached_page_data") else fd.collect()
    html = fd.render(d)
    check("render.ok", html.startswith("<!doctype html>") and "LIVE POSITIONS" in html and "PORTFOLIO MANAGER" in html,
          "bytes=%d" % len(html))
    check("render.closeBtn", "close-pos" in html, "")
    check("render.rebalanceBtn", "act-reb" in html, "")
    check("render.confirmModal", "openConfirm" in html, "")
except Exception as e:
    check("render.ok", False, str(e)[:200])

# 5) vault/safe read-only snapshot
vts = fd._vault_snapshot()
check("vault.snapshot", isinstance(vts, list) and len(vts) >= 2,
      "rows=%d labels=%s" % (len(vts), [v.get("label") for v in vts][:4]))
check("vault.safeAddr", any(str(v.get("addr", "")).lower() == "0xb1acdaf72ca6648ddd54f5db85b9cf75d58f82b8" for v in vts),
      "EVM owner 0xB1AC… present")

fails = sum(0 if ok else 1 for _, ok, _ in results)
print("RESULT: %d/%d passed" % (len(results) - fails, len(results)))
sys.exit(1 if fails else 0)
