# APS-043 Gearlynx visual evidence

最終V0.43.0 ROM（60,217 bytes、SHA-256
`4928ae53c81793b383a294e452d8cf126bb0e68810d3c8f1ebbabc5ead031f76`）を
`scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-043`と`--gui`で各連続2回検証した。
各回Stage 1〜3のNORMAL/CAST/BOSS、hardware palette、boss active、double-buffer同期、
player 8x6・normal enemy 8x8・boss既存寸法のcollision readbackを確認した。

CASTはpaused `GameState.enemies[4]`へhost debuggerから3敵だけを注入するrender検証であり、
spawn、移動、攻撃、dropを含むゲームプレイ検証の代替ではない。13個の個別PNGはGearlynxの
160x102 captureから各visual canvasを切り出した再現可能証跡で、authoring gridの全非空pixelを
hardware palette由来RGBと逐点照合した。GUI/headlessの9 full-screen PNGと13個別PNGは全てbyte一致した。

| target | visual / collision | cells(frame 0/1) | PNG SHA-256 |
|---|---|---:|---|
| player | 12x10 / 8x6 | 55/55 | `aea4117569528ed42e8d92c46ab9025c2b96a5f9804fd646771d862c3373f815` |
| scout | 12x12 / 8x8 | 49/49 | `c798606162250eb425cd2707a3e043d515914944914c5edeec4b71bf1a69abc5` |
| saucer | 12x12 / 8x8 | 50/50 | `5c93f6dbe567b4022da821babae2766523f780b44511cfeff7d80e6ff778e333` |
| dropper | 12x12 / 8x8 | 50/50 | `456eaa281ccf2b114563e9911bc113ab0c1b28bfaf62f348715ee3051e92ed1d` |
| fighter | 12x12 / 8x8 | 50/50 | `f23a169bceddc34fbd6277d44469651e67f8ef8099cddca67b9cd5f355861a18` |
| bomber | 12x12 / 8x8 | 64/68 | `25c115ec109792cebb6dc8fba8185ec338182ef73a7587c5fb6953a549d7e4a1` |
| supply | 12x12 / 8x8 | 49/49 | `e9945527f25088d958958489b1bf915913129b01592716e9a907d556bc0feee5` |
| cave_bat | 12x12 / 8x8 | 48/48 | `449f6d0b96e670083767f1de93474725fde270f3c18c4a78cce213da9c3ea19d` |
| rock_worm | 12x12 / 8x8 | 55/55 | `b9cc06dd026809ec8d02472f203ed95d3cd6774f12f2814dcfdbb7d9ee77e382` |
| mining_drone | 12x12 / 8x8 | 52/52 | `89819ef56589082c9b5a18840a4ca2f76290585b801179cdb144fba777edd35e` |
| coral_bastion | 24x16 / 24x16 | 134/134 | `210b9c621ea02debe5244be9df65fdf2c7a3b3f0f765eb4e9d265158badca026` |
| amber_carrier | 28x14 / 28x14 | 154/154 | `d2fc4f6bd410078b6b8caccf4cfba107eb02a4e0b2e8ab1487026f54d2bb71c8` |
| violet_geode | 24x24 / 24x24 | 144/144 | `0c2ef5fa52d69654f325a6df28f989daccf0771a618a7da3798fa1521e081fdd` |

| full screen | PNG SHA-256 |
|---|---|
| Stage 1 NORMAL | `47bdcc2aaba25999ba3fdac258e22b361e9f6655f1bfe0f35fbcf271894ae514` |
| Stage 1 CAST | `e9c9b07abe3a1a60115e6e8740d0498309a360146aedcf2e4b4009d752baba9c` |
| Stage 1 BOSS | `39b36e99d657c7c570afdd4a6b34d108d7b48227d8241f944a22e7c8256fa192` |
| Stage 2 NORMAL | `be1439ed549c05b958f132358424dc91fbad46473b3972bb871b7120986180d7` |
| Stage 2 CAST | `38b6790f5a7e0b08dc38d0957afc33ad75de3fc9c99ecea09cc97549f7a5e09e` |
| Stage 2 BOSS | `264b67db4e25651406967ae0ff2b00fe4dad71a5efaa1a95391cf011a3f7809e` |
| Stage 3 NORMAL | `bb9c87c0d09f54a380966f54fac04c9d58c0444998a786ee0cc390d21d198c02` |
| Stage 3 CAST | `a858e28a00e23213e9ebb632696ff95cc5b197bbab06c3d59b7c9127b56e6510` |
| Stage 3 BOSS | `8f859323128dda2878e3a85dd76abc5d5e5aa4be7bc12699e5201a8684af828a` |

同じ最終ROMでtitle/GAME OVER voiceとchannel A/C/B回帰も実行した。titleは17,408、GAME OVERは
11,691 Timer 3 IRQ/DAC sampleがreferenceと完全一致しunderrun 0。title後の38 tick wait、
GAME OVER release→press gate、A 6/C 3/B 6 pitch change、logical volumeの75% MIKEY投影を確認した。
Atari Lynx実機LCD・実機音量・残像・Lynx I/II差は未確認。
