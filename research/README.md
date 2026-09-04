# `research/` — research notes

One markdown file per research topic. Naming: `YYYY-MM-DD-<topic>.md`
(e.g. `2026-09-02-eth-vs-sol-layer1s.md`). No other artifacts belong here.

## Note template

```markdown
# <TICKER> — <topic> (<YYYY-MM-DD>)

- Conviction: STRONG BUY | BUY | HOLD | SELL | AVOID
- Timeframe: short / mid / long
- Chain: <chain> | Contract: <0x... from rubic_search_tokens>
- Suggested allocation: <fraction or %>

## Thesis
...

## Catalysts
...

## Risks / counter-thesis
...

## Valuation sanity check
- Latest quote/simulation (rubic_quote_routes / rubic_simulate_swap): <route, est output, fees>

## Sources
- <links/labels; mark unverified data clearly>
```

## Rules
- Contract addresses must come from `rubic_search_tokens` — never from memory.
- A note is a proposal for the Portfolio/Rebalance/Trade agents; it does not authorize a trade.
