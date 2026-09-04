# Turnkey alternatives — open-source self-host options (2026-09-03)

Trigger: Turnkey free tier blocked signing ("Resource exhausted... over its allotted quota").
Boss directive: find an open-source project we can run/build ourselves as a Turnkey replacement.

## Context / our actual requirement (not a generic wallet product)
- ONE autonomous agent (Chief) signing EVM txs programmatically (no browser, 24/7) across 6 EVM
  chains (ETH/BNB/Base/Arb/HyperEVM/Robinhood) + Solana.
- Guardrails: chain allowlist, router/contract allowlist, per-tx USD cap, daily cap, kill-switch,
  full audit log + Telegram.
- Small live capital (Solana ~$20 USDC; EVM Base ~3.07 USDC). Over-engineering is itself a risk.

## Verified candidates (sources: GitHub READMEs + docs, fetched 2026-09-03)

### 1. OpenSigner (openfort-xyz/opensigner) — self-hostable key management
- MIT, TypeScript, docker-compose (iframe 7050, auth_service 7052, hot_storage 7053,
  cold_storage 7054, postgres). Under audit by Quantstamp (NOT yet complete).
- Shamir 2-of-3 shares (device / hot / cold). "Full key only exists in memory inside a sandboxed
  iframe." EVM + Solana. Auth-agnostic (OIDC/passkeys/email). Recovery via password/passkey/OTP.
- CAVEAT: designed for **end-user embedded wallets** (a "device" share lives in the browser/iframe
  and signing is iframe-mediated). A headless server agent signing without a browser is NOT the
  primary flow; needs deeper reading of auth_service/hot/cold_storage APIs before committing.
- No Turnkey-style per-transaction policy/cap layer observed — our caps stay in our engine.

### 2. Safeheron MPC/TSS (multi-party-sig-cpp, ssgx, safeheron-crypto-suites-cpp, mpc-wasm-sdk)
- C++ {t,n} threshold signature libs (MPC-CMP / GG18 / GG20) + SGX TEE framework (ssgx).
- Institutional-grade building blocks; **libraries, not a key-management service** — we'd build
  ceremonies, share servers, signing coordinator ourselves (C++). Heaviest lift.

### 3. AWS Nitro Enclaves (aws-nitro-enclaves-sdk-c, Apache-2.0)
- C API + KMS SDK with attestation; kmstool samples. Write a Go/Rust signer inside the enclave,
  KMS key policy locked to enclave PCR — closest to Turnkey's enclave model.
- CAVEAT: AWS lock-in, Nitro instance cost, build effort; doesn't ride our existing self-host /
  Cloudflare footprint. Strong for "high-security backend signing" parity, not for speed.

### 4. Safe core + ERC-4337 WebAuthn/passkey modules (safe-global/safe-modules)
- modules/ = 4337, allowances, passkey, recovery. Safe + AllowanceModule = on-chain policy
  (per-token daily spend caps for a delegate/agent). Same Safe address deployable on every EVM
  chain (deterministic create2) => preserves "one unified EVM address".
- CAVEAT: passkey/WebAuthn signing requires a user gesture/browser per signature => human auth,
  NOT autonomous bot signing. AllowanceModule (policy) is the valuable part for us.

## Other earlier findings (kept for reference)
- ZenGo-X/multi-party-ecdsa: unmaintained GPL-3.0 (README says no security updates). Avoid.
- HashiCorp Vault Transit: no native secp256k1 => cannot sign EVM. Avoid for EVM lane.
- Lit / Web3Auth: OSS SDKs but managed networks => not fully "our own".

## Recommended architecture (draft)
- **Policy layer (on-chain, today): Safe + AllowanceModule.** Agent EOA is a delegate with
  token-limited + daily-capped spend; even a leaked agent key is capped on-chain.
- **Signing layer:**
  - Fastest unblock: our own `evm-signer` daemon (ethers/viem + engine caps + audit + Telegram),
    key encrypted at rest (Cloudflare Secret / age) — mirrors the working Solana lane.
  - Custody hardening later: self-host OpenSigner (shares) once we confirm a headless signing API,
    or Safeheron/Nitro for MPC/enclave parity.
- Keep Turnkey as an optional paid path (per-signature, pennies) until self-host is proven.

## Decision needed (boss)
Which signing/custody path to build first: (a) evm-signer daemon now, (b) OpenSigner self-host,
(c) Safeheron/Nitro parity, (d) paid Turnkey interim.
