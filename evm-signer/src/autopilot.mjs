// autopilot.mjs - RUNG-EXIT engine for the Safe EVM lane (memory-compliant; NO auto-buys).
// Mirrors the snatcher decision ladder with price proxies: BANK ~50% at >=+30%, TRAIL rest
// at -15% off peak, HARD STOP -30%, TIME STOP 24h. Buys are MANUAL (boss GO) only.
// Usage: node autopilot.mjs [--go]  (default DRY). Scheduler stays OFF until boss activates.
import fs from 'fs';
import os from 'os';
import path from 'path';
import { spawnSync } from 'child_process';
import { ethers } from 'ethers';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..', '..');
const GO = process.argv.includes('--go');
const CFG = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'live', 'evm-autopilot.json'), 'utf8'));
const STATE_FILE = CFG.stateFile || path.join(os.homedir(), '.config', 'agentic-trading', 'evm-autopilot-state.json');
const LOG = path.join(ROOT, 'logs', 'trades.jsonl');
const ABI = JSON.parse(fs.readFileSync(path.join(ROOT, 'safe', 'artifacts', 'SwapModule.json'), 'utf8'));
const modIface = new ethers.Interface(ABI.abi);
const routerIface = new ethers.Interface(['function getAmountsOut(uint256,(address,address,bool,address)[]) view returns (uint256[])']);
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43';
const UA = { 'content-type': 'application/json', 'user-agent': 'evm-autopilot/1.0' };

