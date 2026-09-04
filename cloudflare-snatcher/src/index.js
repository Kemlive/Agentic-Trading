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

export default {
  async scheduled(event, env, ctx) { await loop(env); },
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/run") { await loop(env); return new Response("ok"); }
    return new Response("alive");
  },
};

async function loop(env) {
  const st = JSON.parse((await env.STATE.get("state")) || "{}");
  if (!st.day || st.day !== new Date().toISOString().slice(0, 10)) st.day = new Date().toISOString().slice(0, 10);
  try {
    const { usdc } = await balances(env);
    if (st.off) return;
    if (usdc < Number(env.RESERVE_MIN)) {
      await tg(env, "AUTOPILOT holding: USDC $" + usdc.toFixed(2) + " < reserve floor");
      return;
    }
    if (!st.paused && st.dayStartUsd && usdc <= st.dayStartUsd * 0.90) {
      st.paused = true;
      await env.STATE.put("state", JSON.stringify(st));
      await tg(env, "AUTOPILOT PAUSED: daily loss guard (-10%). Balance $" + usdc.toFixed(2));
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
        await tg(env, "AUTOPILOT SELL " + pos.symbol + " (" + dec.why + ") " + Math.round(dec.pct) + "% tx " + sig.slice(0, 12));
      }
      return;
    }
    const cand = await pickCandidate(env, st);
    if (!cand) {
      await tg(env, "SCAN clean round: no entry (USDC $" + usdc.toFixed(2) + " ready)");
      return;
    }
    const amount = Math.floor(Number(env.SIZE_USDC) * 1e6);
    const { tx } = await jupSwap(env, env.USDC, cand.token, amount, 1500);
    const sig = await signAndSend(env, tx);
    const qty = await tokenBalance(env, cand.token);
    st.pos = { mint: cand.token, symbol: cand.symbol, qty, entryImpliedUsd: Number(env.SIZE_USDC) / qty, openedAt: new Date().toISOString() };
    st.tried = (st.tried || []).concat(cand.token).slice(-30);
    await env.STATE.put("state", JSON.stringify(st));
    await tg(env, "AUTOPILOT BUY " + cand.symbol + " $" + env.SIZE_USDC + " -> " + qty + " tokens tx " + sig.slice(0, 12));
  } catch (e) {
    try { await tg(env, "AUTOPILOT error: " + e.message); } catch (_) {}
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
