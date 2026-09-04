// policy.mjs - guardrails enforced in the signing path (defense-in-depth on top of the engine).
import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const POLICY_PATH = process.env.EVM_POLICY || path.join(__dirname, '..', 'config', 'policy.json');
export const STATE_PATH = process.env.EVM_SIGNER_STATE || path.join(os.homedir(), '.config/agentic-trading/evm-signer-state.json');

export function loadPolicy() {
  return JSON.parse(fs.readFileSync(POLICY_PATH, 'utf8'));
}

export function savePolicy(p) {
  fs.writeFileSync(POLICY_PATH, JSON.stringify(p, null, 2));
}

export function loadState() {
  const def = { date: today(), valueWei: '0', txs: 0 };
  if (!fs.existsSync(STATE_PATH)) return def;
  const s = JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
  return s.date === today() ? s : def;
}

export function saveState(s) {
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  fs.writeFileSync(STATE_PATH, JSON.stringify(s, null, 2), { mode: 0o600 });
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

// returns { ok, reasons[] } - checked BEFORE signing. valueWei and ethUsd optional.
export function checkPolicy({ chainId, to, valueWei = '0', ethUsd = null }) {
  const p = loadPolicy();
  const reasons = [];
  if (p.killSwitch) reasons.push('KILL_SWITCH_ON');
  if (!p.enabled) reasons.push('SIGNING_DISABLED');
  if (!(p.chains || []).includes(chainId)) reasons.push('CHAIN_NOT_ALLOWED');
  const allow = new Set((p.allowlistedTo || []).map((a) => a.toLowerCase()));
  if (to && !allow.has(to.toLowerCase())) reasons.push('TO_NOT_ALLOWLISTED');

  const val = BigInt(valueWei || '0');
  if (p.perTxValueWeiCap != null && val > BigInt(p.perTxValueWeiCap)) reasons.push('PER_TX_VALUE_CAP_EXCEEDED');

  if (ethUsd != null) {
    const usd = Number(val) / 1e18 * Number(ethUsd);
    if (p.perTxUsdCap != null && usd > p.perTxUsdCap) reasons.push('PER_TX_USD_CAP_EXCEEDED');
    const s = loadState();
    const dayUsd = Number(s.valueWei) / 1e18 * Number(ethUsd) + usd;
    if (p.dailyUsdCap != null && dayUsd > p.dailyUsdCap) reasons.push('DAILY_USD_CAP_EXCEEDED');
  } else {
    const s = loadState();
    const dayVal = BigInt(s.valueWei || '0') + val;
    if (p.dailyValueWeiCap != null && dayVal > BigInt(p.dailyValueWeiCap)) reasons.push('DAILY_VALUE_CAP_EXCEEDED');
  }
  return { ok: reasons.length === 0, reasons };
}

export function recordSpend(valueWei) {
  const s = loadState();
  s.valueWei = (BigInt(s.valueWei || '0') + BigInt(valueWei || '0')).toString();
  s.txs += 1;
  saveState(s);
}

export function appendAudit(entry) {
  const logPath = path.join(os.homedir(), '.config/agentic-trading/evm-signer-log.jsonl');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.appendFileSync(logPath, JSON.stringify(entry) + '\n', { mode: 0o600 });
}
