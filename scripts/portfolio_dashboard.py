#!/usr/bin/env python3
"""
portfolio_dashboard.py - Agentic Trading PORTFOLIO MANAGER dashboard (local).

Lets the boss see every managed portfolio and ADD WALLETS to any portfolio
("add wallet" button). Read-only over money - it never signs or moves funds.

Run:  python3 scripts/portfolio_dashboard.py        # http://127.0.0.1:8125
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import portfolio_state  # noqa: E402
import portfolio_wallets  # noqa: E402

PORT = int(os.getenv("PORTFOLIO_DASH_PORT", "8125"))

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<title>Agentic Trading - Portfolio Manager</title><style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:30px auto;max-width:1000px;padding:0 16px;color:#111}
h1{font-size:20px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.card{border:1px solid #ddd;border-radius:10px;padding:14px}
.card h3{margin:0 0 6px;font-size:15px}.muted{color:#666;font-size:12px}
.big{font-size:22px;font-weight:700}
.row{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0} input,select{flex:1;min-width:120px;padding:8px}
button{padding:9px 16px;border:0;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer}
#msg{margin:10px 0;font-size:13px}</style></head><body>
<h1>Portfolio Manager (Agentic Trading)</h1>
<div id="msg">Loading…</div>
<h3>Managed portfolios</h3><div id="grid" class="grid"></div>
<hr/>
<h3>➕ Add Wallet</h3>
<div class="row">
 <input id="pf" placeholder="portfolio id (existing, or type a NEW one)" value="primary"/>
 <input id="label" placeholder="wallet label (e.g. Alt SOL hot)"/>
 <select id="chain"><option>solana</option><option>base</option><option>ethereum</option><option>bsc</option></select>
 <select id="type"><option value="hot">hot</option><option value="vault">vault</option><option value="safe">safe</option><option value="eoa">eoa</option><option value="other">other</option></select>
 <input id="addr" placeholder="address (0x… for EVM, base58 for Solana)" style="min-width:280px"/>
</div>
<button onclick="addWallet()">Add Wallet</button>
<script>
async function load(){
  const r=await fetch('/api/state'); const data=await r.json();
  document.getElementById('grid').innerHTML='';
  for(const s of data.states){
    const c=s&&s.error?'<span class="muted">'+s.error+'</span>':
      '<div class="big">$'+Number(s.usdcTotal||0).toFixed(2)+'</div>'+
      '<div class="muted">lanes: '+JSON.stringify(s.cashByLane||{})+ (s.meta&&s.meta.note?'<br>'+s.meta.note:'')+
      (s.regime?'<br>regime: '+s.regime:'')+'</div>';
    document.getElementById('grid').insertAdjacentHTML('beforeend',
      '<div class="card"><h3>'+s.portfolio+' · '+(s.label||s.portfolio)+'</h3>'+c+'</div>');
  }
  document.getElementById('msg').textContent=data.message||'';
}
async function addWallet(){
  const body={portfolio:pf.value.trim(),label:label.value.trim(),chain:chain.value,type:type.value,address:addr.value.trim()};
  const r=await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json(); document.getElementById('msg').textContent=d.message||d.error||'added';
  if(!d.error){ pf.value='';label.value='';addr.value=''; load(); }
}
load();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype="application/json"):
        body = json.dumps(obj).encode() if not isinstance(obj, str) else obj.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, PAGE, "text/html")
        if self.path == "/api/state":
            states = []
            for pid in portfolio_state.list_portfolios():
                try:
                    states.append(portfolio_state.portfolio_state(pid, live=True))
                except Exception as e:
                    states.append({"portfolio": pid, "error": str(e)[:120]})
            return self._send(200, {"states": states, "message": "live"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/add":
            try:
                body = json.loads(urllib.parse.unquote(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()))
            except Exception:
                body = {}
            try:
                r = portfolio_wallets.add_wallet(
                    body.get("label", "new wallet"), body.get("chain", "solana"),
                    body.get("type", "other"), body.get("address", ""),
                    portfolio=body.get("portfolio", "primary"),
                    new_portfolio=body.get("new_portfolio"))
                return self._send(200, {"ok": True, **r})
            except Exception as e:
                return self._send(400, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("Portfolio Manager dashboard: http://127.0.0.1:%d (Ctrl-C to stop)" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
