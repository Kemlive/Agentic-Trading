# RH Fill-Ability Scan v2 (2026-09-05T09:21:11.771481+00:00 UTC)
Simulation only (eth_call quoters, zero funds). Quote = USDG.
Venues: uniswap-v3 / ramses-v3 / uniswap-v2. PASS = $5 fills, impact <= 5%.
uniswap-v4 & pons-v2 = needs-PoolKey-build (not simulated).

| token | venue | pool | fee | $5 | impact% | maxFill$ | status |
|---|---|---|---|---|---|---|---|
| 0x385f4f8a | uniswap-v3 | 0x5d37b1d8 | 3000 | no-fill | - | 0.0 | no-fill |
| 0x7ad7b225 | - | - | - | no-pool | - | 0 | no-pool |
| 0x44812a88 | - | - | - | no-pool | - | 0 | no-pool |
| 0x39dbed3a | uniswap-v3 | 0x0652d615 | 3000 | no-fill | - | 0.0 | no-fill |
| 0xcec185eb | uniswap-v3 | 0x9664d869 | 500 | no-fill | - | 0.0 | no-fill |
| 0xfb2eab29 | - | - | - | no-pool | - | 0 | no-pool |
| 0x05a3d1cd | uniswap-v3 | 0x5c329ec5 | 500 | no-fill | - | 0.0 | no-fill |
| 0x8e859dbd | - | - | - | no-pool | - | 0 | no-pool |
| 0x50ac4a09 | - | - | - | no-pool | - | 0 | no-pool |
| 0xe45f30d2 | - | - | - | no-pool | - | 0 | no-pool |
| 0x92fd6652 | uniswap-v3 | 0xffb376bf | 100 | no-fill | - | 0.0 | no-fill |
| 0xc697aef3 | - | - | - | no-pool | - | 0 | no-pool |
| 0xfa0653c2 | - | - | - | no-pool | - | 0 | no-pool |
| 0x6635c082 | uniswap-v3 | 0x64135824 | 10000 | no-fill | - | 0.0 | no-fill |
| 0xa45c124f | - | - | - | no-pool | - | 0 | no-pool |
| 0x68666592 | - | - | - | no-pool | - | 0 | no-pool |
| 0x12f190a9 | uniswap-v3 | 0x7b242dfa | 100 | no-fill | - | 0.0 | no-fill |
| 0x0d6bbdd9 | - | - | - | no-pool | - | 0 | no-pool |
| 0x8ae9d32c | - | - | - | no-pool | - | 0 | no-pool |

