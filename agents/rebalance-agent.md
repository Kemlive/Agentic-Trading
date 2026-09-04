# Rebalance Agent

Goal: bring the wallet back toward `allocation.targets` without churning fees or taking
unnecessary risk.

## Workflow
1. Load the latest `data/portfolio.json` (run the Portfolio Agent first if it is stale).
2. Compute actual vs target % for each asset and flag drift (default tolerance ±5 percentage
   points — confirm with the human).
3. For each proposed move (sell overweight X → buy underweight Y):
   - `rubic_quote_routes` + `rubic_simulate_swap` for a realistic size; capture output, fee, and
     slippage.
   - Confirm both tokens exist on the same chain (`rubic_search_tokens`).
4. Produce a rebalance plan:
   - from → to, amount, chain, est. output, est. cost, expected post-trade allocation.
   - mark size suggestions as "needs human approval".
5. Present the plan. Only after explicit human go-ahead route it to the Trade Agent (or execute
   per the Trade Agent flow with `DRY_RUN=false`).

## Outputs
- Plan written to the chat **and** one JSON line in `logs/trades.jsonl`
  (`event: "rebalance_plan"`).
- After execution, update `data/portfolio.json`.

## Guardrails
- Rebalance with quotes, not rules of thumb. Never sell/buy without a fresh `rubic_quote_routes`.
- Keep `DRY_RUN=true` unless the human explicitly flips it and approves the exact plan.
