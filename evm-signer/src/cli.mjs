#!/usr/bin/env node
// cli.mjs - command line for the evm-signer daemon.
//   keygen [--pass P]         generate a new key, encrypt, save (prints address only)
//   import <0xpriv> [--pass P] import+encrypt an existing key
//   address                   print the signer address
//   sign <tx.json> <chainId> [--broadcast] [--ethUsd N]
//   policy                    print policy
//   kill on|off               toggle kill switch
//   status                    print daily usage
import fs from 'fs';
import crypto from 'crypto';
import { Transaction } from 'ethers';
import { newRandomKey, encryptPrivateKey, saveKeystore, loadKeystore, decryptPrivateKey, loadPassphrase, savePassphrase } from './keystore.mjs';
import { loadPolicy, checkPolicy, recordSpend, appendAudit, loadState, savePolicy } from './policy.mjs';
import { buildAndSign, broadcast } from './signer.mjs';

const [, , cmd, ...rest] = process.argv;

function getFlag(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : null;
}

async function main() {
  switch (cmd) {
    case 'keygen': {
      const pass = getFlag('--pass') || process.env.EVM_PASSPHRASE || crypto.randomBytes(24).toString('hex');
      const enc = encryptPrivateKey(newRandomKey(), pass);
      saveKeystore(enc);
      if (!process.env.EVM_PASSPHRASE && !getFlag('--pass')) savePassphrase(pass);
      console.log('ADDRESS', enc.address);
      console.log('keystore saved (0600); passphrase stored in passphrase file unless --pass/EVM_PASSPHRASE given.');
      break;
    }
    case 'import': {
      const priv = rest[0];
      const pass = getFlag('--pass') || process.env.EVM_PASSPHRASE || crypto.randomBytes(24).toString('hex');
      const enc = encryptPrivateKey(priv, pass);
      saveKeystore(enc);
      if (!process.env.EVM_PASSPHRASE && !getFlag('--pass')) savePassphrase(pass);
      console.log('ADDRESS', enc.address, '(imported + encrypted)');
      break;
    }
    case 'address': {
      console.log('ADDRESS', loadKeystore().address);
      break;
    }
    case 'sign-typed-data': {
      // EIP-712 typed-data signing (Swift EVM orders etc). Input: json file
      // {domain, types, primaryType, message}. Output: {address, signature}.
      const f = rest[0];
      if (!f) throw new Error('usage: sign-typed-data <typedData.json>');
      const td = JSON.parse(fs.readFileSync(f, 'utf8'));
      const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());
      const types = { ...(td.types || {}) };
      delete types.EIP712Domain; // ethers derives the domain type itself
      const signature = await wallet.signTypedData(td.domain || {}, types, td.message);
      appendAudit({ ts: new Date().toISOString(), event: 'sign_typed_data', primaryType: td.primaryType || '?' });
      console.log(JSON.stringify({ address: wallet.address, signature }));
      break;
    }
    case 'sign-digest': {
      // Safe (and other EIP-712) flows need a signature over a 32-byte digest, not a tx.
      // Usage: sign-digest <0x32byteDigest> [--chainId N]
      const digest = rest[0];
      if (!digest) throw new Error('usage: sign-digest <0x32byteDigest> [--chainId N]');
      const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());
      const sig = wallet.signingKey.sign(digest); // {r,s,yParity}
      const v = (typeof sig.v === 'number' && sig.v >= 2) ? sig.v : (sig.yParity ? 28 : 27);
      const out = { address: wallet.address, digest, r: sig.r, s: sig.s, v };
      appendAudit({ ts: new Date().toISOString(), event: 'sign_digest', digest: digest.slice(0, 18) + '…' });
      console.log(JSON.stringify(out));
      break;
    }
    case 'sign': {
      const txFile = rest[0];
      const chainId = parseInt(rest[1], 10);
      const doBroadcast = rest.includes('--broadcast');
      const ethUsd = getFlag('--ethUsd') ? Number(getFlag('--ethUsd')) : null;
      if (!txFile || !chainId) throw new Error('usage: sign <tx.json> <chainId> [--broadcast] [--ethUsd N]');
      const tx = JSON.parse(fs.readFileSync(txFile, 'utf8'));

      const wallet = decryptPrivateKey(loadKeystore(), loadPassphrase());

      // policy check BEFORE signing
      const decision = checkPolicy({ chainId, to: tx.to, valueWei: tx.value || '0', ethUsd });
      if (!decision.ok) {
        appendAudit({ ts: new Date().toISOString(), event: 'sign_denied', chainId, to: tx.to, valueWei: tx.value || '0', reasons: decision.reasons });
        console.log('DENIED', JSON.stringify(decision.reasons));
        process.exit(2);
      }

      const { raw, nonce, net } = await buildAndSign(wallet, { to: tx.to, data: tx.data, value: tx.value, chainId });
      console.log('SIGNED nonce', nonce, '| from', Transaction.from(raw).from);

      if (doBroadcast) {
        const hash = await broadcast(net, raw);
        console.log('BROADCAST', hash);
        console.log('EXPLORER', net.explorerUi + '/tx/' + hash);
        recordSpend(tx.value || '0');
        appendAudit({ ts: new Date().toISOString(), event: 'sign_send', chainId, to: tx.to, valueWei: tx.value || '0', txHash: hash, nonce });
      } else {
        appendAudit({ ts: new Date().toISOString(), event: 'sign_only', chainId, to: tx.to, valueWei: tx.value || '0', nonce });
        console.log('sign-only (no broadcast). Add --broadcast to send.');
      }
      break;
    }
    case 'policy': {
      console.log(JSON.stringify(loadPolicy(), null, 2));
      break;
    }
    case 'kill': {
      const v = rest[0];
      const p = loadPolicy();
      p.killSwitch = v === 'on';
      savePolicy(p);
      console.log('killSwitch =', p.killSwitch);
      break;
    }
    case 'status': {
      console.log(JSON.stringify(loadState(), null, 2));
      break;
    }
    default:
      console.log('commands: keygen | import <priv> | address | sign <tx.json> <chainId> [--broadcast] [--ethUsd N] | policy | kill on|off | status');
  }
}

main().catch((e) => { console.log('ERR', (e.message || String(e)).slice(0, 600)); process.exit(1); });

