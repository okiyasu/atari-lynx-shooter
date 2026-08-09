# APS-031 短音声再生の実現性

確認日: 2026-08-08

## 結論

MIKEYには4本の8-bit DAC出力があるが、ADPCM専用デコーダ、サンプルDMA、
ADPCMブロック状態を持つレジスタはない。実現可能な経路は、CPUがsigned
8-bit PCMを音声channelの`OUT`へ一定周期で書く方式である。cc65 2.19の
レジスタ定義、FurnaceのLynx PCM実装、lynxcc HandyMusicの8 kHz実機向け
Timer 3 IRQ実装が同じ方式を示す。

本作では、短音声を0.75秒以下へ編集できるなら **8 kHz・mono・signed
8-bit PCM** を第一候補とする。復号が不要で、タイトル専用再生の失敗面が
最小だからである。0.75秒を超える実音声しか成立しない場合は、4-bit IMA
ADPCMを第二候補とする。ただしC版codecの正しさとcc65ビルドは確認しても、
8 kHz IRQ内の実時間復号は未検証である。採用前に65SC02向け復号器または
小さいリングバッファ方式を追加し、Gearlynxと実機で欠落のないことを測る。

## 根拠

- [AtariAgeのLynx Developer Documentation索引](https://atariage.com/Lynx/archives/developer_docs/index.html?SystemID=LYNX)は、当時の`Handevelop Hardware & Programming Description`、`Handy Appendix 2 Hardware Addresses`、`Lynx Sound Overview`を原資料として公開する。
- [cc65 V2.19 `_mikey.h`](https://github.com/cc65/cc65/blob/V2.19/include/_mikey.h)は各channelを`volume, feedback, dac, shiftlo, reload, control, count, other`の8レジスタとして定義し、A〜Dを`0xFD20`〜`0xFD3F`へ配置する。[同版`lynx.inc`](https://github.com/cc65/cc65/blob/V2.19/asminc/lynx.inc)も`AUD0OUT`〜`AUD3OUT`を定義するが、ADPCMデコーダに相当するレジスタはない。
- [cc65 V2.19 `lynx-snd.s`](https://github.com/cc65/cc65/blob/V2.19/libsrc/lynx/lynx-snd.s)はTimer 7の240 Hz IRQで4channelの音量・周波数・波形を更新するシーケンサであり、PCM/ADPCMデコーダではない。
- [Furnace `lynx.cpp`（`efd85a2`固定）](https://github.com/tildearrow/furnace/blob/efd85a297542e66b085d6eafde30244dcfa6668a/src/engine/platform/lynx.cpp#L126-L150)はLynx PCM sampleをsoftwareで進め、signed 8-bit sampleを`0x22 + channel * 8`へ書く。Lynx側にADPCM展開を委ねていない。
- [lynxcc HandyMusic（`e63e91e`固定）](https://github.com/atarigamer/lynxcc/blob/e63e91eb7fdd0433b2a9856b30edfe6d1c82a0cb/libraries/audio/handymusic/handymusic.s#L337-L404)はTimer 3を125 us周期に設定し、RAM上の8 kHz signed 8-bit PCMを1 byteずつ`AUD0OUT`へ送る。[公開API文書](https://github.com/atarigamer/lynxcc/blob/e63e91eb7fdd0433b2a9856b30edfe6d1c82a0cb/doc/handymusic.html#L183-L201)も同じ排他・完了規則を示す。
- [RFC 3551 section 4.5.1](https://www.rfc-editor.org/rfc/rfc3551.html#section-4.5.1)はIMA ADPCMを4 bit/sampleとし、IMA形式のbyte内順序が先行sample=low nibbleであること、予測値とstep indexを状態として持つことを示す。本プロトタイプもこのnibble順を使う。

以上から「ADPCM hardware decoderなし」は、公開レジスタに無いこと、標準driverに
無いこと、動作実績のある2実装がどちらもCPUから`OUT`へPCMを書いていることの
三点で判定した。

## 方式比較

共通条件は8 kHz、mono、1秒である。

| 方式 | 音声データ | 状態/header | 8 kHz出力時の処理 | 判定 |
|---|---:|---:|---|---|
| signed 8-bit PCM | 8,000 bytes | 0 | 1 sampleにつき1 byte読込+`AUDxOUT`書込 | 第一候補。短さがRAM上限内なら最小リスク |
| 4-bit IMA ADPCM | 4,000 bytes | clipまたはblockごとにpredictor 2 bytes + index 1 byte（保存形式ではreserved 1 byteを推奨） | nibble展開、step table、予測値/index更新、8-bit量子化、`AUDxOUT`書込 | 第二候補。ROM/RAM半減、実時間復号の追加検証が必要 |

容量目安:

| 長さ | PCM 8 kHz/8-bit | IMA ADPCM 8 kHz/4-bit（header除く） |
|---:|---:|---:|
| 0.75秒 | 6,000 bytes | 3,000 bytes |
| 1.00秒 | 8,000 bytes | 4,000 bytes |
| 1.20秒 | 9,600 bytes | 4,800 bytes |
| 1.50秒 | 12,000 bytes | 6,000 bytes |

現行cc65標準Lynx targetはコード・RODATA・DATA・BSSを同じ`MAIN` RAMへ置く。
APS-031プロトタイプ後のBSS終端は`0x9FC1`、C stack開始は`0xB838`で、追加の
resident data余地は6,262 bytesである。このため8 kHz PCMは実質0.75秒が上限で、
1秒のresident PCMは入らない。IMA ADPCMなら1.2秒4,800 bytesが入るが、
リアルタイム復号器のコード/バッファ余地も残す必要がある。カートからの逐次読込は
現行単一resident file構成を変えるため、本課題の最小案から除外する。

4 MHzなら8 kHz出力の理論予算は500 CPU cycle/sample、実効3.6 MHzを置くと
450 cycle/sampleである。今回のPCM IRQはcc65共通IRQ chainとchannel D書込を含む
静的見積りで約130〜180 cycle/sample（約26〜40%）であり、タイトル静止中だけなら
成立余地がある。この値は実機計測ではない。C版IMA decoderは32-bit中間演算を含み、
cc65生成コードの実時間上限をまだ測っていないため、8 kHz再生可能とは判定しない。

## 最小プロトタイプ

- `src/ima_adpcm.c`: 動的確保・浮動小数なしのC89 IMA ADPCM encoder/decoder。
  16-bit予測値、89段step table、index clamp、IMA形式のlow-nibble-first unpack、
  MIKEY向けsigned 8-bit DAC byte変換を持つ。
- `tests/test_ima_adpcm.c`: 既知nibble列、上下clamp、DAC端点、決定的な非発話
  triangle波512 sampleのencoder/decoder状態一致と誤差上限を検証する。
- `src/pcm_stream.s`: cc65 interruptorとしてTimer 3を8 kHzで動かし、resident
  signed 8-bit PCMを未使用channel D `AUD3OUT`へ送る。停止時はTimer 3、channel D
  control、DAC出力を0へ戻す。A/C/B、Timer 0/2/7、TGI、ゲーム状態には触れない。
- 実音声、TTS、外部音声、テストblipは同梱しない。game flowからもdriverを呼ばない。
  したがって通常ROMの画面・入力・300 Hz logic・BGM 4倍・SFX 75 Hzは不変である。

## 将来のタイトル統合

1. タイトルの既存`title_start_armed`が成立した後の最初のA/B edgeだけを受理し、
   `title_voice_pending=1`としてPCMを開始する。受理した入力は`game_start()`へ渡さない。
2. `title_voice_pending`中のA/B edgeは全て無視する。画面描画と75 Hz入力取得は続け、
   300 Hz game logicへは入らない。タイトル中なのでA/C/Bは元から停止状態である。
3. `pcm_stream_is_playing()==0`を75 Hz側で初めて観測した一回だけ`game_start()`し、
   channel D/Timer 3を明示停止して既存A/C/B BGM/SFX初期化へ渡す。
4. GAME OVER/ALL CLEAR/初期化経路でも`pcm_stream_stop()`を呼び、ゲーム中にPCM経路を
   完全停止する。source不正・length 0なら音声をskipして同じ一回だけ開始する。
5. 実音声採用時は0.75秒以下の8 kHz signed 8-bit PCMを先に試聴する。長さまたは品質で
   不成立なら、IMA ADPCMリアルタイム復号のcycle計測とring buffer境界テストを別課題で
   合格させてから切り替える。

## 未確認

- Atari Lynx実機のTimer 3 IRQ負荷、音質、channel D direct DAC、Lynx I/II音量差。
- Gearlynx GUI/実機での8 kHz PCM聴感とsample欠落。音声asset未同梱のため今回未実行。
- C版IMA ADPCM decoderのcc65 cycle/sampleと、IRQ/ring buffer統合後の8 kHz連続性。
- 実在「ゲームスタート」音源の長さ・権利・話者・生成/収録方法。ユーザー選択待ち。
