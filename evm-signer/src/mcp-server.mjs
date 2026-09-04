#!/usr/bin/env node
// mcp-server.mjs — OUR OWN local "wallet-signer" MCP server (keystore-backed).
// Speaks raw stdio JSON-RPC (initialize / tools/list / tools/call) so Cline and
// scripts/evm-exec-call.py can drive it like the npx server, but signing uses
// the encrypted local keystore (~/.config/agentic-trading/evm-keystore.json)
// instead of a browser wallet. Chain/gas policy enforced by on-chain Safe
// module allowlist + evm-networks.json registry. Every sign/send is logged.
import fs from 'fs';
import os from 'os';
import path from 'path';
import readline from 'readline';
import { fileURLToPath } from 'url';

// Honour boss's env name (EVM_KEYSTORE_PATH) while staying compatible w/ keystore.mjs.
process.env.EVM_KEYSTORE ||= process.env.EVM_KEYSTORE_PATH || path.join(os.homedir(), '.config/agentic-trading/evm-keystore.json');
const { ethers } = await import('ethers');
const ks = await import('./keystore.mjs');
const sg = await import('./signer.mjs');

const LOG = path.join(os.homedir(), '.config/agentic-trading', 'mcp-signer-log.jsonl');
function logEvent(e) { try { fs.appendFileSync(LOG, JSON.stringify({ ...e, ts: new Date().toISOString() }) + '\n'); } catch {} }
const text = (t) => ({ content: [{ type: 'text', text: t }] });
const err = (msg) => ({ content: [{ type: 'text', text: 'ERROR: ' + msg }], isError: true });

let wallet = null;
function getWallet() {
  if (!wallet) wallet = ks.decryptPrivateKey(ks.loadKeystore(), ks.loadPassphrase());
  return wallet;
}

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const NETWORKS = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'live', 'evm-networks.json'), 'utf8')).networks;

const TOOLS = [
  { name: 'connect_wallet', description: 'Resolve the keystore signer address (no browser needed).', inputSchema: { type: 'object', properties: { address: { type: 'string' }, chainId: { type: 'number' } } } },
  { name: 'get_balance', description: 'Native balance of the signer (or given address) on a chain.', inputSchema: { type: 'object', properties: { chainId: { type: 'number', default: 8453 }, address: { type: 'string' } } } },
  { name: 'get_token_balance', description: 'ERC-20 balance of signer (or address).', inputSchema: { type: 'object', properties: { chainId: { type: 'number' }, contractAddress: { type: 'string' }, address: { type: 'string' } }, required: ['chainId', 'contractAddress'] } },
  { name: 'sign_message', description: 'personal_sign over the keystore key.', inputSchema: { type: 'object', properties: { message: { type: 'string' }, address: { type: 'string' }, chainId: { type: 'number' } }, required: ['message'] } },
  { name: 'sign_transaction', description: 'Build + sign a tx (to/data/value/chainId). Returns raw hex, does NOT broadcast.', inputSchema: { type: 'object', properties: { to: { type: 'string' }, chainId: { type: 'number', default: 8453 }, value: { type: 'string' }, data: { type: 'string' } }, required: ['to'] } },
  { name: 'send_transaction', description: 'Build + sign + broadcast a tx; returns the tx hash.', inputSchema: { type: 'object', properties: { to: { type: 'string' }, chainId: { type: 'number', default: 8453 }, value: { type: 'string' }, data: { type: 'string' } }, required: ['to'] } },
];

async function handle(name, a) {
  const w = getWallet();
  switch (name) {
    case 'connect_wallet': {
      if (a.address && a.address.toLowerCase() !== w.address.toLowerCase()) return err('requested ' + a.address + ' but keystore holds ' + w.address);
      return text(JSON.stringify({ address: w.address, source: 'local-keystore', chains: NETWORKS.map((n) => ({ chainId: n.chainId, name: n.name || n.chainId })) }));
    }
    case 'get_balance': {
      const chainId = a.chainId || 8453;
      const who = (a.address || w.address).toLowerCase();
      const net = sg.netFor(chainId);
      const bal = await sg.rpcCall(net.rpc, 'eth_getBalance', [who, 'latest']);
      return text(JSON.stringify({ address: who, chainId, balanceEth: ethers.formatEther(bal), balanceWei: bal }));
    }
    case 'get_token_balance': {
      const who = (a.address || w.address).toLowerCase();
      const net = sg.netFor(a.chainId);
      const rpc = net.rpc;
      const dec = await sg.rpcCall(rpc, 'eth_call', [{ to: a.contractAddress, data: '0x313ce567' }, 'latest']);
      const symHex = await sg.rpcCall(rpc, 'eth_call', [{ to: a.contractAddress, data: '0x95d89b41' }, 'latest']);
      const raw = await sg.rpcCall(rpc, 'eth_call', [{ to: a.contractAddress, data: '0x70a08231000000000000000000000000' + who.slice(2) }, 'latest']);
      const decimals = parseInt(dec, 16);
      const symbol = Buffer.from(symHex.slice(2).replace(/0+$/, ''), 'hex').toString();
      return text(JSON.stringify({ address: who, chainId: a.chainId, symbol, decimals, balance: ethers.formatUnits(raw, decimals) }));
    }
    case 'sign_message': {
      const sig = await w.signMessage(String(a.message));
      logEvent({ tool: 'sign_message', addr: w.address });
      return text(JSON.stringify({ address: w.address, signature: sig }));
    }
    case 'sign_transaction':
    case 'send_transaction': {
      const chainId = a.chainId || 8453;
      const built = await sg.buildAndSign(w, { to: a.to, chainId, value: a.value, data: a.data });
      logEvent({ tool: name, addr: w.address, to: a.to, chainId, nonce: built.nonce });
      if (name === 'sign_transaction') return text(JSON.stringify({ address: w.address, chainId, raw: built.raw }));
      const hash = await sg.broadcast(built.net, built.raw);
      return text(JSON.stringify({ address: w.address, chainId, nonce: built.nonce, hash }));
    }
    default:
      return err('unknown tool ' + name);
  }
}


const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
function send(o) { process.stdout.write(JSON.stringify(o) + '\n'); }

rl.on('line', async (line) => {
  let req;
  try { req = JSON.parse(line); } catch { return; }
  if (req.method === 'initialize') {
    return send({ jsonrpc: '2.0', id: req.id, result: { protocolVersion: req.params && req.params.protocolVersion || '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'agentic-wallet-signer', version: '1.0.0' } } });
  }
  if (req.method === 'notifications/initialized' || req.method === 'notifications/cancelled') return;
  if (req.method === 'ping') return send({ jsonrpc: '2.0', id: req.id, result: {} });
  if (req.method === 'tools/list') {
    return send({ jsonrpc: '2.0', id: req.id, result: { tools: TOOLS } });
  }
  if (req.method === 'tools/call') {
    const { name, arguments: args } = req.params || {};
    try {
      const r = await handle(name, args || {});
      send({ jsonrpc: '2.0', id: req.id, result: r });
    } catch (e) {
      send({ jsonrpc: '2.0', id: req.id, result: err(e && e.message || String(e)) });
    }
    return;
  }
  send({ jsonrpc: '2.0', id: req.id, error: { code: -32601, message: 'method not found: ' + req.method } });
});
