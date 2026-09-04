#!/usr/bin/env python3
"""pad-radar.py — OWN-DATA TOKEN RADAR (we build the feed; no paid subscriptions).

We trade the TOKEN only (USDC/SOL in, tokens out, on Solana). This radar fuses
independent on-chain angles for a launchpad token and funnels them to the bots:
  A1 CHAIN-ACTIVITY : recent txs on the mint + freshness (Solana RPC)
  A2 CHAIN-PRICE    : token price inferred from real swaps (token/SOL deltas)
  A4 DEX            : DexScreener, only if the pad posts on a standard DEX
Usage:
  python3 scripts/pad-radar.py <ca>
  python3 scripts/pad-radar.py          # runs all config longyourlongs.watch[] entries
"""
import os
import sys
import json
import time
import datetime
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPC = "https://api.mainnet-beta.solana.com"
CONFIG = os.path.join(ROOT, "data", "live", "launchpads.json")
OUTDIR = os.path.join(ROOT, "data", "live", "radar")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                                       "params": params}).encode(),
                                 headers={"content-type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read()).get("result")


def decode_price_tx(sig, mint):
    """Token/SOL exchange rate from a real swap tx (same-wallet legs)."""
    tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not tx:
        return None
    meta = tx.get("meta") or {}
    pre_sol = meta.get("preBalances") or []
    post_sol = meta.get("postBalances") or []
    pre_tok, post_tok = {}, {}
    for b in meta.get("preTokenBalances") or []:
        if b.get("mint") == mint:
            pre_tok[b["accountIndex"]] = float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
    for b in meta.get("postTokenBalances") or []:
        if b.get("mint") == mint:
            post_tok[b["accountIndex"]] = float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
    for i in set(pre_tok) | set(post_tok):
        td = post_tok.get(i, 0.0) - pre_tok.get(i, 0.0)
        sd = 0.0
        if i < len(pre_sol) and i < len(post_sol):
            sd = (post_sol[i] - pre_sol[i]) / 1e9
        if abs(td) > 1e-9 and sd != 0 and td * sd < 0:
            return abs(td / sd)
    return None


def angle_chain(mint):
    sigs = rpc("getSignaturesForAddress", [mint, {"limit": 15}]) or []
    now = time.time()
    fresh = sum(1 for s in sigs[:15] if s.get("err") is None
                and now - int(s.get("blockTime") or 0) < 3600)
    price = None
    for s in sigs:
        if s.get("err") is None:
            price = decode_price_tx(s["signature"], mint)
            if price:
                break
    return {"sigsRecent": len(sigs), "fresh1h": fresh,
            "lastSig": (sigs[0].get("signature") if sigs else None),
            "lastBlockTime": (sigs[0].get("blockTime") if sigs else None),
            "priceTokenPerSol": price}

def sol_usd():
    try:
        req = urllib.request.Request("https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112",
                                     headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        pr = [p for p in (d.get("pairs") or []) if p.get("chainId") == "solana"]
        return float(max(pr, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))["priceUsd"])
    except Exception:
        return None


def radar(ca):
    rec = {"ca": ca, "ts": NOW, "angles": {}}
    try:  # A4 dex (only if the pad posts on a standard DEX)
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.dexscreener.com/latest/dex/tokens/" + ca,
            headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read())
        pairs = d.get("pairs") or []
        if pairs:
            best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
            rec["angles"]["dex"] = {"px": best.get("priceUsd"),
                                    "liq": (best.get("liquidity") or {}).get("usd")}
    except Exception:
        pass
    ch = angle_chain(ca)  # A1 + A2
    rec["angles"]["chain"] = ch
    price_usd = None
    if ch.get("priceTokenPerSol"):
        sp = sol_usd()
        if sp:
            price_usd = ch["priceTokenPerSol"] * sp
            rec["angles"]["chain"]["priceUsd"] = price_usd
    rec["fused"] = {"ca": ca, "priceUsd": price_usd,
                    "fresh1h": ch.get("fresh1h"), "tradesRecent": ch.get("sigsRecent"),
                    "priceTokenPerSol": ch.get("priceTokenPerSol")}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, ca + ".json"), "w") as fh:
        json.dump(rec, fh, indent=2)
    with open(LOG, "a") as fh:
        fh.write(json.dumps({"event": "pad_radar", "ts": NOW, **rec["fused"]}) + "\n")
    return rec


def print_radar(rec):
    ch = rec["angles"].get("chain", {})
    px = rec["fused"].get("priceUsd")
    print("📡 TOKEN RADAR %s @ %s" % (rec["ca"][:12] + "…", NOW[:19]))
    print("   A1 activity : txs(recent)~%s fresh1h=%s lastSig=%s" %
          (ch.get("sigsRecent"), ch.get("fresh1h"), (ch.get("lastSig") or "")[:16]))
    print("   A2 price    : token/SOL=%.9g  → USD≈%s" %
          (ch.get("priceTokenPerSol") or 0, ("$%.8g" % px) if px else "n/a (no clean swap to decode yet)"))
    print("   saved -> data/live/radar/%s.json" % rec["ca"])


def main():
    args = sys.argv[1:]
    if args:
        print_radar(radar(args[0]))
        return
    cfg = json.load(open(CONFIG))
    watch = (cfg.get("pads", {}).get("longyourlongs", {}).get("watch")) or []
    if not watch:
        print("no CA given and no longyourlongs.watch[] in config")
        return
    for w in watch:
        print_radar(radar(w.get("mint") or w.get("ca")))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("pad-radar error:", e)

