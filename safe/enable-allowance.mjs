// enable-allowance.mjs - enable AllowanceModule + addDelegate(EOA) + setAllowance(USDC daily).
// Idempotent: skips enableModule if already enabled. DRY-RUN by default; --go executes.
import { ethers } from 'ethers';
import { createPublicClient, http } from 'viem';
import Safe from '@safe-global/protocol-kit';
import { getAllowanceModuleDeployment } from '@safe-global/safe-modules-deployments';
import { loadKeystore, decryptPrivateKey, loadPassphrase } from '../evm-signer/src/keystore.mjs';

const GO = process.argv.includes('--go');
const _usdcIdx = process.argv.indexOf('--usdcDaily');
const USDC_DAILY_USD = _usdcIdx >= 0 ? Number(process.argv[_usdcIdx + 1]) : 5;
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const RECEIPT_RPC = 'https://mainnet.base.org';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };

const modDep = getAllowanceModuleDeployment({ network: '8453' });
const MODULE = modDep.networkAddresses?.['8453'] ?? modDep.address;
const modIface = new ethers.Interface(modDep.abi);

async function receipt(hash) {
  for (let i = 0; i < 40; i++) {
    const r = await fetch(RECEIPT_RPC, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getTransactionReceipt', params: [hash] }) });
    const j = await r.json();
    if (j.result && j.result.status) return j.result;
    await new Promise((res) => setTimeout(res, 2000));
  }
  throw new Error('timeout waiting for ' + hash);
}

function makeSafe(wallet) {
  const publicClient = createPublicClient({ transport: http('https://base-rpc.publicnode.com') });
  return Safe.init({ provider: publicClient, signer: wallet.privateKey, safeAddress: SAFE });
}

async function isEnabled() {
  const sel = '0x2d9ad53d' + MODULE.slice(2).toLowerCase().padStart(64, '0');
  const r = await fetch(RECEIPT_RPC, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_call', params: [{ to: SAFE, data: sel }, 'latest'] }) });
  const j = await r.json();
  return j.result === '0x' + '0'.repeat(63) + '1';
}

async function main() {
  const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());
  console.log('Safe:', SAFE, '| owner signer:', wallet.address);
  console.log('AllowanceModule:', MODULE, '| USDC daily allowance:', USDC_DAILY_USD, 'USDC');

  const enabled = await isEnabled();
  console.log('enableModule already done:', enabled);

  const steps = [];
  if (!enabled) steps.push(['enableModule', (safe) => safe.createEnableModuleTx(MODULE)]);
  steps.push(['addDelegate', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('addDelegate', [wallet.address]) }] })]);
  const usdcDailyRaw = ethers.parseUnits(String(USDC_DAILY_USD), 6).toString();
  steps.push(['setAllowance', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setAllowance', [wallet.address, USDC, usdcDailyRaw, 1440, 0]) }] })]);

  if (!GO) {
    console.log('DRY-RUN — would execute', steps.length, 'Safe owner tx(s):', steps.map((s) => s[0]).join(', '));
    return;
  }

  for (const [name, build] of steps) {
    const safe = await makeSafe(wallet); // fresh signer => fresh nonce
    const tx = await build(safe);
    const res = await safe.executeTransaction(tx);
    const hash = res?.hash || res?.transactionResponse?.hash || res;
    console.log(name, '->', hash);
    await receipt(hash);
    console.log(name, 'mined');
  }
  console.log('DONE');
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 400)); process.exit(1); });

