# Solana MCP Server — Vetting Report (2026-09-03)

Decision needed from the boss BEFORE any install. Goal: give the employee a signing path so it
can execute buy/sell trades on Solana (pump.fun) itself, still gated by boss per-trade approval.

## Checklist (from data/live/README.md §5)
| Criterion | Status |
|---|---|
| Open source, auditable code | see candidates below |
| Non-custodial / key handling acceptable | **NO candidate is browser-non-custodial.** All use a local private key → requires boss consent to a dedicated hot wallet policy |
| Reputable & maintained | varies |
| Jupiter / pump.fun / Raydium trade support | only Solana-Agent-Kit-based option has real TRADE |
| Devnet testable | yes (RPC env) |
| Kill switch | unload MCP + delete key file |

## Candidates evaluated
1. **sendaifun/solana-mcp** — `npm solana-mcp` v1.0.1 (Apache-2.0, 163★/52 forks, 31 commits).
   Based on Solana Agent Kit. Tools: TRADE, TRANSFER, DEPLOY_TOKEN, GET_PRICE, BALANCE,
   WALLET_ADDRESS, REQUEST_FUNDS, etc. TRADE covers Jupiter/pump.fun-style swaps via Agent Kit.
   Needs `SOLANA_PRIVATE_KEY`, `RPC_URL` (mainnet/devnet/testnet). **Concerns:** repo idle since
   May-2025; key in env; includes powerful tools (TRANSFER/DEPLOY_TOKEN) → must scope wallet to
   a small balance. Runner must be pinned to Node 20 (same fix as Rubic) to be safe.
2. **solanamcp/solana-mcp** (53★) — README is marketing/platform style; API-server orientation;
   harder to audit as a clean stdio MCP. **Rejected** for now.
3. **ExpertVagabond/solana-mcp-server** (1★, but active 2026-09, MIT, tests+Zod, keys in memory
   only, wallets via ephemeral session/import). **Good security posture but NO token-swap/TRADE
   tool** (SPL token ops, transfers, queries only) → can't execute our buys. **Rejected for
   trading**; could be a fallback for safe transfers.
4. **pumpfun-climcp / noahgsolomon/pumpfun-mcp-server** (22★, no license, stale Mar-2025).
   **Rejected.**

## Recommendation
**Install `solana-mcp` (sendaifun / Solana Agent Kit MCP)** as the Phase-2 execution server, WITH
strict mitigations:

1. **Dedicated agent hot wallet (NEW, generated locally).** Boss's Phantom wallet (8ZGui...) stays
   as the master. Agent wallet receives only small chunks from the boss. Rationale: the server
   needs a private key it can sign with; never reuse the boss's main wallet for that.
2. **Key handling:** private key stored ONLY in the MCP config env + a 0600-permission key file
   (or env only), never printed to chat/logs. `.env`/`.gitignore` already exclude secrets.
3. **Network:** rehearse on **devnet first** (REQUEST_FUNDS tool), then mainnet with a **cap ≤ $5**
   in the hot wallet until boss raises it.
4. **Approvals:** per-trade boss GO stays mandatory (EMPLOYMENT.md). autoApprove stays empty.
5. **Kill switch:** boss says STOP → server config removed + hot wallet drained to master.
6. **Maintenance risk accepted:** stale upstream; pinned Node-20 launcher, vendored if needed.

## Open decision for boss
- (A) Approve install of `solana-mcp` + create dedicated agent hot wallet (recommended).
- (B) Use ExpertVagabond for wallet/transfer only (no self-executed swaps) — keeps manual buys.
- (C) Reject automation; stay Phase-1 manual.

Then: install steps = patch MCP configs (6 clients), create Node-20 launcher, devnet rehearsal,
then mainnet test with the boss.
