# APS-040 Gearlynx visual evidence

最終V0.40.0 ROM（SHA-256 `8706fa5f373ffbb7e9f608fb9e42fe0d149fe75cf20a7a93c30cc17c4bdfe1c3`）を
`scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-040`で連続2回検証した。
Stage 1〜3のNORMAL/CAST/BOSS、生成32-byte palette、boss active、double-buffer同期を各回確認した。

CASTはpaused `GameState.enemies[4]`へhost debuggerから3敵だけを注入したrender検証である。
Stage 1はSCOUT(0)/SAUCER(1)/DROPPER(2)、Stage 2はFIGHTER(3)/BOMBER(4)/SUPPLY(5)、
Stage 3はCAVE_BAT(6)/ROCK_WORM(7)/MINING_DRONE(8)を
`(40,24,8,8)/(80,47,8,8)/(120,70,8,8)`へ配置した。
全type/active/rectをmemory readbackし、player通常表示、player/enemy bulletとpower itemの不在、
stage palette、3種固有run/color gridの全非空pixelとGearlynx framebufferの完全一致を検査した。
state injectionはrender証跡専用であり、通常のspawn、移動、攻撃、dropを含むゲームプレイ検証の代替ではない。

さらに`--gui --output-dir evidence/APS-040/gui`を連続2回成功させ、同じ9場面を検証した。
GUI modeとheadless modeの対応PNGはSHA-256まで一致した。

| 画面 | PNG SHA-256 |
|---|---|
| Stage 1 NORMAL | `ca84fd26272bad2e3416d102c4de4f2126a3f7c182b16a5b0128347e39061144` |
| Stage 1 CAST | `047680a1f0818e75e26d00427ca2a1c274f79ff206b7f496b1a939f572899a1f` |
| Stage 1 BOSS | `6b8b75600bff4f96359f40ef10b401942217e73706fb223831f3e83052591cac` |
| Stage 2 NORMAL | `fb02a5b5265ef360a52015df6a796b8db58610c233b098e6659173b69bada18e` |
| Stage 2 CAST | `ed8fec7a718de0b06ab133c37001d0826d65ade20d7d2fffe8aed59324f9bd29` |
| Stage 2 BOSS | `88f60cc5061d2a16f611fb21cd25029a3163582e8f74e19820730a7b1ac4974b` |
| Stage 3 NORMAL | `3cb0ba739e31b945a159cce9900f4b93e2ccbda252c92613dad2f8563b77fa95` |
| Stage 3 CAST | `1041b23dc0695be9f51854a34b32e48d965c920d1b974f0e304961902ae504ae` |
| Stage 3 BOSS | `2b718597a65c57944410d40f464f62a9df77aed8ae8462278d1a0f1dd5801008` |

Gearlynx 1.2.21のrendered framebuffer検証であり、Atari Lynx実機LCD上の視認性評価ではない。
