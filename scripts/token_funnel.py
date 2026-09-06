#!/usr/bin/env python3
"""token_funnel.py — unified DATA-FEED -> SCAN -> FUNNEL aggregator.
Ingests every discovery/scan artifact into ONE normalized pool and stages each token:
  DISCOVERED (feed tier / watch) -> QUALIFIED (pons/live venues, fills seen)
  -> ACTIONABLE (fresh $5 PASS right now). Writes data/live/feed/funnel.json.
Read-only: never moves funds. Resilient to missing/reshaped inputs."""
import datetime, json, os, glob

ROOT = "/Users/earn/Agentic-Trading"
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")

def read(p, d=None):
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return d

def rows_of(container):
    if isinstance(container, list): return container
    if isinstance(container, dict):
        for k in ("rows", "results", "top", "positions"):
            if isinstance(container.get(k), list): return container[k]
    return []

def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pool = {}  # addr -> record
    src_stats = {}

    def add(addr, sym, source, tier=None, extra=None):
        if not isinstance(addr, str) or not addr.lower().startswith("0x"):
            return
        a = addr.lower()
        rec = pool.setdefault(a, {"address": a, "syms": [], "sources": set(), "tiers": set(), "stage": "DISCOVERED"})
        if sym: rec["syms"].append(str(sym)[:24])
        rec["sources"].add(source); src_stats[source] = src_stats.get(source, 0) + 1
        if tier: rec["tiers"].add(str(tier))
        if extra: rec.update({k: v for k, v in extra.items() if v is not None})

    # 1) feed registry top (robinhood + solana) -> DISCOVERED
    coins = read(os.path.join(FD, "coins.json"), {})
    for chain in ("robinhood", "solana"):
        for r in rows_of(((coins.get("top") or {}).get(chain) or [])):
            add(r.get("key"), r.get("sym"), "feed:" + chain, tier=r.get("topTier"),
                extra={"score": r.get("score"), "t5": r.get("t5"), "t60": r.get("t60"), "u60": r.get("u60")})

    # 2) rh alpha clusters (symbols only when address present)
    alpha = read(os.path.join(FD, "rh_alpha.json"), {})
    for c in rows_of(alpha.get("clusters")):
        if isinstance(c, dict):
            for item in rows_of(c.get("members") if isinstance(c.get("members"), list) else []):
                add(item.get("token") or item.get("address"), item.get("symbol") or c.get("symbol"), "rh-alpha", tier="cluster")

    # 3) pump-scan (SOL) newest -> DISCOVERED/QUALIFIED
    psf = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")), reverse=True)
    if psf:
        pscan = read(psf[0], {})
        for r in rows_of(pscan.get("phases")) + rows_of(pscan):
            if isinstance(r, dict):
                for k in ("mint", "token", "address"):
                    a = r.get(k)
                    if a:
                        add(a, r.get("symbol") or r.get("sym"), "pump-scan", tier=r.get("phase"),
                            extra={"bs": r.get("bs"), "liq": r.get("liq")})
                        break

    # 4) pons-live-fresh -> ACTIONABLE (fresh $5 PASS), plus its stale list
    pf = read(os.path.join(FD, "pons-live-fresh.json"), {})
    for r in rows_of(pf.get("rows")):
        add(r.get("token"), None, "pons-live-fresh", tier="phase0",
            extra={"curve": r.get("curve"), "type": r.get("type"), "impactPct": r.get("impactPct")})
        a = r.get("token", "").lower()
        if a in pool: pool[a]["stage"] = "ACTIONABLE"
    for s in rows_of(pf.get("stale")):
        add(s.get("token"), None, "pons-live-stale", tier="stale")

    # 5) rh-potential tiers add symbol context (no stage change)
    rp = read(os.path.join(FD, "rh-potential.json"), {})
    for tier, lst in (rp.get("tiers") or {}).items():
        for r in rows_of(lst):
            a = (r.get("key") or "")
            if a.lower() in pool:
                pool[a.lower()]["tiers"].add("rh:" + str(tier))

    # finalize
    out_rows = []
    for a, rec in pool.items():
        rec["sources"] = sorted(rec["sources"]); rec["tiers"] = sorted(rec["tiers"])
        rec["syms"] = sorted(set(rec["syms"]))[:4]
        out_rows.append(rec)
    out_rows.sort(key=lambda x: (-(1 if x["stage"] == "ACTIONABLE" else 0),
                                 -(1 if x["stage"] == "QUALIFIED" else 0), x["address"]))
    counts = {"ACTIONABLE": sum(1 for r in out_rows if r["stage"] == "ACTIONABLE"),
              "QUALIFIED": sum(1 for r in out_rows if r["stage"] == "QUALIFIED"),
              "DISCOVERED": sum(1 for r in out_rows if r["stage"] == "DISCOVERED")}
    funnel = {"asOf": now, "total": len(out_rows), "counts": counts, "bySource": dict(sorted(src_stats.items())), "rows": out_rows[:600]}
    out = os.path.join(FD, "funnel.json")
    with open(out + ".tmp", "w") as fh: json.dump(funnel, fh, indent=1)
    os.replace(out + ".tmp", out)
    print("[FUNNEL] total=%d ACTIONABLE=%d QUALIFIED=%d DISCOVERED=%d src=%s" % (
        len(out_rows), counts["ACTIONABLE"], counts["QUALIFIED"], counts["DISCOVERED"],
        {k: v for k, v in list(src_stats.items())[:8]}))

if __name__ == "__main__":
    main()
