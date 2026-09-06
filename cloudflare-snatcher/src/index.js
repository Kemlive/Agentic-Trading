// Agentic Snatcher - Cloudflare Worker (cron every 15 min, 24/7).
// Conservative rails (mirror local autopilot v1):
//   1 open position max, $1.50 size, USDC-leg only, reserve >= $15,
//   daily -10% kill, snatcher exits (stop/trail/bank/time), Telegram on every action.
import { Connection, Keypair, VersionedTransaction } from "@solana/web3.js";
import bs58 from "bs58";

const DEX = "https://api.dexscreener.com/latest/dex/tokens/";
const JUP = "https://api.jup.ag/swap/v1";

function heliusUrl(env) { return "https://mainnet.helius-rpc.com/?api-key=" + env.HELIUS_KEY; }

async function rpc(env, method, params) {
  const r = await fetch(heliusUrl(env), {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  return r.json();
}
async function tg(env, text) {
  try {
    await fetch("https://api.telegram.org/bot" + env.TG_TOKEN + "/sendMessage", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: env.TG_CHAT, text }),
    });
  } catch (e) { console.log("tg fail", e.message); }
}

// Unified desk: every action also lands in KV "events" so the PM dashboard
// (:8127) and Telegram see the same snatcher lane. Never logs secrets.
async function logEvent(env, text, ev) {
  try {
    const evs = JSON.parse((await env.STATE.get("events")) || "[]");
    evs.push({ ts: new Date().toISOString(), text, ...ev });
    while (evs.length > 80) evs.shift();
    await env.STATE.put("events", JSON.stringify(evs));
  } catch (_) {}
  await tg(env, text);
}

function cfJson(obj) {
  return new Response(JSON.stringify(obj), {
    headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
  });
}

async function getJson(url) {
  const r = await fetch(url, { headers: { "user-agent": "agentic-snatcher/1" } });
  return r.json();
}

async function balances(env) {
  const sol = await rpc(env, "getBalance", [env.WALLET]);
  const tb = await rpc(env, "getTokenAccountsByOwner", [env.WALLET, { mint: env.USDC }, { encoding: "jsonParsed" }]);
  let usdc = 0;
  for (const a of (tb.result?.value || [])) usdc += a.account?.data?.parsed?.info?.tokenAmount?.uiAmount || 0;
  return { sol: (sol.result?.value || 0) / 1e9, usdc };
}

async function tokenBalance(env, mint) {
  const tb = await rpc(env, "getTokenAccountsByOwner", [env.WALLET, { mint }, { encoding: "jsonParsed" }]);
  for (const a of (tb.result?.value || [])) return a.account?.data?.parsed?.info?.tokenAmount?.uiAmount || 0;
  return 0;
}

async function signAndSend(env, txB64) {
  const kp = Keypair.fromSecretKey(bs58.decode(env.SOLANA_PRIVATE_KEY));
  const tx = VersionedTransaction.deserialize(Buffer.from(txB64, "base64"));
  const conn = new Connection(heliusUrl(env), "confirmed");
  const bh = await conn.getLatestBlockhash("confirmed");
  tx.message.recentBlockhash = bh.blockhash;
  tx.sign([kp]);
  const sig = await conn.sendTransaction(tx, { skipPreflight: false });
  await conn.confirmTransaction({ signature: sig, ...bh }, "confirmed");
  return sig;
}

async function jupSwap(env, inMint, outMint, amountRaw, slipBps) {
  const q = await getJson(`${JUP}/quote?inputMint=${inMint}&outputMint=${outMint}&amount=${amountRaw}&slippageBps=${slipBps}`);
  if (!q.outAmount) throw new Error("quote fail: " + JSON.stringify(q).slice(0, 160));
  const s = await (await fetch(JUP + "/swap", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ quoteResponse: q, userPublicKey: env.WALLET }),
  })).json();
  if (!s.swapTransaction) throw new Error("swap fail");
  return { tx: s.swapTransaction, out: q.outAmount, route: (q.routePlan || []).map((r) => r.swapInfo.label) };
}

async function pairLive(mint) {
  const d = await getJson(DEX + mint);
  let best = null;
  for (const p of d.pairs || []) {
    if (p.chainId !== "solana") continue;
    const v = p.liquidity?.usd || 0;
    if (!best || v > best[0]) best = [v, p];
  }
  return best ? best[1] : null;
}

