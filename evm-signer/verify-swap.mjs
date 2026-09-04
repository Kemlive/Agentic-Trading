const HASH = '0xe354b819b17ef706e71e7d4253fd84fb0b4ba6dd7801daab5f62309bc0299b6d';
const rpc = 'https://mainnet.base.org';
const LANE = '0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8';
const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
const AERO = '0x940181a94A35A4569E4529A3CDfB74e38FD98631';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };
async function call(method, params) {
  const r = await fetch(rpc, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(JSON.stringify(j.error));
  return j.result;
}
function balOf(token) { return call('eth_call', [{ to: token, data: '0x70a08231000000000000000000000000' + LANE.slice(2).toLowerCase() }, 'latest']); }
const rec = await call('eth_getTransactionReceipt', [HASH]);
console.log('swap status:', rec.status, '| gasUsed:', parseInt(rec.gasUsed, 16), '| block:', parseInt(rec.blockNumber, 16));
const usdc = await balOf(USDC);
const aero = await balOf(AERO);
console.log('USDC balance:', parseInt(usdc, 16) / 1e6);
console.log('AERO balance:', parseInt(aero, 16) / 1e18);
const nxt = await call('eth_getTransactionCount', [LANE, 'latest']);
console.log('next nonce:', parseInt(nxt, 16));
