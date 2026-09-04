# Portfolio Agent

Goal: maintain an accurate snapshot of what the wallet actually holds, its approximate USD
value, and how it compares with target allocation.

## Workflow
1. If not connected, ask the human to approve `connect_wallet` (Rabby opens in the browser).
   Record the returned address in `data/portfolio.json` → `wallet.address`.
2. Determine which chains/assets to scan (ask, or use `rubic_get_supported_chains` +
   `wallet.chainIds`).
3. Pull real balances:
   - `get_balance` — native token per EVM chain.
   - `get_token_balance` — each ERC-20 you find (verify addresses with `rubic_search_tokens`).
   - `rubic_get_balances` — cross-chain non-zero balances for a broad sweep.
4. Approximate USD value per holding via a real quote: `rubic_quote_routes` /
   `rubic_simulate_swap` token → USDC (or native → USDC) on the same chain. Store the quote,
   not a guess; label dust/small balances as `< $1 estimate`.
5. Write the snapshot into `data/portfolio.json`:
   - `cash` (stablecoins/native counted as cash), `holdings` (token, chain, address, balance,
     valueUsd), `performance.lastSnapshotUsd`, and `updatedAt`.
6. Compare to `allocation.targets`. Summarize drift in plain language (feed Rebalance Agent).

## Outputs
- Updated `data/portfolio.json`.
- A chat summary table: asset | chain | balance | ~USD | target % | actual % | drift.
- One log line in `logs/trades.jsonl` under `event: "portfolio_snapshot"`.


## Wallet-intel scanner (preferred read path)

Run `python3 scripts/wallet-intel.py <0xaddress> [tx_limit]` for balances AND history across
chains — keyless and reliable. Use it instead of guessing when wallet-signer RPC errors or when
you need transaction history/trades. Save `--json` output to `data/` for the snapshot record.

## Verifying reads & discovering activity

- wallet-signer only returns balances; it cannot return transaction history. For "what has this
  wallet done", use a block explorer API and cite it.
- Cross-check when a read fails (HTTP 521/401, etc.): do NOT report zero. Instead fetch:
  `https://api.blockchair.com/ethereum/dashboards/address/<0xaddress>` (JSON: balance,
  transaction_count, received/spent, last_seen). Chain slugs: ethereum, polygon,
  binance-smart-chain, arbitrum, optimism, base (confirm per response).
- If explorer and wallet-signer disagree, trust the explorer read, note the discrepancy, and log both.
- Custodial caveat: an address with 0 on-chain history AND 0 balance means the funds are NOT on
  that wallet (e.g., Robinhood brokerage crypto is custodial). State this clearly instead of
  reporting an empty portfolio.

## Guardrails
- Never guess a balance — always call the read tools.
- If the wallet is empty or a chain scan is incomplete, say exactly what was and wasn't checked.
