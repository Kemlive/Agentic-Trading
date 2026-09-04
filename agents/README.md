# Agents

Agent role playbooks for this workspace. One role is active at a time, chosen per request:

| Agent | Playbook | When to use |
|---|---|---|
| Research | `research-agent.md` | "research X", "should I buy/sell X?", watchlist, thesis |
| Portfolio | `portfolio-agent.md` | "show my holdings", "what do I own", snapshot, valuation |
| Rebalance | `rebalance-agent.md` | "rebalance", drift vs targets, allocation review |
| Trade | `trade-agent.md` | "buy/sell/swap X for Y" (after approval), executing an order |
| Live Trader | `live-trader-agent.md` | Phase-1 live orders on the Solana wallet: order tickets → boss approves → boss executes in Phantom |
| Scanner (Sniffer) | `scanner-agent.md` | Run pump-scan cadence; surface candidates by lifecycle phase |
| Migration Analyst | `migration-analyst-agent.md` | Pre-graduation / fresh-pool / migrated / alpha analysis |
| Snatcher Monitor | `snatcher-monitor-agent.md` | Adaptive exits: read holder/trader behavior while trades are open |

## Choosing roles
- New research → **Research Agent**; it writes to `research/`.
- Any question about the wallet → **Portfolio Agent** (read-only first).
- Drift/targets → **Rebalance Agent** (produces a plan, no execution).
- Execution → **Trade Agent** (only after explicit human approval).
- Live Solana orders → **Live Trader Agent** (Phase 1: boss executes in Phantom; see
  `data/live/README.md` for wallet/funding steps).
- Scanning/pipeline → **Scanner Agent** → hands to **Migration Analyst** (phase/graduation) →
  **Snatcher Monitor** (open-position behavior) → **Live Trader** executes only on boss GO.
- If a request spans roles, run them in order and hand off state via `data/portfolio.json` and
  `logs/trades.jsonl`.

## Handoff contract
- Portfolio Agent owns `data/portfolio.json`.
- Research Agent owns `research/`.
- Rebalance + Trade Agents read `data/portfolio.json`, write plans/events to `logs/trades.jsonl`,
  and Trade Agent refreshes `data/portfolio.json` after fills.
- Every agent appends one JSON line per meaningful event — never edits history.
