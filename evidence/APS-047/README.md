# APS-047 VERIFY evidence

## 結果

- weighted capacity: normal=1、boss=4、limit=8。4 normal+bossと8 normal受理、5 normal+boss、8 normal+boss、9 normal拒否。
- cadence: headless/GUIとも0/4/8 normalおよび4 normal+bossで合格。各75 drawあたりinput 75、logic 300、sound 75、previous-display sync 75、display request 75。coexist fixtureはNORMAL/BOSSを各75 draw確認。
- movement: player `+8 px/draw`、player bullet `+16 px/draw`、normal enemy `-4 px/draw`、BOSS phase boss `+2 px/draw`、boss attack timer `+4/draw`。
- runtime sprite: 13種26 frame、274/524 runs。packed run 822 bytes、definition 104 bytes。enemy mapping=`1,2,3,4,5,6,7,8,9`、boss mapping=`255,10,11,12`。JSON→生成C→最終ROM→共通runtime traversal→Gearlynx framebufferを照合。
- actual play: TITLEで実controller Aをrelease→pressし、Stage 1 NORMALへ正規遷移した`actual-play-stage1.png`。GameStateはstage=1、phase=NORMAL、enemy type=0/scout。前回front bufferに対するstateの1 draw先行を考慮し、enemy readback `(134,47)`、一致render origin `(138,47)`をJSONへ記録。
- visual: Stage 1〜3のNORMAL/CAST/BOSS、全13個別spriteをheadless/GUIで照合。対応PNGはbyte一致。
- audio: title 17,408 samples、GAME OVER 11,691 samplesをTimer 3 IRQ/DAC全sample一致、underrun 0、title wait 38→0、release/press gate成功。A/C/Bは8/20/8秒でpitch変化6/3/6、全logical volume→75% MIKEY gain一致。

## 実行

- `make clean && ./scripts/verify.sh`: PASS。stage 51、game 611、sound 351、IMA 14,949、sprite 1,055、strict C89、cc65、assembly、shell lint、voice/gain/cart/LNX。
- ASan/UBSan host suites: PASS。game 611、sound 351、IMA 14,949、sprite 1,055、smoke 19。
- `make smoke-host`: PASS、19 checks。
- `make perf-host`: PASS。sync=75 draw/300 logic/75 sound、logic 298.77 Hz、game speed x1.00。7 pairのlegacy-minus-optimized中央値23,223 us。
- `python3 -m py_compile scripts/generate-stage-data.py scripts/verify-frame-pacing-gearlynx.py scripts/verify-stage-visuals-gearlynx.py scripts/verify-audio-gearlynx.py scripts/verify-title-voice-gearlynx.py`: PASS。
- `git diff --check`: PASS。
- `scripts/verify-frame-pacing-gearlynx.py` headless/`--gui`: PASS。
- `scripts/verify-stage-visuals-gearlynx.py` headless/`--gui`: PASS。
- `scripts/verify-title-voice-gearlynx.py --mode title|game-over`: PASS。
- `scripts/verify-audio-gearlynx.py --channel a|c|b`: PASS。

## Artifact

- ROM: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`
- size: 59,530 bytes
- SHA-256: `06266e561dbd896a6c8db749d6d06a552e374b078d4fe56fc9b39812eaea712b`
- LNX header: magic=LYNX、version=1、bank0 page=1024、bank1 page=0。
- map: CODE `0x0298..0x976B`=`0x94D4`、RODATA `0x976C..0xAF5C`=`0x17F1`、DATA `0xAF5D..0xB090`=`0x134`、BSS `0xB091..0xB57D`=`0x4ED`。
- MAIN final used=`0xB57E`、C stack start=`0xB838`、residual=698 bytes。APS-046 residual 696 bytesから2 bytes改善。
- sprite object: CODE `0x1B2`、RODATA `0x3AB`。run data SHA-256=`b50a98b31030019a2db6a2cdbe718b02ef280131ef13c104f0d927088b8e7fd8`、definition SHA-256=`aef5c9e0c76ee494c997a05747c1e2e93781a49ff4a234ba2c316ceca19cf84d`。
- sprite canonical SHA-256: `ec88754b9b7ed062063d6c0d7c5dbd7fa96b1df016c702b6ad7273a44096297e`。
- title payload: 8,704 bytes、SHA-256 `99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2`。
- GAME OVER payload: 5,846 bytes、SHA-256 `848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f`。

## 証跡索引

- `frame-cadence-gearlynx.json` / `frame-cadence-gearlynx-gui.json`: pipeline、hardware timer、fixture別event count、weighted readback、移動量、拒否fixture。
- `runtime-sprite-gearlynx.json` / `gui/runtime-sprite-gearlynx-gui.json`: ROM table、mapping、GameState、framebuffer照合、PNG hash。
- `actual-play-stage1.png` / `gui/actual-play-stage1.png`: TITLE実入力からの通常ゲームプレイ。
- `stage1|2|3-normal.png`、`stage1|2|3-cast.png`、`stage1|2|3-boss.png`と`gui/`対応物: Stage実行経路。
- `player.png`、通常敵9種、boss3種と`gui/`対応物: 個別runtime sprite。headless/GUI hashは各JSONに記録。
- `title-voice.png`、`game-over-voice.png`、`game-over-voice-active.png`、`audio-a.png`、`audio-c.png`、`audio-b.png`: 音声/音楽回帰。

## 差分・未確認

- APS-047 v001との差分なし。
- collision、visual left-top anchor、2 frame、palette role、移動量、ゲームルール、難度、stage進行、boss script、開始音声後38 tick、voice/IRQ/cart、dynamic allocationは不変。
- Atari Lynx実機の75 Hz持続、weighted 8のcycle margin、LCD原寸判読性/残像、Lynx I/II差、speaker音量/音質、IRQ margin、長時間playthroughは未確認。
- commit/push/stash/reset/checkout、BIOS・外部ROM・外部素材操作なし。
