// rebalance.mjs - sell just enough AERO so the Safe is >=50% USDC by value. Writes /tmp/tk-rebalance.json
import fs from 'fs';
import { ethers } from 'ethers';
const CFG = JSON.parse(fs.readFileSync('/Users/earn/Agentic-Trading/data/live/evm-autopilot.json', 'utf8'));
const ABI = JSON.parse(fs.readFileSync('/Users/earn/Agentic-Trading/safe/artifacts/SwapModule.json', 'utf8'));
const modIface = new ethers.Interface(ABI.abi);
const routerIface = new ethers.Interface(['function getAmountsOut(uint256,(address,address,bool,address)[]) view returns (uint256[])']);
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' };
async function rpc(method, params) {
  for (const url of CFG.rpc) {
    try {
      const r = await fetch(url, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) });
      const j = await r.json();
      if (!j.error) return j.result;
    } catch (e) { }
  }
  throw new Error('rpc fail');
}
const balOf = async (t, w) => BigInt(await rpc('eth_call', [{ to: t, data: '0x70a08231000000000000000000000000' + w.slice(2).toLowerCase() }, 'latest']));
(async () => {
  const usdc = Number(await balOf(CFG.usdc, CFG.safe)) / 1e6;
  const aero = Number(await balOf(CFG.aero, CFG.safe)) / 1e18;
  // price USDC per AERO = sell 1 AERO -> usdc
  const out = await rpc('eth_call', [{ to: ROUTER, data: routerIface.encodeFunctionData('getAmountsOut', [ethers.parseEther('1'), [[CFG.aero, CFG.usdc, false, CFG.factory]]]) }, 'latest']);
  const arr = ethers.AbiCoder.defaultAbiCoder().decode(['uint256[]'], out)[0];
  const px = Number(arr[1]) / 1e6;
  const total = usdc + aero * px;
  const targetCash = total / 2;
  const need = targetCash - usdc; // usdc to add
  const sellAero = need > 0 ? need / px : 0;
  console.log('usdc', usdc.toFixed(4), 'aero', aero.toFixed(4), 'px', px.toFixed(5), 'total', total.toFixed(3));
  console.log('sell AERO:', sellAero.toFixed(4), '-> adds ~$', (sellAero * px).toFixed(3));
  if (sellAero < 0.05) { console.log('nothing to sell'); return; }
  const amountIn = ethers.parseEther(sellAero.toFixed(18));
  const out2 = await rpc('eth_call', [{ to: ROUTER, data: routerIface.encodeFunctionData('getAmountsOut', [amountIn, [[CFG.aero, CFG.usdc, false, CFG.factory]]]) }, 'latest']);
  const arr2 = ethers.AbiCoder.defaultAbiCoder().decode(['uint256[]'], out2)[0];
  const minOut = BigInt(arr2[1]) * 98n / 100n;
  const data = modIface.encodeFunctionData('swap', [CFG.aero, CFG.usdc, amountIn, minOut, CFG.factory, false, BigInt(Math.floor(Date.now() / 1000) + 1200)]);
  fs.writeFileSync('/tmp/tk-rebalance.json', JSON.stringify({ to: CFG.module, data, value: '0', sellAero: sellAero.toFixed(6), minOutUsdc: (Number(minOut) / 1e6).toFixed(6) }));
  console.log('wrote /tmp/tk-rebalance.json | minOut USDC', (Number(minOut) / 1e6).toFixed(6));
})().catch((e) => { console.log('ERR', e.message); process.exit(1); });
