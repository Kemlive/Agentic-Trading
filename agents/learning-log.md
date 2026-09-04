# Learning Log — Agent Memory / Behavior File

Purpose: the agent's permanent, honest memory of what works and what fails. The agent MUST
read this before every session and update it after every closed trade and weekly review.
The boss may add rules at any time — they override playbooks.

## How to update
Append a dated entry under the right section. Never delete old lessons. Format:
`(YYYY-MM-DD, <context>) <lesson + evidence>`.

## RULES THAT PAID (do more of this)
- (2026-09-03, setup) Capital protection first: small test sizes + predefined exits kept the
  account alive while oversized gambles fail. Verified via base-dust demo (sim rejected a
  trade whose fees exceeded value — that rejection was a WIN).
- (2026-09-03, setup) Fewer, higher-conviction positions with hard exits outperform many trades.

## MISTAKES TO NEVER REPEAT
- (2026-09-03, setup) Never act on screenshots/vibes — verify with on-chain/explorer data
  (Blockscout/public RPC/Blockchair). Screenshots of a wallet balance are NOT evidence of an
  on-chain balance.
- (2026-09-03, setup) Never report a balance as zero when a provider errored (521/401) —
  say "unverified", not "zero".

## MARKET / PUMP NOTES
- (2026-09-03, setup) Pump.fun tokens overwhelmingly go to zero; fast rule-based exits and
  tiny test sizes are the only edge available to a retail agent. Treat every entry as likely
  -100% until proven otherwise.

## BEHAVIOR OBSERVATIONS (boss feedback)
- (2026-09-03, setup) Boss requires the employee to say "I don't have the data" instead of
  guessing, and to escalate before doing anything irreversible.
- (2026-09-03, setup) Boss rewards: honest reporting, fast stop-losses, asking before trades,
  updating this file, and never fabricating P&L.

## PENDING / OPEN ITEMS
- (2026-09-03) Enable Solana signing path (Phantom + approved MCP/script) before any live
  Pump.fun trade. Until then: research + paper mode only.

### 2026-09-03 - First LIVE fill (SOLFONE, ticket-0001)
- Loop proven end-to-end: ticket -> boss manual execution -> sig verified on-chain (err null) -> fill logged.
- Honest lessons: (1) entry landed ~13.6% above ticket reference - microcap slipped even at ; real slippage matters. (2) For records trust token-account balance + finalized sig, not chart price. (3) ~0.002 SOL ATA rent locked on first token account - small but real at this wallet size.
- Position OPEN, rules armed: stop -30% = 0.00012772, TP rungs +50%/+trail, 24h time-stop. Enforce exits exactly like paper.

### 2026-09-03 - First LIVE round-trip CLOSED (SOLFONE): +28% in 17 min
- Buy 07:09:55Z .50 -> Sell 07:26:51Z .92. Realized +/bin/zsh.42. Verified both sigs on-chain (err null).
- Pipeline timings (boss manual execution): decision->buy-fill 134s, decision->sell-fill 232s, fill->fill 17 min.
- Key insight: manual pipeline is FAST ENOUGH for window trades, NOT for sub-minute snipes. True sniping needs Phase-2 automation.
- Snatcher lesson confirmed: sold +28% even though we were -22% on a mid-dip read minutes earlier; rules+patience > panic.

### 2026-09-03 - Phase-2: Solana MCP INSTALLED (solana-mcp@1.0.1, AgentKit)
- Agent hot wallet GHojAXGEY8... created; key 0600 outside repo; devnet gate;  mainnet cap.
- Verified on Node 20 (12 tools incl TRADE); first install corrupted by interrupted npm -> clean tree works (lesson: never kill mid-install).
- Registered in cline/claude-code/cursor/vscode. Devnet faucet down (upstream) - retry later.

### 2026-09-03 - AGENT-EXECUTED SWAP PROVEN (calibration SOL->USDC)
- Path: Rubic quote/build (unsigned VersionedTransaction) -> sign with agent hot-wallet key -> broadcast. Tx 5cRvZZ... finalized err null.
- Numbers: tool dispatch ~6s, send->confirm 613ms, quote->confirm ~60s (manual copy included; scriptable <10s). Accuracy: got 0.502984 USDC vs 0.5027-0.5028 quoted.
- Jupiter quote-api.jup.ag is DEAD in this timeline; AgentKit TRADE unusable; Rubic build + own signer is the working path.
- Blockhash: refresh recentBlockhash before sign/send if tx sits > ~1min (signer auto-refreshes, 3 retries).
- Next: convert USDC back to SOL or buy first real pump token on a clean candidate; both now fully agent-executable.

