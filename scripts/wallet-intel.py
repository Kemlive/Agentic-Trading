#!/usr/bin/env python3
"""Wallet intelligence scanner for Agentic-Trading.

Reads FULL wallet picture (native + token balances, transaction/trade history)
across EVM chains using keyless providers (Blockscout v2 + public RPCs +
Blockchair for Ethereum). No API keys required. Works regardless of balance.

Usage:
  python3 scripts/wallet-intel.py <0xaddress> [tx_limit] [--json]
"""
import json
import sys
import urllib.request

ADDR = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 5
AS_JSON = "--json" in sys.argv

CHAINS = [
    {"name": "Ethereum", "sym": "ETH", "bs": "eth.blockscout.com",
     "bc": "ethereum", "rpc": "https://ethereum-rpc.publicnode.com",
     "explorer": "etherscan.io", "chainId": 1},
    {"name": "Base", "sym": "ETH", "bs": "base.blockscout.com",
     "rpc": "https://mainnet.base.org", "explorer": "basescan.org", "chainId": 8453},
    {"name": "Polygon", "sym": "POL", "bs": "polygon.blockscout.com",
     "rpc": "https://polygon.drpc.org", "explorer": "polygonscan.com", "chainId": 137},
    {"name": "Arbitrum", "sym": "ETH", "bs": "arbitrum.blockscout.com",
     "rpc": "https://arb1.arbitrum.io/rpc", "explorer": "arbiscan.io", "chainId": 42161},
    {"name": "Optimism", "sym": "ETH", "bs": "optimism.blockscout.com",
     "rpc": "https://mainnet.optimism.io", "explorer": "optimistic.etherscan.io", "chainId": 10},
    {"name": "BNB Chain", "sym": "BNB", "bs": None,
     "rpc": "https://bsc-dataseed.binance.org", "explorer": "bscscan.com", "chainId": 56},
    {"name": "Scroll", "sym": "ETH", "bs": "scroll.blockscout.com",
     "rpc": "https://rpc.scroll.io", "explorer": "scrollscan.com", "chainId": 534352},
    {"name": "zkSync Era", "sym": "ETH", "bs": "zksync.blockscout.com",
     "rpc": "https://mainnet.era.zksync.io", "explorer": "era.zksync.network", "chainId": 324},
    {"name": "Gnosis", "sym": "xDAI", "bs": "gnosis.blockscout.com",
     "rpc": "https://rpc.gnosischain.com", "explorer": "gnosisscan.io", "chainId": 100},
    {"name": "Celo", "sym": "CELO", "bs": "celo.blockscout.com",
     "rpc": "https://forno.celo.org", "explorer": "celoscan.io", "chainId": 42220},
    {"name": "Avalanche", "sym": "AVAX", "bs": None,
     "rpc": "https://api.avax.network/ext/bc/C/rpc", "explorer": "snowtrace.io", "chainId": 43114},
    {"name": "Fantom", "sym": "FTM", "bs": None,
     "rpc": "https://rpc.ftm.tools", "explorer": "ftmscan.com", "chainId": 250},
    {"name": "Linea", "sym": "ETH", "bs": None,
     "rpc": "https://rpc.linea.build", "explorer": "lineascan.build", "chainId": 59144},
    {"name": "Mantle", "sym": "MNT", "bs": None,
     "rpc": "https://rpc.mantle.xyz", "explorer": "mantlescan.xyz", "chainId": 5000},
    {"name": "Polygon zkEVM", "sym": "POL", "bs": None,
     "rpc": "https://zkevm-rpc.com", "explorer": "zkevm.polygonscan.com", "chainId": 1101},
    {"name": "Cronos", "sym": "CRO", "bs": None,
     "rpc": "https://evm.cronos.org", "explorer": "cronoscan.com", "chainId": 25},
    {"name": "Blast", "sym": "ETH", "bs": None,
     "rpc": "https://rpc.blast.io", "explorer": "blastscan.io", "chainId": 81457},
    {"name": "Aurora", "sym": "ETH", "bs": None,
     "rpc": "https://mainnet.aurora.dev", "explorer": "aurorascan.dev", "chainId": 1313161554},
]


