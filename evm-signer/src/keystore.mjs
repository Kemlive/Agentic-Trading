// keystore.mjs - encrypted EVM private-key storage (scrypt + AES-256-GCM). Keyfile 0600.
import fs from 'fs';
import os from 'os';
import path from 'path';
import crypto from 'crypto';
import { Wallet } from 'ethers';

export const KEYSTORE_PATH = process.env.EVM_KEYSTORE || path.join(os.homedir(), '.config/agentic-trading/evm-keystore.json');
export const PASSPHRASE_FILE = process.env.EVM_PASSPHRASE_FILE || path.join(os.homedir(), '.config/agentic-trading/evm-keystore.pass');

function scryptKey(pass, salt, N = 32768, r = 8, p = 1) {
  return crypto.scryptSync(pass, salt, 32, { N, r, p, maxmem: 64 * 1024 * 1024 });
}

export function encryptPrivateKey(privHex, pass) {
  const priv = privHex.startsWith('0x') ? privHex.slice(2) : privHex;
  if (!/^[0-9a-fA-F]{64}$/.test(priv)) throw new Error('private key must be 32 bytes hex');
  const wallet = new Wallet('0x' + priv);
  const salt = crypto.randomBytes(16);
  const iv = crypto.randomBytes(12);
  const key = scryptKey(pass, salt);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const data = Buffer.concat([cipher.update(Buffer.from(priv, 'hex')), cipher.final()]);
  const tag = cipher.getAuthTag();
  return {
    version: 1,
    address: wallet.address,
    kdf: { name: 'scrypt', N: 32768, r: 8, p: 1, salt: salt.toString('hex') },
    cipher: { name: 'aes-256-gcm', iv: iv.toString('hex'), tag: tag.toString('hex') },
    data: data.toString('hex'),
  };
}

export function decryptPrivateKey(enc, pass) {
  const key = scryptKey(pass, Buffer.from(enc.kdf.salt, 'hex'), enc.kdf.N, enc.kdf.r, enc.kdf.p);
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(enc.cipher.iv, 'hex'));
  decipher.setAuthTag(Buffer.from(enc.cipher.tag, 'hex'));
  const priv = Buffer.concat([decipher.update(Buffer.from(enc.data, 'hex')), decipher.final()]);
  const wallet = new Wallet('0x' + priv.toString('hex'));
  if (wallet.address.toLowerCase() !== enc.address.toLowerCase()) throw new Error('keystore address mismatch (wrong passphrase?)');
  return wallet;
}

export function loadPassphrase() {
  if (process.env.EVM_PASSPHRASE) return process.env.EVM_PASSPHRASE;
  if (fs.existsSync(PASSPHRASE_FILE)) return fs.readFileSync(PASSPHRASE_FILE, 'utf8').trim();
  throw new Error('no passphrase: set EVM_PASSPHRASE or create ' + PASSPHRASE_FILE);
}

export function saveKeystore(enc) {
  fs.mkdirSync(path.dirname(KEYSTORE_PATH), { recursive: true });
  fs.writeFileSync(KEYSTORE_PATH, JSON.stringify(enc, null, 2), { mode: 0o600 });
}

export function loadKeystore() {
  if (!fs.existsSync(KEYSTORE_PATH)) throw new Error('no keystore at ' + KEYSTORE_PATH + ' (run `keygen` or `import` first)');
  return JSON.parse(fs.readFileSync(KEYSTORE_PATH, 'utf8'));
}

export function savePassphrase(pass) {
  fs.mkdirSync(path.dirname(PASSPHRASE_FILE), { recursive: true });
  fs.writeFileSync(PASSPHRASE_FILE, pass + '\n', { mode: 0o600 });
}

export function newRandomKey() {
  return '0x' + crypto.randomBytes(32).toString('hex');
}
