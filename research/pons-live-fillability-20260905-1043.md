# Pons Live Discovery + Fill Scan (20260905103829 UTC)

Source: official Pons v2 factory 0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e TokenLaunched logs.
Filter: exists && phase=0 (NotGraduated); native-ETH or USDG pair only. $5 sim = real non-revert eth_call (state-override funded test EOA).
ETH price for $5 sizing: coingecko-simple-price.

Discovered 350 unique launches (back to block 55015499). PASS=183 no-fill=61 not-phase0=4 custom-pair-skipped=100

| token | phase | curve | pair | status | tokensOut
|---|---|---|---|---|
| `0xfcf2af2d` | 0 | `0x95011c49` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x41f292fa` | 0 | `0x291fe341` | ETH | PASS 1138304257974814688115956 |
| `0xc57d107e` | 0 | `0x453384a1` | ETH | PASS 228815123593372209888975 |
| `0xacd1ab42` | 0 | `0x367abe74` | ETH | PASS 1198779772967094774826419 |
| `0x6b8de487` | 0 | `0x80d0e366` | 0xe93237c50d904957cf27e7b1133b510c669c2e74 | custom-pair-skipped |
| `0x39a89316` | 0 | `0x6f8b0c0b` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x267fd1e3` | 0 | `0x08b68d5e` | ETH | PASS 824920344762018309391358 |
| `0x68c66061` | 0 | `0xbf77151b` | ETH | PASS 1157934989021242172215614 |
| `0x08485766` | 0 | `0xd334b393` | ETH | PASS 1179999927154731586747809 |
| `0x180262e3` | 0 | `0x8b535938` | ETH | PASS 1154243721568694754882437 |
| `0xbab39d9f` | 0 | `0x383659e9` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xe43815f3` | 0 | `0xe5baa5c8` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x6fbb0b94` | 0 | `0x2392237a` | ETH | PASS 1134302272780729874733532 |
| `0xcb606639` | 0 | `0x555575b8` | ETH | PASS 403762925289598836965130 |
| `0x02d8dcea` | 0 | `0xbfb6e613` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0xd18a9d8c` | 0 | `0x1c283d8a` | ETH | PASS 1149165160854228522265492 |
| `0xbe68dcb8` | 0 | `0x3018a4b6` | ETH | PASS 1198779772967094772688307 |
| `0xc28f0565` | 0 | `0x514e21ad` | ETH | PASS 1158161963139786328348874 |
| `0x33ebdfdd` | 0 | `0x8c303513` | ETH | PASS 1198779772967094774826419 |
| `0xb47b028c` | 0 | `0x7876e87a` | ETH | PASS 1175605089173769340008382 |
| `0x61bd8999` | 0 | `0x29110108` | ETH | PASS 1156751333049994721698873 |
| `0xcafe429b` | 0 | `0xb577a468` | ETH | PASS 297722054738968050673906 |
| `0x44965603` | 0 | `0xd5f14a9e` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x637e99bb` | 0 | `0x39be25d6` | ETH | PASS 1185665104036443195163511 |
| `0xd7675bfe` | 0 | `0xfbe45685` | ETH | PASS 1156416613443752869787796 |
| `0x292e3157` | 0 | `0x38da7bac` | 0x48e39e56acdba37b09020c0b734a613c9a2f100a | custom-pair-skipped |
| `0x7f6c1feb` | 1 | `0x3010a8fb` | 0x0000000000000000000000000000000000000000 | not-phase0 |
| `0x15cf3da7` | 0 | `0x51097096` | ETH | PASS 820533188984304182943770 |
| `0x69cddd43` | 0 | `0xbe7b4e09` | ETH | PASS 1187405272636523783629525 |
| `0xc868ceb6` | 0 | `0x62871674` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x994bb4e7` | 0 | `0xc8072ca0` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0x2a598242` | 0 | `0x3d2922cb` | ETH | PASS 1084809500830138257825253 |
| `0x73ebc734` | 0 | `0xa8b175bb` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xa86731ea` | 0 | `0xef320679` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0xbbf9e749` | 0 | `0x00beb118` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x648637e6` | 0 | `0x9140fea9` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x64629322` | 0 | `0x867879bc` | ETH | PASS 1198779772967094773401011 |
| `0x6fdeee00` | 0 | `0x5b4b83a9` | ETH | PASS 1198779772967094774113715 |
| `0xb2e6d528` | 0 | `0x740330e1` | ETH | PASS 1167841788155728723325423 |
| `0xd9ed8746` | 0 | `0xcac6cb65` | ETH | PASS 1184922275838457903335460 |
| `0x2c9ce272` | 0 | `0x4984303f` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xc29f4750` | 0 | `0x15368165` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x49842915` | 0 | `0x6eca05dd` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x75beef46` | 0 | `0xb928bc52` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x0973aa89` | 0 | `0xaa287248` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xac4faa20` | 0 | `0xc5d8ab34` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x691d788d` | 0 | `0x4d5b7a0f` | 0xccee82fe024c36fa15e1005ede3e9e4787e23d09 | custom-pair-skipped |
| `0x3a6e78c1` | 0 | `0xdffa7d28` | ETH | PASS 1118961343974872465486976 |
| `0xcf75ead6` | 0 | `0x489d3a1f` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0xf66e5ec0` | 0 | `0x9f217fa3` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xdb76fb5f` | 0 | `0xffcb97e0` | ETH | PASS 357671848345477717956104 |
| `0xc78897a2` | 0 | `0xe0b36fcb` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0xd44f9041` | 0 | `0x9730bcc1` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x1594ae76` | 0 | `0x9c395064` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x9785678c` | 0 | `0xb6434838` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0xe4f67e1f` | 0 | `0xea98cf90` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x36ef6c98` | 0 | `0x0f3c56f5` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0x36acda6e` | 0 | `0x0110cb75` | ETH | PASS 1176558652975666341744347 |
| `0xcb5b2916` | 0 | `0x1f36251d` | ETH | PASS 1174590445740848033204619 |
| `0x76ec792f` | 0 | `0x22690f52` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xed4eb0b1` | 0 | `0xf22cd6bf` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x43d1d26f` | 0 | `0xb1c9dd3a` | ETH | PASS 1054134327148231594162118 |
| `0xa0719bdc` | 0 | `0x0c8821bb` | 0x1b0e319c6a659f002271b69db8a7df2f911c153e | custom-pair-skipped |
| `0xf9f40f92` | 0 | `0xb767e06f` | 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68 | custom-pair-skipped |
| `0x0488ce48` | 0 | `0x36dcc28e` | ETH | PASS 1174590445721680709627883 |
| `0x0f9a2807` | 0 | `0x039c7dd2` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x1493b299` | 0 | `0x17f78f47` | ETH | PASS 1198779772954958298875288 |
| `0x3e208dc6` | 0 | `0xc12c8f35` | ETH | PASS 303748885082222068901271 |
| `0xb7535834` | 0 | `0x503f8a73` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x51ccc8bf` | 0 | `0x3d33e893` | ETH | PASS 1189468478776172103425360 |
| `0x23942f30` | 0 | `0xd8428c5d` | 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 | custom-pair-skipped |
| `0x65130d11` | 0 | `0x3f554e76` | 0x4e62068525ab11fe768e29dfd00ef909b9803016 | custom-pair-skipped |
| `0x0e939393` | 0 | `0xd1c1e9e1` | ETH | PASS 1056275520249104646860274 |
| `0xd2dd6f8a` | 2 | `0x7398a421` | 0x0000000000000000000000000000000000000000 | not-phase0 |
| `0x3e07bde3` | 0 | `0xcf30d03e` | ETH | PASS 1166199689268305765811195 |
| `0xe5ae5ac9` | 0 | `0x8a6eb595` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xffd4a033` | 0 | `0x421fe368` | ETH | PASS 1198779772967094774113715 |
| `0xbf970d94` | 0 | `0x8162982f` | 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 | custom-pair-skipped |
| `0xb2a7cf78` | 0 | `0xd44e8ee4` | ETH | PASS 822213540746547542019402 |
| `0x6a38b8a2` | 0 | `0xc9fbe403` | ETH | PASS 1198779772967094771262899 |
| `0x9b8a1828` | 0 | `0x8cbeef9a` | 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 | custom-pair-skipped |
| `0x47b4f45f` | 0 | `0x7ee8d2b2` | ETH | PASS 1098344369393301059584813 |
| `0x14f573cb` | 0 | `0xd809701d` | ETH | PASS 1171592969913786638812218 |
| `0x0df659bb` | 0 | `0x79689c95` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x331a244c` | 0 | `0xa9fc5138` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x6e5aae66` | 0 | `0x0b51a9a0` | ETH | PASS 1183922798840852209621003 |
| `0x7b202d70` | 0 | `0xd552285a` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x78581635` | 0 | `0x776a8b66` | ETH | PASS 1148827523848857984673395 |
| `0xfa35b8fc` | 0 | `0x6753b694` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x250e3905` | 0 | `0xe88884c7` | ETH | PASS 1180796695292902305321124 |
| `0x261f6fbe` | 0 | `0xad7e4331` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x132cb8b5` | 0 | `0x45b619e1` | ETH | PASS 1198109071781560235029086 |
| `0x83e71161` | 0 | `0x15c27c6a` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xcb5b3bde` | 0 | `0x123c128d` | ETH | PASS 1174590445740848032506279 |
| `0xa794bef7` | 0 | `0x04d32afb` | ETH | PASS 1159786581877024112635525 |
| `0xd4b8f71e` | 0 | `0xcd65f336` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x88958ec4` | 0 | `0x09678bec` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xc2089973` | 0 | `0x8041d5e7` | ETH | PASS 1198779772967094772688307 |
| `0x5d00de7a` | 0 | `0x89dab439` | ETH | PASS 1198779772967094773401011 |
| `0xb8e9dd7e` | 0 | `0x648bcab9` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xb5d9091a` | 0 | `0xb691ea36` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0xa7cc3d4a` | 0 | `0x4784886e` | 0x62fd0668e10d8b72339be2dcf7643001688ff13b | custom-pair-skipped |
| `0x7f9c9f23` | 0 | `0xdab6a9a1` | ETH | PASS 1174590445733336513610778 |
| `0xb3f0269e` | 0 | `0xd5b6d792` | 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 | custom-pair-skipped |
| `0x7d29e42d` | 0 | `0x4b08a855` | ETH | PASS 1198040618662217952463249 |
| `0xe2e3692e` | 0 | `0xdc904c97` | 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 | custom-pair-skipped |
| `0x3bf8a84f` | 0 | `0x574b43f1` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xd0494032` | 0 | `0x725c5f1f` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0xc3cf62c3` | 0 | `0x9570646c` | ETH | PASS 1186685255808654910738566 |
| `0xb326f29d` | 0 | `0x2a15a895` | ETH | PASS 1155254151641538957064120 |
| `0xca87873b` | 0 | `0x306d51e1` | 0x980dcf6766fa79f5cf0c4aadb3ab477ff15a9619 | custom-pair-skipped |
| `0xfff3a36f` | 0 | `0xa932275a` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0xadb79cdf` | 0 | `0x7767ae72` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xb438cd38` | 0 | `0xfbed24fd` | 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 | custom-pair-skipped |
| `0x8d64b0d1` | 0 | `0xa9f3390a` | ETH | PASS 1184519342263672006824463 |
| `0x1187f60a` | 0 | `0x265b0ec6` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xfa6ea172` | 0 | `0x11dc8bb0` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x27e68d50` | 0 | `0xd7a6be1b` | ETH | PASS 1186539199434825584694403 |
| `0x1917078d` | 0 | `0xf76464fc` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x9ff2bfb5` | 0 | `0x7239f4ca` | 0x322f0929c4625ed5bad873c95208d54e1c003b2d | custom-pair-skipped |
| `0xc477b9cd` | 0 | `0x23164186` | ETH | PASS 1174590445721680708929544 |
| `0x08749de2` | 0 | `0x5764d385` | ETH | PASS 1198779772967094774113715 |
| `0x1d5653e2` | 0 | `0x58e62a3f` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xbbd512a9` | 0 | `0xb7e7a591` | ETH | PASS 1186685255808654889192970 |
| `0x8fb957e4` | 0 | `0x00e1f800` | ETH | PASS 1191700212370556732234795 |
| `0xc0d393a0` | 0 | `0x16caf543` | ETH | PASS 1198779772967094774826419 |
| `0x3be470a0` | 0 | `0x33e08885` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x4bc8ff42` | 0 | `0x3ea9fb8c` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x12977045` | 0 | `0x8050da5d` | 0x980dcf6766fa79f5cf0c4aadb3ab477ff15a9619 | custom-pair-skipped |
| `0xe2a74c45` | 0 | `0x2ebfebe8` | ETH | PASS 1169532776468056092959923 |
| `0x6115b029` | 0 | `0xc9aa3d57` | ETH | PASS 908422348620183463207573 |
| `0x5e7bae6d` | 0 | `0x8986a729` | 0xb90a19ff0af67f7779aff50a882a9cff42446400 | custom-pair-skipped |
| `0x8f46ac3f` | 0 | `0xb583b16b` | ETH | PASS 451345793162960400329017 |
| `0xe72bfa4a` | 0 | `0xc15bfae7` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0x7cd4a120` | 0 | `0xeadb8490` | 0x6330d8c3178a418788df01a47479c0ce7ccf450b | custom-pair-skipped |
| `0x3287f2ca` | 0 | `0xe27b3f52` | ETH | PASS 345043345392775424451446 |
| `0xaee354d7` | 0 | `0xb16aee50` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x086c6dce` | 0 | `0x3ccea555` | ETH | PASS 1158208094884329271780906 |
| `0x1683e4d3` | 0 | `0x01c41156` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x6ad46b10` | 0 | `0xafd2324e` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x7b1d1aba` | 0 | `0xe3427a22` | ETH | PASS 1159843026865639030120621 |
| `0x6ea88c1d` | 0 | `0xdd09c1f5` | 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 | custom-pair-skipped |
| `0x7925c041` | 0 | `0x16d306ac` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x85bab471` | 0 | `0xf29c7149` | ETH | PASS 1149100749106206388063529 |
| `0x0dcd3026` | 0 | `0x56ed787c` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0x66539bf9` | 0 | `0x295c9ba0` | ETH | PASS 1187638251061645547275744 |
| `0x5946eff9` | 0 | `0xc0994505` | ETH | PASS 1012831935767188027061000 |
| `0xffbf0196` | 0 | `0x962d3ddf` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x2cfed4f0` | 0 | `0x89bde3c0` | ETH | PASS 1198779772967094764848563 |
| `0xf4bb7c5f` | 0 | `0x59519d11` | ETH | PASS 1198779772967094773401011 |
| `0x15a9e141` | 0 | `0x025216a8` | ETH | PASS 1146740990708820573925526 |
| `0x59fa6276` | 0 | `0xe714941f` | ETH | PASS 1198779772967094774826419 |
| `0x380bc6f0` | 0 | `0xd355894f` | ETH | PASS 1198779772967094774113715 |
| `0xaebf2ba5` | 0 | `0xdc98f921` | ETH | PASS 1198779772967094774826419 |
| `0xd2496b97` | 0 | `0x82da2c96` | ETH | PASS 1155188799189775550696915 |
| `0xc7a88ae8` | 0 | `0x0f08cb69` | ETH | PASS 1161554583910914822069233 |
| `0xe1be971f` | 0 | `0x112c7220` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x97ee12b0` | 0 | `0x5f8a179b` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x0b49e370` | 0 | `0xa1962f6b` | ETH | PASS 1154928978845909102665017 |
| `0x2a7cc9e6` | 0 | `0x8bbde4a7` | ETH | PASS 1198776624605835417919699 |
| `0x3b7fc565` | 0 | `0x3b5571cf` | ETH | PASS 1149005725454232957566602 |
| `0xd539271d` | 0 | `0x723a6f4e` | 0xb90a19ff0af67f7779aff50a882a9cff42446400 | custom-pair-skipped |
| `0x10efde82` | 0 | `0x21a37c4e` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x307cb197` | 0 | `0x44b46355` | ETH | PASS 1155707594047249385640273 |
| `0x8348b118` | 0 | `0x07b4f81d` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xa9c19dc1` | 0 | `0x0180836a` | 0x322f0929c4625ed5bad873c95208d54e1c003b2d | custom-pair-skipped |
| `0x61e8626b` | 0 | `0x01f24067` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x1f02704f` | 0 | `0xe9e3c7a9` | ETH | PASS 1186685255808654909327522 |
| `0x6efeada1` | 0 | `0x6e8d4155` | ETH | PASS 1180637887386433954143833 |
| `0x85b1e52f` | 0 | `0x7589d119` | ETH | PASS 1185766528856481437942381 |
| `0x03b759df` | 0 | `0x39ab594a` | ETH | PASS 1118347620276096807927237 |
| `0x6cabf375` | 0 | `0x751bcae3` | ETH | PASS 1158761497660976102392668 |
| `0xa7153672` | 0 | `0x38770aa3` | ETH | PASS 1194460170621924212367905 |
| `0x9411a656` | 0 | `0x4c56d39f` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0xa756296b` | 0 | `0x20f1e2be` | ETH | PASS 1186685255808654910033044 |
| `0x1be41583` | 0 | `0xe7e2c6c8` | ETH | PASS 1120708926766601043564170 |
| `0xf30a9085` | 0 | `0x98e4394f` | ETH | PASS 1148827523848857984673395 |
| `0xbbcc3676` | 0 | `0xcd7fe7f4` | ETH | PASS 1174590445739052862552422 |
| `0x9ce5746e` | 0 | `0xb6547aed` | ETH | PASS 1192731155825849685327319 |
| `0x6a3bf53a` | 0 | `0xae210188` | ETH | PASS 1038723187584037492494163 |
| `0x5f7fd169` | 2 | `0x8e28323d` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | not-phase0 |
| `0x2ede1ac8` | 0 | `0xa0afa276` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xe708bc94` | 0 | `0xc5704c59` | ETH | PASS 1177071816455920229284459 |
| `0xf80f2ebd` | 0 | `0x61910492` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x313d20f3` | 0 | `0xe130074d` | ETH | PASS 1174590445733874851578689 |
| `0x4b28093d` | 0 | `0x64712dfa` | ETH | PASS 1161151125963439360158992 |
| `0x47a5e847` | 0 | `0x3bb80718` | ETH | PASS 642958203384700608754936 |
| `0x0d013a65` | 0 | `0xef67684e` | ETH | PASS 1198779772967094774113715 |
| `0x817fe276` | 0 | `0xf6b20314` | ETH | PASS 1198779772967094774113715 |
| `0x64154047` | 0 | `0x49b52499` | ETH | PASS 1149331802907448351105539 |
| `0x164260cf` | 0 | `0xafbdfc09` | ETH | PASS 1198601329350231131606689 |
| `0x84bc8d7c` | 0 | `0x09504b2a` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x8077bce6` | 0 | `0xe4cebd01` | ETH | PASS 1137408676100342646376933 |
| `0x745fcd6d` | 0 | `0xf9845f0e` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x81e9c3c6` | 0 | `0x52a7bfb1` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0x1e9b78e6` | 0 | `0x655a21cf` | ETH | PASS 1198779772967094771975603 |
| `0x149a743f` | 0 | `0x06b51697` | 0xe93237c50d904957cf27e7b1133b510c669c2e74 | custom-pair-skipped |
| `0x95b02240` | 0 | `0x18190b03` | ETH | PASS 1132432423255384006143306 |
| `0x839a93de` | 0 | `0xbbfea68d` | ETH | PASS 1197843427285071620646096 |
| `0xde0e4f0b` | 0 | `0xbe55240d` | ETH | PASS 1198779772967094761997747 |
| `0x88778672` | 0 | `0x01feea15` | ETH | PASS 1198779772967094773401011 |
| `0xfb097e2a` | 0 | `0x0b7ce5c5` | ETH | PASS 1186685255808654910033044 |
| `0x83bf52d4` | 0 | `0xf7038867` | 0xc9a981fee1f9dec688bb123ccdecc63d0debfc4e | custom-pair-skipped |
| `0x7bb57e65` | 0 | `0x0b49158c` | ETH | PASS 1186685255808654905094390 |
| `0x80c3b329` | 0 | `0x285a8a5a` | 0xad25ac6c84d497db898fa1e8387bf6af3532a1c4 | custom-pair-skipped |
| `0x59cd69ec` | 0 | `0x5d60126e` | ETH | PASS 1186407207484159762132904 |
| `0x16ead0a8` | 0 | `0x190b7260` | ETH | PASS 1198779772967094773401011 |
| `0xb7fd23cf` | 0 | `0x03e190cf` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0xd978e18b` | 0 | `0x5445c103` | ETH | PASS 1154540757134530169769598 |
| `0x1abcc398` | 0 | `0x18d52d6f` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x9900fd42` | 0 | `0x516eeefd` | ETH | PASS 1170336207496150184258501 |
| `0x88a2daa2` | 0 | `0xe0d22cdc` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xdc28cef2` | 0 | `0xf6d11ce2` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x1a1269fb` | 0 | `-` | - | factory-revert (Too Many Requests) |
| `0xfefe4b0b` | 0 | `0xfd6b1882` | ETH | PASS 1198777079561709984880808 |
| `0x48efeef0` | 0 | `0xee8fab54` | ETH | PASS 1132077593821683416115652 |
| `0x6318813d` | 0 | `0xe2683aae` | ETH | PASS 1198779772967094774826419 |
| `0x43fd4752` | 0 | `0x6067a4e3` | ETH | PASS 1196177237941690857380850 |
| `0x7fbfc779` | 0 | `0xf0c49bdf` | ETH | PASS 1077821419177685692807131 |
| `0x5c59d48f` | 0 | `0xd862715f` | ETH | PASS 1151460740085157527038796 |
| `0xb2d9d6d0` | 0 | `0x2daf9fc2` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x2caed28e` | 0 | `0x7fce5077` | ETH | PASS 1197363448078004467830257 |
| `0x9ef0e828` | 0 | `0x7bb7a0ae` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xbebd46f5` | 0 | `0x89559075` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x2882299a` | 0 | `0x9e7b02d4` | ETH | PASS 1102015433641378298358578 |
| `0xcc63c367` | 0 | `0x575e6b86` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xb5e6f003` | 0 | `0x9b71ddb8` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x0f34e3e8` | 0 | `0x33bf43ac` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x5a1ef3c4` | 0 | `0x829d16de` | ETH | PASS 1198779772967094772688307 |
| `0xdcde713b` | 0 | `0x771248df` | ETH | PASS 1174454899902358978509346 |
| `0x7ccea94c` | 0 | `0xa5b9d2e1` | ETH | PASS 1198779772967094774113715 |
| `0xf3ea2cf7` | 0 | `0x166e241e` | 0xccee82fe024c36fa15e1005ede3e9e4787e23d09 | custom-pair-skipped |
| `0xca5e2751` | 0 | `0x4ce60889` | 0xccee82fe024c36fa15e1005ede3e9e4787e23d09 | custom-pair-skipped |
| `0x06d9ac9b` | 0 | `0x7eaa91d9` | ETH | PASS 1188743888722569909873926 |
| `0xa5cd23bc` | 0 | `0xbf9ba1ea` | 0x941ae714ec6d8130c7b75d67160ca08f1e7d11dd | custom-pair-skipped |
| `0xce614272` | 0 | `0x50921d80` | ETH | PASS 1149317354295336359096762 |
| `0x55058250` | 0 | `0xa4f4180e` | ETH | PASS 1148948479638908792557050 |
| `0x7334b2f6` | 0 | `0x55dccb66` | ETH | PASS 1198779772967094774113715 |
| `0x62413061` | 0 | `0x12e63c21` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0x08986745` | 0 | `0x3c81419a` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x7dca49d7` | 0 | `0xfe19f1a7` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x8e6e3ef7` | 0 | `0xfb3b4808` | ETH | PASS 1174135000757015216505510 |
| `0x4f3081e4` | 0 | `0x7793bd2f` | ETH | PASS 657783256439162741130593 |
| `0xfd58a5c4` | 0 | `0x1811b541` | ETH | PASS 1165896563117540336614387 |
| `0x5929a98f` | 0 | `0x1cf870e0` | 0x12f190a9f9d7d37a250758b26824b97ce941bf54 | custom-pair-skipped |
| `0xe3832176` | 0 | `0x124d25d3` | ETH | PASS 1183922798840852209621003 |
| `0x05991fa5` | 0 | `0x21203dd0` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0x89705bfd` | 0 | `0x021ef209` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x34191d25` | 0 | `0xb45a9836` | ETH | PASS 1174590445740848029014580 |
| `0xaa2080dd` | 0 | `0xa61d430f` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x50164d2d` | 0 | `0xbedfb88c` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xcffb2e5f` | 0 | `0xcd30de55` | ETH | PASS 1099269963767352407560829 |
| `0x1187d864` | 0 | `0x2f324285` | 0xcef9027c7d6985b85f0ba431125073529a947a68 | custom-pair-skipped |
| `0xd2a67ba9` | 0 | `0xd25caa73` | 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 | custom-pair-skipped |
| `0x7d3c5513` | 0 | `0x694ba52e` | 0x894e1ec2d74ffe5aef8dc8a9e84686accb964f2a | custom-pair-skipped |
| `0x9ae0d7d9` | 0 | `0xd16a4292` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xdd5abaf5` | 0 | `0x2d3eb708` | 0x05b37fb53a299a1b874a619e1c4c404d52c36f4c | custom-pair-skipped |
| `0x203ecec8` | 0 | `0x56b1be0c` | ETH | PASS 1159245470788269246216226 |
| `0x97f7f9d5` | 0 | `0x5be244d5` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xb8ed626e` | 0 | `0xa9672035` | ETH | PASS 1186126478945956123049863 |
| `0x41759343` | 0 | `0x494ec814` | 0xcef9027c7d6985b85f0ba431125073529a947a68 | custom-pair-skipped |
| `0x131d3204` | 0 | `0xb1c00448` | ETH | PASS 1185611758659745374971419 |
| `0xb2acb6b2` | 0 | `0xef32513f` | ETH | PASS 1198779772967094774113715 |
| `0x20daec9a` | 0 | `0xba79cefc` | ETH | PASS 1198779772967094774113715 |
| `0x699402a8` | 0 | `0xc1423375` | ETH | PASS 1198779772967094705694132 |
| `0x24d9bc4e` | 0 | `0x045d2696` | ETH | PASS 1177041885084812502193411 |
| `0x0b5d26c8` | 0 | `0x434a3bab` | ETH | PASS 1144275950077648058969537 |
| `0xcce46027` | 0 | `0x50923c20` | 0xc9a981fee1f9dec688bb123ccdecc63d0debfc4e | custom-pair-skipped |
| `0x32ec7bb6` | 0 | `0xd5fb7db2` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xfc973191` | 0 | `0x6d0a8be4` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xe6d9bd6b` | 0 | `0x939582ac` | ETH | PASS 1196163038314646996202426 |
| `0x71521666` | 0 | `0xa7f808f1` | 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 | custom-pair-skipped |
| `0xf9ea6ab7` | 0 | `0xd18a3767` | ETH | PASS 1174590445740848032506279 |
| `0x529cc204` | 0 | `0xf4a796f9` | ETH | PASS 177668429063625037801628 |
| `0x412c0dbe` | 0 | `0x6b69fcbd` | ETH | PASS 1184121028537456022336433 |
| `0x4ef272b2` | 0 | `0xd3c95826` | ETH | PASS 1197746173746427927296850 |
| `0xc38cae44` | 0 | `0x91738024` | ETH | PASS 1198779772967094761997747 |
| `0xedb455ca` | 0 | `0x8c2217b2` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x5ca997c1` | 0 | `0x4c296637` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xe7f1f246` | 0 | `0x2f25bde8` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x8af651e9` | 0 | `0xd0ed0ac7` | ETH | PASS 1138304257958419707090537 |
| `0x7cbc6682` | 0 | `0xb8311c67` | ETH | PASS 1174590445719419761838041 |
| `0x11f17f31` | 0 | `0x933858fb` | 0x117cc2133c37b721f49de2a7a74833232b3b4c0c | custom-pair-skipped |
| `0x3bc8e6e9` | 0 | `0x7dcecd74` | 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68 | custom-pair-skipped |
| `0xc1eba37e` | 0 | `0xbaf34952` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xca0baab5` | 0 | `0x44ae16b7` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xa1db5d7f` | 0 | `0x61e25430` | ETH | PASS 1188259520436642887495340 |
| `0x5ee73cc0` | 0 | `0xbbffb05e` | 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea | custom-pair-skipped |
| `0x7c1796ee` | 0 | `0xeb972325` | ETH | PASS 1198719578301634155094814 |
| `0x0f4b6c4a` | 0 | `0x80655ab7` | ETH | PASS 1174473175558315634292097 |
| `0x398cc9a0` | 0 | `0xa96596f1` | 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 | custom-pair-skipped |
| `0xe04b4d9a` | 2 | `0x704dcb2c` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | not-phase0 |
| `0xd1864e54` | 0 | `0xeb994e59` | ETH | PASS 1172669503045317793902367 |
| `0x9e43e16f` | 0 | `0x1d13bd70` | ETH | PASS 1186685255808654909327522 |
| `0x8a9e5157` | 0 | `0xbcfef4bb` | ETH | PASS 1174355677328789400737136 |
| `0x7587d4c0` | 0 | `0x59214cfa` | 0x84cab63bc87912e71ad199ff14a0ba45de68fef8 | custom-pair-skipped |
| `0xbd689a43` | 0 | `0xc707bdc3` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x65566986` | 0 | `0x28d63926` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xfc1579c4` | 0 | `0xd981d1b0` | 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 | custom-pair-skipped |
| `0x41e152a6` | 0 | `0x0eff4612` | ETH | PASS 1163024350646741690178429 |
| `0xeecf699f` | 0 | `0xf7e2e7d0` | 0x84cab63bc87912e71ad199ff14a0ba45de68fef8 | custom-pair-skipped |
| `0xab6dd4fa` | 0 | `0xd7d94776` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x5050d81d` | 0 | `0xed16f097` | ETH | PASS 1133471710609521278663149 |
| `0xb6fc4995` | 0 | `0x2c398391` | ETH | PASS 1174590445740848032506279 |
| `0x56998b30` | 0 | `0x81ad0e55` | ETH | PASS 1158658808065869748051571 |
| `0xa50b4d51` | 0 | `0x8322e1cf` | ETH | PASS 1161583281947502414282574 |
| `0x80a7326b` | 0 | `0xed76c2ff` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xccc4aa4d` | 0 | `0x837139f3` | ETH | PASS 1095827247407662048320314 |
| `0xfc269504` | 0 | `0xc01cdf8a` | ETH | PASS 1198779772967094774826419 |
| `0x8de24da6` | 0 | `0x3c7e3f93` | ETH | PASS 998216650426893362997407 |
| `0x06e8a9fc` | 0 | `0x981abde8` | ETH | PASS 1189119225072640981021887 |
| `0xed2b3d04` | 0 | `0xbad4142d` | ETH | PASS 1174590445740848032506279 |
| `0x29baa90a` | 0 | `0x82571fc3` | ETH | PASS 1198779772967094774826419 |
| `0x0e69da10` | 0 | `0x5007095a` | ETH | PASS 1186685255808654910033044 |
| `0x9fb89cd4` | 0 | `0x97c5a396` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x7ce3f693` | 0 | `0x5e9dac98` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x0b3a0412` | 0 | `0xb7116476` | ETH | PASS 1197652113562744231764306 |
| `0x17488dcb` | 0 | `0xa42d7a30` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xf471bbc0` | 0 | `0x62fc85c9` | ETH | PASS 1174590445740848026919561 |
| `0x79165533` | 0 | `0xa7c1be65` | ETH | PASS 1149100749106206389429161 |
| `0x5e517b8f` | 0 | `0xf284fd80` | ETH | PASS 1174590445740848031807939 |
| `0xce276e08` | 0 | `0x9818508e` | 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 | custom-pair-skipped |
| `0xca8cdd7c` | 0 | `0xcba180e9` | 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 | custom-pair-skipped |
| `0x813eaf49` | 0 | `0xc12d2588` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0x48a9a409` | 0 | `0x242a42b6` | ETH | PASS 1131523168304855490417412 |
| `0xcd47848e` | 0 | `0xc9b8b0fb` | ETH | PASS 1187487775790975446033884 |
| `0x4e180599` | 0 | `0x9a16b8af` | 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec | custom-pair-skipped |
| `0xba213d23` | 0 | `0xc610ebf1` | 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 | custom-pair-skipped |
| `0x01ba126f` | 0 | `0xc8d9bbbc` | ETH | PASS 1186685255808654909327522 |
| `0xa31d092c` | 0 | `0x082e0576` | ETH | PASS 1020522291579177519178414 |
| `0x5121d0c6` | 0 | `0x1c9c977b` | ETH | PASS 1186685255808654909327522 |
| `0xc80340c0` | 0 | `0x52bbca54` | 0x5e81213613b6b86eab4c6c50d718d34359459786 | custom-pair-skipped |
| `0xcabacd46` | 0 | `0xa73dc078` | ETH | PASS 1186685255808654910033044 |
| `0x7428c76c` | 0 | `0x3078d2fb` | 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 | custom-pair-skipped |
| `0xe17a12c5` | 0 | `0x3392b527` | 0x12f190a9f9d7d37a250758b26824b97ce941bf54 | custom-pair-skipped |
| `0xcc798b52` | 0 | `0x455d2bb9` | 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 | custom-pair-skipped |
| `0xfd3d458f` | 0 | `0x95d53fc3` | 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 | custom-pair-skipped |
| `0x55931e1c` | 0 | `0x649320d3` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xb00cda8a` | 0 | `-` | - | factory-revert (Too Many Requests) |
| `0x084cf085` | 0 | `0x2974fd48` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xe601779e` | 0 | `0x949b0685` | ETH | PASS 1198779772967094759859635 |
| `0xc33ce70f` | 0 | `0xd24921a6` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0xb765b379` | 0 | `0x52b91656` | ETH | PASS 1198779772967094774826419 |
| `0xea860075` | 0 | `0x9f31a8da` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x79325553` | 0 | `0x1dc1e55e` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |
| `0x0d377555` | 0 | `0xfa81eda3` | 0xe0444ef8bf4ed74f74fd73686e2ddf4c1c5591e8 | custom-pair-skipped |
| `0x160457b9` | 0 | `0x1280d0c0` | ETH | PASS 1186685255808654909327522 |
| `0x1af70406` | 0 | `0x53175722` | ETH | PASS 1143376922763944755190207 |
| `0xec931eb1` | 0 | `0x099c05ba` | ETH | PASS 1195960753096125429651887 |
| `0xb9513560` | 0 | `0xf15daf2c` | 0x5fc5360d0400a0fd4f2af552add042d716f1d168 | no-fill (execution reverted [0x13be252b]) |

Result in research/pons-live-fillability-20260905-1043.json. PASS requires real non-revert eth_call returning tokensOut>0 at $5.

## USDG-pair verdict (2026-09-05)
0x13be252b = InsufficientAllowance() (public selector DBs). This RH RPC ignores state-override storage entries, so ERC20 balance/allowance cannot be injected into eth_call. USDG-pair 'no-fill' rows are a SIM ARTIFACT - not verified either way. Native-ETH rows stand.
