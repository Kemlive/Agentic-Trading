#!/usr/bin/env python3
"""cmc-feed.py - CoinMarketCap feed wrapper for the agent team.

Talks to the CoinMarketCap **MCP server** (https://mcp.coinmarketcap.com/mcp) using the key
already stored at ~/.config/agentic-trading/coinmarketcap.json (0600). No API key lives here.

Public helpers (all return plain dicts/lists, or {"error": ...} on failure):
  get_quote("BTC")               -> latest USD quote for a symbol or numeric CMC id
  get_metrics()                  -> global market dashboard (incl. Fear & Greed under ["sentiment"])
  fear_greed()                   -> quick {value, index} snapshot
  search("solana")               -> resolve symbol/name to CMC id
  get_trending()                 -> ranked narrative categories
  call(tool_name, args)          -> raw escape hatch to any CMC MCP tool

Usage:
  python3 scripts/cmc-feed.py quote BTC
  python3 scripts/cmc-feed.py quote 1027            # by numeric CMC id
  python3 scripts/cmc-feed.py metrics
  python3 scripts/cmc-feed.py fear-greed
  python3 scripts/cmc-feed.py search solana
  python3 scripts/cmc-feed.py trending
"""
import json
import os
import sys
import urllib.request

URL = "https://mcp.coinmarketcap.com/mcp"
CFG = os.path.expanduser("~/.config/agentic-trading/coinmarketcap.json")
PROTOCOL = "2025-03-26"


def _load_key():
    if not os.path.exists(CFG):
        raise RuntimeError("no CMC config at %s (add ~/.config/agentic-trading/coinmarketcap.json)" % CFG)
    return json.load(open(CFG)).get("apiKey") or ""


class CMCFeed:
    """Tiny MCP (streamable HTTP) client for the CoinMarketCap server."""

    def __init__(self):
        self._session = None
        self._key = _load_key()

    def _post(self, body):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-CMC-MCP-API-KEY": self._key,
        }
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            self._session = r.headers.get("Mcp-Session-Id") or self._session
            obj = {}
            for line in r.read().decode().splitlines():
                if line.startswith("data:"):
                    try:
                        obj = json.loads(line[5:])
                        break
                    except Exception:
                        continue
            return obj

    def _ready(self):
        if not self._session:
            self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                                   "clientInfo": {"name": "cmc-feed", "version": "1.0"}}})
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call(self, tool, arguments=None):
        """Call one CMC MCP tool; return the parsed payload (dict/list) or {"error": ...}."""
        try:
            self._ready()
            res = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                              "params": {"name": tool, "arguments": arguments or {}}})
        except Exception as e:
            return {"error": "cmc transport failure: %s" % e}
        if "error" in res:
            return {"error": json.dumps(res["error"])}
        return _extract(res.get("result", {}))


def _extract(result):
    """Pull the usable payload out of an MCP tool result."""
    content = result.get("content") or []
    if content and isinstance(content[0], dict):
        text = content[0].get("text")
        if text is not None:
            try:
                return json.loads(text)
            except Exception:
                return {"raw": text}
        sc = content[0].get("structuredContent")
        if sc is not None:
            return sc
    return result


def _resolve_id(feed, symbol):
    """Accept a numeric CMC id or resolve a symbol/name through search_cryptos."""
    if str(symbol).isdigit():
        return str(symbol)
    found = feed.call("search_cryptos", {"query": str(symbol)})
    if isinstance(found, dict) and "error" in found:
        return found
    rows = found if isinstance(found, list) else (found.get("rows") or found.get("data") or [])
    if not rows:
        return {"error": "unknown asset: %s" % symbol}
    row = rows[0] if isinstance(rows[0], dict) else {}
    return row.get("id")


def get_quote(symbol):
    """Latest USD quote for a symbol or numeric CMC id."""
    feed = CMCFeed()
    cid = _resolve_id(feed, symbol)
    if isinstance(cid, dict):
        return cid
    out = feed.call("get_crypto_quotes_latest", {"id": cid})
    if isinstance(out, list):
        return out[0] if out else {"error": "empty quote"}
    return out


def get_metrics():
    """Whole-crypto-market dashboard (market size, liquidity, sentiment incl Fear & Greed...)."""
    return CMCFeed().call("get_global_metrics_latest", {})


def fear_greed():
    """Quick {value, index} snapshot from the global dashboard."""
    m = get_metrics()
    fg = (m.get("sentiment") or {}).get("fear_greed") or {}
    cur = fg.get("current") or {}
    if not cur:
        return {"error": "fear & greed not present in metrics", "metrics_error": m.get("error")}
    return {"value": cur.get("value"), "index": cur.get("index"),
            "yesterday": (fg.get("history") or {}).get("yesterday")}


def search(query):
    """Resolve a name/symbol to CoinMarketCap id(s)."""
    return CMCFeed().call("search_cryptos", {"query": str(query)})


def get_trending():
    """Ranked trending narrative categories (aggregate mcap/volume + top coins per category)."""
    return CMCFeed().call("trending_crypto_narratives", {})


def call(tool, arguments=None):
    """Raw escape hatch: call any CMC MCP tool by name (see the 14 discovered tools)."""
    return CMCFeed().call(tool, arguments)


def _main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1].replace("-", "_")
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == "quote":
        if not arg:
            print("usage: cmc-feed.py quote <symbol-or-id>")
            return 1
        out = get_quote(arg)
    elif cmd == "metrics":
        out = get_metrics()
    elif cmd == "fear_greed":
        out = fear_greed()
    elif cmd == "search":
        out = search(arg) if arg else {"error": "usage: cmc-feed.py search <query>"}
    elif cmd == "trending":
        out = get_trending()
    else:
        out = call(cmd, {"query": arg} if arg else {})
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        raise