function snatcher(pos, price, txn, chg, peak, ageH) {
  const entry = pos.entryImpliedUsd;
  const pct = (price / entry - 1) * 100;
  if (price <= entry * 0.70) return { act: "SELL", why: "hard stop -30%", pct };
  if (ageH >= 24) return { act: "SELL", why: "time stop 24h", pct };
  if (pct >= 30 && (chg.m5 || 0) <= 0) return { act: "SELL", why: "bank +" + Math.round(pct) + "% momentum fading", pct };
  if (pct >= 5 && price <= peak * 0.85) return { act: "SELL", why: "trail -15% off peak", pct };
  return { act: "HOLD", why: "ride", pct };
}

async function readKv(env, key) { return JSON.parse((await env.STATE.get(key)) || "{}"); }

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function pageFor(state, status, events, cfg) {
  const now = Date.now();
  const age = (t) => {
    if (!t) return "n/a";
    const s = Math.max(0, Math.floor((now - new Date(t).getTime()) / 1000));
    return s < 90 ? s + "s" : s < 3600 ? Math.floor(s / 60) + "m" : (s / 3600).toFixed(1) + "h";
  };
  const st = state || {}, desk = status || {}, pids = desk.pids || {};
  const pos = st.pos || {};
  const dead = Object.entries(pids).filter(([, v]) => !v).map(([k]) => k);
  const evs = (events || []).slice(-8).reverse()
    .map((e) => `<li><span style="color:#64748b">${age(e.ts)}</span> ${esc(e.text || "")}</li>`).join("");
  return `<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="20">
<title>agentic-snatcher · 24/7 maintainer</title>
<style>body{font-family:ui-monospace,Menlo,monospace;background:#0b1020;color:#e6edf3;padding:16px}
h1{font-size:16px;color:#7ee787}.card{background:#111a2e;border:1px solid #26324a;border-radius:10px;padding:12px;margin:10px 0}
.k{color:#8b98b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em}td,th{padding:4px 8px;border-bottom:1px solid #1f2a44;text-align:left}
.ok{color:#4ade80}.bad{color:#f87171}.pill{display:inline-block;border:1px solid #334155;border-radius:999px;padding:2px 9px;font-size:.7rem;background:#0b1220;margin-right:6px}
.green{border-color:#14532d;color:#7ee787}.red{border-color:#7f1d1d;color:#ff7b72}</style></head><body>
<h1>☁️ agentic-snatcher — Cloudflare 24/7 maintainer</h1>
<div class="card"><span class="k">worker</span><br>
${st.off ? '<span class="pill red">WORKER OFF (halt flag)</span>' : (st.paused ? '<span class="pill red">WORKER PAUSED (daily guard)</span>' : '<span class="pill green">WORKER ACTIVE</span>')}
<br>worker loop ping ${age(st.ping || state.ts)} ago · USDC last seen $${st.usdc != null ? Number(st.usdc).toFixed(2) : "n/a"} (floor $${cfg.reserveMin})</div>
<div class="card"><span class="k">local desk report</span><br>
host <b>${esc(desk.host || "—")}</b> · received ${age(desk.receivedAt || desk.ts)} ago<br>
<span class="pill ${dead.length ? "red" : "green"}">feeds ${dead.length ? "DOWN: " + esc(dead.join(",")) : "all alive"}</span></div>
<div class="card"><span class="k">snatcher lane</span><br>
open: ${pos.symbol ? esc(pos.symbol) + " (entry ~$" + Number(pos.entryImpliedUsd || 0).toFixed(4) + ", age " + age(pos.openedAt) + ")" : "none — scanning every 15 min"}</div>
${evs ? '<div class="card"><span class="k">recent events</span><ul style="font-size:.8rem">' + evs + "</ul></div>" : ""}
<p style="color:#64748b;font-size:.7rem">Cloudflare 24/7 maintainer · desk reports here every ~60s while the machine is on</p>
</body></html>`;
}

