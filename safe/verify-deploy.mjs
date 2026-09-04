const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const rpc = 'https://mainnet.base.org';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };
async function call(method, params) {
  const r = await fetch(rpc, { method: 'POST', headers: UA, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(JSON.stringify(j.error));
  return j.result;
}
const code = await call('eth_getCode', [SAFE, 'latest']);
console.log('Safe code deployed:', code !== '0x', '| codeLen:', code.length / 2 - 1);
const owners = await call('eth_call', [{ to: SAFE, data: '0xa0e67e2b' }, 'latest']); // getOwners()
const th = await call('eth_call', [{ to: SAFE, data: '0xe75235b8' }, 'latest']); // getThreshold()
console.log('threshold:', parseInt(th, 16), '| owner0:', '0x' + owners.slice(26, 66));


