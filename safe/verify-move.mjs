const rpc = 'https://mainnet.base.org';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' };
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const call = async (m, p) => (await (await fetch(rpc, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: m, params: p }) })).json()).result;
const balOf = async (token, who) => parseInt(await call('eth_call', [{ to: token, data: '0x70a08231000000000000000000000000' + who.slice(2).toLowerCase() }, 'latest']), 16);

(async () => {
  const rec = await call('eth_getTransactionReceipt', ['0x0d8f9b6371dda2a94fe4b77046e038245d5af8dc23dd26c0362eec47a1531d86']);
  console.log('settle status:', rec && rec.status, '| gasUsed:', rec && parseInt(rec.gasUsed, 16));
  const USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', AERO = '0x940181a94A35A4569E4529A3CDfB74e38FD98631';
  console.log('Safe USDC:', (await balOf(USDC, SAFE)) / 1e6);
  console.log('Safe AERO:', (await balOf(AERO, SAFE)) / 1e18);
})();
