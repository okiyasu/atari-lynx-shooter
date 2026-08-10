# APS-042 Gearlynx visual evidence

最終V0.42.0 ROM（60,217 bytes、SHA-256
`42bbf19423b3a9c261e1c1ce6cf49cab142ea53acd3a5683204da7435c26d57c`）を
`scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-042`と`--gui`で各連続2回検証した。
各回Stage 1〜3のNORMAL/CAST/BOSS、hardware palette、boss active、double-buffer同期、
player 8x6・normal enemy 8x8・boss既存寸法のcollision readbackを確認した。

CASTはpaused `GameState.enemies[4]`へhost debuggerから3敵だけを注入するrender検証であり、
spawn、移動、攻撃、dropを含むゲームプレイ検証の代替ではない。13個の個別PNGはGearlynxの
160x102 captureから各visual canvasを切り出した再現可能証跡で、authoring gridの全非空pixelを
hardware palette由来RGBと逐点照合した。GUI/headlessの9 full-screen PNGと13個別PNGは全てbyte一致した。

| target | visual / collision | PNG SHA-256 |
|---|---|---|
| player | 12x10 / 8x6 | `8a3903f3f2549b1faa3688a53fac02b81903debe512168d9f867c9544a62e19d` |
| scout | 12x12 / 8x8 | `ba0936bc57cb482b92a76b07150b199c3cb4e086971695240fc99766085115ff` |
| saucer | 12x12 / 8x8 | `d13dc9d334371e700765659f5a90194dbc3093b742137fc82090fa7d7170d843` |
| dropper | 12x12 / 8x8 | `1d023901dd38d8ea9135b92563251c76dca8cd5059adfb3ac3ab04adcb38baef` |
| fighter | 12x12 / 8x8 | `eb93e36fd01dd10fe0f7c9a1b9f8f0f444a6232a96edaa1ac4f51fef80e9049a` |
| bomber | 12x12 / 8x8 | `c9ebf162338807ac5724e056d2cb611f62f36f5ad901a0491aa992f04b7912ad` |
| supply | 12x12 / 8x8 | `c003b89f51b009d323c5d9a997905c01f63a41332c0a9c2ee64a1f013a771121` |
| cave_bat | 12x12 / 8x8 | `fda79416ea3240d9a46e486e1743c124ee9867d2fab1ba57a2ae4dea9f61a1fe` |
| rock_worm | 12x12 / 8x8 | `57276da63b15d0b81ed36cae15740d044d170109a2552c0ce361751e2e1b9e82` |
| mining_drone | 12x12 / 8x8 | `2ac44637e96e168107fde6d999e53e0b58df51946137b3059c1e3abc90c12da3` |
| coral_bastion | 24x16 / 24x16 | `645031918e12633d8cadf8a98e43999e3d82290dd712875dae21c9a4cf24412c` |
| amber_carrier | 28x14 / 28x14 | `b8a52bc218738129ffc752a5dffe953afc92a90dfc0e5e849652af1ceadce4bb` |
| violet_geode | 24x24 / 24x24 | `d8150f38636cabf574aa371e178a9a1bcbda64e3e01ce2ed64a35fdf15e1860b` |

| full screen | PNG SHA-256 |
|---|---|
| Stage 1 NORMAL | `056d137fb4a9ad22861dd75102e739a6908e08a9940eb9f3330c7549c9a85c3a` |
| Stage 1 CAST | `44fbe9857f56b13b771906ed3501f80c1b993ad2300a945fec2c6b50bc9d32cf` |
| Stage 1 BOSS | `ba27386e0e5c4bcb2427aa283c9152ece1290a4768c161fa0b284a95f114f5b7` |
| Stage 2 NORMAL | `8161e2abf20bdf30c64545b4d61434bbbc87f2c54f054f932521af2f12953b5a` |
| Stage 2 CAST | `8944d856652f73a0553d8a6501577300b1cc22498067e45715744df623dc6fb5` |
| Stage 2 BOSS | `db74a2b94718c18036ffc830904d78b88ac161f7727a241e937a2b207b09122f` |
| Stage 3 NORMAL | `f4f543cf366350807e497c2f8f12a9d7c0df888bc5bdd9fec5b02e54365a37b6` |
| Stage 3 CAST | `54746e0f5f7f8904d1463152cefc1590d43ddee4cb633065a6a7dec6c7c8c333` |
| Stage 3 BOSS | `aff6fc83e44c82c0c88af323ea6b9435c418e57f8bc52d77721e1b63d763089a` |

同じ最終ROMでtitle/GAME OVER voiceとchannel A/C/B回帰も実行した。titleは17,408、GAME OVERは
11,691 Timer 3 IRQ/DAC sampleがreferenceと完全一致しunderrun 0。title後の38 tick wait、
GAME OVER release→press gate、A 7/C 3/B 6 pitch change、logical volumeの75% MIKEY投影を確認した。
Atari Lynx実機LCD・実機音量・残像・Lynx I/II差は未確認。
