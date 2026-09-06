# UNIFIED LANES — DRY-RUN TEST (2026-09-05)
Same Safe owner (0xB1AC signs caps), same Base-USDC settlement, same caps (2/25), for every lane. No per-chain native wallets. All dry (no funds).

| Lane | Unified leg | Dry-test | Result |
|---|---|---|---|
| BASE (reference) | Safe 0x203F + SwapModule 0x315F, USDC↔AERO on Aerodrome, owner-signed | Real settlement txs proven (config note, signer log) | PASS (live-capable, currently disabled per boss 2026-09-04) |
| ETHEREUM | Base USDC → ETH USDC via Rubic/LiFi | route 38abe4ad: $4.98 → 4.979004 USDC, impact 0.02%, ~1min | PASS (dry) |
| BNB | Base USDC → BSC USDT via Rubic/Squid | route 0a9b591d: $4.98 → 4.977383 USDT, impact 0.05%, ~1min | PASS (dry) |
| ROBINHOOD (Pons) | Pons v2 curves (USDG-pair/native) | $5 real eth_call fills PASS (183 native + 42 usdg earlier; freshness-gated 77) | PASS at venue (dry); USDC bridge leg: Rubic does NOT list RH → needs RH-native/USDG leg for unified settlement |

Config registry: `data/live/config.json → evmLane.venues` = {pons, ethereum, bnb}; each binds settlement BASE-USDC + caps 2/25 + mode dry. Investigation note: `research/INVESTIGATION-unified-usdc-pipeline-2026-09-05.md`.

Blocks to close before any of these go live as a unified flow: (1) RH cross-chain USDC leg (Rubic lacks RH) — RH-native USDG leg or bridge; (2) per-chain execution still needs either an RH-side Safe+allowlisted module or a unified EVM signing key; Base module stays Aerodrome-only. No live claims.
