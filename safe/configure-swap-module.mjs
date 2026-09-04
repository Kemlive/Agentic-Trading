// configure-swap-module.mjs - after SwapModule deployed: enable + setDelegate + token allowlists + caps + approveRouter.
// DRY-RUN default; --go executes (sequential Safe owner txs). Usage: node configure-swap-module.mjs --go <MODULE_ADDRESS>
import fs from 'fs';
import { ethers } from 'ethers';
import { createPublicClient, http } from 'viem';
import Safe from '@safe-global/protocol-kit';
import { loadKeystore, decryptPrivateKey, loadPassphrase } from '../evm-signer/src/keystore.mjs';

const GO = process.argv.includes('--go');
const MODULE = process.argv[process.argv.length - 1];
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const AERO = '0x940181a94A35A4569E4529A3CDfB74e38FD98631';
const RECEIPT_RPC = 'https://mainnet.base.org';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };

const artifact = JSON.parse(fs.readFileSync(new URL('./artifacts/SwapModule.json', import.meta.url), 'utf8'));
const modIface = new ethers.Interface(artifact.abi);

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

async function main() {
  if (!/^0x[0-9a-fA-F]{40}$/.test(MODULE)) throw new Error('pass MODULE address as last arg (run --go 0x...)');
  const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());
  console.log('Safe:', SAFE, '| SwapModule:', MODULE, '| owner:', wallet.address);

  const steps = [];
  steps.push(['enableModule', (safe) => safe.createEnableModuleTx(MODULE)]);
  steps.push(['setDelegate', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setDelegate', [wallet.address]) }] })]);
  steps.push(['setToken USDC', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setToken', [USDC, true, true]) }] })]);
  steps.push(['setToken AERO', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setToken', [AERO, true, true]) }] })]);
  steps.push(['setCaps USDC $2/$5', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setCaps', [USDC, 2000000n, 5000000n]) }] })]);
  steps.push(['setCaps AERO 4/6', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('setCaps', [AERO, ethers.parseEther('4'), ethers.parseEther('6')]) }] })]);
  steps.push(['approveRouter USDC', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('approveRouter', [USDC]) }] })]);
  steps.push(['approveRouter AERO', (safe) => safe.createTransaction({ transactions: [{ to: MODULE, value: 0n, data: modIface.encodeFunctionData('approveRouter', [AERO]) }] })]);

  if (!GO) { console.log('DRY-RUN — would execute', steps.length, 'Safe owner txs:', steps.map((s) => s[0]).join(', ')); return; }

  for (const [name, build] of steps) {
    const safe = await makeSafe(wallet);
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
