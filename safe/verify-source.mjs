// verify-source.mjs - submit SwapModule source to Base Blockscout for verification (standard-input-json).
import fs from 'fs';
import solc from 'solc';
import { ethers } from 'ethers';

const ADDRESS = '0x315f754ef53bb14c2f9001be8fe0d857e2e31013';
const SAFE = '0x203FD7cefb443672ef5700A1E27521c22A6E7B3A';
const ROUTER = '0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43';
const UA = { 'content-type': 'application/json', 'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0 Safari/537.36' };

const src = fs.readFileSync(new URL('./contracts/SwapModule.sol', import.meta.url), 'utf8');
const standardInputJson = {
  language: 'Solidity',
  sources: { 'contracts/SwapModule.sol': { content: src } },
  settings: { optimizer: { enabled: true, runs: 200 }, outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } },
};
const constructorArgs = ethers.AbiCoder.defaultAbiCoder().encode(['address', 'address'], [SAFE, ROUTER]);
console.log('constructor args:', constructorArgs);

const body = {
  standardInputJson,
  compilerVersion: 'v0.8.20+commit.a1b79de6',
  optimizationRuns: 200,
  constructorArguments: constructorArgs,
};

const res = await fetch('https://base.blockscout.com/api/v2/smart-contracts/' + ADDRESS + '/verification/via/standard-input-json', {
  method: 'POST',
  headers: UA,
  body: JSON.stringify(body),
});
console.log('http', res.status);
const text = await res.text();
console.log('response:', text.slice(0, 800));
