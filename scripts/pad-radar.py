#!/usr/bin/env python3
"""pad-radar.py — OWN-DATA RADAR (we build the feed; never pay for a data subscription).

Fuses independent angles for one launchpad token into a radar record:
  A1 CHAIN-ACTIVITY : recent txs on the mint (Solana RPC signatures)
  A2 CHAIN-PRICE    : price inferred by decoding REAL swap txs (token/SOL deltas)
  A3 PERP-NAV       : Hyperliquid mark of the backing asset (public allMids)
  A4 DEX            : DexScreener, only when the pad posts on a standard DEX
Usage:
  python3 scripts/pad-radar.py <ca> [--asset SOL]
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
HL = "https://api.hyperliquid.xyz/info"
CONFIG = os.path.join(ROOT, "data", "live", "launchpads.json")
OUTDIR = os.path.join(ROOT, "data", "live", "radar")
LOG = os.path.join(ROOT, "logs", "trades.jsonl")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                                       "params": params}).encode(),
                                 headers={"content-type": "application/json", "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read()).get("result")


def hl_marks(assets):
    req = urllib.request.Request(HL, data=json.dumps({"type": "allMids"}).encode(),
                                 headers={"content-type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=12).read())
    return {a: d.get(a) for a in assets}


def decode_price_tx(sig, mint):
    tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not tx:
        return None
    meta = tx.get("meta") or {}
    # native SOL balances align by index with accountKeys
    pre_sol = meta.get("preBalances") or []
    post_sol = meta.get("postBalances") or []
    # token balances keyed by accountIndex -> uiAmount
    pre_tok = {}
    post_tok = {}
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
        if abs(td) > 1e-9 and sd != 0 and td * sd < 0:  # same wallet: got token, paid SOL (or reverse)
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

def radar(ca, asset=None, sol_px=None):
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
    if ch.get("priceTokenPerSol") and sol_px:
        price_usd = ch["priceTokenPerSol"] * sol_px
        rec["angles"]["chain"]["priceUsd"] = price_usd
    if asset:  # A3 perp NAV anchor
        mk = hl_marks([asset])
        rec["angles"]["perp"] = {"asset": asset, "mark": mk.get(asset),
                                 "note": "NAV anchor (perp moves the curve)"}
    rec["fused"] = {"ca": ca, "priceUsd": price_usd,
                    "fresh1h": ch.get("fresh1h"), "tradesRecent": ch.get("sigsRecent"),
                    "asset": asset,
                    "mark": (rec.get("angles", {}).get("perp") or {}).get("mark")}
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, ca + ".json"), "w") as fh:
        json.dump(rec, fh, indent=2)
    with open(LOG, "a") as fh:
        fh.write(json.dumps({"event": "pad_radar", "ts": NOW, **rec["fused"]}) + "\n")
    return rec


def print_radar(rec):
    ch = rec["angles"].get("chain", {})
    pp = rec["angles"].get("perp", {})
    px = rec["fused"].get("priceUsd")
    print("📡 RADAR %s @ %s" % (rec["ca"][:12] + "…", NOW[:19]))
    print("   A1 activity : trades(recent)~%s fresh1h=%s lastSig=%s" %
          (ch.get("sigsRecent"), ch.get("fresh1h"), (ch.get("lastSig") or "")[:16]))
    print("   A2 price    : token/SOL=%.9g  → USD≈%s" %
          (ch.get("priceTokenPerSol") or 0, ("$%.8g" % px) if px else "n/a (decode needed)"))
    if pp:
        print("   A3 perp     : %s mark=%s (NAV anchor)" % (pp.get("asset"), pp.get("mark")))
    print("   saved -> data/live/radar/%s.json" % rec["ca"])


def main():
    args = sys.argv[1:]
    ca = args[0] if args else None
    asset = args[args.index("--asset") + 1] if "--asset" in args else None
    sol_px = None
    try:
        sol_px = float(hl_marks(["SOL"]).get("SOL"))
    except Exception:
        pass
    if ca:
        print_radar(radar(ca, asset=asset, sol_px=sol_px))
        return
    cfg = json.load(open(CONFIG))
    watch = (cfg.get("pads", {}).get("longyourlongs", {}).get("watch")) or []
    if not watch:
        print("no CA given and no longyourlongs.watch[] in config")
        return
    for w in watch:
        print_radar(radar(w.get("mint") or w.get("ca"), asset=w.get("asset") or asset, sol_px=sol_px))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("pad-radar error:", e)

