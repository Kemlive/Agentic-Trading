# evm-signer — self-hosted EVM signing daemon (our own Turnkey replacement)

Local signing service for the agent's EVM lane. Replaces Turnkey (which blocked on a free-plan
signing quota) with a key-agnostic daemon we fully control.

## What it does
- **Encrypted keystore**: private key stored AES-256-GCM + scrypt; keyfile and passphrase file are
  `0600`. The key only decrypts in memory at signing time.
- **Policy guardrails enforced in the signing path** (before any signature):
  - chain allowlist (1/56/8453/42161/999/4663)
  - `to`-address allowlist (tokens + routers only)
  - per-tx native value cap (wei) + per-tx USD cap
  - daily native value cap + daily USD cap
  - kill switch
- **Full audit log** at `~/.config/agentic-trading/evm-signer-log.jsonl` (0600): every attempt
  (sign_only / sign_send / sign_denied) with chain, to, value, nonce, txHash.
- **Sign + broadcast**: build unsigned tx (nonce/fees/gas from chain RPC) → sign → optional
  broadcast + explorer link. ERC-20 trade-size caps remain enforced by the engine (trade-agent).

## Layout
- `src/keystore.mjs` — encrypt/decrypt keystore
- `src/policy.mjs` — guardrails + daily-state + audit log
- `src/signer.mjs` — build/sign/broadcast (ethers)
- `src/cli.mjs` — commands
- `config/policy.json` — policy

## Usage
```bash
cd evm-signer && npm install

node src/cli.mjs keygen            # new key, encrypted, prints address
node src/cli.mjs import 0xPRIVKEY  # import existing key (e.g. the lane EOA) + encrypt
node src/cli.mjs address           # show signer address
node src/cli.mjs policy            # show policy
node src/cli.mjs kill on|off       # kill switch

node src/cli.mjs sign /tmp/tx.json 8453 --broadcast --ethUsd 2415
# tx.json: {"to":"0x...","data":"0x...","value":"0"}
```

## Keys & security (boss rules)
- Keystore: `~/.config/agentic-trading/evm-keystore.json` (0600)
- Passphrase: `~/.config/agentic-trading/evm-keystore.pass` (0600) or env `EVM_PASSPHRASE`
- **Never** put the private key / passphrase in this repo, chat, or logs. The repo only holds the
  encrypted-key *format* code and policy — no secrets.

## Safe route (next, per boss directive)
- Deploy a Safe (same deterministic address on all 6 EVM chains) as the funds holder, with the
  agent EOA (this signer's address) as owner, and `AllowanceModule` giving it token-limited,
  daily-capped spend. Even if the signer key leaks, on-chain policy caps the blast radius.
- Scripts live in `safe/` (added in the next step).
