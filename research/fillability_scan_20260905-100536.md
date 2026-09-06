# RH Fill-Ability Scan v2 (2026-09-05T10:05:36.738847+00:00 UTC)
Simulation only (eth_call quoters, zero funds). Quote = USDG.
Venues: uniswap-v3 / ramses-v3 / uniswap-v2. PASS = $5 fills, impact <= 5%.
uniswap-v4 & pons-v2 = needs-PoolKey-build (not simulated).

| token | venue | pool | fee | $5 | impact% | maxFill$ | status |
|---|---|---|---|---|---|---|---|
| 0x4a0e65a3 | uniswap-v3 | 0x87c58b43 | 100 | no-fill | - | 0.0 | no-fill |
| 0xd0601ce1 | uniswap-v3 | 0xb75d2d02 | 100 | no-fill | - | 0.0 | no-fill |
| 0x117cc213 | uniswap-v3 | 0xa7bb1ac6 | 500 | no-fill | - | 0.0 | no-fill |
| 0x2e0847e8 | uniswap-v3 | 0xa3617bb4 | 100 | no-fill | - | 0.0 | no-fill |
| 0x020bfc65 | uniswap-v3 | 0xf3a57982 | 500 | no-fill | - | 0.0 | no-fill |
| 0x2e8c3116 | uniswap-v3 | 0x3a290b42 | 3000 | no-fill | - | 0.0 | no-fill |
| 0xab5d6a69 | - | - | - | no-pool | - | 0 | no-pool |
| 0x8e859dbd | - | - | - | no-pool | - | 0 | no-pool |
| 0x39dbed3a | uniswap-v3 | 0x0652d615 | 3000 | no-fill | - | 0.0 | no-fill |
| 0x7ad7b225 | - | - | - | no-pool | - | 0 | no-pool |
| 0x44812a88 | - | - | - | no-pool | - | 0 | no-pool |
| 0x0d6bbdd9 | - | - | - | no-pool | - | 0 | no-pool |
| 0xcec185eb | uniswap-v3 | 0x9664d869 | 500 | no-fill | - | 0.0 | no-fill |
| 0x6635c082 | uniswap-v3 | 0x64135824 | 10000 | no-fill | - | 0.0 | no-fill |
| 0x322f0929 | uniswap-v3 | 0x7868622f | 100 | no-fill | - | 0.0 | no-fill |
| 0xca907cfd | - | - | - | no-pool | - | 0 | no-pool |
| 0x157a752f | uniswap-v3 | 0xdebbab20 | 10000 | no-fill | - | 0.0 | no-fill |
| 0xfa0653c2 | - | - | - | no-pool | - | 0 | no-pool |
| 0x12f190a9 | uniswap-v3 | 0x7b242dfa | 100 | no-fill | - | 0.0 | no-fill |

