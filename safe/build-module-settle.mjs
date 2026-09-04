// build-module-settle.mjs - quote AERO->USDC, build module.swap calldata, estimate gas.
import fs from 'fs';
import { ethers } from 'ethers';
const MODULE = '0x315f754ef53bb14c2f9001be8fe0d857e2e31013';
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43';
const FACTORY = '0x420DD381b31aEf6683db6B902084cB0FFECe40Da';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const AERO = '0x940181a94A35A4569E4529A3CDfB74e38FD98631';
const EOA = '0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8';
const AMOUNT = 500000000000000000n; // 0.5 AERO (18 dec)
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' };
const RPC = ['https://base-rpc.publicnode.com', 'https://mainnet.base.org'];
const artifact = JSON.parse(fs.readFileSync(new URL('./artifacts/SwapModule.json', import.meta.url), 'utf8'));
const modIface = new ethers.Interface(artifact.abi);
const routerIface = new ethers.Interface(['function getAmountsOut(uint256,(address,address,bool,address)[]) view returns (uint256[])']);
async function call(to, data) {
  for (const url of RPC) {
    try {
      const r = await fetch(url, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_call', params: [{ to, data }, 'latest'] }) });
      const j = await r.json();
      if (j.error) throw new Error(JSON.stringify(j.error));
      return j.result;
    } catch (e) { await new Promise((x) => setTimeout(x, 300)); }
  }
  throw new Error('reads failed');
}
(async () => {
  const routes = [[AERO, USDC, false, FACTORY]];
  const out = await call(ROUTER, routerIface.encodeFunctionData('getAmountsOut', [AMOUNT, routes]));
  const [amounts] = ethers.AbiCoder.defaultAbiCoder().decode(['uint256[]'], out);
  const amountOut = amounts[1];
  const minOut = amountOut * 98n / 100n;
  const deadline = BigInt(Math.floor(Date.now() / 1000) + 1200);
  console.log('quote: 0.5 AERO ->', (Number(amountOut) / 1e6).toFixed(6), 'USDC | minOut(2%):', (Number(minOut) / 1e6).toFixed(6));
  const data = modIface.encodeFunctionData('swap', [AERO, USDC, AMOUNT, minOut, FACTORY, false, deadline]);
  let est = null;
  for (const url of RPC) {
    try {
      const r = await fetch(url, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_estimateGas', params: [{ from: EOA, to: MODULE, data }] }) });
      const j = await r.json();
      if (!j.error) { est = parseInt(j.result, 16); break; }
    } catch (e) { }
  }
  console.log('module.swap estimateGas:', est);
  fs.writeFileSync('/tmp/tk-module-settle.json', JSON.stringify({ to: MODULE, data, value: '0', amountOut: amountOut.toString(), minOut: minOut.toString() }));
  console.log('wrote /tmp/tk-module-settle.json');
})().catch((e) => { console.log('ERR', e.message); process.exit(1); });