export default {
  async scheduled(event, env, ctx) { await loop(env); },
  async fetch(request, env) {
    const u = new URL(request.url);
    const p = u.pathname;
    if (p === "/ping") {
      if (request.method !== "POST") return cfJson({ ok: false, error: "POST required" });
      let body = {};
      try { body = await request.json(); } catch (_) { return cfJson({ ok: false, error: "bad json" }); }
      const tok = body.pingToken || u.searchParams.get("token") || "";
      if (env.PING_TOKEN && tok !== env.PING_TOKEN) return cfJson({ ok: false, error: "bad token" });
      delete body.pingToken;
      const rec = { ...body, receivedAt: new Date().toISOString() };
      await env.STATE.put("status", JSON.stringify(rec));
      return cfJson({ ok: true, ts: rec.receivedAt });
    }
    if (p === "/page") {
      if (request.method !== "POST") return cfJson({ ok: false, error: "POST required" });
      let body = {};
      try { body = await request.json(); } catch (_) { return cfJson({ ok: false, error: "bad json" }); }
      const tok = body.pingToken || u.searchParams.get("token") || "";
      if (env.PING_TOKEN && tok !== env.PING_TOKEN) return cfJson({ ok: false, error: "bad token" });
      const html = String(body.html || "");
      if (html.length < 500) return cfJson({ ok: false, error: "html too small" });
      await env.STATE.put("page", JSON.stringify({ html, ts: new Date().toISOString() }));
      return cfJson({ ok: true });
    }
    const state = await readKv(env, "state");
    const status = await readKv(env, "status");
    const events = JSON.parse((await env.STATE.get("events")) || "[]");
    const cfg = { sizeUsdc: Number(env.SIZE_USDC), reserveMin: Number(env.RESERVE_MIN), wallet: env.WALLET };
    if (p === "/state") return cfJson({ ok: true, service: "agentic-snatcher", ts: new Date().toISOString(), cfg, state, status, events });
    if (p === "/run") { await loop(env); return new Response("ok"); }
    if (p === "/" || p === "/status") {
      const mirror = await readKv(env, "page");
      if (mirror && mirror.html) {
        const age = () => {
          if (!mirror.ts) return "n/a";
          const s = Math.max(0, Math.floor((Date.now() - new Date(mirror.ts).getTime()) / 1000));
          return s < 90 ? s + "s" : s < 3600 ? Math.floor(s / 60) + "m" : (s / 3600).toFixed(1) + "h";
        };
        const ribbon = "<div style='position:sticky;top:0;z-index:99;background:#0b1020;border-bottom:1px solid #7c3aed;padding:7px 12px;font-size:11px;color:#a78bfa;font-family:ui-monospace,Menlo,monospace'>☁️ Cloudflare 24/7 mirror of the local PM desk — updated " + age() + " ago · read-only (CLOSE/Rebalance stay on the Mac) · <a href='/state' style='color:#8b98b8'>json</a></div>";
        const out = mirror.html.includes("</head><body>")
          ? mirror.html.replace("</head><body>", "</head><body>" + ribbon)
          : ribbon + mirror.html;
        return new Response(out, { headers: { "content-type": "text/html; charset=utf-8" } });
      }
      return new Response(pageFor(state, status, events, cfg), { headers: { "content-type": "text/html; charset=utf-8" } });
    }
    return cfJson({ ok: true, service: "agentic-snatcher", ts: new Date().toISOString() });
  },
};

