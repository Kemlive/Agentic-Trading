// deploy-swap-module.mjs - deploy the SwapModule (Safe + Aerodrome router). DRY-RUN default; --go deploys.
import fs from 'fs';
import { ethers } from 'ethers';
import { loadKeystore, decryptPrivateKey, loadPassphrase } from '../evm-signer/src/keystore.mjs';

const GO = process.argv.includes('--go');
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43'; // Aerodrome router (Base)
const artifact = JSON.parse(fs.readFileSync(new URL('./artifacts/SwapModule.json', import.meta.url), 'utf8'));
const provider = new ethers.JsonRpcProvider('https://base-rpc.publicnode.com');
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };

async function receipt(hash) {
  for (let i = 0; i < 40; i++) {
    const r = await fetch('https://mainnet.base.org', { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getTransactionReceipt', params: [hash] }) });
    const j = await r.json();
    if (j.result && j.result.status) return j.result;
    await new Promise((res) => setTimeout(res, 2000));
  }
  throw new Error('timeout waiting for ' + hash);
}

async function main() {
  const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase()).connect(provider);
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);
  const deployData = (await factory.getDeployTransaction(SAFE, ROUTER)).data;
  const gas = await provider.estimateGas({ from: wallet.address, data: deployData });
  const fee = await provider.getFeeData();
  console.log('SwapModule constructor: safe=', SAFE, 'router=', ROUTER);
  console.log('deploy gas:', gas.toString(), '| approx cost ETH:', (Number(gas) * Number(fee.maxFeePerGas) / 1e18).toFixed(8));

  if (!GO) { console.log('DRY-RUN. To deploy: node deploy-swap-module.mjs --go'); return; }

  const contract = await factory.deploy(SAFE, ROUTER);
  const hash = contract.deploymentTransaction().hash;
  console.log('BROADCAST', hash);
  const rec = await receipt(hash);
  console.log('status', rec.status, '| module address:', rec.contractAddress);
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 500)); process.exit(1); });
