# Agentic Trading — Agent Workspace

You are operating in an agentic trading workspace. Goal: **research → decide → trade/rebalance**
using two MCP tool suites that are available to this chat:

- **wallet-signer** — connects your Rabby wallet (browser) and signs/sends with per-transaction
  human approval. No private keys live anywhere on disk.
- **rubic** — searches tokens/chains, quotes routes, simulates swaps, builds swap transactions,
  and generates swap URLs.

Everything you read or write as an agent lives inside this folder. No keys are stored here.

## Roles (load the matching playbook before acting)

| Role | Playbook | Responsibility |
|---|---|---|
| Research | `agents/research-agent.md` | Which coins/chains to buy, sell, or watch; thesis + risks; verified addresses |
| Portfolio | `agents/portfolio-agent.md` | Balance snapshots, USD valuation, vs. target allocation |
| Rebalance | `agents/rebalance-agent.md` | Detect drift from targets and propose a rebalance plan |
| Trade | `agents/trade-agent.md` | Quote → simulate → build → execute a swap (only with explicit approval) |
| Live Trader | `agents/live-trader-agent.md` | Phase-1 live orders on the dedicated Solana wallet: build tickets → boss executes manually in Phantom |
| Fix/Guard | `agents/team-ops.md` | Watches code 24/7, proposes bug/config fixes to Chief/boss; NEVER edits code or funds without approval |

`agents/README.md` explains when to switch roles.

## Boss / Employee setup (read first)

- `EMPLOYMENT.md` — contract: mission, authority limits, kill switch, honesty clause.
- The agent is the **employee**; the human is the **boss** with final approval on all trades.
- `agents/learning-log.md` is the agent's **permanent memory** — read before every session,
  update after every closed trade and weekly review.
- Live trading target: **Pump.fun (Solana)** via `agents/pump-trader-agent.md` (hunting rules)
  and `agents/live-trader-agent.md` (Phase-1 execution protocol). **Phase 1 = manual only**: the
  agent builds order tickets; the boss executes in a dedicated Phantom wallet. Automated signing
  (Phase 2) is NOT wired and requires the vetting checklist in `data/live/README.md` to pass.

## Tools you may call

**wallet-signer (Rabby):**
- `connect_wallet` — connect Rabby. User must approve in the browser; returns the address.
- `get_balance`, `get_token_balance` — read-only chain queries (safe anytime).
- `tron_*` variants — same idea on TRON via TronLink.
- `send_transaction`, `sign_message`, `sign_typed_data` — **only** after the human confirms the
  exact amount, token, chain, and counterparty. These open a browser for approval.

**rubic (read-only configuration — no `EVM_WALLET_PRIVATE_KEY`):**
- `rubic_get_instructions`, `rubic_get_supported_chains`, `rubic_search_tokens`,
  `rubic_get_balances`, `rubic_quote_routes`, `rubic_simulate_swap`, `rubic_build_swap_tx`,
  `rubic_get_swap_url`, `rubic_track_status`.
- To move real funds: build with `rubic_build_swap_tx` then execute via wallet-signer
  (`send_transaction`, Rabby approves) **or** hand the human `rubic_get_swap_url`.

## Local wallet-intelligence scanner (use this for reads/history)

`python3 scripts/wallet-intel.py <0xaddress> [tx_limit] [--json]`

Pulls the FULL picture keylessly (no API keys, works at $0 balance): native balance per chain,
ERC-20 token balances with USD, transaction count, and recent transaction history across
Ethereum, Base, Polygon, Arbitrum, Optimism, and BNB Chain (source: Blockscout v2 + public RPCs +
Blockchair). wallet-signer/Rubic CANNOT return history — this scanner is the authoritative read
for balances AND activity. Add `--json` to get structured output to save in `data/`.

## Where state lives

- `data/portfolio.json` — canonical portfolio snapshot (refresh after every balance check or trade).
- `research/YYYY-MM-DD-<topic>.md` — research notes (template in `research/README.md`).
- `logs/trades.jsonl` — append-only event log: every decision, quote, approval, and trade.
  (`logs/` is gitignored; `data/` and `research/` are tracked.)

## Pre-action data directive (MANDATORY)

Before ANY trade, rebalance, allocation, or portfolio answer:
1. Fetch REAL-TIME wallet state for ALL reachable chains:
   `python3 scripts/wallet-intel.py <walletAddress> 5 --json`
   (native + ERC-20 balances + tx history; covers Ethereum, Base, Polygon, Arbitrum,
   Optimism, BNB, Scroll, zkSync, Gnosis, Celo, Avalanche, Fantom, Linea, Mantle, zkEVM,
   Cronos, Blast, Aurora).
2. Cross-check with wallet-signer `get_balance`/`get_token_balance` for the connected chain
   and Rubic quote/simulate for any asset being traded.
3. Never act on stale `data/portfolio.json` — re-scan first, then save the fresh snapshot.
4. If a scan reports an address empty across all reachable chains, say so and ask the human
   for the coin + network or a tx hash instead of guessing.

## Operating rules (must follow)

1. Read `data/portfolio.json` before discussing allocation, rebalance, or trade size.
2. Never invent balances or prices. Call `get_balance` / `get_token_balance` /
   `rubic_get_balances`, and get a real `rubic_quote_routes` + `rubic_simulate_swap` before
   quoting numbers to the user.
3. `DRY_RUN=true` is the default (`.env`). While it is true: research, plan, quote, and simulate
   only — **never** call a sending/signing tool.
4. Every send/sign requires the human to state the exact details first, and approval always
   happens in Rabby. Tell the user precisely what they will be approving before calling.
5. Persist your work: research → `research/`; snapshots → `data/portfolio.json`; decisions and
   attempts → `logs/trades.jsonl` (one JSON object per line).
6. If chain, token, or amount is ambiguous, ask. Always double-check token contract addresses via
   `rubic_search_tokens` before quoting or building anything.
