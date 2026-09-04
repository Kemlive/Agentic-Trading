# Reverse Auto-Bridge Leg (BASE → SOLANA) — design & cost (T-6)

**Date:** 2026-09-04 · **Status:** quoted + designed; execution gated on boss choice

## Route (verified live, Mayan)
`Base USDC → Solana USDC` = **FAST_MCTP** (Circle CCTP), ~35s, protocolBps 3.

## Cost reality (fixed relayer cost dominates at small size)
| Amount | Expected out | All-in cost |
|---|---|---|
| $2.00 | 1.522 USDC | **23.9%** (≈ $0.48 fixed) |
| $20.00 | 19.514 USDC | **2.4%** |
| $50+ | ~0.5–1% | scales down further |

Recommendation: micro $2 reverse test costs ~$0.48; a $20 test costs ~$0.49 too but delivers
19.5 USDC to the SOL vault (also tops the SOL lane). Either is fine as a one-time proof.

## Execution design (Safe stays the ONLY holder — no EOA USDC)
1. **Quote** via `bridge_usdc.py mayan-quote --from base`.
2. **Safe approves Mayan Forwarder** on Base: owner EOA signs
   `Safe.execTransaction(USDC, approve(forwarder, amt))`.
3. **Safe calls Forwarder** with the Mayan swap payload (built from the SDK's
   `getSwapFromEvmTxPayload` / route params): another owner-signed `execTransaction`.
   Swapper = Safe; USDC input leaves the Safe; destination = SOL vault `8ZGuiQZ…`.
4. Relayer completes the Solana leg → USDC lands in the vault. EOA balance stays $0.00.

## Blocker to implement
`evm-signer` currently only signs transactions (`sign <tx.json>`), but Safe threshold-1
owner signatures require **signing the Safe EIP-712 tx-hash digest** and passing it in
`execTransaction(..., signatures)`. Small capability to add: `sign-digest <hex>` in
evm-signer (same encrypted keystore), then a Safe-call builder. This is a code change to
the signer (guard-reviewed, boss-approved), then the $2/$20 live test.


---
## LIVE RESULT 2026-09-04 — REVERSE LEG **PASSED**

After Base funding (+$50 → Safe 56.72), boss gave GO for the $20 Base→Solana proof.

| Step | Detail |
|---|---|
| 1. Approve | Safe.execTransaction approve Mayan fwd `0x3376…` 20e6 → tx `0x7484f593…` (confirmed) |
| 2. Re-sim + payload | SIM2 clean after allowance on-chain → Safe.execTransaction FAST_MCTP → tx `0x9d7367f8…` |
| Settle (Solana) | Mayan `5thSARnTq…`, clientStatus **COMPLETED** in ~30 s |
| Received | vault ATA `GRiCE…` 4.117257 → **23.630824 USDC** (+19.513567, ~99.95% of estimate) |
| Cost | $20 in → $19.5136 out ≈ **2.42% all-in** (relayer 0.478 + protocol 0.006) |


**Bug found & fixed during run**: Safe re-sim reverted `GS026` right after the approve landed — signature-vs-owner mismatch caused by an RPC race (hash fetched from a lagging node using the pre-approve nonce, sim executed on a fresh node). Fix: `rpc()` in `safe_reverse_bridge.mjs` now **pins the whole sequence to one node** + `SKIP_APPROVE=1` re-run of STEP2 passed clean.

## Files
`scripts/bridge_usdc.py` (quote/reverse now live) · mayan-sdk in
`~/.local/share/mayan-sdk` · Safe `0x203F…`, owner EOA `0xB1AC…`, dest vault `8ZGuiQZ…`.


