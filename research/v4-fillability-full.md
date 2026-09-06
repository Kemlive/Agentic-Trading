# RH Uniswap v4 — full shortlist fill scan (2026-09-05)

Method: `scripts/v4resolve3.cjs` — for each shortlist token, tested PoolKeys over
vanilla (static fees 100–10000, tickSpacings 1–1000, both orders) + **Pons Meme hook
`0xE5e70264…`** and **Twofold DualPoolHook `0x127B3f3b…`** (fee 0 and 0x800000) —
existence PROVEN via `PoolManager.getSlot0(keccak(poolKey))`; quotes via official
V4Quoter (`quoteExactInputSingle`) at $5/$25/$50 when a pool exists.
Official RH docs checked (docs.robinhood.com): canonical USDG `0x5fc5…`, WETH
`0x0Bd7…`; **no v4-hook registry on the chain doc** — hook set above is from
Pons/Twofold official sources. bankr = hook-address-unknown (never simulated).

Result (18 shortlist tokens): **every token = no-v4-pool (0 initialized pools)**.
- vanilla: 0 · Pons hook: 0 · Twofold hook: n/a for non-TWO tokens.
- Therefore: no v4/Pons quotes possible -> no PASS, nothing funded.

Raw data: `research/v4-fillability-full.json`
