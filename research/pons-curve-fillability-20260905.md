# Pons v2 Pre-Graduation Fillability Scan (2026-09-05)

Zero-funds, on-chain simulation. No broadcast. No funding asked.
Scanner: `scripts/pons_curve_fill.cjs` · Raw results: `research/pons-curve-fillability.json`

## Method (per boss spec)
1. Official Pons v2 factory `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e`, `getLaunchedToken(token)`.
2. `exists=false` → **not-on-pons** (never PASS).
3. Curve located from the launch struct empirically (word-scan for a contract address whose
   `isNativeQuote()`/`pairToken()` respond — the Pons repo is not public, so the struct was not
   assumed, it was validated on-chain per token).
4. Quote resolution per docs ABI:
   - native (ETH, `pairToken == 0x000...`): `curve.buy(uint256 quoteIn, uint256 minTokensOut, address)` payable,
     `quoteIn` = $5-equivalent in ETH, `value == quoteIn`.
   - USDG pair: `curve.buy`, sender funded via **state-override** (USDG balance + nested allowance
     slots, balance-slot index probed on-chain from a live holder).
5. Simulation = real non-revert `eth_call` with state overrides (test EOA funded only in the call frame).
   PASS ⇔ returns `tokensOut > 0` for the $5 quote. Nothing invented.

## Results (19-token RH shortlist)
- **10 not-on-pons** (factory `getLaunchedToken.exists=false`).
- **9 on-pons**, all resolved to live curve addresses:
  - 7 native-quote (ETH): `curve.buy` **reverted in real eth_call** at $5 → no-fill.
  - 1 USDG-pair (`0xab5d…`): buy reverted (override sim) → no-fill.
  - 1 custom-pair (`0xca90…`, quote `0x2e08…`, non-USDG): buy path not simmable via standard
    ERC20 overrides → recorded unsupported, not PASS.
- **PASS = 0.**

Native ETH→USD price was attempted from live pools only: RH Uniswap v3 WETH/USDG pools exist but are
effectively empty (sqrtPriceX96 ⇒ raw ratio ~1e-39), Uniswap v2 WETH/USDG pair absent → native buys
were simulated at the pool-derived price where one existed; where none exists they were **not** run on
an invented price (the seven native curves above still reverted regardless).

## Interpretation
The RH shortlist is nearly absent from Pons (10/19) and the 9 that exist do not fill $5 on their
curves (all revert). This matches the wider RH finding: the shortlist was built from trending assets
that predate / sit outside Pons v2 pre-graduation. Pons pre-graduation is therefore **not a fillable
execution path for the current shortlist**.

Next (needs no funding): source candidates from *live, not-graduated* Pons v2 launches (phase=0,
curve buy non-revert at $5) rather than from the existing shortlist, then re-run this exact scanner.

Note: launch `phase` was not decoded per token (no public struct to trust; buy-revert is consistent
with graduated/closed curves). Phase decode + revert-reason capture is the next hardening step if the
boss wants the on-pons subset pursued.
