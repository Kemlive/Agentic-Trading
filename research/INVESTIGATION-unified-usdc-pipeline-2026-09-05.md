# INVESTIGATION — Unified USDC Execution Pipeline + Pons as another chain (2026-09-05)

**Rule applied:** foundation-first (per project-memory / AGENTS.md rule 6) — investigate before wiring.

## What was investigated (files read)
- `evm-signer/src/autopilot.mjs` — Safe EVM lane (rung-exit + fresh dip entry), default DRY, `--go` to live. Executes via SwapModule.swap; owner 0xB1AC signs through `cli.mjs sign --broadcast`. State/caps in `evm-autopilot.json` + `~/.config/agentic-trading/evm-autopilot-state.json`; events → `logs/trades.jsonl` + telegram notify.
- `data/live/evm-autopilot.json` — Base config: enabled=false (disabled 2026-09-04, capital consolidated to Solana), safe=0x203F, module=0x315F, usdc=Base USDC, aero, Aerodrome factory, stable=false; perTradeUsdCap 2, dailyBuyUsdCap 5, reserve floor, auto-entry on 4% dip.
- `safe/contracts/SwapModule.sol` + `safe/artifacts/SwapModule.json` — functions: allowedBuy/allowedSell, approveRouter, caps, delegate, router, safe, setCaps, setDelegate, setToken, swap. SwapModule is AERODROME-ROUTER-SPECIFIC (swap(tokenIn→tokenOut via factory/stable)) — it does NOT call arbitrary venues.
- `evm-signer/src/cli.mjs`, `src/mcp-server.mjs`, `src/networks.mjs`, `evm-signer/config/policy.json` — local keystore signer (0xB1AC), MCP tools (connect/balance/sign/send), policy allowlist + native/USD caps (perTxUsd 2.0 / dailyUsd 25.0).
- `data/live/config.json` evmLane — unified model: ONE Safe (0x203F) + ONE USDC pool + settlement = BASE USDC; other chains fed by bridging USDC on demand; buys sit on chain, sells settle to Base USDC. `venues.pons` now registered (see below).
- Learning-log LOCKED entries: 0x203F has no key (Safe; owner signs), 0xB1AC never trades directly, unified-USDC-not-per-chain principle.

## Observed foundation facts (what the pipeline actually is)
1. Custody: Safe 0x203F (Base) owns funds; module 0x315F is enabled with delegate + token allowlists + caps; ONLY the owner 0xB1AC (this machine's keystore) signs module ops.
2. Execution path: build module `swap` calldata → `cli.mjs sign ... --broadcast` (Base chain 8453) → module enforces router + token allowlists and per-token caps on-chain.
3. Settlement: sells convert to Base USDC inside the Safe; caps (2/25) mirror policy.
4. Chain extension today is UNIFORM-USDC: no per-chain Safe/native wallet. RH fits this if USDC is bridged on demand and any chain-local quote (USDG) is a swap leg.

## What "wire Pons as just another chain" means here (applies to)
- Same custody: Safe 0x203F owner-signs; same policy caps; same settlement (Base USDC).
- Pons on RH (4663) adds a venue leg: bridge USDC (Base→RH) on demand → swap USDC→USDG (RH local stable; Pons USDG-pair quotes it) → curve buy/sell direct on Pons v2 curve.
- Registered in `data/live/config.json → evmLane.venues.pons` (chain robinhood, venue pons-v2, safe/owner/settlement/caps, mode dry).

## Conflicts / contradictions found (must NOT be glossed over)
- SwapModule (0x315F) is Aerodrome-router specific; it cannot call a Pons bonding curve. Reusing "same Safe" for Pons needs either (a) an RH-side execution module supporting allowlisted direct calls (curve buy/sell) + Safe proxy on RH, or (b) a unified EOA trading key (boss-owned) that the engine signs with — no per-chain native wallets, but one chain-capable EVM signer that can hold bridged USDC/RH gas.
- 0x203F / 0x315F have NO code on RH (4663) — verified. The Safe pattern is Base-only today.
- RH gas = native (small ETH); Pons USDG-pair buys need RH USDG (convert from bridged USDC).
- Pons lane stays DRY until one of those execution prerequisites is true. No live claim.
