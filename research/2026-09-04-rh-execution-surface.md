# Robinhood Chain — Gas & Fee Baseline (execution surface mapping for future bot)

> Measured live 2026-09-04 (block 54,625,378) from public RPC `https://rpc.mainnet.chain.robinhood.com`.
> Feed/analysis only — no keys, no balances, no transactions sent.

## Network facts (verified on-chain)
| Field | Value |
|---|---|
| chainId | 4663 (0x1237) |
| Client | Arbitrum Nitro `nitro/v3.11.4-rc.3` · ArbOS 61 |
| Currency / gas | ETH (EIP-1559, type-0/1/2 supported) |
| Block explorer | `robinhoodchain.blockscout.com` |
| Sequencer feed (node sync) | `wss://feed.mainnet.chain.robinhood.com` (not an event-sub WS) |
| Public `eth_subscribe` | not exposed on public RPC → push requires self-hosted node (docs) |

## Measured gas profile (baseline)
| Metric | Value |
|---|---|
| baseFeePerGas | 0.4105 gwei |
| eth_gasPrice | 0.3980 gwei |
| maxPriorityFeePerGas | 0 (bots can use 0 priority) |
| Block gas used / limit | ~5.19M used of huge 1.125e15 cap (Nitro) — effectively no congestion ceiling |
| Block time | sub-second batches (same-second multi-block) |

## Real unit costs @ effGasPrice ~0.4 gwei, ETH ≈ $2,530
| Op | Gas units | ETH | USD |
|---|---|---|---|
| Native transfer | ~21,000 | 0.0000084 | ~$0.021 |
| ERC-20 transfer | ~65,000 | 0.0000260 | ~$0.066 |
| Simple DEX swap | ~250–350k | ~0.00012 | ~$0.30 |
| Measured heavy RH tx (type-2) | 748,919 | 0.0002986 | **$0.76** |

## Execution-surface mapping (for future bot config)
- **Fees are effectively negligible on RH** → gas is NOT a bottleneck; confirmation latency + slippage dominate.
- Fee math (EIP-1559): `maxFeePerGas = (baseFee * 1.5) + priority`; priority can stay 0; cap around current gasPrice ×2 as safety.
- Send path: `eth_sendRawTransaction` via the public RPC; polling `eth_getTransactionReceipt` for finality.
- Push option (later): self-hosted Nitro node (docs: run-a-full-node) exposes local WS 8548 with `eth_subscribe` for true real-time signals.
- Signing stays chain-native/out-of-repo (same model as our EVM lane: local keystore 0600, never in feed/bot config).

## Re-baseline anytime
`python3 /tmp/rh_gas.py` (baseFee/gasPrice/priority) — numbers above are a snapshot, not a promise.

## Status
Feed layer for RH is live (asset-transfer + pool/swap watchers). This gas/fee map is the accounting pre-flight for a future execution bot — no bot exists yet, per one-thing-at-a-time.
