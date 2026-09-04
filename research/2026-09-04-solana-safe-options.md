# Solana "Safe" Options — Research & Cost/Risk Comparison (Agentic Trading)

**Date:** 2026-09-04 · **Author:** Chief (Agentic Trading) · **Status:** research for boss decision

## Context
EVM lane mirrors the Safe pattern: funds live in a smart-contract Safe (`0x203FD7…`),
the owner EOA is kept at 0 USDC, and `SwapModule` enforces on-chain allowlists + caps.
Solana lane currently has **no on-chain safe layer**: funds sit in plain wallets
(agent hot wallet `GHojAX…`, boss vault `8ZGuiQZ…`) with only **off-chain** caps
(`hotWalletCapUsd 5`, reserve floor $12, sweep-back protocol). Boss asked whether SOL
"uses a Safe" and to research how to mirror it.

## Current model (baseline)
- Hot wallet OWNS its balance; agent key signs directly. Protection = small balance +
  off-chain policy + sweep-back. Risk: if the hot key file leaks, the entire hot balance
  is spendable with no on-chain limit. No contract/rent; zero extra cost; simplest ops.
- This is the model we run today ($11.97 USDC on hot).

## Option A — SPL Token Delegate cap (closest analog to "EOA 0 + Safe allowance")
Mechanism (Solana-native, documented):
- A token account stores one **delegate** + one **delegated_amount**. The delegate may
  transfer (or burn) up to that amount on the owner's behalf. "Until you revoke it or the
  delegate spends the full allowance, that program can move up to that many tokens
  without asking you again for each transfer." (solana.com/docs/tokens/basics/approve-delegate;
  SPL `Approve`, `Revoke`.)
- Design for us: vault `8ZGuiQZ` stays the **owner** of the USDC; set delegate =
  hot wallet key with delegated amount = cap (e.g. $15). Agent buys = 2-step:
  (1) delegate-transfer USDC vault→hot ATA up to cap, (2) normal swap from hot.
  Sells still land on hot → sweep back to vault as today. Top-up = boss approves more
  delegate amount (Phantom) as the cap is spent — mirrors EVM allowance mental model.

| Criterion | Score |
|---|---|
| On-chain cap enforced | YES - delegate amount; hot key can't exceed it |
| Vault stays owner of funds | YES - hot never owns the reserve |
| Cost | ~0 (SPL approve/revoke txs = fees only, no rent) |
| Effort to integrate | Medium: add an approve/transfer leg to autopilot buys; small script to set/refill cap |
| Boss control | Approve/revoke/top-up from Phantom at any time; instant revoke |
| Fits autonomy | Good - agent runs within a fixed delegated allowance; boss tops up periodically |

Risk notes: delegate allowance applies per token account; attacker with the hot key can
move up to the delegated cap to any address (cap = blast radius). Residual risk if cap
set high. Trade leg needs vault→hot pull first (extra tx/instructions).

## Option B — Squads v4 multisig / smart account (the Solana "Safe")
Mechanism: Squads Protocol v4 = audited on-chain "m-of-n" account layer, the Solana
equivalent of Safe. Features (per Squads docs/blog, 2026): **roles & permissions,
spending limits, sub-accounts, time locks, network-fee relayer**, address lookup tables.
Teams hold treasury funds in a Squads vault with member-level authority — an agent signer
can be a member with a **spending limit** while the boss holds the owner role.

| Criterion | Score |
|---|---|
| On-chain cap enforced | Strongest: multisig quorum + roles + spending limits (+ optional timelock) |
| Vault stays owner | YES - funds in the Squads vault (smart account) |
| Cost | Higher: vault creation + account rent + program fees; Squads offers a fee relayer; advanced features have a subscription model (verify current pricing) |
| Effort to integrate | High: deploy multisig, configure roles/limits, integrate @sqds/multisig SDK into autopilot (propose+sign vault txs), test on devnet |
| Boss control | Owner/multisig authority; can veto/rotate members; strongest guarantees |
| Fits autonomy | Good at scale - agent autonomy bounded by roles + spending limits |
| Testability | Devnet; Squads is the standard multisig layer used by Solana treasuries |

Risk notes: more moving parts (SDK, config, key management); if the agent key is the only
signer with spending limits, a leak still only loses up to the limit (same blast radius as
Option A) — the real gain vs A is governance (multi-signer, timelock, roles), which matters
more when balances grow or multiple humans/agents share the account.

## Comparison matrix
| | Today (hot owns) | A: Delegate cap | B: Squads v4 |
|---|---|---|---|
| On-chain spend limit | No | Yes (delegated amount) | Yes (roles + spending limit) |
| Funds owner | Hot wallet | Vault | Squads vault |
| Blast radius if hot key leaks | Entire hot balance | Cap only | Cap only (+ governance) |
| Governance (multi-sig/timelock) | No | No (single approver) | Yes |
| Setup cost / ops complexity | 0 / simplest | ~0 / medium | Higher / highest |
| Autonomy fit at current size (~$12) | ok | best | overkill |
| Autonomy fit at scale (+$50, +$100s) | risky | good | best |

## Recommendation (Chief)
1. **Now / at +$50:** adopt **Option A (SPL delegate cap)** — Solana-native, ~free, exactly
   mirrors the EVM mental model ("vault owns, agent has a capped allowance, hot = 0").
   Small pilot on mainnet (cap ~$15, vault as owner, refill after each sweep-back).
2. **Later, when balances grow / multiple operators:** migrate the vault to **Squads v4**
   so the boss gets real ownership + governance while the agent keeps a spending-limited
   role. This is the true Solana "Safe".
3. Either way, sweep-back (hot→vault) and the Safe-only-holder rule stay permanent.

## Open items to verify before build
- Squads v4 current rent/pricing + whether a free tier suffices (docs.squads.so; verify 2026).
- Autopilot buy-flow refactor for a vault→hot delegate-transfer leg (blockhash + ATA edge
  cases); whether Phantom UI can set/refill delegate amounts cleanly.
- Exact blast-radius wording for delegate across DEX swap programs (SPL delegate applies to
  token transfers; swaps still run from the hot wallet after the pull leg).

## Sources
- Solana docs — Approve Delegate / Token basics (solana.com/docs/tokens/basics).
- SPL Token Program docs (approve/revoke; one delegate + delegated amount per account).
- Squads Protocol v4 docs/blog (roles, spending limits, sub-accounts, time locks, relayer).
- Internal: data/live/README §7 (sweep-back), config hotWalletCapUsd, learning-log.

