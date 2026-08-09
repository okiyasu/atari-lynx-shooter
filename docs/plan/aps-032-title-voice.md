# APS-032 タイトル開始音声

確認日: 2026-08-09（APS-037 VOICEVOX Nemo差替え反映）

## 生成物

- 入力文言: `わしは宇宙の帝王ザカリテ`
- TTS: VOICEVOX Nemo Engine 0.24.0、男性2（エンジン表記`男声2`）、UUID `7ecc7a17-1465-4b22-a3b5-842a110ff55e`、`ノーマル` style ID `10000`
- 合成設定: speed 0.9、pitch -0.08、intonation 0.9、volume 1.0
- 生成環境: macOS 26.6 (build 25G72)、arm64 native、Rosetta不使用
- 中間形式: VOICEVOX loopback API出力の8 kHz mono signed 16-bit PCM WAV
- 最終形式: 8 kHz mono 4-bit IMA ADPCM、low nibble first、predictor 0、step index 0
- 自然長: 17,408 samples、2.176000秒
- 圧縮データ: 8,704 bytes、SHA-256 `99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2`

`scripts/generate-title-voice.py generate`はlocalhost限定の公式Nemo engineへ入力を渡し、
WAVを一時ディレクトリにだけ生成し、既定post-phoneme 0.1秒を800 sampleのexact zeroへ
決定的に正規化して、
`assets/voice/title-start.adpcm`、`assets/voice/title-start.json`、
`include/title_voice_data.h`を更新する。原音AIFF/WAVは同梱しない。`voice-check`は最終
artifactの長さ・SHA-256・metadata・headerを検証し、C89 codec回帰は全17,408 sampleを
復号して宣言byte数、波形範囲、非無音sample、最終状態を検査する。

## ライセンス制約

