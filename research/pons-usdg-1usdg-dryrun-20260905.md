# Pons USDG top-5 — 1 USDG dry-run buy + live-test prep

Buy = real eth_call of curve.buy(1 USDG) from a live holder (zero funds). Sell leg cannot be dry-simulated:
no third-party holder currently holds the post-buy token amount (sell measured in the live round-trip instead).

| token | curve | 1-USDG tokensOut |
|---|---|---|
| `0x65566986` | `0x28d63926` | 271834717428346286286544 |
| `0x39a89316` | `0x6f8b0c0b` | 270410905070790459216778 |
| `0x9ae0d7d9` | `0xd16a4292` | 302751329756284055041251 |
| `0x97f7f9d5` | `0x5be244d5` | 302751329662755108468923 |
| `0xfa35b8fc` | `0x6753b694` | 302751328446879111038663 |

Live round-trip plan (1 USDG to-and-fro on ONE curve):
1. approve curve  (ERC20 allow)
2. buy 1 USDG -> tokens to desk wallet
3. read token balance, preview sell via eth_call
4. sell tokens -> USDG back to desk wallet
Blocker: RH desk wallet 0xB1ACDaF7... has 12 USDG but 0 native gas on chain 4663.