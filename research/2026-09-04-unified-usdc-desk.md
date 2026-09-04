# Unified USDC Desk — One Account Operating Model (Agentic Trading)

**Date:** 2026-09-04 · **Status:** ratified (boss full approval) · **Benchmark:** fomo.family mechanics

## Model (mirrors how fomo.family runs its account, self-custody variant)

1. **ONE account, one unit of account = USDC.** Every deposit/trade/withdrawal is
   denominated in USDC. The account spans two trading lanes that share one equity,
   one risk budget, and one daily kill switch:
   - **Solana lane** — USDC held in the SOL hot wallet (`GHojAX…`), reserve floor $12.
   - **EVM lane** — USDC held in the Base Safe (`0x203FD7…`, owner `0xB1AC…`), floor $5.
   - All native tokens (SOL/ETH) are **reserve + gas only**, never a trade leg.
2. **Every buy is USDC → token**, executed on the coin's **native chain** (enforced
   by the USDC-ONLY GATE). The coin then **sits on its native chain**.
3. **Every sell is token → USDC**, returning to the lane's USDC:
   - Solana memes → Solana USDC (`settleToUsdcLane: solana-usdc`).
   - EVM tokens → Base USDC (`settleToUsdcLane: base-usdc`), per `evmLane.settlement`.
4. **One balance sheet** (unified): `portfolio_state` reports `usdcTotal` +
   `cashByLane {solana, base, other}` + non-meme value (AERO); `portfolio_manager`
   computes equity = cash + meme + other and applies meme caps only to memes.
5. **Deposit protocol (one account → fund ONCE, anywhere):** USDC is chain-specific
   (Solana-USDC ≠ Base-USDC contracts), so funds must physically sit on the chain a
   trade executes on. BUT you never have to split a top-up yourself: deposit the whole
   amount to the vault on whichever chain is easiest for you (Solana USDC to `8ZGuiQZ`,
   or Base USDC to the EOA/Safe), then the advisor (`usdc-topup-advisor.py`) rebalances
   lanes (bridge) to keep every lane above its floor before the next trade. Optional
   hint to avoid bridge fees: if the top-up is for the SOL memecoin desk send Solana
   USDC; for the EVM desk send Base USDC. USDC in, USDC desk.
6. **Cross-lane top-up (advisor-only):** when a lane is below its floor and the other
   lane has surplus, `scripts/usdc-topup-advisor.py` recommends a bridge amount
   (never executes; boss GO + Execution required). A lane never sends below its floor.

## Bridge provider of record (2026-09-04) — Phantom DexBridge
- Boss directive: use **Phantom DexBridge** for cross-chain moves; it supports our
  EVM settlement set. Verified vs Phantom docs (help.phantom.com, "Supported networks"):
  **Solana · Ethereum · Base · Robinhood Chain · HyperEVM** (also Polygon/Sui/Bitcoin).
  **BNB & Arbitrum are NOT Phantom-supported wallet networks** per the same docs —
  treat as "verify-in-app before routing" (if DexBridge shows them live, note it here).
- Execution model: **manual Phase-1** — boss opens Phantom → DexBridge/swap →
  picks from-network USDC, amount, destination address (EVM lane = Base Safe
  `0x203FD7…` for Base-USDC settlement), and confirms. Rubic stays for quoting and
  for non-Phantom legs (e.g., native Solana memecoin swap paths).
- Why this matters for us: Rubic lists no route for Robinhood chain (4663); DexBridge
  covers RH + HyperEVM + Base in one UI, matching `evmLane.chains` minus BNB/Arbitrum.

## Position record contract (fields on every open position)
`chain` (native chain the coin sits on) · `settleToUsdcLane` · `inputAsset: "USDC"` ·
plus existing `qty / costUsdc / marketValueUsd / status`.

## Sources / evidence
- fomo.family: "your cash balance is held in USDC, and trades go USDC → token and back"
  (SellThePump tutorial/FAQ 2026-08); self-custodial wallet, coins native-chain,
  cross-chain swaps gasless (DataWallet 2026); one account across chains (fomo blog).
- Ours: `data/live/config.json` (`evmLane.settlement`, `operatingPolicy.tradeLeg=usdc`,
  `walletAccounts`), `scripts/portfolio_state.py`, `scripts/usdc-topup-advisor.py`.


## Multi-chain topology ledger (boss, 2026-09-04) — LIVE vs REGISTERED
```
                     CORE TREASURY (Base USDC in Safe 0x203F…)  = settlement anchor
              ┌──────────────────────┴───────────────────────┐
   LIVE INFRASTRUCTURE (funds + engines)        REGISTERED READY-SURFACES (funded $0)
   • Solana lane  - hot GHojAX + vault 8ZGuiQZ   • ETH · BSC · ARBITRUM
   • Base lane    - Safe USDC + AERO (Base autopilot)         • HYPER_EVM · ROBINHOOD
   - balance reads active                       - balance reads = 0 (per-chain now wired
   - auto-bridge wired (Solana<->Base)             where USDC addr verified; RH pending)
   - live capital deployed                      - no execution engines live
                                                - settlement routes map back to BASE USDC
```
Rules this enforces: the desk may hold exposure on ANY of the 6 registered EVM networks
(coin stays on its native chain), but BASE is the operational + settlement anchor of the
whole EVM side. Solana is the meme lane anchor. No subagent may assume capital or engines
exist on a registered-only surface.

## Verified USDC contracts (per chain, for multi-chain reads)
- BASE `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (6dp) · verified (Circle)
- ETHEREUM `0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48` (6dp) · Circle canonical
- BSC `0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d` (6dp) · Circle canonical
- ARBITRUM `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` (6dp) · Circle canonical
- HYPER_EVM `0xb88339cb7199b77e23db6e890353e22632ba630f` (6dp) · verified via Rubic
- ROBINHOOD — address PENDING verification (not in Rubic registry); reads return unread
- SOLANA `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (6dp) · verified

