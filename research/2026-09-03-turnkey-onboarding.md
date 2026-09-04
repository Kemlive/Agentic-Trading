# Turnkey MPC onboarding + auto-trading (2026-09-03)

Goal: replace browser/Rabby signing with **Turnkey API signing** so the agent executes trades
programmatically (no copy-paste, no truncation, no pairing) across all six EVM networks - and,
longer-term, Solana - under boss-defined **policies** (auto-trading with guardrails).

## Status: CREDENTIALS VERIFIED - SIGNER BUILDING (2026-09-03)

- Organization ID + API public/private key received from boss, stored at
  `~/.config/agentic-trading/turnkey.json` (chmod 0600). **Never** print the private key again.
- API creds verified: signed `list wallets` request returned the org wallet.
- **Wallet found: "Buon"** (walletId `6437e844-a267-5f14-b9d7-433be0371e35`) with TWO accounts:
  - EVM `0xB1ACDaF72cA6648DdD54F5dB85B9Cf75d58f82b8`
    (walletAccountId `f0fb66a4-b96f-4ce1-acd7-0f777b68ed86`, path `m/44'/60'/0'/0/0`,
    `ADDRESS_FORMAT_ETHEREUM`) - **confirms the canonical lane address IS Turnkey-origin.** No
    address change needed; config.json already points at it.
  - SOLANA `8ZGuiQZzb6BMDeWjzPzowr6B839ftaJS15ihoscfqEk4`
    (walletAccountId `27559004-b6c3-4c1f-9451-0029b024d633`, path `m/44'/501'/0'/0'`).
- ✅ **First live MPC-signed broadcast VERIFIED on Base** (boss GO): tx
  `0x623b07506f7e1ed3c59a34773c29266f91bb454b00f99e5e85760bdd52ab8665` - status 0x1, from/to
  `0xb1ac...82b8`, value 0, gas used 21000, nonce 18 -> 19, gas cost ~0.0006 USD.
  Explorer: https://base.blockscout.com/tx/0x623b07506f7e1ed3c59a34773c29266f91bb454b00f99e5e85760bdd52ab8665
- Base lane capital verified live via direct RPC: **3.065134 Base USDC**, 0.0006705 Base ETH,
  nonce now 19.

## Capture points (RESOLVED)
1. Organization ID `4214c4d6-129c-4e49-9814-eee96319fc2f` - provided
2. API Public Key `0335f276...` - provided, verified
3. API Private Key - provided, stored 0600
4. Is `0xb1ac...` Turnkey-origin? **YES** - EVM account f0fb66a4 inside wallet Buon

## Why Turnkey for this
- Sign from code via API (Turnkey private key stamper) -> no 2KB calldata ceiling, no browser.
- Programmable **policy engine**: allowlist signers/contracts/chains, per-tx caps, daily caps.
- Keys are MPC-sharded by Turnkey; we hold only API credentials + policy control.
- One integration spans ETH/BNB/Base/Arb/HyperEVM/Robinhood(4663) + Solana.

## Signer integration (built in ~/.local/share/turnkey-signer/)
- Deps: `@turnkey/sdk-server` (Turnkey class + apiClient: ethSendTransaction /
  pollTransactionStatus / getNonces / getWalletAccounts), `@turnkey/api-key-stamper`,
  `@turnkey/http`, `ethers`.
- `turnkey.mjs` - shared helpers (config load, EVM account discovery, RPC helper).
- `list-wallets.mjs` - signed query: org wallets + accounts/addresses (verification only).
- `sign-broadcast.mjs` - **PRODUCTION PATH (verified live 2026-09-03, proof tx 0x623b0750...8665
  on Base)**: build unsigned tx (nonce/fees/gas from chain RPC) -> sdk-server
  `apiClient().signTransaction({ organizationId, signWith: <wallet ACCOUNT ADDRESS>,
  type: 'TRANSACTION_TYPE_ETHEREUM', unsignedTransaction })` -> returns FULLY SIGNED RAW TX
  (activity COMPLETED) -> ecrecover verify via ethers -> self-broadcast via chain RPC. Wallet
  accounts CANNOT use v1 `signTransaction`/`privateKeyId` ("private key not found"); the flat
  `signWith`-style call is the wallet-account route. Works on ALL EVM chains (any RPC), no
  Turnkey broadcast feature needed.
- `send-tx.mjs` - OPTIONAL Turnkey-managed `ethSendTransaction` (auto nonce/fee/broadcast +
  pollTransactionStatus until INCLUDED). Currently BLOCKED: org feature flag `EthSendTransaction`
  is not enabled (boss may toggle in console / plan-gated). Not required for trading.
- `@turnkey/viem` account pattern confirmed as the same underlying flat `signTransaction` route.

## Auto-trading policy (next: implement after first live trade params are agreed)
- Allow `signTransaction` (wallet-account, signWith = lane address) FROM our API key - already
  working without an approval policy (single-user org auto-completes its own activities). A
  policy will be added for guardrails as trading scales.
- Chain allowlist: 1, 56, 8453, 42161, 999, 4663 - ALL supported by the self-broadcast path.
- Per-tx value cap + daily cumulative cap (boss-set; e.g., start $5/tx, $25/day).
- Contract allowlist: our known routers (Rubic 0x3335..., 1inch 0x1111..., DEX routers on 4663).
- Every sign logged; Telegram confirmation per execution.

## Honest notes
- API PRIVATE key is a powerful secret (can sign per policy). Stored 0600; never in chat/logs.
- Real EVM capital on lane = 3.065 USDC Base + dust; auto-trading starts small and scales only
  with boss approval (tuning, not patching).
