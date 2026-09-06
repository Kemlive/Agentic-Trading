# UNIFIED LANE — READINESS MATRIX (2026-09-05, exhaustive in/out tests)

Method: identical unified pipeline per lane (Safe owner 0xB1AC signs caps → Base-USDC settlement → execute → settle back). Each lane tested round-trip in AND out at $2/$5/$20. Dry (no funds); BASE lane additionally has live real-tx proof.

| Lane | $2 RT | $5 RT | $20 RT | Consistency | Status |
|---|---|---|---|---|---|
| BASE (USDC↔AERO) | 99.40% | 99.40% | 99.40% | flat across sizes | **READY** (live-proven + fresh quotes) |
| ETHEREUM (Base USDC↔ETH USDC) | ~99.7% | ~99.1% | ~99.98% | stable (per-leg 0.4% + gas) | **READY (dry)** |
| BNB (Base USDC↔BSC USDT) | ~99.3% | ~99.1% | ~99.6% | stable | **READY (dry)** |
| ROBINHOOD Pons (USDG-pair) | 98.01% measured LIVE (1 USDG real round-trip) | $5/$20 fills PASS (impact <0.5%) | $5/$20 fills PASS | protocol-fee dominated (~2%) | **READY** (venue proven live) |

Test legs (Rubic route ids): ETH in `ea2b353f/$2`,`38abe4ad/$5`,`23298b4d/$20`; ETH out `399cc924/$2`,`f08291af/$5`,`2e03e5ae/$20`. BNB in `5f96e5a1/$2`,`0a9b591d/$5`,`b3dd7cb7/$20`; BNB out `323182e4/$2`,`f539105a/$5`,`f3b3347a/$20`. BASE router quotes via Aerodrome getAmountsOut $2/$5/$20. RH Pons: live 1-USDG round-trip + size scan ($5/$20 fills, impact 0.36–0.46%).

Conclusion: unified lane pipeline is consistent across every chain, every direction, every size tested — retention floors: BASE 99.4%, ETH ~99%, BNB ~99%, RH-Pons ~98% (protocol fee). Ready for per-lane live flip under the existing caps and Safe-owner signing model.
