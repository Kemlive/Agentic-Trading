#!/usr/bin/env python3
"""DESK SLA AUDIT - the manager card the boss watches.
Answers: is the desk producing? How long idle? What phase tactic is active?
Usage: python3 scripts/sla-audit.py [--json]
Exit 0 = healthy posture; 1 = RED flags (needs boss attention)."""
import argparse, datetime, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso_to_ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc)
    card = {"asOf": now.isoformat(), "flags": [], "warnings": []}

    # --- live lane state ---
    st = {}
    try:
        st = json.load(open(os.path.join(ROOT, "data", "live", "autopilot.json")))
    except Exception:
        card["warnings"].append("autopilot.json unreadable")
    card["lossStreak"] = st.get("lossStreak", 0)
    card["dryRuns"] = int(st.get("emptyRuns", 0))
    cd = float(st.get("cooldownUntil") or 0)
    card["cooldownActive"] = cd > now.timestamp()
    if card["cooldownActive"]:
        card["warnings"].append("6h cooldown active (2 straight stop-outs)")

    # --- active market phase (single source: latest scanner file) ---
    reg = {}
    try:
        files = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")))
        reg = (json.load(open(files[-1])) or {}).get("regime") or {}
    except Exception:
        pass
    card["phase"] = {"label": reg.get("label"), "mode": reg.get("mode"), "note": reg.get("note"),
                     "bar": reg.get("bar")}

    # --- performance: closed trades + last action ---
    holds = {"positions": []}
    try:
        holds = json.load(open(os.path.join(ROOT, "data", "live", "holdings.json")))
    except Exception:
        pass
    closed = [p for p in holds.get("positions", []) if p.get("status") == "closed"]
    card["openPositions"] = len([p for p in holds.get("positions", []) if p.get("status") == "open"])
    realized = sum(float(p.get("realizedUsdc") or 0) for p in closed)
    card["realizedUsdcAllTime"] = round(realized, 2)
    today_key = now.strftime("%Y-%m-%d")
    today = [p for p in closed if str(p.get("closedAt", ""))[:10] == today_key]
    card["realizedUsdcToday"] = round(sum(float(p.get("realizedUsdc") or 0) for p in today), 2)
    last_ts = max([iso_to_ts(p.get("closedAt")) for p in closed] or [0.0])
    card["lastClosedAt"] = datetime.datetime.fromtimestamp(last_ts, datetime.timezone.utc).isoformat() if last_ts else None
    idle_h = (now.timestamp() - last_ts) / 3600.0 if last_ts else None
    card["hoursSinceLastClose"] = round(idle_h, 1) if idle_h is not None else None

    # --- boss flags ---
    if idle_h is not None and idle_h > 24:
        card["flags"].append("🔥 no close in >24h")
    if idle_h is not None and idle_h > 48:
        card["flags"].append("🚨 no close in >48h - escalate")
    if card["dryRuns"] >= 5:
        card["flags"].append("🕸️ relief net engaged (dry tape)")
    if card.get("cooldownActive"):
        card["flags"].append("🧊 cooldown")
    if not closed:
        card["flags"].append("no closed trades in record yet")

    if a.json:
        print(json.dumps(card, indent=2))
    else:
        print("DESK SLA CARD  %s" % now.strftime("%Y-%m-%d %H:%M UTC"))
        print("  market phase : %s -> %s" % (card["phase"].get("label"), card["phase"].get("mode")))
        print("                 %s" % card["phase"].get("note"))
        print("  open pos     : %d" % card["openPositions"])
        print("  dry runs     : %d (relief net engages at 5)" % card["dryRuns"])
        print("  idle since   : %s (%.1fh)" % (card["lastClosedAt"], card["hoursSinceLastClose"] if card["hoursSinceLastClose"] is not None else -1))
        print("  realized     : today $%.2f | all-time $%.2f" % (card["realizedUsdcToday"], card["realizedUsdcAllTime"]))
        if card["flags"]:
            print("  FLAGS:")
            for fl in card["flags"]:
                print("    - %s" % fl)
        else:
            print("  posture      : healthy")
    return 1 if card["flags"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