function loadState() {
  const def = { enteredAt: null, aeroCostUsd: CFG.seedAeroCostUsd || 0, peakUsd: 0, banked: false, buysUsdToday: 0, day: new Date().toISOString().slice(0, 10) };
  if (!fs.existsSync(STATE_FILE)) return def;
  const s = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  if (s.day !== new Date().toISOString().slice(0, 10)) { s.day = new Date().toISOString().slice(0, 10); s.buysUsdToday = 0; }
  return s;
}
function saveState(s) { fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true }); fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2), { mode: 0o600 }); }
function logEvent(e) { fs.appendFileSync(LOG, JSON.stringify({ ...e, ts: new Date().toISOString() }) + '\n'); }
function notify(text) { spawnSync('python3', [path.join(ROOT, 'scripts', 'notify-telegram.py'), 'msg', text]); }
function sendCard(kind, payload) {
  try {
    const f = '/tmp/evm_card.json';
    fs.writeFileSync(f, JSON.stringify(payload));
    spawnSync('python3', [path.join(ROOT, 'scripts', 'notify-telegram.py'), 'card', kind, f]);
  } catch (e) { /* best-effort card */ }
}
function fmtDur(secs) {
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(Math.floor(secs % 60)).padStart(2, '0')}s`;
}

async function rpcCall(method, params) {
  for (const url of CFG.rpc) {
    try {
      const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), 12000);
      const r = await fetch(url, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }), signal: ctrl.signal });
      clearTimeout(t);
      const j = await r.json();
      if (!j.error) return j.result;
    } catch (e) { /* next */ }
  }
  throw new Error('rpc failed ' + method);
}
const balOf = async (token, who) => BigInt(await rpcCall('eth_call', [{ to: token, data: '0x70a08231000000000000000000000000' + who.slice(2).toLowerCase() }, 'latest']));
async function amountOutRaw(sell, buy, amountIn) {
  const out = await rpcCall('eth_call', [{ to: ROUTER, data: routerIface.encodeFunctionData('getAmountsOut', [amountIn, [[sell, buy, CFG.stable, CFG.factory]]]) }, 'latest']);
  const arr = ethers.AbiCoder.defaultAbiCoder().decode(['uint256[]'], out)[0];
  return BigInt(arr[arr.length - 1]);
}
async function priceUsdcPerAero() { return Number(await amountOutRaw(CFG.aero, CFG.usdc, ethers.parseEther('1'))) / 1e6; }
async function swapViaModule(sellToken, buyToken, amountIn, minOut) {
  const data = modIface.encodeFunctionData('swap', [sellToken, buyToken, amountIn, minOut, CFG.factory, CFG.stable, BigInt(Math.floor(Date.now() / 1000) + 1200)]);
  const file = '/tmp/evm-auto-tx.json';
  fs.writeFileSync(file, JSON.stringify({ to: CFG.module, data, value: '0' }));
  const r = spawnSync('node', [path.join(__dirname, 'cli.mjs'), 'sign', file, String(CFG.chainId), '--broadcast'], {
    cwd: path.join(__dirname, '..'), encoding: 'utf8', env: { ...process.env, EVM_KEYSTORE: '', EVM_PASSPHRASE: '' },
  });
  const m = (r.stdout || '').match(/BROADCAST (0x[0-9a-fA-F]{64})/);
  return m ? m[1] : 'ERR ' + ((r.stdout || '') + (r.stderr || '')).slice(-300);
}
async function receiptOk(hash) {
  for (let i = 0; i < 20; i++) {
    const rec = await rpcCall('eth_getTransactionReceipt', [hash]).catch(() => null);
    if (rec && rec.status) return rec.status === '0x1';
    await new Promise((x) => setTimeout(x, 2000));
  }
  return null;
}



async function main() {
  if (!CFG.enabled) { console.log('autopilot disabled in config'); return; }
  const usdc = Number(await balOf(CFG.usdc, CFG.safe)) / 1e6;
  const aero = Number(await balOf(CFG.aero, CFG.safe)) / 1e18;
  const price = await priceUsdcPerAero();
  const st = loadState();
  const now = Math.floor(Date.now() / 1000);
  const holding = aero > 0.000001;

  if (!holding) {
    st.aeroCostUsd = 0; st.banked = false; st.enteredAt = null;
    if (!st.peakUsd || price > st.peakUsd) st.peakUsd = price;
    const ae = CFG.autoEntry || { enabled: false };
    const dailyLeft = (CFG.dailyBuyUsdCap || 5) - (st.buysUsdToday || 0);
    const spendCap = Math.max(0, Math.min(ae.entryUsdCap || 2, dailyLeft, usdc / 2)); // keep >=50% cash
    const dipOk = price <= st.peakUsd * (1 - (ae.dipPct || 0.04));
    let note = `FLAT | usdc=$${usdc.toFixed(3)} px=$${price.toFixed(4)} peak=$${st.peakUsd.toFixed(4)} dipOk=${dipOk} spendCap=$${spendCap.toFixed(2)}`;
    if (!(ae.enabled && dipOk && spendCap >= CFG.minTradeUsd)) {
      saveState(st);
      console.log(note);
      return;
    }
    if (!GO) { console.log(note + ' | would BUY (fresh entry)'); saveState(st); return; }
    const amountIn = BigInt(Math.floor(spendCap * 1e6));
    const minOut = (await amountOutRaw(CFG.usdc, CFG.aero, amountIn)) * 98n / 100n;
    const txHash = await swapViaModule(CFG.usdc, CFG.aero, amountIn, minOut);
    if (!txHash.startsWith('0x')) { console.log('BUY_ERR | ' + txHash); saveState(st); return; }
    const ok = await receiptOk(txHash);
    const naero = Number(await balOf(CFG.aero, CFG.safe)) / 1e18;
    st.enteredAt = now; st.aeroCostUsd = spendCap; st.peakUsd = price; st.banked = false;
    st.buysUsdToday = (st.buysUsdToday || 0) + spendCap;
    saveState(st);
    const line = `BUY_ENTRY | bought $${spendCap.toFixed(2)} USDC -> AERO ok=${ok} aero=${naero.toFixed(4)}`;
    console.log(line + ' | tx ' + txHash);
    logEvent({ event: 'evm_auto_buy_entry', chain: 'BASE', txHash, detail: line });
    notify(`[EVM AUTO BUY_ENTRY] $${spendCap.toFixed(2)} -> AERO ok=${ok} tx=${txHash}`);
    try {
      sendCard('open', { engine: 'Base Execution Engine', symbol: 'AERO',
        ca: '0x9401…98631', entryTime: new Date(st.enteredAt * 1000).toISOString().slice(0, 16) + ' UTC',
        sizeUsdc: spendCap, qty: naero.toFixed(4), entryPrice: (spendCap / naero).toFixed(6),
        slip: '~0.11% (Aerodrome route)', hardStopPct: '-30.00%',
        hardStopPrice: ((spendCap / naero) * 0.70).toFixed(6),
        targetPct: '+30% bank-half / trail', regime: 'Base AUTO (T-7)' });
    } catch (e) { /* best-effort */ }
    return;
  }
  if (!st.enteredAt) { st.enteredAt = now; st.aeroCostUsd = st.aeroCostUsd || CFG.seedAeroCostUsd; st.peakUsd = 0; }
  if (st.aeroCostUsd <= 0) st.aeroCostUsd = aero * price; // fallback basis = current price
  const basis = st.aeroCostUsd / aero;
  if (!st.peakUsd) st.peakUsd = price;
  if (price > st.peakUsd) st.peakUsd = price;
  const pctFromBasis = (price / basis - 1) * 100;
  const hrs = ((now - st.enteredAt) / 3600).toFixed(1);

  let action = 'HOLD';
  const reasons = [];
  if (price <= basis * 0.70) { action = 'SELL_ALL'; reasons.push('HARD_STOP_-30%'); }
  else if (!st.banked && price >= basis * 1.30) { action = 'BANK_HALF'; reasons.push('+30%_rung'); }
  else if (st.banked && price <= st.peakUsd * 0.85) { action = 'SELL_ALL'; reasons.push('TRAIL_-15%_off_peak'); }
  else if (now - st.enteredAt > 24 * 3600) { action = 'SELL_ALL'; reasons.push('TIME_STOP_24h'); }
  else reasons.push('hold');

  let note = `usdc=$${usdc.toFixed(3)} aero=${aero.toFixed(3)} px=$${price.toFixed(4)} basis=$${basis.toFixed(4)} (${pctFromBasis.toFixed(1)}%) peak=$${st.peakUsd.toFixed(4)} hrs=${hrs} banked=${st.banked}`;

  if (action === 'HOLD') {
    console.log(`${action} | ${note} | ${reasons.join(',')}`);
    saveState(st);
    return;
  }

  const sellFraction = action === 'BANK_HALF' ? 0.5 : 1;
  const sellAero = Math.min(aero, aero * sellFraction, CFG.aeroSellPerSwapCap || 99);
  if (!GO) {
    console.log(`${action} | ${note} | ${reasons.join(',')} | would SELL ${sellAero.toFixed(3)} AERO -> USDC`);
    saveState(st);
    return;
  }
  const amountIn = ethers.parseEther(sellAero.toFixed(18));
  const minOut = (await amountOutRaw(CFG.aero, CFG.usdc, amountIn)) * 98n / 100n;
  const txHash = await swapViaModule(CFG.aero, CFG.usdc, amountIn, minOut);
  if (!txHash.startsWith('0x')) { console.log(`${action}_ERR | ${note} | ${txHash}`); saveState(st); return; }
  const ok = await receiptOk(txHash);
  const naero = Number(await balOf(CFG.aero, CFG.safe)) / 1e18;
  if (action === 'BANK_HALF') {
    st.aeroCostUsd = st.aeroCostUsd * (naero / aero);
    st.banked = true;
    note += ` | BANKED ${sellAero.toFixed(3)} AERO ok=${ok} aero=${naero.toFixed(3)}`;
  } else {
    const proceedsUsd = sellAero * price;
    const costUsd = st.aeroCostUsd || 0;
    const realized = proceedsUsd - costUsd;
    const durSecs = now - (st.enteredAt || now);
    st.aeroCostUsd = 0; st.peakUsd = 0; st.banked = false; st.enteredAt = null;
    note += ` | EXITED ${sellAero.toFixed(3)} AERO ok=${ok} aero=${naero.toFixed(3)}`;
    try { // rich close card (never blocks the engine)
      const pct = costUsd > 0 ? ((realized / costUsd) * 100).toFixed(2) : '0.00';
      const pay = { engine: 'Base Execution Engine', symbol: 'AERO',
        duration: fmtDur(durSecs), reason: reasons.join('/') || 'EXIT',
        costUsdc: costUsd, grossUsdc: proceedsUsd, dest: 'Base Safe (0x203F…)',
        destLane: 'Safe', netPnl: realized, pnlPct: pct + '%',
        fees: { 'Total EVM Gas': '$0.005 (Base L2)', 'Slippage': '~0.11% (Aerodrome)' } };
      sendCard(realized >= 0 ? 'profit' : 'loss', pay);
    } catch (e) { /* best-effort */ }
  }
  saveState(st);
  console.log(`${action} | ${note} | tx ${txHash}`);
  logEvent({ event: 'evm_auto_' + action.toLowerCase(), chain: 'BASE', txHash, reason: reasons.join(','), detail: note });
  notify(`[EVM AUTO ${action} ${reasons.join('/')}] ${note} tx=${txHash}`);
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 500)); process.exit(1); });
