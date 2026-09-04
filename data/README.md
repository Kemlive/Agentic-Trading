# `data/` — portfolio state

`portfolio.json` is the canonical portfolio snapshot. Agents refresh it after every balance
check and after any confirmed fill. Keep it valid JSON at all times.

## Schema

```jsonc
{
  "schemaVersion": 1,
  "updatedAt": "ISO-8601 UTC timestamp of last snapshot",
  "wallet": {
    "address": "0x... from connect_wallet",
    "label": "Rabby (via wallet-signer)",
    "chainIds": ["1", "137", ...]       // EVM chain ids scanned
  },
  "cash": [
    { "symbol": "USDC", "chain": "ethereum", "address": "0x...", "balance": "123.45", "valueUsd": 123.45 }
  ],
  "holdings": [
    { "symbol": "ETH", "chain": "ethereum", "address": "native", "balance": "1.25", "valueUsd": 4250 }
  ],
  "allocation": {
    "targets": { "ETH": 0.4, "USDC": 0.3 },   // fractions summing to 1
    "note": "..."
  },
  "performance": { "costBasisUsd": null, "lastSnapshotUsd": 4373.45 }
}
```

## Rules

- Values must come from `get_balance` / `get_token_balance` / `rubic_get_balances` and real
  `rubic_quote_routes`/`rubic_simulate_swap` quotes — never from memory.
- Balances are strings (decimal precision); USD values are numbers.
- After a rebalance/trade the Trade Agent updates this file and bumps `updatedAt`.
