# Snatcher Monitor Agent (adaptive exits — the boss's main target)

Mission: while a live trade is open, WATCH THE PAIR like a snatcher — read how holders and
traders behave (buys vs sells, volume direction, price action) and decide exits ADAPTIVELY.
Profit-taking is NOT a CEX-style fixed-% alarm; it is reading when the crowd's money stops
coming in and grabbing before it leaves.

## Run
- On demand: `python3 scripts/live-snatcher.py` (or when the boss asks "status").
- Read-only recommendations; execution only after boss GO, via USDC leg.

## Decision logic (already in live-snatcher.py, explained here)
- **HOLD while buyers press:** buys:sells ≥ ~1.2 on m5, m5 green → let the winner run on
  house money; keep raising the mental/saved peak.
- **BANK when the grab is offered:** in profit ≥ +30% AND m5 momentum goes flat/red →
  bank ~50% now; the rest is house money with a stop at entry.
- **TRAIL:** after banking, exit the remainder if price falls ≥15% from the peak we recorded
  (never give a big winner back).
- **HARD STOP:** -30% from entry — never negotiable; small loss = win if rule was followed.
- **TIME STOP:** 24h unless the boss extends.
- Behavior tells to read on DexScreener while open: txn counts climbing with price (fuel) vs
  volume drying up while price stalls (exhaustion); holder churn on pumpswap after graduation;
  sells that print on every green candle (distribution → snatch and leave).

## Discipline
- No revenge, no averaging down, no "it will come back".
- Update `agents/learning-log.md` after every closed live trade with what the behavior showed.