# UNIFIED LANE PIPELINE — WIRED + DRY-RUN PASS (2026-09-05)

**How every chain is wired (identical pipeline, one Safe owner signs caps, settlement = Base USDC, caps 2/25):**
`Lane config (evmLane.venues) → signer 0xB1AC (Safe owner, keystore) → settlement leg (Base USDC) → on-chain execution (module or Rubic) → profits settle back to Base USDC`.

| Lane | Buy leg (unified USDC out) | Settle leg (Base USDC back) | Round-trip net | Pipeline |
|---|---|---|---|---|
| BASE (reference) | USDC→AERO via SwapModule (owner-signed, real txs proven) | AERO→USDC into Safe | proven | PASS (live-capable) |
| ETHEREUM | Base USDC→ETH USDC (LiFi, 4.98→4.979004) | ETH USDC→Base USDC (Across, 4.959→4.955169) | **99.10%** (~0.90% all-in) | PASS (dry) |
| BNB | Base USDC→BSC USDT (Squid, 4.98→4.97738) | BSC USDT→Base USDC (LiFi, 4.957→4.953559) | **99.07%** (~0.93%) | PASS (dry) |
| ROBINHOOD (Pons) | Pons v2 USDG-pair $5 real fill (proven live 2026-09-05) | sell back 0.9801/1.00 | **98.01%** (~1.99% incl. protocol fees) | PASS (dry for auto; venue proven live) |

Route evidence (Rubic, dry quotes): ETH route `38abe4ad` + return `f08291af`; BNB route `0a9b591d` + return `f539105a`.
Config registry: `data/live/config.json → evmLane.venues {pons, ethereum, bnb}` — same owner/settlement/caps everywhere.
Auto pipeline: `scripts/pons_autopilot.mjs` (RH/Pons lane, dry) extends the same engine pattern as `evm-signer/src/autopilot.mjs` (Base lane).
