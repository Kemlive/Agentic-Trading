#!/usr/bin/env python3
"""token_funnel.py v2 — chain-aware feed->scan->funnel aggregator (EVM + SOLANA).
Stages: ACTIONABLE (fresh $5 PASS now) / QUALIFIED (venue-scan evidence) / DISCOVERED (feed).
Read-only."""
import datetime, json, os, glob, re

ROOT = "/Users/earn/Agentic-Trading"
LIVE = os.path.join(ROOT, "data", "live")
FD = os.path.join(LIVE, "feed")
SOL_ID = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

def read(p, d=None):
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return d

def norm(addr):
    if not isinstance(addr, str):
        return None
    a = addr.strip()
    if a.lower().startswith("0x"):
        return ("evm", a.lower())
    if SOL_ID.match(a):
        return ("solana", a)
    return None

def rows_of(c):
    if isinstance(c, list): return c
    if isinstance(c, dict):
        for k in ("rows", "results", "positions", "tokens"):
            if isinstance(c.get(k), list): return c[k]
    return []

def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pool = {}; src_stats = {}

    def add(addr, sym, source, tier=None, extra=None):
        n = norm(addr)
        if not n: return
        chain, key = n; k = chain + ":" + key
        rec = pool.setdefault(k, {"id": key, "chain": chain, "syms": [], "sources": [], "tiers": [], "stage": "DISCOVERED"})
        if sym: rec["syms"].append(str(sym)[:24])
        if source not in rec["sources"]: rec["sources"].append(source)
        src_stats[source] = src_stats.get(source, 0) + 1
        if tier: rec["tiers"].append(str(tier))
        if extra: rec.update({kk: vv for kk, vv in extra.items() if vv is not None})
        return k

    def stage_up(k, st):
        if k in pool and st == "ACTIONABLE": pool[k]["stage"] = st
        elif k in pool and st == "QUALIFIED" and pool[k]["stage"] == "DISCOVERED": pool[k]["stage"] = st

    # ---- sources ----
    coins = read(os.path.join(FD, "coins.json"), {})
    for chain in ("robinhood", "solana"):
        for r in rows_of(((coins.get("top") or {}).get(chain) or [])):
            add(r.get("key"), r.get("sym"), "feed:" + chain, tier=r.get("topTier"),
                extra={"score": r.get("score"), "t5": r.get("t5"), "t60": r.get("t60"), "u60": r.get("u60")})

    alpha = read(os.path.join(FD, "rh_alpha.json"), {})
    for c in rows_of(alpha.get("clusters")):
        if isinstance(c, dict):
            members = c.get("members") if isinstance(c.get("members"), list) else []
            for it in rows_of(members):
                add(it.get("token") or it.get("address"), it.get("symbol") or c.get("symbol"), "rh-alpha", tier="cluster")

    psf = sorted(glob.glob(os.path.join(ROOT, "data", "pump-scan-*.json")), reverse=True)
    if psf:
        pscan = read(psf[0], {})
        for r in rows_of(pscan) + rows_of(pscan.get("phases")):
            if isinstance(r, dict):
                for k in ("mint", "token", "address", "id"):
                    if r.get(k):
                        add(r[k], r.get("symbol") or r.get("sym"), "pump-scan", tier=r.get("phase"),
                            extra={"bs": r.get("bs"), "liq": r.get("liq")}); break

    wl = read(os.path.join(LIVE, "fast-watchlist.json"), {})
    names = wl.get("names") or {}
    for m in rows_of(wl) or (wl.get("tokens") or []):
        k = add(m, names.get(m) if isinstance(names, dict) else None, "fast-watchlist", tier="sol-watch")
        if k: stage_up(k, "QUALIFIED")

    for p in rows_of(read(os.path.join(LIVE, "fastlane-positions.json"), {})):
        k = add(p.get("mint"), p.get("symbol"), "fastlane:" + str(p.get("status", "hist")), tier=p.get("status"),
                extra={"realizedUsdc": p.get("realizedUsdc"), "realizedPct": p.get("realizedPct")})
        if k: stage_up(k, "QUALIFIED")

    pf = read(os.path.join(FD, "pons-live-fresh.json"), {})
    for r in rows_of(pf.get("rows")):
        k = add(r.get("token"), None, "pons-live-fresh", tier="phase0",
                extra={"curve": r.get("curve"), "type": r.get("type"), "impactPct": r.get("impactPct")})
        if k: stage_up(k, "ACTIONABLE")
    for s in rows_of(pf.get("stale")):
        k = add(s.get("token"), None, "pons-live-stale", tier="stale")
        if k: stage_up(k, "QUALIFIED")

    rp = read(os.path.join(FD, "rh-potential.json"), {})
    for tier, lst in (rp.get("tiers") or {}).items():
        for r in rows_of(lst):
            k = add(r.get("key"), None, "rh-potential", tier="rh:" + str(tier))
    # ---- fillability status maps (venue-scan evidence -> QUALIFIED) ----
    fb = {}
    for pat, field in [("research/pons-size-rank-*.json", "rows"), ("research/pons-curve-fillability-*.json", "rows"),
                       ("research/pons-usdg-pair-replay-*.json", "rows"), ("research/fillability_scan_2026*.json", "rows")]:
        files = sorted(glob.glob(os.path.join(ROOT, pat)))
        if not files: continue
        j = read(files[-1], {})
        for r in rows_of(j.get(field) if isinstance(j, dict) else j):
            if not isinstance(r, dict): continue
            tk = r.get("token") or r.get("address")
            n = norm(tk)
            if n: fb[n[0] + ":" + n[1]] = str(r.get("status") or r.get("verdict") or "")[:20]

    # ---- finalize ----
    for k, rec in pool.items():
        rec["sources"] = sorted(set(rec["sources"]))
        rec["tiers"] = sorted(set(rec["tiers"]))
        rec["syms"] = sorted(set(rec["syms"]))[:4]
        if k in fb:
            rec["fillability"] = fb[k]
            stage_up(k, "QUALIFIED")

    out_rows = sorted(pool.values(), key=lambda x: (-(x["stage"] == "ACTIONABLE"), -(x["stage"] == "QUALIFIED"), x["chain"], x["id"]))
    counts = {s: sum(1 for r in out_rows if r["stage"] == s) for s in ("ACTIONABLE", "QUALIFIED", "DISCOVERED")}
    bychain = {}
    for r in out_rows: bychain[r["chain"]] = bychain.get(r["chain"], 0) + 1
    funnel = {"asOf": now, "total": len(out_rows), "counts": counts, "byChain": bychain,
              "bySource": dict(sorted(src_stats.items())), "rows": out_rows[:800]}
    out = os.path.join(FD, "funnel.json")
    with open(out + ".tmp", "w") as fh: json.dump(funnel, fh, indent=1)
    os.replace(out + ".tmp", out)
    print("[FUNNEL] total=%d ACTIONABLE=%d QUALIFIED=%d DISCOVERED=%d chains=%s src=%s" % (
        len(out_rows), counts["ACTIONABLE"], counts["QUALIFIED"], counts["DISCOVERED"],
        bychain, dict(list(src_stats.items())[:8])))

if __name__ == "__main__":
    main()
