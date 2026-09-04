# MPC multi-chain signing for the 6 EVM networks — Research (2026-09-03)

Goal: ONE MPC signing setup covering ETH · BNB · Base · Arbitrum · HyperEVM · Robinhood Chain,
so funding once → no more per-chain patching → only tuning + execution confirmation.

## Robinhood Chain facts (verified via search + explorer)
- Permissionless Ethereum-compatible **L2 built with Arbitrum Nitro/Orbit**; settles to Ethereum.
- **Chain ID 4663** (0x1237). Gas = ETH. Sub-second soft confirmations. 100 ms blocks.
- Public RPC: `https://rpc.mainnet.chain.robinhood.com`
- Explorer: `robinhoodchain.blockscout.com` (v1+v2 API; requires a browser User-Agent - plain bots get 403)
- Robinhood Wallet natively supports it; any EVM wallet can add it manually (chain 4663).
- Bridges: canonical (Ethereum <-> Robinhood, trustless) + partner cross-chain routes (deBridge etc.).
- Being an Arbitrum-Orbit EVM means **standard EVM tooling + any custom-EVM MPC applies**.

## MPC provider shortlist (custom-EVM capable → Robinhood 4663 works)
| Provider | Fit | Notes |
|---|---|---|
| **Fordefi** | Custom Chain feature (add any EVM chain w/ custom RPC) | enterprise MPC; policy engine; strong for teams/agents |
| **MPCVault** | Custom EVM networks via dashboard | non-custodial MPC, multisig, many chains |
| **Turnkey** | 30+ chains + programmable policy engine (SOC2) | explicitly marketed for AI-agent signing (best conceptual match to our Chief Agent) |
| **Web3Auth / Particle** | 30+ chains + chain abstraction | consumer-friendly; key shards |
| Fireblocks / Coinbase MPC | likely covers 4663 + majors | enterprise; verify Robinhood support + API access |

Note: none of the big six is "patched per chain" once the provider allows custom chainId/RPC add
(e.g., 4663). Execution after that = our loop: quote (Rubic for Rubic-supported majors; direct
DEX router for RH chain + others) -> propose -> MPC sign -> broadcast -> Telegram confirm.

## Architecture recommendation (post-funding, "tuning" phase)
1. Single MPC org/account (boss-owned) with ONE EVM address across all 6 nets.
2. Networks defined once in the MPC dashboard (chain id + RPC): 1/56/8453/42161/999/4663.
3. Our engine switches by chain config (no code patches): majors via Rubic/aggregator,
   Robinhood-chain tokens via its DEX route on 4663.
4. Funding lands on chosen chain; cross-chain moves only on demand (bridges incl. canonical).
5. Every execution proposed for boss confirm -> MPC policy signs -> logged + Telegram.

## Honest open items
- Robibnhood chain is NOT in Rubic's BLOCKCHAIN_NAME list -> RH-chain swaps need a direct DEX
  router (Uniswap-style on 4663) or 0x-style aggregator on that chain; verify liquidity later.
- MPC = custody moves from "key file we hold" to "provider-held key shards + policies" - boss must
  approve that model + choose provider (signup/API keys needed, like Cloudflare).
- Decision recorded to learning log (boss memory): no shortcuts, no per-chain wallet splits,
  custom network support is the requirement.
