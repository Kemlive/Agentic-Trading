// verify-sourcify.mjs - verify SwapModule via Sourcify v2 API (chain 8453 = Base).
import fs from 'fs';
const ADDRESS = '0x315f754ef53bb14c2f9001be8fe0d857e2e31013';
const CHAIN = '8453';
const TX = '0x83f653e8570b521ae6af1f0d0c10045f1d8e60fae3d2d51e392349cc06cd79bf';
const src = fs.readFileSync(new URL('./contracts/SwapModule.sol', import.meta.url), 'utf8');
const body = {
  stdJsonInput: {
    language: 'Solidity',
    sources: { 'SwapModule.sol': { content: src } },
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  compilerVersion: '0.8.20+commit.a1b79de6',
  contractIdentifier: 'SwapModule.sol:SwapModule',
  creationTransactionHash: TX,
};
const r = await fetch(`https://sourcify.dev/server/v2/verify/${CHAIN}/${ADDRESS}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
console.log('http', r.status);
const j = await r.json();
console.log('resp:', JSON.stringify(j).slice(0, 600));
const vid = j.verificationId;
if (vid) {
  for (let i = 0; i < 20; i++) {
    await new Promise((x) => setTimeout(x, 2000));
    const s = await (await fetch(`https://sourcify.dev/server/v2/verify/${vid}`)).json();
    console.log('status:', JSON.stringify(s).slice(0, 400));
    if (s.verificationStatus && s.verificationStatus !== 'inProgress') break;
  }
}
