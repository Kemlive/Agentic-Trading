// verify-swapmodule.mjs - read module config + router allowances on-chain (with retry/fallback)
import { ethers } from 'ethers';
import fs from 'fs';
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const MOD = '0x315f754ef53bb14c2f9001be8fe0d857e2e31013';
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const AERO = '0x940181a94A35A4569E4529A3CDfB74e38FD98631';
const artifact = JSON.parse(fs.readFileSync(new URL('./artifacts/SwapModule.json', import.meta.url), 'utf8'));
const modIface = new ethers.Interface(artifact.abi);
const RPC = ['https://base-rpc.publicnode.com', 'https://mainnet.base.org'];
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' };
async function call(to, data) {
  for (const url of RPC) {
    try {
      const r = await fetch(url, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_call', params: [{ to, data }, 'latest'] }) });
      const j = await r.json();
      if (j.error) throw new Error(JSON.stringify(j.error));
      return j.result;
    } catch (e) { await new Promise((res) => setTimeout(res, 300)); }
  }
  throw new Error('reads failed');
}
const u = (name, hex) => parseInt(hex, 16);
console.log('delegate:', ethers.getAddress('0x' + (await call(MOD, modIface.encodeFunctionData('delegate'))).slice(26)));
console.log('module enabled on Safe:', u('', await call(SAFE, '0x2d9ad53d' + MOD.slice(2).toLowerCase().padStart(64, '0'))) === 1);
const erc = new ethers.Interface(['function allowance(address,address) view returns (uint256)']);
for (const [n, t] of [['USDC', USDC], ['AERO', AERO]]) {
  console.log(n, 'allowedSell', u('', await call(MOD, modIface.encodeFunctionData('allowedSell', [t]))) === 1, '| allowedBuy', u('', await call(MOD, modIface.encodeFunctionData('allowedBuy', [t]))) === 1);
  const raw = await call(MOD, modIface.encodeFunctionData('caps', [t]));
  const [p, d, , s] = ethers.AbiCoder.defaultAbiCoder().decode(['uint256', 'uint256', 'uint256', 'uint256'], raw);
  const dec = t === USDC ? 6 : 18;
  console.log(n, 'caps perSwap', Number(p) / 10 ** dec, '| daily', Number(d) / 10 ** dec, '| spent', Number(s) / 10 ** dec);
  const al = await call(t, erc.encodeFunctionData('allowance', [SAFE, ROUTER]));
  const av = ethers.AbiCoder.defaultAbiCoder().decode(['uint256'], al)[0];
  console.log(n, 'Safe->router allowance MAX:', av === ethers.MaxUint256);
}