## 11. Round-trip closed + token-coverage finding (2026-09-03)
- SOL->USDC->SOL round-trip: both legs agent-executed (613ms/225ms send-confirm); net cost 0.000021 SOL (~0.4%). DFLOW fills async ~45s after broadcast - verify by re-polling balances.
- Coverage: Rubic registry is WHITELISTED - fresh pumpswap memecoins (AGI, Solicorn) return RUBIC_1007 invalid. Agent-executed buys of those tokens need a pumpswap-native route builder (Jupiter host is dead; Rubic can't see them). Majors (SOL/USDC) fully agent-executable.

### 2026-09-03 - ADAPTIVE SNATCHER MODEL + specialists
- Live profits taken by READING BEHAVIOR (buys vs sells, volume, txns on dexscreener), not a fixed CEX %. Bank when momentum fades >=+30%; trail rest -15% off peak; hard stop -30%; time stop 24h.
- Scanner classifies ON-CURVE/GRADUATING(50-90k fdv)/EARLY-MIGRATED/MIGRATED/ALPHA.
- Roles: Scanner -> Migration Analyst -> Snatcher Monitor -> Live Trader(exec on GO).
- AGI live: -6.7%, buys/sells m5 1.42 but m5 price -10% pullback - watch: snatch if m5 turns sellers; stop 0.00004023.

### 2026-09-03 - LESSON LOGGED: NEVER SLEEP ON AN OPEN TRADE
- Boss caught the agent not monitoring AGI after entry. That is a FAILURE of the snatcher mindset. Corrective: (1) decision to defend was MINE - closed AGI at -25.4% (-/bin/zsh.115) when behavior showed distribution (fading buyers, m5 red, approaching stop); (2) live-snatcher.py is now part of the 3x/day watchdog so open live positions are behavior-checked automatically; (3) in-session the agent proactively reports status on open trades without being asked.
- P&L recap: SOLFONE +/bin/zsh.42 (manual, early) | AGI -/bin/zsh.115 (agent, defensive close). Net live ~ +/bin/zsh.30. Reserve intact, all caps respected.

### 2026-09-03 - HELIUS ONLINE: holder concentration analytics
- Key validated (RPC 4.2.2). scripts/solana-holders.py gives top-10 holders + concentration.
- Lesson: #1 holder is often the AMM pool PDA (AGI: 22.75% = Pump.fun Amm pool GWEpF...). Exclude pool-sized accounts before judging rug risk. AGI real top-9 ~18.6% -> spread, not a whale dump setup.

### 2026-09-03 - SOLCATE exit -/bin/zsh.30: lessons
- (1) TOOLING: my retry loop double-fired the sell (both attempts broadcast) - NEVER auto-retry sends; single-shot with manual re-verify. (2) 20% slippage on an illiquid pump route fills badly - cap exit slippage at ~10% and expect worse fill. (3) Tape dumped between the +12% monitor read and fills minutes later - for hot memecoins, if you decide to bank, bank FAST or the edge vanishes. (4) Chasing a +180% 1h spike gets shaken; better fills come on pullback entries.
- Book after close: USDC 20.03 (mandate start 20.3357, -/bin/zsh.30/-1.5%). 12h window continues to 21:20Z.

## BOSS PROFILE - how the boss works (permanent memory; update on every correction)
- NO SHORTCUTS, no skipping steps. Do the full job, verify everything, finish properly.
- One unified EVM address for all EVM chains - never split wallets by chain.
- Each chain has its OWN explorer/network - never assume Etherscan-style. Robinhood = robinhoodchain.blockscout.com (needs browser UA; 403 for plain bots).
- Funds are custodial until actually withdrawn on-chain to a self-custody key - verify on-chain before claiming anything.
- Wants MPC so all 6 EVM nets (ETH/BNB/Robinhood/HyperEVM/Base/Arb) work from ONE signing setup; then only tuning + execution confirmation, no more chain patching.
- Reads/claims must be backed by evidence (traces, balances, explorer). Boss catches sloppy claims.


### 2026-09-03 - EVM BASE LANE TEST PASSED
- ETH->USDC on Base via Rubic quote/build + Rabby approval: tx 0x0a9add27... success. USDC 3.065 now on Base.
- Lesson: wallet-signer MCP times out at 60s while waiting approval - tx still broadcasts; always verify by block explorer after timeout, never assume failure. Raise server timeout in cline settings.

### 2026-09-03 - CHIEF MANDATE: EVM lane FULLY autonomous (boss: "Activate Automate... you're the Chief")
- Boss is away/not watching 24/7; delegated ongoing operation to the Chief. EVM lane now runs
  fully autonomous inside hard caps: RUNG-EXIT on open AERO (BANK ~50% @+30%, TRAIL -15% off
  peak, HARD STOP -30%, TIME STOP 24h) + FRESH auto-ENTRY only when flat after >=4% dip (never
  averaging down an open position). Reserve >=50% USDC. $2/entry, $5/day. Executes via
  SwapModule (on-chain allowlist+caps) + evm-signer; every tx -> trades.jsonl + Telegram.
  Scheduler: com.agentic-trading.evm-autopilot (15-min ticks) - verified HOLD tick.
- SOLANA lane honest status: snatcher SCAN/watchdog/paper agents are running
  (com.agentic-trading.autopilot/.paper + Cloudflare cron). LIVE auto-EXECUTION is NOT wired in
  any script (liveEnabled is config-only; AGENTS/EMPLOYMENT gate Phase-2 behind the vetting
  checklist). Flipping flags changes nothing - I reported this instead of faking activation.
  Next: build+vet the Phase-2 Solana auto-executor (hot wallet GHojAX, caps identical) with
  boss review before it touches real orders.

### 2026-09-04 - MULTI-CHAIN FIX + TOPOLOGY LOGGED (boss)
- research/2026-09-04-unified-usdc-desk.md now carries the MULTI-CHAIN TOPOLOGY LEDGER:
  live infra = Solana lane + Base lane (Safe treasury anchor); registered ready-surfaces =
  ETH/BSC/ARB/HYPE/RH (funded $0, settle back to Base USDC). Rules for subagents included.
- portfolio_state multi-chain reads FIXED: per-chain USDC contract + own RPCs via
  evm-networks.json (verified: base 0x8335, eth 0xA0b8, bsc 0x8AC7, arb 0xaf88,
  hyper 0xb883 via Rubic; robinhood PENDING). Extra-portfolio wallets now valued on their
  OWN chain (bug: 'ethereum' was being read on Base RPC). Tested live: base(SAFE)=6.46,
  eth/bsc/arb/hyper(EOA)=0.0, robinhood=None(unread). compile OK.
- Ready for funding + execution phase (boss "fix the multi and we proceed").

### 2026-09-04 - T-6 REVERSE: LIVE DEFERRED (boss choice, no wasted fees)
- Boss chose defer: Safe only $6.46 (needs $20+) and reverse is the wrong direction while
  Base is the short lane. Reverse infra is BUILT + DRY-VALIDATED and stays ready:
  evm-signer sign-digest/sign-typed-data (EIP-712) verified; forced FAST_MCTP quote+payload
  builder; Safe exec orchestrator (SIM1 clean, owner sigs verified). T-6 remains open until
  the Safe holds genuine EVM surplus (profits) — then run the live proof.
- temp files cleaned; team channel updated.

### 2026-09-04 - T-6 REVERSE BUILD: dry-sim status (Safe exec path)
- evm-signer: added sign-digest + sign-typed-data (EIP-712) - both verified live locally
  (recoverAddress == owner EOA for Safe tx-hash digests).
- Forced FAST_MCTP quote ($20 -> 19.5145, eff 20e6) -> payload via getFastMctpFromEvmTxPayload:
  to 0x337685fdaB40D39bd02028545a4FfA7D287cC3E2 (Mayan/CCTP), data len ok.
- Safe orchestrator (evm-signer/src/safe_reverse_bridge.mjs): SIM1 (approve via Safe
  execTransaction) = CLEAN. SIM2 (payload) reverts GS013 ONLY because allowance isn't
  on-chain yet (step1 simulated, not broadcast) - standalone eth_call can't see a future
  approve. Next: broadcast approve (harmless, no funds move), re-sim SIM2, then payload
  broadcast. Boss GO already covers the $20 live test; dry-only guard honoured until SIM2
  passes post-approve.

### 2026-09-04 - T-6 REVERSE LEG: quoted + designed (BASE->SOLANA, Safe-owned)
- Mayan reverse route VERIFIED: FAST_MCTP Base->Solana USDC ~35s, protocolBps 3. Cost is
  fixed-cost dominant at micro size: $2 -> 23.9% (~$0.48), $20 -> 2.4%, $50+ -> ~0.5-1%.
  bridge_usdc.py mayan-quote --from base works both sizes.
- Design (Safe stays ONLY holder): owner EOA signs Safe.execTransaction(USDC.approve
  forwarder) then Safe.execTransaction(forwarder swap) built from SDK payload; dest = SOL
  vault. research/2026-09-04-reverse-bridge-leg.md written.
- BLOCKER: evm-signer lacks digest-signing for Safe EIP-712 owner sigs -> add sign-digest
  + Safe exec builder (guard-reviewed code change). Live test gated on boss: accept $0.48
  cost at $2, or test $20 (19.5 USDC to vault, also tops SOL lane).

### 2026-09-04 - AUTO-BRIDGE PROVEN LIVE (Mayan SOL->BASE, boss-GO $1 test)
- Calibrated Mayan SWIFT/MCTP API from official docs (price-api/v3/quote + sia/v10/init +
  swap-sdk signatures from dist/*.d.ts - never guessed params). Installed swap-sdk 15.2.2
  in ~/.local/share/mayan-sdk; mayan-solana-swap.mjs signs source leg with the AGENT key
  and lets Mayan's relayer complete the destination.
- LIVE $1 test COMPLETED: source tx gXNz5XRZ... (Solana confirmed err null),
  status COMPLETED, Base Safe USDC 5.465690 -> 6.460691 (+0.995001 = ~0.5% all-in).
  bridge_usdc.py provider mayan now ready (quote + note). T-5 closed; T-6 open for the
  reverse leg BASE->SOLANA (Safe outbound wiring via evm-signer) - needs-boss.
- No funds lost; both lanes above floors; Safe-only holder rule intact (dest = Safe).

### 2026-09-04 - LANE FUNDING RESOLVER + AUTO-BRIDGE ORCHESTRATOR (boss GO)
- Boss: "never sit & wait for topup / never ignore a lane". Built the funding brain:
  scripts/lane_funding.py resolve() -> READY | AUTO_BRIDGE | BRIDGE_TICKET | NEEDS_FUND
  (+ SKIP_BRIDGE_TOO_SMALL). Guardrails: sender never drops below its floor, min bridge
  $1.50, buffer $0.50, auto-retry each tick. Tested scenarios incl. classic (sol 20/base 2,
  base need 6 -> BRIDGE/AUTO sol->base $4.50 keeping sol >=12) and live (base need 4 READY).
- scripts/bridge_usdc.py: providers layer (mayan=calibration pending, rubic=sim-gated,
  dexbridge_ticket=ready) + make_ticket() (exact amount/from/to + Rubic/Phantom URL) logged
  to Team HQ - so when auto is unavailable there is NO silence: exact ticket, auto-retry.
- T-5 open (needs-boss): calibrate Mayan SWIFT API schema + wire source-leg signing
  (sol agent key / evm-signer) + $1 micro mainnet test w/ boss GO. NO real funds moved yet.

### 2026-09-04 - T-1 DONE: PORTFOLIO MANAGER WIRED INTO AUTOPILOT DECISION LOOP
- Autopilot now runs the full PM advisory every tick: import portfolio_state/manager,
  build_portfolio_state(live), all_recommendations -> Risk cycle (daily-loss halt writes
  autopilot.off if haltNewEntries), Execution sized by sizing_for_regime
  (pm_size = clamp(suggested, floor 1.0, cap SIZE_USDC 2.5)) - used for vault pull,
  swap, position costUsdc & logs. Advisory result logged (portfolio_manager_advisory).
- Dry-validated: equity 20.85 / halt False / current pmSize ~1.04 (Extreme Greed + small
  equity - scales up with +$50). py_compile OK; guard scan clean. T-1 closed on board.
- Remaining open: T-4 (add real extra portfolio), T-3 (raise delegate cap to $50 after
  funding - needs boss approve in signer page).

### 2026-09-04 - MULTI-PORTFOLIO + ADD-WALLET (boss: "manage other portfolios")
- Portfolio Manager can now track/manage ANY portfolio, not just the main account.
  - data/live/portfolios.json registry (primary seeded = unified account; vault/hot/Safe/EOA).
  - scripts/portfolio_wallets.py: `add` (add wallet) + `list` (validation per chain).
  - scripts/portfolio_state.py: list_portfolios() + portfolio_state(pid): primary = full rich
    state; extra portfolios = read-only per-wallet USDC (solana/base lanes) so the PM can
    value/manage them. Aggregation of other chains ready to extend.
  - scripts/portfolio_dashboard.py: local dashboard (127.0.0.1:8125) - cards per portfolio +
    "➕ Add Wallet" button (POST /api/add, GET /api/state). Tested via API; compile OK.
- Team HQ notes: T-1 (wire PM into execution loop) still open; guard watch live.

### 2026-09-04 - TEAM HQ MESH LIVE (boss: wire agents to talk/report; guard on watch)
- Own-brand in-repo coordination (external task-board brand stays retired per cleanup).
- scripts/team_ops.py (renamed team_ops for import): board data/live/team/board.json +
  channel data/live/team/chat.jsonl; router kind->owner (scan->scanner, trade->execution,
  risk->risk, portfolio/rebalance->portfolio, sla->monitoring, fix/bug/config->guard,
  else->chief/boss). Commands: assign/claim/done/post/list/report.
- scripts/coder_guard.py (FIX/GUARD agent): read-only patrol - compile all scripts, core
  imports, TODO/FIXME markers -> posts needs-boss proposals. NEVER edits code/funds.
- agents/team-ops.md + AGENTS.md row. Demo: T-1 portfolio hookup, T-2 risk seed,
  T-3 guard proposal "Raise SOL delegate cap to $50" (needs-boss). Guard scan clean.
- Boss report = `python3 scripts/team_ops.py report`; money truth unchanged (data/+logs).

### 2026-09-04 - AUTOPILOT VAULT-CAP WIRING DONE (pull -> swap -> auto push-back)
- Boss chose A: autopilot now trades OUT OF THE VAULT under the SPL delegate cap.
- autopilot.py: VAULT_MODE=1; helpers vault_usdc/delegate_remaining/vault_pull/
  hot_to_vault/spl_transfer; new signer builder ~/.local/share/solagent-signer/
  spl-transfer.cjs (V0 base64, matches sign-broadcast). Buy path: if hot < trade size,
  pull SIZE_USDC from vault (cap-checked) then swap; sells auto push proceeds to vault;
  reserve/equity guards now vault-aware (cash_total = hot + vault). Position rows tagged
  fundedFrom=vault-delegate. Verified: py_compile OK, tx builder emits payer GHojAX + 1
  ix, live read sees vault $4.117 / remaining cap $3.80.
- BEHAVIOUR next tick: idle hot USDC (11.97) consolidates to vault (own wallets), then
  any qualifying buy pulls $2.50 from vault (cap rem 3.8 -> ~1.3 after one buy). When
  cap is exhausted autopilot SKIPS + Telegram asks boss to top up the delegate cap.
  Disable anytime: VAULT_MODE=0 or data/live/autopilot.off.

### 2026-09-04 - SOL DELEGATE-CAP PILOT: PASSED end-to-end
- Approve executed by boss in Phantom (tx 3Jm9k4PU...): delegate GHojAX on vault USDC
  GRiCE, cap $4.00. Verified on-chain (delegate + delegatedAmount 4.0), tx finalized.
- Pull test PASSED: GHojAX signed as DELEGATE, moved 0.20 USDC vault->hot
  (tx 31M1DjcK...); preflight OK (cap enforced on-chain). Balances mid: vault 3.917,
  hot 12.167. Push-back as owner (tx 4W59C9Gq...) restored: vault 4.117257, hot
  11.967357. Remaining delegated allowance now 3.8 (cap consumed 0.2) - cap stays
  active; boss can re-approve to reset to 4.0 later.
- LOG: events in logs/trades.jsonl (solana_delegate_cap_pilot). Tooling: 
  safe/solana-delegate-approve.html (signer page) + scripts/solana-check-delegate.py.
- PROOF: on-chain cap works; vault remains owner; hot can only spend allowance.

### 2026-09-04 - SOL DELEGATE-CAP PILOT STARTED (boss "proceed")
- Goal: vault 8ZGuiQZ owns USDC; agent hot GHojAX gets SPL delegate cap (on-chain
  allowance analog of EVM Safe+module). Canonical approve verified via @solana/spl-token:
  opcode4, source GRiCE (vault USDC, balance 4.117257), delegate GHojAX, owner vault
  signer, data 0400093d0000000000 (4,000,000 micros = $4.00 cap).
- Built: safe/solana-delegate-approve.html (localhost Phantom signer page, enforces
  vault account) + scripts/solana-check-delegate.py (verify). Current state verified:
  NO DELEGATE YET (owner 8ZGui, balance 4.117257).
- NEXT: boss opens page in Phantom (python3 -m http.server 8123 at repo root ->
  http://localhost:8123/safe/solana-delegate-approve.html), approves; then agent tests
  a delegated pull (vault->hot under cap) + push-back; log results.

### 2026-09-04 - RESEARCH: Solana Safe options (boss asked "does SOL use a Safe?")
- Answer: NO - SOL lane has no Safe/smart-account; only plain wallets + off-chain caps.
- research/2026-09-04-solana-safe-options.md compares: Today(hot owns) vs SPL delegate-cap
  (vault owns, hot gets delegated amount - EVM-allowance analog) vs Squads v4 (true Solana
  Safe: roles/spending limits/multisig). Chief rec: delegate-cap now (+$50), Squads later.

### 2026-09-04 - SAFE = ONLY EVM USDC HOLDER; EOA CLEARED (boss rule)
- Boss: use the Safe to avoid confusion - EOA balances will recur if we don't clear them.
- Executed EOA->Safe sweep tx 0xb82a2296... (evm-signer, nonce 40): 3.943739 USDC moved.
  Verified: EOA 0.000000, Safe 5.465690. EOA now signing+gas ONLY.
- New standing rule + helper: data/live/README s16 + scripts/evm-eoa-sweep.py (build
  full-balance transfer, optional --sign). After ANY EOA USDC inflow (esp. DexBridge
  deliveries landing on the connected wallet), run the sweep.
- Lesson: DexBridge pays the connected wallet (EOA), not the Safe - plan the sweep into
  the bridge procedure every time.

### 2026-09-04 - DEXBRIDGE DELIVERED: Base USDC +3.9437 (tx verified)
- Boss executed Phantom DexBridge Solana->Base. BaseScan tx 0x7a4d287a... SUCCESS,
  block 50855784: USDC 3.943739 -> 0xB1AC...82b8 (the unified EOA, NOT the Safe we
  put on the ticket - both ours; EOA owns the Safe).
- Net: bridge cost ~$0.13 on $4.07 (~96.9%). Unified desk now: solana 11.97 / base
  5.47 (Safe 1.52 + EOA 3.94) / total 17.43. Advisor: all lanes >= floor - done.
- Fix: portfolio_state live USDC read now sums BOTH Base holders (Safe + owner EOA)
  because DexBridge deliveries can land on either.
- OPEN: move EOA-held 3.94 USDC -> Safe (settlement model says funds in Safe) or keep
  EOA as a valid lane holder. Needs boss GO for the EOA->Safe tx via evm-signer.

### 2026-09-04 - SWEEP DONE: GHojAX -> 8ZGuiQZ 4.10 USDC (for Phantom DexBridge test)
- Boss-approved sweep executed via raw Token-program transfer signed by agent key.
  Tx 2uSmZa2Vjhuptdrpo8uVUFPzD98vijHLS2kk8GKhpj2KKXJXoidKytp6SDCPP64LeUgUnmTQePhgjV97y8VbuP33.
  Verified: 8ZGuiQZ 4.017->8.117 USDC; GHojAX 16.067->11.967 (hot floor $12 briefly
  under by $0.03 - acceptable one-off for the test).
- Lesson: right after broadcast, mainnet-beta RPC reads looked stale (balances
  unchanged + getParsedTransaction 'not found'), but getSignatureStatuses showed
  finalized err null; correct balances confirmed ~10s later. Always verify with
  signature status before trusting a first balance read.
- Note: solana-mcp TRANSFER has float->BigInt bug (amount*1e6 non-integer) - use
  exact integer-micros instruction scripts for SPL moves.
- NEXT (boss executes): Phantom DexBridge from 8ZGuiQZ (8.12 USDC available) ->
  Base USDC to Safe 0x203FD7..., then confirm sig here.

### 2026-09-04 - BRIDGE PROVIDER OF RECORD: PHANTOM DEXBRIDGE (boss directive)
- Boss: use Phantom DexBridge for cross-chain moves - it has ETH/BNB/BASE/ROBINHOOD/HYPER.
- Verified vs help.phantom.com "Supported networks": Phantom supports Solana/Ethereum/Base/
  Polygon/Robinhood Chain/HyperEVM/Sui/Bitcoin; BSC & Arbitrum are listed UNSUPPORTED.
  -> DexBridge confirmed for SOL/ETH/BASE/ROBINHOOD/HYPER; BNB/ARB = verify-in-app.
- Recorded in research/2026-09-04-unified-usdc-desk.md + data/live/README s16. Execution
  = manual Phase-1 (boss in Phantom). Rubic stays for quoting + non-Phantom legs.
- Next: run the $4.07 solana->base top-up through DexBridge once boss confirms the
  source Phantom wallet (see open question).

### 2026-09-04 - BRIDGE TEST: Across SOL-USDC->BASE-USDC sim FAILS (blocked)
- Tested advisor recommendation ($4.07 solana->base) end-to-end in SIMULATION ONLY:
  quote OK (Across, 0% fee, ~1min, min 3.9475), but rubic_simulate_swap AND
  rubic_build_swap_tx both returned simulationSuccess:false on the SVM leg (twice,
  fresh builds). NOT broadcast - never send a tx that fails simulation.
- Boss chose "try another provider": Across blacklisted -> relay (4.044, 0.64% impact)
  builds a tx but NO simulationSuccess field (backend does not sim SVM builds for
  relay) and summary riskLevel "high" (mismatched generic reason). mayan/near_intents
  similar no-sim. CONCLUSION: no green-simulation path for SOL-USDC->BASE-USDC via
  this Rubic MCP right now; bridge stays blocked. Manual browser test remains the only
  live option (swap URL logged below).
- Possible next steps (not done): browser test via swap URL
  (https://app.rubic.exchange/?fromChain=SOLANA&from=USDC&to=USDC&toChain=BASE&amount=4.07)
  with the hot wallet in a UI; or provider alternatives. Bridge stays blocked until a
  build simulates true. Lesson: quote != executable; always gate on simulation.

### 2026-09-04 - UNIFIED USDC DESK (items 1-6 approved; benchmark: fomo.family)
- Research: fomo.family = self-custody USDC-desk model - deposits convert to USDC, buys
  USDC->token native-chain, sells token->USDC, one balance across chains. Adopted the
  mechanics (NOT their custody/relayer/social parts).
- Implemented: portfolio_state cashByLane{solana,base,other}+usdcTotal (live-verified
  17.59 = 16.07 sol + 1.52 base); positions now carry settleToUsdcLane + inputAsset USDC
  (autopilot writes them); USDC-ONLY GATE guards buys; usdc-topup-advisor.py recommends
  cross-lane Rubic top-ups (sender never drops below its floor - found+fixed in test:
  naive bridge would have starved the SOL lane below $12). Docs: research/2026-09-04-
  unified-usdc-desk.md + data/live/README.md s16. Boss approval = full (1-6).
- Verified: advisor currently recommends $4.07 base <- solana (base $1.52 < $5 floor;
  solana keeps $12.00). Execution still requires boss GO for any bridge.

### 2026-09-04 - UNIFIED ACCOUNT MODEL (boss: "SOL+EVM one account, not two engines")
- Boss flagged portfolio code looked like it was splitting SOL & EVM into 2 engines.
  Ground truth from config.json/README/learning-log:
    ONE identity: Turnkey 'Buon' f0fb66a4 -> walletAccounts {solana 8ZGuiQZ..., evm
    0xB1AC...} (same account; learning-log: "Solana account 8ZGuiQZ also inside").
    Chain-native signing is required (Solana tx != EVM tx) but that is NOT two accounts.
    Execution sub-wallets: SOL agentHotWallet GHojAX (separate 0600 key, README sweep-
    back to vault) and EVM funds on Safe 0x203FD7 owned by the unified EOA.
- Code fix (no engine changes): portfolio_manager now accepts state["nonMemeValueUsd"]
  -> equity = cash + meme + other (EVM AERO counts as equity/reserve math, never as
  meme exposure). portfolio_state now: live-reads Base AERO balance + spot price into
  nonMemeValueUsd, and emits accounts{identity, execution} map. Verified live: equity
  19.15 = cash 17.59 (SOL 16.07 + Base USDC 1.52) + AERO 1.56; cash 91.8%/other 8.2%.
- Decision still OPEN with boss: canonical identity (Turnkey 8ZGui+0xB1AC w/ GHojAX as
  sweeping hot wallet) vs fully single-key routing on Solana.

### 2026-09-04 - PORTFOLIO STATE ADAPTER (boss directive: wire PM into decision loop)
- New scripts/portfolio_state.py: builds the real state dict for portfolio_manager.py.
  Sources: holdings.json (open positions), autopilot.json (dayStartEquity - only if
  day==today), config.json snapshots, newest pump-scan regime; live mode adds public-RPC
  USDC reads (Solana hot wallet + Base Safe) + DexScreener prices per open mint.
  Robust: never raises on missing files/feeds; degrades to defaults. Branded "agentic-trading".
- Verified live: cash 17.59 (16.07 SOL USDC + 1.52 Base USDC) matches heartbeat; regime
  Extreme Greed from newest scan; dayStartEquity correctly null (autopilot day stale -> -10%
  switch honestly unarmed until the day-start rolls). Pipeline all_recommendations() ok.
- Next (after +$50): wire Risk cycle -> all_recommendations(); Execution -> sizing_for_regime().

### 2026-09-04 - External task-board tooling retired (boss directive)
- Removed the third-party task-board integration from the codebase on boss directive
  (install artifacts, database dir, generated docs, editor hooks, playbook).
  Team task coordination + persistent memory now live fully in in-repo files again:
  this learning log, `agents/*.md` playbooks, `logs/trades.jsonl`, and `data/*.json`
  as the single financial source of truth.

### 2026-09-04 - PORTFOLIO MANAGER MODULE (boss: "do this, then I fund +$50")
- New scripts/portfolio_manager.py - pure, state-driven (no hardcoded balances; state dict
  in, recommendation dicts out). Policy: single meme 12%, cluster 25%, total meme 80%,
  cash 20% min; rebalance triggers 15/30/85/15; regime entry sizing Fear 12% / Neutral
  8-10% / Greed 5-7%; profit tiers +50 trim 25%, +100 trim 30%, +200 aggressive/trail;
  kill switches daily -10% & single -45% = HARD REVIEW (never auto-sell a dust flag).
- API: set_state / portfolio_snapshot / sizing_for_regime / profit_taking / rebalance /
  risk_kill_switches / all_recommendations (bundle) / policy. update_position() patches
  live marks. Demo runs in __main__; compiled & executed cleanly (single>cap, cluster>cap,
  +120% tier, -55% drawdown flag all fired in the demo).
- Next (boss): +$50 top-up -> wire holdings.json/portfolio.json adapters + wire Execution
  (autopilot SIZE_USDC -> manager sizing) once the wallet is funded.

### 2026-09-04 - CHIEF DIRECTIVE: "Snatcher adapts to the phase; cash on desk or shutdown"
- Boss: this is NOT CEX-style static rules. The desk must auto-SWITCH its tactic as the
  market goes neutral / bear / bull, keep hunting in EVERY phase, and never idle for hours.
  No cash/portfolio growth = subscription money gone = shutdown risk. Subagents exist to be
  monitored; manager watches output.
- Implemented SNATCHER_PHASES (scanner + autopilot share single source: pump-scan file
  regime.bar; autopilot label map only fallback):
    bear    -> BEAR_SNATCH:   hunt resilient SURVIVORS (age 0.35-24h) that show BUYER
                              SUPPORT (bs>=1.2) during dips; looser liq/vol (15k).
    neutral -> NEUTRAL_SNATCH: balanced pullback snatch (40k/20k/0.25-8h).
    bull    -> BULL_SNATCH:   crowded tape: CLEAN liquid dips only (liq>=25k, fdv>=45k,
                              age>=0.5h, h1<=80, bs>=1.1), banks fast.
  Never-chase (m5<=0) and never-top caps hold in every phase.
- DRY-TAPE RELIEF NET: after 5 consecutive no-entry scans the desk widens (liq/vol 12k,
  age 0.1-24h, m5 +2% allowed) so silence is impossible while cash is ready. Empty runs
  counted in autopilot.json emptyRuns; tg msgs now tag the phase + dry count; buys tag
  [BULL_SNATCH]/[RELIEF...].
- New scripts/sla-audit.py = manager card: phase, dry runs, idle hours, realized today/all,
  red flags (>24h no close). Verified live: F&G 78 -> BULL_SNATCH, _BAR synced 45k/25k/bs1.1.
- Stand-out truth for boss: even perfect phase logic cannot print money at $16 balance minus
  $12 reserve (~$2.5-4/trade). Revenue ceiling = capital; plan for a top-up.

### 2026-09-04 - BOSS OVERRIDE: Greed no longer raises the bar
- After the silence incident the boss chose "Drop Greed to STANDARD bar entirely (more trades,
  more risk on a crowded tape)". Applied to pump-scan regime_policy AND autopilot REGIME_FLOORS:
  Greed/Extreme Greed now use STANDARD (fdv 40k/liq 20k/vol 20k/age .25h/h6 200). Fear still
  WIDE_NET. No-green / no-top / h1-uptrend rules still enforced in every regime.
- Verified live at F&G 78: scanner 0/22 passers (HIGH_BAR) -> 8/22 (STANDARD). Autopilot
  _BAR syncs the STANDARD floor from the scan file. Current tape still yields 0 execution-gate
  passers (all 8 fail structural rules: tiny fdv/liq or h1>100) -> "no clean entry" remains the
  correct message until a qualifying pullback appears.

### 2026-09-04 - "AGENT WENT SILENT" INCIDENT: not silent, gate was blocking everything
- Boss saw ~16h with zero trades after BENNIE/CTO stops. Autopsy of autopilot.json + scan files:
  1) NOT silent - launchd loaded, autopilot.out ticking, "no clean entry" TG msgs proving runs.
  2) Cooldown (6h after 2 stop-outs) covered most of the window; expired on schedule.
  3) ROOT CAUSE BUG: pump-scan stored vol_h24 as comma-formatted STRING ('3,284,584');
     autopilot eligible() did float('3,284,584') -> ValueError -> 0 -> vol<minVol ->
     EVERY candidate auto-rejected regardless of quality/regime. (Was masked before the
     entry-gate rewrite added the vol24 check.)
  4) Also Extreme Greed (F&G 77-78) -> HIGH_BAR 60k floor -> live scans 0/8..0/22.
- FIX: scanner now writes numeric vol (print-only formatting stays); gate leniently parses
  comma/space strings (old files work too). Verified: old comma-style candidate now passes.
- Lesson: gate bugs can look like market stand-downs (and vice versa). Every regime change
  + gate edit should include a canary: dry-run the gate over the last real scan and check
  pass-count != 0 when the histogram says opportunities exist.

### 2026-09-03 - SCANNER MARKET-REGIME GATE (CMC Fear & Greed, Meme Snatcher mindset)
- Integrated cmc-feed (fear_greed/metrics) into pump-scan.py + autopilot.py as a REGIME bar:
  Fear/Extreme Fear -> WIDE_NET (floors down: fdv 30k/liq 15k/age .15h), Neutral -> STANDARD
  (40k/20k/.25h), Greed/Extreme Greed -> HIGH_BAR (60k/25k/.5h, maxH6 150). Never-buy-green
  and no-tops rules hold in ALL regimes. Trending/narratives = soft context only.
- Discovery unchanged: DexScreener feeds + Gecko cross-check; CMC only tunes strictness.
- Fixed pump-scan missing `import os` (regime fetch had silently fallen back to Neutral).
- Verified live: F&G 77 (Extreme Greed) -> HIGH_BAR -> 0/8 candidates passed (stand-down
  on a crowded tape is the correct snatcher behavior). Scanner writes regime meta per scan;
  autopilot syncs entry floors from the latest scan file (single source of truth).

### 2026-09-03 - INDEPENDENT FEED: GeckoTerminal cross-check (fomo.family rejected)
- Boss asked about fomo.family: verdict = consumer social trading app (FOMO Labs, $75M B), NO public
  API/docs -> not a legitimate feed; following retail top-traders contradicts entry discipline.
- Added scripts/gecko-feed.py (GeckoTerminal public API, no key): token price/fdv/reserve + top-pool
  liq/vol + m5/h1/h6/h24 changes. Shows big provider disagreement on meme pairs (CTO: DexScreener
  dead-pair ~$2e-6 vs Gecko ~$0.000107, $67k pool) - exactly why cross-checking matters.
- autopilot.py now calls gecko_check(mint) before any buy; skips when Gecko says liq<15k / fdv<30k /
  h1>150 / h24>800 (provider disagreement = no entry). Entry still gated by the earlier boss rules.

### 2026-09-03 - ENTRY QUALITY OVERHAUL (boss: stop buying tops/green; <40k fdv deadly)
- Root cause of all day's losses: ENTRY, not exit. I bought heat (CTO after +1318%/6h) into
  illiquid microcaps and ignored the Scanner's own chg_m5/h6/h24/vol fields. Sub-agents were
  producing the right warnings; the buy path never consumed them.
- IMPLEMENTED (autopilot.py): hard gate = fdv>=40k, liq>=20k, vol24>=20k, age 0.25-8h,
  chg_m5<=0 (never green), 0<chg_h1<=100, chg_h6<=200 & chg_h24<=500 (never tops); rank by
  liquidity not heat. 2 straight losing auto-closes -> 6h entry cooldown (armed after BENNIE+CTO).
- Ledger honesty fixed: dust exits book proceeds-cost. BENNIE -1.4671 (-97.8%), CTO -2.50 (-100%).
- Net day on GHojAX: ~-3.97 on $20 seed (SOLFONE +0.42 win). All future entries: pullback-only,
  >=40k fdv, deep liquidity. Prove over >=10 clean round-trips before any scaling.

### 2026-09-03 - SOLANA RE-TUNE (boss: "deploy more, be adaptive") + bug fixes
- Boss pushed back: 1 position @ $1.50 with $15 reserve leaves ~8% working - "the market isn't waiting".
  Re-tuned autopilot.py: SIZE $2.50, MAX_OPEN 2, RESERVE_MIN $12 (balanced option chosen by boss).
- Multi-position support: management loop now exits EVERY open position independently (was opens[0]
  only) with PER-POSITION peaks (STATE "peaks" map, was one global peak) + per-sell realized calc.
- FIXED daily-loss guard bug: it compared USDC cash vs the day-start cash constant -> ANY buy
  looked like a -10% loss and paused the bot. Now EQUITY-based (cash + open positions at market).
- FIXED post-buy qty race again (BENNIE, then CTO both recorded qty 0): added token_balance_retry
  (poll up to ~12s after a buy). Verify holdings qty/entry after every auto-buy.
- Auto round-trips today: BENNIE -97.9% stop (dead pair), CTO -39% stop (pair dried between read
  and sell -> proceeds ~dust). Stops work; entries still suffer memecoin reality.
- Lesson reinforced: on meme pairs, liquidity can vanish between decision and fill - expect dust on
  losers and bank FAST.

### 2026-09-03 - CORRECTION: Solana live EXECUTION IS wired (autopilot.py is the Phase-2 executor)
- I earlier reported "live auto-execution NOT wired" (wrong - I only grepped for `liveEnabled`). The
  real executor is `scripts/autopilot.py` (runs via com.agentic-trading.autopilot every ~45 min):
  it auto-MANAGES open positions (snatcher_decision: bank/trail/hard-stop/time-stop) and auto-BUYS
  scanner candidates ($1.50, liq/fdv/b:s filters, USDC reserve >=$15, daily -10% guard ->
  autopilot.off). Signs via solagent-signer (jup route). Gates: data/live/autopilot.off.
- PROOF of live autonomous loop: BENNIE was auto-BOUGHT 10:51Z and auto-EXITED at 15:29:30Z by the
  autopilot (hard stop -30%; actual -97.9%, tx 5eELtdcs... finalized). Ledger bug fixed: holdings
  entry had qty/entry 0.0 (balance read raced the buy) -> would block the exit; reconciled to
  on-chain balance. Lesson: after any auto-buy, VERIFY the holdings record has real qty/entry.
- Lesson: to know if automation is wired, read the scheduler/executor scripts, don't grep config.

### 2026-09-03 - EVM AUTO CORRECTION: memory rules override invented strategy
- Boss caught me proposing mean-reversion (BUY_DIP = averaging down) + fixed % alarm on the EVM
  lane. CONFLICTS with memory: "no averaging down", "profit-taking is NOT a fixed % alarm",
  "reserve >=50% cash". Corrective action taken:
  1) Rebalanced Safe to ~50/50 USDC/AERO (sell 1.436 AERO, tx 0x3ce21afe...). Now USDC 1.522.
  2) Rewrote evm-autopilot.mjs to a memory-compliant RUNG-EXIT engine (NO auto-buys): BANK ~50%
     at +30%, TRAIL rest -15% off peak, HARD STOP -30%, TIME STOP 24h. Buys = manual (boss GO).
  3) Scheduler NOT activated. Solana snatcher system untouched.
- Rule reinforced: memory file is the source of truth; check it before designing any trade logic.

### 2026-09-03 - EVM lane LIVE via SELF-HOSTED evm-signer (Turnkey replaced)
- Built `evm-signer/` (repo): encrypted keystore (AES-256-GCM+scrypt, 0600) + policy guardrails
  (chain allowlist, to-allowlist, per-tx $2, daily $25, kill-switch) + audit log + sign/broadcast.
- FIRST real EVM trade on it: 1.5 USDC -> 3.01627 AERO via Aerodrome direct (no Rubic ~$0.77 fee,
  no Turnkey quota). approve 0x14803651..., swap 0xe354b819... (Base, status 0x1, gas 207k).
- Lesson: Turnkey free tier = 25 sigs/month, org-gated; wallet-account signing = flat
  signTransaction(signWith=address). For self-host: import the EOA key LOCALLY via
  `node evm-signer/src/cli.mjs import 0xKEY` (boss runs it; key never in chat).
- Next: Safe + AllowanceModule (same address all 6 chains), EOA as delegate w/ on-chain caps.

### 2026-09-03 - TURNKEY MPC VERIFIED: canonical EVM addr 0xb1ac...82b8 IS Turnkey-origin
- Boss creds landed; org 4214c4d6-129c-4e49-9814-eee96319fc2f verified via signed API list.
- Wallet "Buon" (6437e844) already holds EVM account f0fb66a4 (m/44'/60'/0'/0/0) = the SAME
  0xb1ac...82b8 in config - no address change, no split. Solana account 8ZGuiQZ also inside.
- API keys stored 0600 at ~/.config/agentic-trading/turnkey.json (never print/repeat in chat).
- Execution signing on EVM lane = sdk-server `apiClient().signTransaction` with `signWith: <wallet
  account ADDRESS>` (flat call) -> returns FULLY SIGNED RAW TX -> self-broadcast via chain RPC.
  VERIFIED LIVE on Base tx 0x623b0750...8665 (status 0x1, nonce 18->19). This is the PRODUCTION
  path. Do NOT use v1 signTransaction/privateKeyId (wallet accounts have none) and do NOT depend on
  Turnkey ethSendTransaction (org feature EthSendTransaction not enabled). All 6 EVM chains work.
- Robinhood 4663 + HyperEVM 999 reachable via the same self-broadcast path (any EVM RPC).
- Base lane verified live: 3.065134 USDC, 0.0006705 ETH gas. First MPC broadcast test DONE under
- 2026-09-04: T-6 REVERSE LIVE **PASSED** ($20 Base→SOL). Safe 56.72 → 36.72; SOL vault USDC 4.117 → 23.631 (received 19.5136 ≈ 2.42% all-in, ~30s settle). GS026 = RPC nonce race → pinned single-node RPC + SKIP_APPROVE in safe_reverse_bridge.mjs. Approve tx 0x7484f59, payload 0x9d7367f, settle 5thSARnT.
- 2026-09-04: SOL desk funded & reconciled. Base +$50 swept to Safe (tx 0x71540cbf); T-6 reverse PASSED ($20→19.5136 SOL, vault 4.117→23.63); boss approved delegate cap **$15** (html 127.0.0.1:8126, 15,000,000 micro); halt `autopilot.off` cleared on boss GO, fresh day 09-04 baseline; idle hot $10.87 consolidated → vault (tx 2B8Ft6qX), vault **34.498** / hot 0.10; delegate remaining 13.08 (1.92 pulled for a candidate that failed to fill, then pushed back — SPL allowance needs a new approve to refill to 15). PM bugfix: `portfolio_state._live_sol_usdc` now sums **vault + hot** (VAULT_MODE) with 3-RPC fallback (was hot-only → PM missed $23.63+); new `data/live/unified.json` dayStartEquity **$72.91** so the PM daily-loss kill compares like-for-like (was comparing unified equity to SOL-lane start → fake +100%).
- Earlier 2026-09-04 (evm-signer broadcast test): boss GO (0 ETH self-transfer, Base, tx 0x623b0750...8665, status 0x1, cost ~0.0006 USD).
- 2026-09-04: Telegram **rich cards** implemented (boss spec): `notify-telegram.py` gained `card balance|open|profit|loss <payload.json>` (Markdown, parse errors surfaced) + precision `_price()` for microcap stops. Balance card LIVE-sent & API-verified. Wired SOL autopilot (entry→open card incl. delegate remaining; close→profit/loss card w/ duration/streak/cooldown) and EVM autopilot.mjs (AERO open + TIME_STOP/exit cards). New launchd `com.agentic-trading.daily-card` → `card balance` at 23:45 daily. JS snippet (env BOT_TOKEN/CHAT_ID, port 4443) not adopted — python notifier w/ `~/.config/agentic-trading/telegram.json` is the desk standard; delegate refill to $15 confirmed on-chain (GRiCE delAmt 15.0).




