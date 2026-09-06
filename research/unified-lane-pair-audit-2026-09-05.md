# UNIFIED LANE — MULTI-PAIR AUDIT (2026-09-05)
Dry quotes/sims of varied pairs across chains from unified Base USDC ($5). All PASS. No failures/missing connections in tested matrix.

| Chain | Pair | Provider | Got (for ~$4.98-5) | Impact |
|---|---|---|---|---|
| BASE | USDC→WETH | LiFi (on-chain) | 0.001997 WETH ($4.99) | 0.12% |
| ETHEREUM | USDC→WETH | Relay | 0.001974 WETH ($4.93) | 0.91% |
| ETHEREUM | USDC→USDT | LiFi | 4.9665 USDT | 0.27% |
| BSC | USDC→WBNB | Squid | 0.006512 WBNB ($4.96) | 0.39% |
| BSC | USDC→CAKE | Squid | 2.2170 CAKE ($4.97) | 0.28% |
| ARBITRUM | USDC→WETH | LiFi | 0.001985 WETH ($4.97) | 0.29% |
| POLYGON | USDC→WETH | LiFi | 0.001986 WETH ($4.97) | 0.28% |
| POLYGON | USDC→USDT | Squid | 4.9658 USDT | 0.29% |
| ROBINHOOD | Pons USDG-pair | Pons v2 curve (real eth_call) | fills PASS $1/$5/$20 | 0.36-0.46% |

Plus (readiness matrix): stable round-trips at $2/$5/$20 in+out on ETH/BNB (~0.02–0.18%/leg), Base USDC↔AERO 99.40% retention flat, RH live 1-USDG round-trip measured 98.01%.

Cross-chain providers used in tests: LiFi, Squid, Across, Relay — pipeline selects best per route automatically (Rubic aggregation). All returned sane fills; variance is provider fee/gas only. Audits continue as a standing gate before live flip.
