# LIVE Base in-and-out via Safe module (2026-09-05)

USDC→AERO→USDC through SwapModule from Safe 0x203F funds, owner-signed.
- buy leg `0x64875b67…` (gas 306446) — Safe now holds AERO
- sell leg `0xa60d4469…` (gas 224367) — AERO back to 0, USDC back in Safe
Result: USDC 0.50 → 0.497304 (net −0.0027 = ~0.60% round-trip), matching dry 99.40% Aerodrome retention.