2026-08-09確認の[VOICEVOX Nemo利用規約](https://voicevox.hiroshiba.jp/nemo/term/)は、
クレジット表記を条件に生成音声の商用・非商用利用を許諾する。
[VOICEVOXソフトウェア利用規約](https://voicevox.hiroshiba.jp/term/)も各音声ライブラリ規約の
遵守とVOICEVOX利用が分かるクレジットを求める。本作は固定クレジット
`VOICEVOX:Nemo（男性2）`をROMタイトル画面と文書へ表示する。禁止事項と再許諾条件は
`assets/voice/LICENSE.md`を正本とする。公式arm64配布物をrepo外へ導入し、合成は同一Macの
loopback内だけで完結する。外部API、外部送信、Personal Voice、第三者音声素材は使用しない。

## 容量設計

自然長ADPCMはresident余地を超えるため、短縮、PCM化、sample rate変更は行わない。
cc65標準の単一directory entryを3 entryへ拡張し、entry 0をresident executable、entry 1を
cartridge-only title ADPCM、entry 2をcartridge-only GAME OVER ADPCMとした。custom linker config
`cfg/lynx-voice.cfg`と`src/cart_directory.s`がdirectoryを作り、
`src/title_voice_asset.s`の`TITLEVOICE`/`GAMEVOICE` segmentをRAMへloadせずROM末尾へ置く。

APS-037最終mapはBSS `0xB1E2..0xB6CE`（1,261 bytes）、C stack開始`0xB838`、
残余361 bytes。最終LNXは59,867 bytes。entry 1はblock 44、offset 197、cart offset
45,253、length 8,704、entry 2はblock 52、offset 709、cart offset 53,957、length 5,846。
`scripts/inspect-title-voice-cart.py`が両checked-in assetとのbyte同一性とROM末尾を検査する。

## 実時間復号

APS-035以降はTimer 3 backup 125を使う。1 us clockの実周期は`backup + 1` tickなので
126 us（7,936.508 Hz）。APS-037 assetの実効再生時間はtitle 2.193408秒、GAME OVER
1.473066秒。現行producerは128-byte buffer 5本と3段assembly queue、音声専用IRQ vectorを
共有し、active中の別clip開始を拒否する。

mainlineはcc65 raw-cart `open("1")`/`open("2")`と`read()`で選択clipをresident bufferへ
先読みする。`src/title_voice_stream.s`がTimer 3 IRQごとに1 nibbleを65SC02 assemblyで
IMA復号し、predictor high byteへAPS-038のcenter-preserving +25% saturating gainを
一度適用して、signed 8-bit DAC値としてchannel D `AUD3OUT`へ書く。
A/C=BGM、B=SFXには触れず、APS-036の75% hardware gainもchannel Dへ適用しない。
chunk境界は常にlow nibbleから始まる。

89 step × 8 magnitudeの`difference`は
`scripts/generate-title-voice-delta.py`でlow/high tableへ事前計算し、IRQ内の16-bit shift/addを
除去した。4 MHz/8 kHzの500 cycle/sample（3.6 MHz仮定450 cycle/sample）に対し、
common IRQ chain、Timer判定、table lookup、predictor clamp、index更新、DAC書込を含む
静的保守見積は約300〜410 cycles/sample。実機cycle counterの実測値ではないため、
Gearlynxで両clip全sampleの完走とproducer underrun flag 0を実動検査する。

APS-037最終LNXをGearlynx 1.2.21で各clip連続2回検査し、title 17,408 IRQ/17,408 DAC
sample、GAME OVER 11,691 IRQ/11,691 DAC sampleがそれぞれC89 reference decoderと完全一致。
両方とも`remaining=0 active=0 underrun=0`で停止した。titleは完了後channel A BGM開始、
GAME OVERはA/C/B停止とrelease→press入力gateを確認した。

APS-038では`AUD3VOL`ではなく復号後PCMへgainを置いた。Lynx Sound Overviewのdirect DAC
説明、cc65 V2.19の`AUD3VOL=$FD38`/`AUD3OUT=$FD3A`定義、Gearlynx main
`f0be31d2c33da1e9b5d4cb1fe93c34b6dc34af70`の独立したvolume/output registerと
output直接mix実装を照合すると、停止中のpolynomial generator用volume registerはCPUの
`AUD3OUT`直書きを増幅しない。256-entry tableはsigned magnitudeの`floor(5/4)`、符号復元、
`-128..127` clampを事前計算し、IRQ内はpredictor high byteによる一定時間lookupだけを追加する。
zero/silenceは`0x00`を保ち、両voice共有`decode_complete`で二重適用を避ける。

## タイトル状態機械

既存`title_start_armed`成立後の最初のFIREは`title_voice_pending=1`だけを設定する。同一描画の
残り3 logic updateと再生中の全FIREはpending guardで無視する。main adapterがstream開始・
cartridge refill・完了監視を行い、完了を一度だけ`game_title_voice_complete()`へ渡して
`game_start()`する。source/length失敗時は音声をskipして同じ完了APIへ進む。非タイトルphaseへ
移る全経路でstreamをstopし、Timer 3/channel D/queueをzero化する。GAME OVERは最終爆発
SFX完了後だけpendingとなり、画面表示後に同じstreamを一回再生する。完了前はA/Bを無視し、
完了後もrelease→pressが成立するまでタイトルへ戻さない。

## 未確認

- Atari Lynx実機のIRQ cycle、sample欠落、音質、Lynx I/IIの音量差
- Gearlynx GUIまたは実機スピーカーでの日本語の聴感・音量バランス
- VOICEVOX Nemo規約変更後に新たな公開物を作る場合の再確認

## APS-036による現行拡張

APS-036で同じstream implementationをGAME OVER clipと共有した。APS-037で両assetを
VOICEVOX Nemo男性2へ差し替え、runtime/rateは維持した。
cartridge directoryはresident executable + title entry 1 + GAME OVER entry 2の3 entryとなった。
GAME OVER clipは`assets/voice/game-over.*`、11,691 samples、5,846 bytes、SHA-256
`848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f`。両clipの
生成条件と配布制約は`assets/voice/README.md`を現行正本とする。
