# Pumpswap / pump-token Agent-Execution Builder — Research Note (2026-09-03)

Goal: let the employee agent-execute buys/sells of FRESH pump.fun / pumpswap tokens
(whitelisted majors already work via Rubic + signer).

## Findings
- **Rubic registry is whitelisted**: fresh memecoins (AGI, Solicorn) → `RUBIC_1007 invalid`.
- **quote-api.jup.ag is dead** in this timeline (no DNS record on any resolver; forced-IP refused).
  AgentKit TRADE unusable.
- **`api.jup.ag/swap/v1/quote` IS alive** (CloudFront) but is a NEW/different contract:
  - `GET /swap/v1/quote?...&amount=...` returns JSON errors (e.g. `TOKEN_NOT_TRADABLE` for SOL)
    → it parses requests, so it exists; semantics/allowlist unknown. Needs contract discovery
    (auth header? supported input mints? correct amount units? docs moved from
    station.jup.ag/docs/apis/swap-api which 404s).
- `lite-api.jup.ag` resolves but returns "Route not found" for trivial mainnet pairs → not a
  usable Jupiter quote backend.
- pump.fun frontend API was Cloudflare-blocked earlier (error 1016) from this machine.

## Next steps (ordered)
1. Discover the `api.jup.ag` swap contract: GET allowed input mints (try USDC, JUP, USDT as
   source), check for an OpenAPI spec at common paths, HEAD/OPTIONS, error messages for hints.
   If USDC→X works, it may be the v2 "Jupiter Swap" service with an allowlist of output tokens
   that still includes pumpswap tokens.
2. If Jupiter can't route pumpswap tokens, inspect the **pumpswap AMM program** used by
   DexScreener pairs (program id from pair data) and its public swap-instruction layout via
   program IDL/accounts on-chain — then build `scripts/pumpswap-swap.cjs` (quote from pool
   reserves → build CPI instructions → sign with agent key via existing signer pattern).
3. Validate on a $0.50 dust buy on ONE of the live paper-tracked tokens; verify; log.
4. If DEX program route is blocked, fallback = Pump.fun frontend swap API with browser-like
   headers (needs testing from this machine).

## Cadence (unchanged, verified)
- Paper scheduler `com.agentic-trading.paper` loaded (3×/day). Paper book: 5 open, -$1.95
  realized. Scans landing in `data/pump-scan-*.json`.
- Live agent wallet: 0.0478 SOL (~$4.82), all calibrations documented.
