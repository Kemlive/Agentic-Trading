# Terminal Trending-Funnel Recon — how others funnel "trending" tokens (2026-09-04)

Scope: identify how Phantom Terminal (Solana) and the Robinhood-Chain scanner
ecosystem surface + funnel trending tokens; compare with our own feed so we can
tune/trick our data layer later. RESEARCH ONLY — no code or config changed.

## 1. Phantom Terminal (Solana side)
- What it is: Phantom wallet's pro web terminal (public beta, trade.phantom.com),
  built by the **SolSniper** team (Phantom acquired SolSniper Aug 2025).
- Funnel presented to users: **Trending tokens · Newly launched memes · Migrated
  tokens · Perp markets (Hyperliquid)**; P&L, wallet tracking, watchlists,
  TradingView charts, limit/stop/take-profit.
- Solana-only today; "support for more chains" explicitly planned. **No
  Robinhood Chain coverage yet** — RH trending is a separate ecosystem (below).
- Algo detail is not public. Public docs only promise: "Explore trending tokens,
  newly launched memes", "lightning-fast execution, sub-second", wallet sync.
  The discovery backbone is inherited from SolSniper (scanner heritage).

## 2. Solana terminals (to widen the comparison)
- **BullX Neo**: token discovery "Neo Vision", Safety Score, sniper detection,
  multi-chain; strong pump.fun hunt tooling. Community playbooks: slippage
  10–15% new launches / 5–8% established; priority fee 0.015–0.02 SOL congested;
  "MEV Only" mode + bribe for new launches.
- **Photon**: Raydium + Jupiter web sniper; auto-buy on price performance
  (e.g. target tokens up ≥50% in their first hour).
- **Axiom / xFractal (AI-agent terminal) / pump.fun Terminal (ex-Padre)**.
- Common Solana funnel: launchpad (pump.fun) new pair → watch migration
  (graduation to Raydium) → trade on DEX. Filters used everywhere: age band,
  mcap band, min liquidity, min 24h volume, txns, holders, **maker buy/sell
  split**, rug/honeypot + safety checks, dev-buy / sniper flags.
## 3. Robinhood Chain (chain 4663) — where "trending RH tokens" actually live
- **Pons launchpad** = RH's bonding-curve layer (pump.fun analog). Tokens climb
  a curve *before any DEX pool exists*, then **graduate** into normal DEX pools.
  RobinSight's "Pons" tab filters: Recent buys · Newest · Market cap · Nearest
  graduation; quote assets ETH / USDG / other; refreshes every 1–2 min from a
  "Pons launchpad API". (Our launchpads.json still lists pons.money as
  bot-walled "research" — this recon says the launchpad is real and live.)
- **RobinSight (rsight.io)**: per-token AI risk ("Signals" tiers, relative to a
  chosen window), holder map / behavior clusters, verdict/audit ("Audited by
  Claude"). Data: Robinscan + RH RPC + GeckoTerminal + DexScreener.
- **STONKSCAN**: real-time screener + trading terminal. Funnels: Trending ·
  Stocks · Gainers · New · Volume · Watch. Filters: min liquidity, min 24h vol,
  max age (hrs). Columns: mcap, price, 5m/1h/24h change, vol, liq, makers B/S,
  age. Security checks read live from Blockscout + on-chain. Swaps via Uniswap.
  Data: GeckoTerminal + Blockscout (⇒ GeckoTerminal indexes RH pools).
- **Robinscan**: "Top Tokens ranked by on-chain DEX volume" over 1h/12h/24h/7d;
  quote tokens excluded (they'd win every window); plus Stocks / Smart money /
  Top Traders tools. Volume = DEX swaps valued in USD.
- **BirdScan**: Trending · New · Top gainers · Hidden gems · Stocks & ETFs;
  sortable price / 24h / vol / liquidity / mcap / holders; whale activity + AI
  intel. Live sample (fetched): FAMI, AMC, **GME $19.56 +2.3%**, PONS ($0.68,
  $486M mcap, 40.9k holders), CASHCAT ($0.25, $245M mcap, **93.2k holders**),
  HOOD, ROBINCAT +65%, FATCOIN +300%, microduck, SHRUB, $AI (20.2k holders).

## 4. Coverage map: our feed vs these funnels
| Layer | Terminals do | We do today |
|---|---|---|
| Solana new launches | pump.fun new pairs, push/sniper | ✅ solfeed — pumpfun/raydium_v4/clmm/meteora program-level events |
| Solana migration | watch graduation pump→Raydium | ⚠️ we see Raydium events; no explicit "graduated" enrichment |
| Solana trending rank | vol/mcap/age/holder/social filters | ❌ no ranker (we're earliness-first, by design) |
| RH pre-DEX curve | Pons bonding tokens, curve progress | ❌ not captured (transfers only; pons flagged research) |
| RH DEX pools/volume | Top tokens by DEX volume 1h/12h/24h/7d | ❌ earlier Uni factory poolCount was empty; terminals show live pools ⇒ **re-verify** |
| RH asset behaviour | holder clusters, behavior, whale, AI risk | 🟡 rh_alpha transfer clustering (equity/stable/native/other) + uniqueFrom counts |
| RH price series | 5m/1h/24h %, gainers, hidden gems | ❌ we read price only at detection / for open positions |
| Buy/sell split, makers | B/S split columns | ❌ not computed |
| Risk pre-screen | BullX Safety Score, RobinSight Signals | ❌ rely on capital-guard stops, not pre-entry scoring |
| Duplicate tickers | PvP (1,900 "PONS") | ❌ no ticker dedupe |

## 5. Candidate tuning levers (for a LATER pass — nothing changed now)
1. **RH: treat graduation as migration.** Mirror our SOL pump→Raydium logic on
   the RH Pons curve → DEX graduation once we can observe curve/graduation
   events on-chain or via an index (RobinSight references a "Pons launchpad API").
2. **RH trending ≈ rolling transfer-volume velocity.** Robinscan ranks by DEX
   volume windows; pre-pool tokens can be ranked by transfer-rate acceleration +
   unique-address growth (we already log transfers + uniqueFrom) — approximates
   BirdScan/Robinscan trending from OUR OWN data only (no aggregator fees).
3. **Earliness as a leading filter.** Our forward-delta avg is now ~0.4s
   post-purge; positive-delta new mints (we beat DexScreener) are the funnel head.
4. **Borrow terminal threshold bands** for our ladder (already config-driven):
   STONKSCAN min-liq/min-vol-24h/max-age + BullX-style B/S split later.
5. **PvP dedupe rule** for RH before any buy path (same ticker, wrong contract).
6. **Risk pre-score** (optional) = holder concentration + dev/sniping flags to
   gate entries, complementing guard stops.

## 6. Open verifications (read-only next steps, no building)
- Pons launchpad program address + curve/graduation event signature (or API).
- Re-check RH Uniswap V3 factory poolCount now (was 0 earlier; ecosystem grew).
- Confirm GeckoTerminal indexes chain 4663 → usable as an external "trending"
  cross-check in the earliness style (our T_detect vs their T_trend).

