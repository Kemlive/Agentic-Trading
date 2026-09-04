// pc.mjs - probe ProxyFactory callability + selectors
import { ethers } from 'ethers';
const factory = '0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67';
const sel1 = ethers.id('proxyCreationCode()').slice(0, 10);
const sel2 = ethers.id('getChainId()').slice(0, 10);
console.log('proxyCreationCode() selector:', sel1, '| getChainId() selector:', sel2);
async function call(data, label) {
  const r = await fetch('https://base-rpc.publicnode.com', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_call', params: [{ to: factory, data }, 'latest'] }),
  });
  const j = await r.json();
  console.log(label, '->', j.error ? 'ERR ' + JSON.stringify(j.error) : 'ok ' + j.result);
}
await call(sel2, 'getChainId');
await call(sel1, 'proxyCreationCode');
const c = await fetch('https://base-rpc.publicnode.com', { method: 'POST', headers: { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getCode', params: [factory, 'latest'] }) });
const cj = await c.json();
console.log('factory code len:', cj.result ? cj.result.length / 2 - 1 : cj.error);

