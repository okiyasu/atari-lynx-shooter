# APS-051 evidence

段階1のcadence測定修理証跡（v003、通常ROM/計測ROM分離）。

- `frame-cadence-gearlynx.json`: cadence ROMでのTimer 2 VBLANK基準と、0/4/8 normal・boss+4 normal（NORMAL/BOSS）の独立2 batch×各75 display request interval。全raw sampleとrun別中央値/最大値を保存。
- 通常ROM: `GAME_VERSION_STRING=0.51.2`、LNX `60,062 bytes`、SHA-256 `710bd88fd025eab61821ece965d46198d21b56e6da7ca21bdb967ad86e9ad256`。計測ROM: LNX `60,178 bytes`、SHA-256 `0ce571704f96c64f82a72078aa380a936d1aa18f672bda18d62ed7a7df49ebf6`。
- 通常ROMはprobe object/header/main hookなし。計測ROMは`main-cadence.o`＋`cadence_probe.o`と専用map/label/cfgのみを含む。計測ROM BSS `$B319..$B857`、interval `$B76B..$B7B5` (75 bytes)、C stack `$B878`、残余32 bytesをmapから機械検査。
- VBLANK基準: `184,482 ticks = 13,333.333333333334us`、許容比率 `1.05`。ROM内のTimer 2 interruptorがVBlank IRQ回数をdisplay request間でバッチ保存し、完了フラグのwrite breakpointをfixtureごとに1回だけ使用する。
- TITLE校正: 独立2 batchのraw 75 samplesが全て`3 VBlank`、両run中央値/最大値`3`、既存基準`553,362 / 184,482 = 2.999544671`との差`+0.000455329`、校正PASS。
- 現行未最適化ROMは全fixtureで契約g FAIL。これは段階2の描画最適化前に期待される失格であり、FAIL内容を隠す閾値緩和は行っていない。
- `make frame-cadence-gearlynx`は両ROMのLNX header検査PASS後、契約g FAILで終了コード1。`debug_step_frame`、requestごとのpause/resume、host wall-clockは合否根拠に不使用。
- 旧v001のbreakpoint介入値（14x〜145x）は性能事実として無効。今回の契約gにはdebug_step_frame、requestごとのpause/resume、ホストwall-clockを使用していない。