## v4 / Pons pools (needs-PoolKey-build - not simulated, never PASS)
- 0x385f4f8a uniswap-v4-robinhood pool=0xcfa4f4a01e55
- 0x385f4f8a uniswap-v4-robinhood pool=0x161610470ba6
- 0x385f4f8a uniswap-v4-robinhood pool=0x3253d38dbea1
- 0x385f4f8a uniswap-v4-robinhood pool=0xc6e298e137f2
- 0x385f4f8a uniswap-v4-robinhood pool=0x3cfd56783ecb
- 0x7ad7b225 pons-v2-dex pool=0x48f9cb210e8f
- 0x7ad7b225 uniswap-v4-robinhood pool=0x8540e9a6eb9b
- 0x7ad7b225 uniswap-v4-robinhood pool=0xc659c91c64a6
- 0x7ad7b225 uniswap-v4-robinhood pool=0xc143aa1303d5
- 0x7ad7b225 uniswap-v4-robinhood pool=0x871b9a274316
- 0x7ad7b225 uniswap-v4-robinhood pool=0x1be3bb04ada9
- 0x7ad7b225 uniswap-v4-robinhood pool=0x969984dd5915
- 0x7ad7b225 uniswap-v4-robinhood pool=0x1f164135a077
- 0x44812a88 pons-v2-dex pool=0xbe1fd8b6b642
- 0x44812a88 uniswap-v4-robinhood pool=0xa9969505b824
- 0x44812a88 uniswap-v4-robinhood pool=0x775889ca7189
- 0x44812a88 uniswap-v4-robinhood pool=0x702025e74cf8
- 0x44812a88 uniswap-v4-robinhood pool=0xb00b1d2a1647
- 0x44812a88 uniswap-v4-robinhood pool=0xc2d744147bdd
- 0x44812a88 uniswap-v4-robinhood pool=0xf972596c1c63
- 0x44812a88 uniswap-v4-robinhood pool=0x51e682abe6ef
- 0x39dbed3a uniswap-v4-robinhood pool=0x4be9657ec900
- 0x39dbed3a uniswap-v4-robinhood pool=0x13f9ab4e07b7
- 0xcec185eb uniswap-v4-robinhood pool=0x94c62eebf645
- 0xcec185eb pons-v2-dex pool=0x40fe32f224ea
- 0xcec185eb pons-v2-dex pool=0x879f6ee2a52b
- 0xcec185eb uniswap-v4-robinhood pool=0x690525411680
- 0xfb2eab29 pons-v2 pool=0xbe669689efbd
- 0x05a3d1cd uniswap-v4-robinhood pool=0x7499938c352d
- 0x05a3d1cd uniswap-v4-robinhood pool=0xf452715675de
- 0x05a3d1cd uniswap-v4-robinhood pool=0x5c7032ccc30c
- 0x05a3d1cd uniswap-v4-robinhood pool=0x226082f4e1ed
- 0x05a3d1cd pons-v2-dex pool=0x5ee097c4d662
- 0x8e859dbd pons-v2-dex pool=0x2a5c52399e78
- 0x8e859dbd uniswap-v4-robinhood pool=0x7686aca0b66b
- 0x8e859dbd uniswap-v4-robinhood pool=0x714bb4597ec9
- 0x8e859dbd uniswap-v4-robinhood pool=0xcf6cf65c31d5
- 0x8e859dbd uniswap-v4-robinhood pool=0x0c1cc60595ee
- 0x8e859dbd uniswap-v4-robinhood pool=0x37befd2c507a
- 0x8e859dbd uniswap-v4-robinhood pool=0xc89fc36bc763
- 0x8e859dbd uniswap-v4-robinhood pool=0xcad309aa058a
- 0x50ac4a09 pons-v2-dex pool=0xd4d64e9726ad
- 0x50ac4a09 uniswap-v4-robinhood pool=0xb6b176773a1b
- 0x50ac4a09 uniswap-v4-robinhood pool=0xa87e04d5f21c
- 0x50ac4a09 uniswap-v4-robinhood pool=0x2c78ed7ea9e5
- 0x50ac4a09 uniswap-v4-robinhood pool=0x4864692f2a1e
- 0x50ac4a09 uniswap-v4-robinhood pool=0x3a54ea3bf57a
- 0x50ac4a09 uniswap-v4-robinhood pool=0xff54eabe91a6
- 0x50ac4a09 uniswap-v4-robinhood pool=0x6cd9b0e42f6a
- 0xe45f30d2 pons-v2-dex pool=0xad6b41d4e67a
- 0xe45f30d2 uniswap-v4-robinhood pool=0xaa3608615728
- 0xe45f30d2 uniswap-v4-robinhood pool=0x838c7f6357ec
- 0xe45f30d2 uniswap-v4-robinhood pool=0x2276697a046c
- 0xe45f30d2 uniswap-v4-robinhood pool=0xbea758bac268
- 0xe45f30d2 uniswap-v4-robinhood pool=0x4c0b43f33628
- 0xe45f30d2 uniswap-v4-robinhood pool=0xeaf9302e5097
- 0xe45f30d2 uniswap-v4-robinhood pool=0x5734f9f09f4e
- 0x92fd6652 uniswap-v4-robinhood pool=0x2a72510d7d92
- 0x92fd6652 pons-v2-dex pool=0x75cb93baaaa8
- 0xc697aef3 pons-v2-dex pool=0x3e75792a04dd
- 0xc697aef3 uniswap-v4-robinhood pool=0x33b702861b5e
- 0xc697aef3 uniswap-v4-robinhood pool=0x6b1491a6e433
- 0xfa0653c2 pons-v2-dex pool=0xf9bfebd09dcb
- 0xfa0653c2 uniswap-v4-robinhood pool=0x1e9c7ea3f4c8
- 0xfa0653c2 uniswap-v4-robinhood pool=0x59954c3736ac
- 0xfa0653c2 uniswap-v4-robinhood pool=0x60d8ba1c12a1
- 0xfa0653c2 uniswap-v4-robinhood pool=0xd5b95578bd05
- 0xfa0653c2 uniswap-v4-robinhood pool=0xa0fbae33b9ff
- 0xfa0653c2 uniswap-v4-robinhood pool=0xaf109cec3637
- 0xfa0653c2 pons-v2 pool=0x4ff370a4cd9b
- 0xa45c124f pons-v2-dex pool=0x423781faeaa4
- 0xa45c124f uniswap-v4-robinhood pool=0xda77c22adff0
- 0xa45c124f uniswap-v4-robinhood pool=0xc7cd0bfad10a
- 0xa45c124f uniswap-v4-robinhood pool=0x215bf8f99009
- 0xa45c124f uniswap-v4-robinhood pool=0xfb46dbb243da
- 0xa45c124f pons-v2 pool=0x354d03c2d214
- 0xa45c124f uniswap-v4-robinhood pool=0xa1505b1b0e0e
- 0x68666592 pons-v2-dex pool=0x46b21aa8b495
- 0x68666592 uniswap-v4-robinhood pool=0xe29702572ee3
- 0x68666592 uniswap-v4-robinhood pool=0xef69517befac
- 0x68666592 pons-v2 pool=0x5be9a22d3863
- 0x12f190a9 uniswap-v4-robinhood pool=0x68beff3b4270
- 0x12f190a9 pons-v2-dex pool=0x81721a33257b
- 0x12f190a9 pons-v2-dex pool=0x31c56f7170f6
- 0x12f190a9 pons-v2-dex pool=0xec55cbe1f376
- 0x0d6bbdd9 pons-v2-dex pool=0x1732eaa23a27
- 0x0d6bbdd9 uniswap-v4-robinhood pool=0x80eac3859fdb
- 0x0d6bbdd9 uniswap-v4-robinhood pool=0x922566a0db30
- 0x0d6bbdd9 pons-v2 pool=0x90a6ed36815c