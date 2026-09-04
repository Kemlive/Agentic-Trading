# Agentic Trading

An agent workspace for crypto **research → portfolio → rebalance → trade** workflows that run in
your MCP-capable coding agent (Cline), backed by two MCP servers:

- **wallet-signer** — connects your **Rabby** wallet (browser). Every send/sign is approved by you
  in Rabby. No private keys are stored on disk.
- **rubic** — token/chain search, cross-chain quotes, simulation, swap transaction building, and
  swap URLs.

## Layout

```text
AGENTS.md                 # operating rules auto-loaded when an agent works in this folder
agents/                   # role playbooks (research / portfolio / rebalance / trade)
data/portfolio.json       # canonical portfolio snapshot (read & written by agents)
research/                 # research notes, one file per topic/date
logs/                     # append-only trade/decision event log (gitignored)
src/                      # original Node starter (browser window.ethereum approach) — legacy
.env.example              # environment template (no keys)
```

## Typical session

1. **Connect** — agent calls `connect_wallet`; you approve in Rabby.
2. **Snapshot** — Portfolio Agent pulls `get_balance` / `get_token_balance` / `rubic_get_balances`
   and saves `data/portfolio.json`.
3. **Research** — Research Agent writes a note to `research/` (thesis, verified addresses, risks).
4. **Decide/Rebalance** — Rebalance Agent compares holdings vs `allocation.targets` and proposes a
   plan with live `rubic_quote_routes` + `rubic_simulate_swap`.
5. **Trade (only after your approval)** — Trade Agent builds the swap (`rubic_build_swap_tx`) and
   you approve in Rabby via `wallet-signer send_transaction`, or you run the provided
   `rubic_get_swap_url`.

## Safety

- Default is **DRY_RUN=true**. Flip it only when you are ready to send real transactions.
- The agent never sends without your explicit confirmation of amount, token, chain, and cost.
- No secrets or private keys belong in this repository (`.env` and `logs/` are gitignored).

