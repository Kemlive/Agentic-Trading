# Safe + AllowanceModule — on-chain policy layer for the EVM lane

Boss directive: deploy a Safe as the funds holder (same address across EVM chains) with the agent
EOA as owner, and enable AllowanceModule so the EOA is a *delegate* with token-limited, daily-capped
spend — even a leaked signer key is capped on-chain.

## Verified addresses (Base, from `@safe-global/*-deployments`)
- Safe singleton 1.4.1: `0x41675C099F32341bf84BFc5382aF534df5C7461a`
- ProxyFactory 1.4.1: `0x4e1DCf7AD4e460CfD30791CCC4F9c8a4f820ec67`
- FallbackHandler 1.4.1: `0xfd0732Dc9E303f09fCEf3a7388Ad10A83459Ec99`
- AllowanceModule: `0xAA46724893dedD72658219405185Fb0Fc91e091C`

## Cost + address
- Deployment gas ≈ **258,883** (≈ **$0.007**). Enable+configure = 3 Safe owner txs (~few $0.01 total).
- **Deployed Safe (Base): `0x203FD7cefb443672ef5700A1E27521c22A6E7B3A`** (owner `0xb1ac…82b8`, threshold 1).
  (create2 salt = keccak256(keccak256(initializer) ‖ saltNonce); identical address on every EVM chain
  with the canonical Safe deployment.)

## Caveat (verified)
- `@safe-global/safe-deployments` has **no specific entry** for HyperEVM(999) or Robinhood(4663);
  the canonical singleton/factory may not be deployed there. Those two chains need a manual
  permissionless singleton/factory deployment before the same-address Safe can exist there.
  Base/ETH/BNB/Arb/Polygon/OP are all present.

## Steps
1. `node deploy.mjs --go` — DONE (tx 0x4e5f16da…cc81d).
2. `node enable-allowance.mjs` (DRY-RUN) → `--go` to execute 3 Safe owner txs:
   enableModule · addDelegate(EOA) · setAllowance(USDC daily = $5, resetTimeMin=1440).
3. `allowances`: after module is enabled, the delegate EOA spends via
   `executeAllowanceTransfer(...)` (capped on-chain) — trading execution path next.
4. Move lane capital (1.565 USDC + 3.016 AERO + gas) into the Safe.

## Scripts
- `predict.mjs` — read-only: addresses, predicted Safe, deploy gas estimate.
- `deploy.mjs` — deploy Safe (dry-run default; `--go` broadcasts).
