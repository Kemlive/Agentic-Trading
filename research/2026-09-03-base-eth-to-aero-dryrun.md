# AERO — Base ETH→AERO dry-run demo (2026-09-03)

- Conviction: HOLD (dry-run demo — see fee analysis below)
- Timeframe: n/a
- Chain: BASE | Contract: `0x940181a94a35a4569e4529a3cdfb74e38fd98631` (Aerodrome, from `rubic_search_tokens`)
- Suggested allocation: n/a

## Demo executed (DRY_RUN=true — no funds moved)

Wallet: `0xb1acdaf72ca6648ddd54f5db85b9cf75d58f82b8` (Base dust: 0.0002045 ETH)

1. `rubic_quote_routes` (BASE ETH → AERO, 0.0002 ETH) → best route 1inch on-chain
   - Est. output: **1.0295 AERO** (~$0.50), min 1.0192 AERO, slippage 1%
   - Route path: ETH → (SOL) → USDC → AERO
2. `rubic_simulate_swap` → **rejected: RUBIC_3003 "not enough balance"**
   - Required for this route ≈ 0.0002 (amount) + 0.000319 ETH protocol fee (~$0.77) + gas (~$0.02) ≈ **0.00052 ETH**
   - Available dust (0.0002045 ETH) is insufficient → the trade is also uneconomical (fees > swap value)
3. `rubic_get_swap_url` (demo artifact):
   https://app.rubic.exchange/?fromChain=BASE&from=ETH&to=AERO&toChain=BASE&amount=0.0002

## Takeaways
- Full research→quote→simulate pipeline works end-to-end with real prices/fees.
- Dust balances cannot be swapped economically on Base via this route (fixed protocol fee dominates).
- Next live-capable test needs a funded wallet (≥ ~$10 per trade on Base is a reasonable floor).

## Sources
- Rubic MCP live quotes/simulation; wallet balances via wallet-signer (Base RPC).
- Ethereum mainnet + Polygon balances unverified (public RPC outages at snapshot time).