def http_get(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "agentic-trading/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def rpc_call(rpc, method, params, timeout=6):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(rpc, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("result")


def wei_to_units(wei, decimals):
    try:
        return int(wei) / (10 ** decimals)
    except Exception:
        return None


def native_usd(rate, native):
    return (float(rate) * native) if (rate and native is not None) else None


def scan_blockscout(c):
    host = c["bs"]
    base = f"https://{host}/api/v2"
    out = {"native": None, "rate": None, "tokens": [], "txs": [], "tx_count": None, "ok": False}
    try:
        info = http_get(f"{base}/addresses/{ADDR}")
        rate = info.get("exchange_rate")
        out["rate"] = rate
        cb = info.get("coin_balance")
        if cb:
            out["native"] = wei_to_units(cb, 18)
        try:
            tb = http_get(f"{base}/addresses/{ADDR}/token-balances")
            for t in tb or []:
                tok = t.get("token") or {}
                sym = tok.get("symbol") or "?"
                try:
                    dec = int(tok.get("decimals") or 18)
                except Exception:
                    dec = 18
                val = wei_to_units(t.get("value"), dec)
                t_rate = tok.get("exchange_rate")
                out["tokens"].append({
                    "symbol": sym, "name": tok.get("name"),
                    "address": tok.get("address_hash"),
                    "balance": val,
                    "usd": (float(val) * float(t_rate)) if (val is not None and t_rate) else None,
                })
        except Exception:
            pass
        try:
            txs = http_get(f"{base}/addresses/{ADDR}/transactions")
            items = txs.get("items") or []
            out["tx_count"] = txs.get("total")
            for tx in items[:LIMIT]:
                out["txs"].append({
                    "hash": tx.get("hash"),
                    "ts": tx.get("timestamp"),
                    "method": (tx.get("method") or "")[:40],
                    "from": ((tx.get("from") or {}).get("hash") or "")[:12],
                    "to": ((tx.get("to") or {}).get("hash") or "")[:12],
                    "value_units": wei_to_units(tx.get("value"), 18),
                    "status": tx.get("status"),
                })
        except Exception:
            pass
        out["ok"] = True
    except Exception:
        out["ok"] = False
    return out


def scan_rpc(c):
    try:
        wei = rpc_call(c["rpc"], "eth_getBalance", [ADDR, "latest"])
        return wei_to_units(wei, 18)
    except Exception:
        return None


def scan_blockchair(c, out):
    try:
        d = http_get(f"https://api.blockchair.com/{c['bc']}/dashboards/address/{ADDR}?limit={LIMIT}")
        a = d.get("data", {}).get(ADDR, {})
        info = a.get("address") or {}
        out["native"] = wei_to_units(info.get("balance"), 18)
        out["tx_count"] = info.get("transaction_count")
        out["received_approx"] = info.get("received_approximate")
        out["spent_approx"] = info.get("spent_approximate")
        out["calls"] = a.get("calls") or []
    except Exception:
        pass
    return out


def main():
    if not ADDR.startswith("0x") or len(ADDR) != 42:
        print("usage: python3 scripts/wallet-intel.py <0xaddress> [tx_limit] [--json]")
        sys.exit(1)
    report = {"address": ADDR, "chains": []}
    total_usd = 0.0
    lines = []
    for c in CHAINS:
        row = {"chain": c["name"], "symbol": c["sym"], "explorer": c["explorer"]}
        bs = scan_blockscout(c) if c.get("bs") else {"ok": False}
        native = bs.get("native")
        if native is None:
            native = scan_rpc(c)
        row["native"] = native
        rate = bs.get("rate")
        row["nativeUsd"] = native_usd(rate, native)
        row["tokens"] = bs.get("tokens", [])
        row["txCount"] = bs.get("tx_count")
        row["txs"] = bs.get("txs", [])
        if c.get("bc"):
            scan_blockchair(c, row)
        if row["nativeUsd"]:
            total_usd += row["nativeUsd"]
        for t in row["tokens"]:
            if t.get("usd") and t.get("balance"):
                total_usd += t["usd"]
        row["source"] = "blockscout+rpc" if bs.get("ok") else ("rpc only" if native is not None else "unreachable")
        report["chains"].append(row)
        if AS_JSON:
            continue
        lines.append(f"\n== {row['chain']} [{row['source']}] ==")
        lines.append(f"  native: {row['native'] if row['native'] is not None else 'n/a'} {c['sym']}"
                     + (f" (~${row['nativeUsd']:.2f})" if row.get("nativeUsd") else ""))
        for t in row["tokens"]:
            if not t.get("balance"):
                continue
            lines.append(f"  token: {t['symbol']} balance={t['balance']}"
                         + (f" (~${t['usd']:.2f})" if t.get("usd") else ""))
        if row.get("txCount") is not None:
            lines.append(f"  transactions: {row['txCount']}")
        for tx in row["txs"]:
            lines.append(f"    tx {tx['ts']} {tx['method'] or 'call'} value={tx['value_units']} {tx['hash'][:18]}...")
    report["totalUsdEstimate"] = round(total_usd, 2)
    if not AS_JSON:
        print("\n".join(lines))
        print(f"\nTOTAL ~USD (with explorer rates): ${report['totalUsdEstimate']:.2f}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()


