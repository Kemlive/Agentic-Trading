// signer.mjs - build + sign + optionally broadcast an EVM tx using the decrypted wallet.
import fs from 'fs';
import { Transaction } from 'ethers';
import { NETWORKS_PATH } from './networks.mjs';

export function netFor(chainId) {
  const nets = JSON.parse(fs.readFileSync(NETWORKS_PATH, 'utf8')).networks;
  const n = nets.find((x) => x.chainId === chainId);
  if (!n) throw new Error('unknown chainId ' + chainId);
  return n;
}

export async function rpcCall(rpcs, method, params) {
  let lastErr = null;
  for (const url of rpcs) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 15000);
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'user-agent': 'evm-signer/1.0' },
        body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      const j = await r.json();
      if (j.error) throw new Error(method + ': ' + JSON.stringify(j.error));
      return j.result;
    } catch (e) {
      lastErr = e;
    }
  }
  throw new Error('all RPCs failed for ' + method + ': ' + (lastErr && lastErr.message));
}

// Build unsigned tx (nonce/fees/gas from chain), sign with wallet, return raw signed tx.
export async function buildAndSign(wallet, { to, data = '0x', value = '0', chainId }) {
  const net = netFor(chainId);
  const from = wallet.address;
  const nonce = parseInt(await rpcCall(net.rpc, 'eth_getTransactionCount', [from, 'latest']), 16);
  let gasPrice = null, maxFee, maxPrio;
  try {
    maxPrio = await rpcCall(net.rpc, 'eth_maxPriorityFeePerGas', []);
    const block = await rpcCall(net.rpc, 'eth_getBlockByNumber', ['latest', false]);
    const baseFee = BigInt(block.baseFeePerGas);
    maxFee = (baseFee * 2n + BigInt(maxPrio)).toString();
    maxPrio = BigInt(maxPrio).toString();
  } catch {
    gasPrice = await rpcCall(net.rpc, 'eth_gasPrice', []);
  }
  let gasLimit;
  try {
    const est = await rpcCall(net.rpc, 'eth_estimateGas', [{ from, to, value: value || '0x0', data: data || '0x' }]);
    gasLimit = (BigInt(est) * 120n / 100n).toString();
  } catch {
    gasLimit = '1000000';
  }
  const base = { to, value: value || '0', data: data || '0x', nonce, chainId, gasLimit };
  const unsigned = gasPrice
    ? Transaction.from({ ...base, type: 0, gasPrice })
    : Transaction.from({ ...base, type: 2, maxFeePerGas: maxFee, maxPriorityFeePerGas: maxPrio });
  const signed = await wallet.signTransaction(unsigned);
  return { raw: signed, nonce, gasLimit, gasPrice, maxFee, maxPrio, net };
}

export async function broadcast(net, raw) {
  return rpcCall(net.rpc, 'eth_sendRawTransaction', [raw]);
}