async function loop(env) {
  // FEED KEY GUARD (2026-09-05): the worker must NOT hold wallet keys; until its
  // HELIUS_KEY is fixed server-side, the autopilot loop is disabled to stop the
  // repeated `Unauthorized` feed failures. /status, /ping and the dashboard mirror
  // keep working. Remove this guard only when a valid HELIUS_KEY is configured.
  if (!env.HELIUS_KEY) {
    const st0 = JSON.parse((await env.STATE.get("state")) || "{}");
    if (!st0.noHeliusKeyNotified) {
      st0.noHeliusKeyNotified = true;
      await env.STATE.put("state", JSON.stringify(st0));
      await logEvent(env, "AUTOPILOT DISABLED: no HELIUS_KEY on worker - loop paused until the feed key is fixed (wallet keys are never stored here)", { kind: "ERROR" });
    }
    return;
  }
  const st = JSON.parse((await env.STATE.get("state")) || "{}");
  if (!st.day || st.day !== new Date().toISOString().slice(0, 10)) st.day = new Date().toISOString().slice(0, 10);
  try {
    const { usdc } = await balances(env);
    st.usdc = usdc;
    st.ping = new Date().toISOString();
    await env.STATE.put("state", JSON.stringify(st));
    if (st.off) return;
    if (usdc < Number(env.RESERVE_MIN)) {
      await logEvent(env, "AUTOPILOT holding: USDC $" + usdc.toFixed(2) + " < reserve floor", { kind: "HOLD", usdc });
      return;
    }
    if (!st.paused && st.dayStartUsd && usdc <= st.dayStartUsd * 0.90) {
      st.paused = true;
      await env.STATE.put("state", JSON.stringify(st));
      await logEvent(env, "AUTOPILOT PAUSED: daily loss guard (-10%). Balance $" + usdc.toFixed(2), { kind: "PAUSE", usdc });
      return;
    }
    st.dayStartUsd = st.dayStartUsd || usdc;
    const pos = st.pos;
    if (pos) {
      const pr = await pairLive(pos.mint);
      if (!pr) return;
      const price = Number(pr.priceUsd);
      st.peak = Math.max(st.peak || 0, price);
      const ageH = (Date.now() - new Date(pos.openedAt).getTime()) / 36e5;
      const dec = snatcher(pos, price, pr.txns || {}, pr.priceChange || {}, st.peak, ageH);
      if (dec.act === "SELL") {
        const qtyRaw = Math.floor(pos.qty * 1e6);
        const { tx } = await jupSwap(env, pos.mint, env.USDC, qtyRaw, 1000);
        const sig = await signAndSend(env, tx);
        delete st.pos;
        await env.STATE.put("state", JSON.stringify(st));
        await logEvent(env, "AUTOPILOT SELL " + pos.symbol + " (" + dec.why + ") " + Math.round(dec.pct) + "% tx " + sig.slice(0, 12), { kind: "SELL", symbol: pos.symbol, pct: Math.round(dec.pct), sig: sig.slice(0, 12), usdc });
      }
      return;
    }
    const cand = await pickCandidate(env, st);
    if (!cand) {
      await logEvent(env, "SCAN clean round: no entry (USDC $" + usdc.toFixed(2) + " ready)", { kind: "SCAN", usdc });
      return;
    }
    const amount = Math.floor(Number(env.SIZE_USDC) * 1e6);
    const { tx } = await jupSwap(env, env.USDC, cand.token, amount, 1500);
    const sig = await signAndSend(env, tx);
    const qty = await tokenBalance(env, cand.token);
    st.pos = { mint: cand.token, symbol: cand.symbol, qty, entryImpliedUsd: Number(env.SIZE_USDC) / qty, openedAt: new Date().toISOString() };
    st.tried = (st.tried || []).concat(cand.token).slice(-30);
    await env.STATE.put("state", JSON.stringify(st));
    await logEvent(env, "AUTOPILOT BUY " + cand.symbol + " $" + env.SIZE_USDC + " -> " + qty + " tokens tx " + sig.slice(0, 12), { kind: "BUY", symbol: cand.symbol, usdc: Number(env.SIZE_USDC), qty, sig: sig.slice(0, 12) });
  } catch (e) {
    try { await logEvent(env, "AUTOPILOT error: " + e.message, { kind: "ERROR" }); } catch (_) {}
  }
}

async function pickCandidate(env, st) {
  let addrs = new Map();
  for (const kind of ["https://api.dexscreener.com/token-boosts/latest/v1", "https://api.dexscreener.com/token-profiles/latest/v1"]) {
    try {
      for (const it of (await getJson(kind)) || []) {
        if (it.chainId !== "solana" || !it.tokenAddress) continue;
        addrs.set(it.tokenAddress, it);
      }
    } catch (_) {}
  }
  let best = null;
  let n = 0;
  for (const addr of addrs.keys()) {
    if ((st.tried || []).includes(addr)) continue;
    if (n++ >= 8) break;
    try {
      const pr = await pairLive(addr);
      if (!pr) continue;
      const liq = pr.liquidity?.usd || 0, fdv = pr.fdv || 0;
      const age = pr.pairCreatedAt ? (Date.now() - pr.pairCreatedAt) / 36e5 : 99;
      const t = pr.txns || {};
      const bs = (t.m5?.buys || 0) / (t.m5?.sells || 1);
      if (liq >= 15000 && fdv >= 30000 && fdv <= 150000 && age > 0.15 && bs >= 1.3 && !pr.labels) {
        const cand = { token: addr, symbol: pr.baseToken?.symbol, bs, liq, fdv };
        if (!best || bs > best.bs) best = cand;
      }
    } catch (_) {}
  }
  return best;
}
