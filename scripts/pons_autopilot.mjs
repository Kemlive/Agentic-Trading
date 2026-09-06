// pons_autopilot.mjs — Pons v2 AUTO-EXECUTION LANE (same rails as SOL/BASE desk, RH 4663).
// DRY first (no txs). LIVE only when data/live/pons-autopilot.json {mode:"live"} AND no
// kill-switch data/live/pons-autopilot.off. Candidate source: pons-live-fresh.json (phase0+$5 gate).
import fs from "fs";
import os from "os";
import path from "path";
import { createRequire } from "module";
import { decryptPrivateKey } from "/Users/earn/Agentic-Trading/evm-signer/src/keystore.mjs";
const require = createRequire(import.meta.url);
const { ethers } = require("/Users/earn/Agentic-Trading/evm-signer/node_modules/ethers");
const ROOT = "/Users/earn/Agentic-Trading";
const FD = path.join(ROOT, "data", "live", "feed");
const LIVE = path.join(ROOT, "data", "live");
const CFG = path.join(LIVE, "pons-autopilot.json");
const STATE = path.join(LIVE, "pons-autopilot-state.json");
const OFF = path.join(LIVE, "pons-autopilot.off");
const R = "https://rpc.mainnet.chain.robinhood.com";
const CHAIN = 4663;
const USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168";
const FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e";
const TEST = "0x1111111111111111111111111111111111111111";
const provider = new ethers.JsonRpcProvider(R, CHAIN, { staticNetwork: true });
const DEF = { mode: "dry", walletAddress: "", dailyUsdCap: 25, tradeUsd: 5, maxPos: 1, stopPct: -30, timeStopH: 24, trailPct: 15, bankPct: 30, types: ["pons-usdg", "pons-native"] };
const load = (p, d) => { try { return JSON.parse(fs.readFileSync(p)); } catch { return d; } };
const save = (p, o) => { fs.writeFileSync(p + ".tmp", JSON.stringify(o, null, 1)); fs.renameSync(p + ".tmp", p); };
async function rpc(m, p) { const x = await fetch(R, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: m, params: p }) }); return x.json(); }
async function ec(tx, ov) { const r = await rpc("eth_call", ov ? [tx, "latest", ov] : [tx, "latest"]); if ("result" in r) return { ok: true, out: r.result }; return { ok: false }; }
const a40 = (w) => "0x" + w.toString(16).padStart(64, "0").slice(24);
const ERC = new ethers.Interface(["function balanceOf(address) view returns (uint256)"]);
const BI = new ethers.Interface(["function buy(uint256,uint256,address) payable returns (uint256)"]);
const SI = new ethers.Interface(["function sell(uint256,uint256,address) returns (uint256)"]);
const tr0 = ethers.id("Transfer(address,address,uint256)");
async function launch(tok) {
  const g = await ec({ to: FACTORY, data: "0x3cf28b5a" + tok.slice(2).padStart(64, "0") });
  if (!g.ok || !g.out) return null;
  let h = g.out.slice(2); h = h.slice(0, h.length - (h.length % 64));
  if (h.length < 64 * 15) return null;
  const w = []; for (let i = 0; i + 64 <= h.length && w.length < 15; i += 64) w.push(BigInt("0x" + h.slice(i, i + 64)));
  return { exists: w[14] !== 0n, phase: Number(w[10]), curve: a40(w[1]) };
}
async function ethUsd() { try { const j = await (await fetch("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")).json(); const p = Number((j.ethereum || {}).usd); if (p > 50) return p; } catch { } return null; }
async function simSell(tok, curve, qRaw, fromAddr) {
  let holder = fromAddr || null, have = 0n;
  if (holder) { const b = await ec({ to: tok, data: ERC.encodeFunctionData("balanceOf", [holder]) }); have = b.ok ? BigInt(b.out) : 0n; }
  else {
    const bal = await ec({ to: tok, data: ERC.encodeFunctionData("balanceOf", [TEST]) });
    holder = TEST; have = bal.ok ? BigInt(bal.out) : 0n;
    if (have < qRaw) {
      const latest = parseInt((await rpc("eth_blockNumber", [])).result, 16);
      const logs = await rpc("eth_getLogs", [{ address: tok.toLowerCase(), topics: [tr0, "0x" + "0".repeat(64)], fromBlock: "0x" + (latest - 800000).toString(16), toBlock: "latest" }]);
      for (const l of ((logs.result) || [])) {
        const o = "0x" + l.topics[2].slice(26).toLowerCase();
        if (o.toLowerCase() === curve.toLowerCase() || o.toLowerCase() === tok.toLowerCase()) continue;
        const b2 = await ec({ to: tok, data: ERC.encodeFunctionData("balanceOf", [o]) });
        if (b2.ok && BigInt(b2.out) >= qRaw) { holder = o; have = BigInt(b2.out); break; }
      }
    }
  }
  if (have < qRaw) return null;
  const s = await ec({ from: holder, to: curve, data: SI.encodeFunctionData("sell", [qRaw, 0n, holder]) });
  return s.ok ? BigInt(s.out) : null;
}
function loadWallet(expected) {
  const KEYS = JSON.parse(fs.readFileSync(path.join(process.env.HOME || os.homedir(), ".config/agentic-trading/evm-keystore.json")));
  const PASS = fs.readFileSync(path.join(process.env.HOME || os.homedir(), ".config/agentic-trading/evm-keystore.pass"), "utf8").trim();
  const w = decryptPrivateKey(KEYS, PASS).connect(provider);
  // Desk rule (boss): trade from the trading wallet (Base unified 0x203F...). The boss Safe EOA
  // 0xB1AC... is ONLY an owner-signer for that wallet's Safe/module ops — never a direct trade account.
  const BOSS_SAFE_EOA = "0xb1acdaf72ca6648ddd54f5db85b9cf75d58f82b8";
  const TRADING = "0x203fd7cefb443672ef5700a1e27521c22a6e7b3a";
  const ad = w.address.toLowerCase();
  const exp = String(expected || "").toLowerCase();
  if (!/^0x[0-9a-fA-F]{40}$/.test(exp)) throw new Error("REFUSED: walletAddress must be set to the trading wallet");
  const ownerSigningSafe = exp === TRADING && ad === BOSS_SAFE_EOA; // 0xB1AC signs Safe ops for 0x203F only
  if (ad === BOSS_SAFE_EOA && !ownerSigningSafe) throw new Error("REFUSED: boss Safe EOA 0xB1AC may only sign for the trading wallet 0x203F (Safe/module ops), never trade directly");
  if (ad !== exp && !ownerSigningSafe) throw new Error("REFUSED: keystore " + ad + " != configured walletAddress " + exp);
  return { wallet: w, safeOwner: ownerSigningSafe, trading: exp };
}
async function viewA(iface, fn, args, at) { const d = iface.encodeFunctionData(fn, args || []); const r = await provider.call({ to: at, data: d }); return iface.decodeFunctionResult(fn, r)[0]; }
async function send(w, tag, to, iface, fn, args) {
  const data = iface.encodeFunctionData(fn, args);
  const gas = await provider.estimateGas({ from: w.address, to, data });
  const tx = await w.sendTransaction({ to, data, gasLimit: gas * 120n / 100n });
  console.log("TX", tag, tx.hash);
  const rec = await tx.wait();
  console.log("MINED", tag, rec.status, rec.gasUsed.toString());
  return rec;
}
async function main() {
  const cfg = { ...DEF, ...load(CFG, {}) };
  let st = load(STATE, { pos: null, peakQuote: null, enteredAt: null, todayUsd: 0, day: "", nDry: 0, nLive: 0, lastCycle: null, notes: [] });
  const today = new Date().toISOString().slice(0, 10);
  if (st.day !== today) { st.day = today; st.todayUsd = 0; }
  st.lastCycle = new Date().toISOString();
  const live = cfg.mode === "live";
  let wallet = null;
  if (live) { if (!cfg.walletAddress) { console.log("pons-autopilot REFUSED: set walletAddress (trading wallet) before live"); save(STATE, st); return; } try { const loaded = loadWallet(cfg.walletAddress); if (loaded.safeOwner) { console.log("pons-autopilot REFUSED: trading wallet is the Safe 0x203F — direct curve trades need an EOA trading key (boss EOA signs caps/sweeps only)"); save(STATE, st); return; } wallet = loaded.wallet; console.log("pons-autopilot LIVE wallet", wallet.address); } catch (e) { console.log("pons-autopilot LIVE wallet guard:", e.message); save(STATE, st); return; } }
  if (fs.existsSync(OFF)) { save(STATE, st); console.log("pons-autopilot OFF (kill switch file present)"); return; }
  const now = Date.now();
  if (st.pos) {
    const p = st.pos;
    const ls = await launch(p.token);
    const stillPhase0 = ls && ls.exists && ls.phase === 0;
    let val = null;
    if (stillPhase0) val = await simSell(p.token, ls.curve, BigInt(p.qRaw), wallet ? wallet.address : null);
    const ageH = (now - new Date(st.enteredAt).getTime()) / 3600000;
    const pnl = val ? Number((val - BigInt(p.entryQuote)) * 100n) / Number(BigInt(p.entryQuote)) : null;
    let reason = null;
    if (!stillPhase0) reason = "curve-closed/graduated";
    else if (pnl !== null && pnl <= cfg.stopPct) reason = "stop-" + pnl.toFixed(1) + "%";
    else if (pnl !== null && pnl >= cfg.bankPct) reason = "bank+" + pnl.toFixed(1) + "%";
    else if (ageH >= cfg.timeStopH) reason = "time-stop-" + ageH.toFixed(1) + "h";
    else if (val !== null) { const peak = st.peakQuote ? BigInt(st.peakQuote) : BigInt(p.entryQuote); if (val > peak) { st.peakQuote = val.toString(); } else if (val <= peak * BigInt(100 - cfg.trailPct) / 100n) reason = "trail-off-peak"; }
    if (reason) {
      const tag = live ? "LIVE-EXIT" : "DRY-EXIT";
      st.notes.unshift({ at: new Date().toISOString(), tag, token: p.token, reason, val: val ? val.toString() : null, pnlPct: pnl !== null ? Math.round(pnl * 100) / 100 : null });
      if (live) {
        const q = BigInt(p.qRaw);
        const tokAllow = await viewA(ERC, "allowance", [wallet.address, ls.curve], p.token);
        if (tokAllow < q) await send(wallet, "approve-token->curve", p.token, ERC, "approve", [ls.curve, q]);
        await send(wallet, "sell", ls.curve, SI, "sell", [q, 0n, wallet.address]);
        st.nLive += 1;
      }
      else st.nDry += 1;
      st.pos = null; st.peakQuote = null; st.enteredAt = null;
      st.notes = st.notes.slice(0, 40);
      save(STATE, st);
      console.log(tag, reason, p.token.slice(0, 10));
      return;
    }
    save(STATE, st);
    console.log("pons-autopilot holding", p.token.slice(0, 10), "pnl", pnl !== null ? pnl.toFixed(2) + "%" : "n/a", "age", ageH.toFixed(1) + "h");
    return;
  }
  if (st.todayUsd + cfg.tradeUsd > cfg.dailyUsdCap) { console.log("pons-autopilot daily cap reached"); return; }
  const fr = load(path.join(FD, "pons-live-fresh.json"), null);
  if (!fr || !fr.rows || !fr.asOf || (Date.now() - new Date(fr.asOf).getTime()) > 3600000) { console.log("pons-autopilot no fresh feed"); return; }
  const eth = await ethUsd();
  const cands = fr.rows.filter((r) => cfg.types.includes(r.type)).sort((a, b) => (a.impactPct ?? 1e9) - (b.impactPct ?? 1e9));
  for (const c of cands) {
    const ls = await launch(c.token);
    if (!ls || !ls.exists || ls.phase !== 0) continue;
    const buyAmt = c.type === "pons-native" ? BigInt(Math.floor((cfg.tradeUsd / eth) * 1e18)) : BigInt(cfg.tradeUsd * 1e6);
    let simBuy = null;
    if (live) {
      if (c.type === "pons-native") {
        const nat = await provider.getBalance(wallet.address);
        if (nat < buyAmt + 50000000000000n) continue;
        await send(wallet, "buy", ls.curve, BI, "buy", [buyAmt, 0n, wallet.address]);
      } else {
        const bal = await viewA(ERC, "balanceOf", [wallet.address], USDG);
        if (bal < buyAmt) { console.log("skip entry: insufficient USDG", bal.toString()); continue; }
        const allow = await viewA(ERC, "allowance", [wallet.address, ls.curve], USDG);
        if (allow < buyAmt) await send(wallet, "approve-USDG->curve", USDG, ERC, "approve", [ls.curve, buyAmt * 2n]);
        await send(wallet, "buy", ls.curve, BI, "buy", [buyAmt, 0n, wallet.address]);
      }
      simBuy = await viewA(ERC, "balanceOf", [wallet.address], c.token);
    } else if (c.type === "pons-native") {
      const d = BI.encodeFunctionData("buy", [buyAmt, 0n, TEST]); const ov = { [TEST]: { balance: "0x" + (buyAmt + 1000000000000000n).toString(16) } }; const s = await ec({ from: TEST, to: ls.curve, data: d, value: "0x" + buyAmt.toString(16) }, ov); if (s.ok) simBuy = BigInt(s.out);
    } else {
      const rep = load(path.join(ROOT, "research", "pons-usdg-pair-replay-20260905-1123.json"), null);
      let owner = null; if (rep) for (const rr of rep.rows || []) if (rr.verdict === "PASS" && rr.token.toLowerCase() === c.token.toLowerCase() && rr.detail && rr.detail.owner) owner = rr.detail.owner;
      if (owner) { const d = BI.encodeFunctionData("buy", [buyAmt, 0n, TEST]); const s = await ec({ from: owner, to: ls.curve, data: d }); if (s.ok) simBuy = BigInt(s.out); }
    }
    if (!simBuy || BigInt(simBuy) === 0n) continue;
    const tag = live ? "LIVE-ENTRY" : "DRY-ENTRY";
    st.pos = { token: c.token.toLowerCase(), curve: ls.curve.toLowerCase(), type: c.type, qRaw: simBuy.toString(), entryQuote: buyAmt.toString() };
    st.enteredAt = new Date().toISOString(); st.peakQuote = null;
    st.todayUsd += cfg.tradeUsd;
    st.notes.unshift({ at: new Date().toISOString(), tag, token: c.token, q: simBuy.toString(), quote: buyAmt.toString(), type: c.type });
    st.notes = st.notes.slice(0, 40);
    if (live) st.nLive += 1; else st.nDry += 1;
    save(STATE, st);
    console.log(tag, c.type, c.token.slice(0, 10), "q", simBuy.toString().slice(0, 18));
    return;
  }
  console.log("pons-autopilot no candidate passed gate");
  save(STATE, st);
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });

