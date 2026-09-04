// compile.mjs - compile SwapModule.sol -> safe/artifacts/SwapModule.json (abi + bytecode)
import fs from 'fs';
import solc from 'solc';

const src = fs.readFileSync(new URL('./contracts/SwapModule.sol', import.meta.url), 'utf8');
const input = {
  language: 'Solidity',
  sources: { 'SwapModule.sol': { content: src } },
  settings: { optimizer: { enabled: true, runs: 200 }, outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } },
};
const out = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (out.errors || []).filter((e) => e.severity === 'error');
if (errors.length) { console.log('COMPILE ERRORS:\n', errors.map((e) => e.formattedMessage).join('\n')); process.exit(1); }
const c = out.contracts['SwapModule.sol']['SwapModule'];
const artifact = { abi: c.abi, bytecode: '0x' + c.evm.bytecode.object, source: src };
fs.mkdirSync(new URL('./artifacts/', import.meta.url), { recursive: true });
fs.writeFileSync(new URL('./artifacts/SwapModule.json', import.meta.url), JSON.stringify(artifact, null, 2));
console.log('compiled OK | bytecode len:', artifact.bytecode.length / 2 - 1, '| abi fns:', c.abi.filter((x) => x.type === 'function').map((x) => x.name).join(', '));
