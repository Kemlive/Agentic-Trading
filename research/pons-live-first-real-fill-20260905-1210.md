# Pons USDG-pair — first REAL 1-USDG live round-trip (20260905-1210 UTC)

Wallet 0xB1ACDaF7... (RH 4663) · token `0x65566986…` · curve `0x28d63926…`

| step | tx | result |
|---|---|---|
| approve USDG→curve | `0x6c83ff2c7b0dd2b9…` | ok |
| buy 1 USDG | `0x57304aeef2134c77…` | ok → 2718347174283462862865 tokens |
| approve token→curve | `0x7fe4e29eea035847…` | ok |
| sell all back | `0xf828994733173851…` | ok → 0.9801 USDG |

Round-trip: 1.0000 USDG in → 0.9801 USDG back (**1.99% all-in**, incl. fees). Tokens back to 0. Gas ≈ 0.000136 native ETH.

This is the sim→operational proof for a Pons v2 USDG-pair curve. Venue execution proven at 1 USDG; automated lane NOT armed (scaling/caps/policy remain boss-gated).