## v4 / Pons pools (needs-PoolKey-build - not simulated, never PASS)
- 0x4a0e65a3 uniswap-v4-robinhood pool=0xcb6ffbcc8435
- 0x4a0e65a3 pons-v2-dex pool=0xedf5d3c9f4a0
- 0x4a0e65a3 pons-v2-dex pool=0x9d3e7931d8ae
- 0x4a0e65a3 pons-v2-dex pool=0xd70769115133
- 0xd0601ce1 uniswap-v4-robinhood pool=0xbc732a1a0baa
- 0xd0601ce1 pons-v2-dex pool=0xcde4d35e3419
- 0xd0601ce1 uniswap-v4-robinhood pool=0x3bb34a44f1b2
- 0xd0601ce1 pons-v2-dex pool=0xe436b5264fca
- 0x117cc213 uniswap-v4-robinhood pool=0xfe2a80bb5618
- 0x117cc213 uniswap-v4-robinhood pool=0x8674c1c5544f
- 0x117cc213 uniswap-v4-robinhood pool=0xe5923c8a8be4
- 0x117cc213 uniswap-v4-robinhood pool=0xf38009b34829
- 0x117cc213 uniswap-v4-robinhood pool=0xf224a070c862
- 0x117cc213 uniswap-v4-robinhood pool=0xcc2a903a8744
- 0x2e0847e8 uniswap-v4-robinhood pool=0xd4ecb79fdc52
- 0x2e0847e8 uniswap-v4-robinhood pool=0x2bca43d9d8c7
- 0x2e0847e8 pons-v2-dex pool=0x5e2cf3ad5d8e
- 0x2e0847e8 uniswap-v4-robinhood pool=0x36970ce890b2
- 0x020bfc65 uniswap-v4-robinhood pool=0xa92a3df27a00
- 0x020bfc65 uniswap-v4-robinhood pool=0xf7dc0af99fce
- 0x2e8c3116 uniswap-v4-robinhood pool=0x7aebd80541bf
- 0x2e8c3116 uniswap-v4-robinhood pool=0x1f1778596d8c
- 0x2e8c3116 uniswap-v4-robinhood pool=0x0ff2e264ba5a
- 0xab5d6a69 pons-v2-dex pool=0x1f9506ccd2d0
- 0xab5d6a69 uniswap-v4-robinhood pool=0x6b6e909aa356
- 0xab5d6a69 uniswap-v4-robinhood pool=0xf44f2e7f24f1
- 0xab5d6a69 pons-v2 pool=0x225f1e20a137
- 0x8e859dbd pons-v2-dex pool=0x2a5c52399e78
- 0x8e859dbd uniswap-v4-robinhood pool=0x7686aca0b66b
- 0x8e859dbd uniswap-v4-robinhood pool=0x714bb4597ec9
- 0x8e859dbd uniswap-v4-robinhood pool=0xcf6cf65c31d5
- 0x8e859dbd uniswap-v4-robinhood pool=0x0c1cc60595ee
- 0x8e859dbd uniswap-v4-robinhood pool=0xc89fc36bc763
- 0x8e859dbd uniswap-v4-robinhood pool=0x37befd2c507a
- 0x8e859dbd uniswap-v4-robinhood pool=0xcad309aa058a
- 0x39dbed3a uniswap-v4-robinhood pool=0x4be9657ec900
- 0x39dbed3a uniswap-v4-robinhood pool=0x13f9ab4e07b7
- 0x7ad7b225 pons-v2-dex pool=0x48f9cb210e8f
- 0x7ad7b225 uniswap-v4-robinhood pool=0x8540e9a6eb9b
- 0x7ad7b225 uniswap-v4-robinhood pool=0xc659c91c64a6
- 0x7ad7b225 uniswap-v4-robinhood pool=0xc143aa1303d5
- 0x7ad7b225 uniswap-v4-robinhood pool=0x871b9a274316
- 0x7ad7b225 uniswap-v4-robinhood pool=0x1f164135a077
- 0x7ad7b225 uniswap-v4-robinhood pool=0x1be3bb04ada9
- 0x7ad7b225 uniswap-v4-robinhood pool=0x969984dd5915
- 0xcec185eb uniswap-v4-robinhood pool=0x94c62eebf645
- 0xcec185eb pons-v2-dex pool=0x40fe32f224ea
- 0xcec185eb pons-v2-dex pool=0x879f6ee2a52b
- 0xcec185eb uniswap-v4-robinhood pool=0x690525411680
- 0x6635c082 pons-v2-dex pool=0x7227c1bea940
- 0x6635c082 uniswap-v4-robinhood pool=0x90c38e2a5680
- 0x6635c082 uniswap-v4-robinhood pool=0xb257777c8cf5
- 0x6635c082 uniswap-v4-robinhood pool=0x90b948d06774
- 0x6635c082 uniswap-v4-robinhood pool=0x7e6ab880516f
- 0x6635c082 uniswap-v4-robinhood pool=0x67bda2034514
- 0x6635c082 uniswap-v4-robinhood pool=0xe5b279e9ef7c
- 0x322f0929 uniswap-v4-robinhood pool=0x8517f8071ae5
- 0x322f0929 pons-v2-dex pool=0xa1771923045e
- 0x322f0929 uniswap-v4-robinhood pool=0xa821b3724b45
- 0xca907cfd pons-v2-dex pool=0xea1b74371597
- 0xca907cfd uniswap-v4-robinhood pool=0xac0e4c4e6c57
- 0xca907cfd uniswap-v4-robinhood pool=0x01d6ed63bafe
- 0xca907cfd uniswap-v4-robinhood pool=0x55ec0ae3d175
- 0xca907cfd uniswap-v4-robinhood pool=0x67a9e4a7728c
- 0xca907cfd uniswap-v4-robinhood pool=0xf0c5bcb61eef
- 0xca907cfd uniswap-v4-robinhood pool=0x8033f6f50d2f
- 0xca907cfd uniswap-v4-robinhood pool=0xb792f993ec4e
- 0x157a752f pons-v2-dex pool=0x77a0e74e47dd
- 0x157a752f uniswap-v4-robinhood pool=0x77c75b061598
- 0x157a752f uniswap-v4-robinhood pool=0x9ff44159bbb9
- 0x157a752f uniswap-v4-robinhood pool=0xe78f0a73e913
- 0x157a752f uniswap-v4-robinhood pool=0x23c11ab8d39e
- 0x157a752f uniswap-v4-robinhood pool=0x1bd2b0f544ac
- 0x157a752f uniswap-v4-robinhood pool=0x2d431bed7cd0
- 0x157a752f uniswap-v4-robinhood pool=0x327d14549d0c
- 0xfa0653c2 pons-v2-dex pool=0xf9bfebd09dcb
- 0xfa0653c2 uniswap-v4-robinhood pool=0x1e9c7ea3f4c8
- 0xfa0653c2 uniswap-v4-robinhood pool=0x59954c3736ac
- 0xfa0653c2 uniswap-v4-robinhood pool=0x60d8ba1c12a1
- 0xfa0653c2 uniswap-v4-robinhood pool=0xd5b95578bd05
- 0xfa0653c2 uniswap-v4-robinhood pool=0xa0fbae33b9ff
- 0xfa0653c2 uniswap-v4-robinhood pool=0xaf109cec3637
- 0xfa0653c2 pons-v2 pool=0x4ff370a4cd9b
- 0x12f190a9 uniswap-v4-robinhood pool=0x68beff3b4270
- 0x12f190a9 pons-v2-dex pool=0x81721a33257b
- 0x12f190a9 pons-v2-dex pool=0x31c56f7170f6
- 0x12f190a9 pons-v2-dex pool=0xec55cbe1f376