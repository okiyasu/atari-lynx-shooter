# Suzyスプライト移行 設計書 v2(RAM超過を受けた全面改訂)

- 作成: 2026-08-12 Fable5(設計担当)
- 旧版: `docs/plan/2026-08-11-suzy-sprite-migration.md`(v1)。**v1 §4のRAM見積もりは誤りと確定**。本書がPhase 2以降の正本。Phase 1(案C: logic catch-up)の設計・実装は有効のまま
- 対象プロジェクト: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/`
- 本書は dev-front への委譲ブリーフを兼ねる。現在dev-frontはPhase 2の未コミット差分を作業ツリーに保持して待機中(直近コミット `95a77a9` = Phase 1完了分)

---

## 1. v1見積もりが外れた原因の総括(再発防止のため全員が読むこと)

Phase 2実装の実測(リンク失敗時も出力される `build/asteroid-patrol.map` のSegment listから集計):

| Segment | Size |
|---|---:|
| CODE | 38,796 |
| RODATA | 7,436 |
| DATA | 308 |
| BSS | 1,270 |
| 合計(+STARTUP系152) | 47,962 |
| MAIN上限(`$B6B8`) | 46,776 |
| **超過** | **1,186** |

### 誤り1(最大): 「空き2.2KB」はC stack予約を空きに数えていた

v1は「BSS終端 `0xB791` 〜 TGIフレームバッファ `0xC038` の空き約2.2KB」としたが、この区間には **cc65のC stack予約 `__STACKSIZE__ = $0780`(1,920B、`$B8B8–$C037`)が丸ごと含まれる**。リンカー(`cfg/lynx-voice.cfg`)のMAINサイズは `$BE38 − __STACKSIZE__` であり、実際のPhase 1完了時点のMAIN余剰は **53バイト**(cadence版は15バイト)だった。空きを13倍過大評価していた。

### 誤り2: CODEコストの未計上

追加需要「2〜2.5KB」はスプライトデータしか数えていなかった。実測では:

- `static_layer_data.o`(データ): RODATA **1,800B**
- `static_layer.o`(SCB組み立て・HUD合成コード): CODE **3,172B**

コードがデータの1.76倍。cc65(C89、ローカル変数も静的領域)ではCコードの追加はほぼそのままRAM増になる。**LynxはカートをRAM 64KBへ全ロードするため、RODATAもCODEも「ROMだから無料」にはならない**。

### 誤り3: 回収時期の取り違え

「run列廃止で約1KB回収」はPhase 3(可動オブジェクト)の作業。Phase 2スコープで回収できたのは `main.c` の旧背景/HUD表+描画コードの約3,746Bのみで、追加4,973Bに届かず**純増+1,227B**となった。

### 誤り4: エスカレーション先の誤指定

v1 §4「不足時はGAMEVOICE/TITLEVOICE圧縮を検討」は**無効**。両音声はVOICEメモリ領域(`file=%O`、カート専用 `$0000/$4000`)にあり**RAMを1バイトも使っていない**。圧縮してもRAM問題は解決しない。この選択肢は削除する。

### 実装側の名誉のための付記

BSSの増分は実質**+1バイト**だった。実装は `title_voice_scratch_buffer[5][128]`(640B)をSCB置き場(21×23=483B)+HUDビットマップ(56B)に流用しており、RAM新設をゼロに抑えていた。超過の正体は「BSS膨張」ではなく「CODE+RODATAの純増」である。差し戻しv001〜v003で解けなかったのは実装の質の問題ではなく、**v1の会計モデル自体が破綻していたため**。

---

## 2. RAM会計の正モデル(以後この表を唯一の基準とする)

64KB RAMの実マップ(通常CFG、`cfg/lynx-voice.cfg`):

| 範囲 | サイズ | 用途 | 流用可否 |
|---|---:|---|---|
| `$0000–$01FF` | 512 | ZP + 6502 HWスタック | 不可 |
| `$0200–$B8B7` | 46,776 | **MAIN**(STARTUP+CODE+RODATA+DATA+BSS) | ここが戦場 |
| `$B8B8–$C037` | 1,920 | cc65 C stack予約 | 原則不可(§6) |
| `$C038–$E017` | 8,160 | TGI screen page 1 | 不可 |
| `$E018–$FFF7` | 8,160 | TGI screen page 0 | 不可 |

会計ルール:

1. **「空き」の定義はMAIN上限(46,776B)−全セグメント合計**。C stack領域・フレームバッファは空きに含めない
2. **コード追加の事前見積もりは「データの1.5〜2倍のCODE」を係数として計上する**(static_layer.oの実測1.76倍に基づく)
3. 各実装刻みで**リンク成立を必須**とし、mapのSegment list(リンク失敗時も出る)を証跡として提出する
4. Suzyコリジョンバッファ(`COLLBAS = $A058`)はMAIN内側に食い込む設定のため、**Suzy collisionは今後も絶対に有効化しない**(v1決定の維持+理由の明文化)

現状の勘定(Phase 2未コミット差分込み): **超過1,186B**(cadence版1,224B)。

---

## 3. 方針判断: 案Aは継続する(ただし進め方を全面改訂)

### 選択肢の再評価

| 選択肢 | 評価 | 判断 |
|---|---|---|
| 案Cのみで妥協(Suzy移行撤退) | ゲーム速度の正常化は済むがfpsは約5fpsのまま。75Hz目標(契約g)を放棄することになる。またPhase 2実装は「SCBチェーン+SPRGO 1回」の技術検証まで済んでおり、撤退で捨てる資産が大きい | 不採用(ただし§7の撤退基準に該当したら再浮上) |
| Suzy化の対象を絞る(背景のみ/HUDのみ) | RAM収支の観点では逆効果。**Phase 3(可動オブジェクト)こそ回収(sprite_data 1,463B+main.o描画コード)が大きく、部分止めは「追加だけして回収しない」v1の失敗の再演になる** | 不採用 |
| データ圧縮率の向上 | データは既に小さい(背景全レイヤで1,800B、大半1bpp)。絞っても数百Bで、主因(CODE 3,172B)に効かない | 主策にはしない |
| **CODE縮小+回収先行の再段階化で完遂** | 超過の主因(コード肥大)に直接効き、Phase 3完遂後の収支は黒字見込み | **採用** |

### 完遂後の収支見通し(概算、Phase 3の事前見積もりで確定させる)

- 回収: `sprite_data.o` 1,463B + `main.o` 可動描画コード(`draw_sprite`/`draw_mask`/`draw_clipped_hline`/`draw_environment`/`draw_phase_overlay`、main.o CODE 6,768Bの過半) + `tgi_outtextxy` 系のlynx.lib分(BSS 185B含む数百B)
- 追加: 可動用スプライトデータ(bpp最適化前提、§5)+ SCB置き場(短縮SCBで550〜1,150B)+ SCB更新コード(係数2で見積もる)

全面移行を**完遂すれば**RAMはむしろ改善する構造。問題は中間状態が成立しない段階割りだったので、そこを直す。

---

## 4. 緊急修理(Phase 2R-0): 性能バグの修正 — RAM問題と切り離して先行

Phase 2の cadence 悪化(敵0体 15→約100 VBlank)はRAM超過とは**独立のバグ**である。

- **`src/static_layer.c:44-45` の `hsize/vsize` 誤設定**: SuzyのHSIZE/VSIZEは8.8固定小数の**拡大率**(等倍=`0x0100`)。現実装はソース実寸(`width << 8`)を入れているため、例えば山レイヤ192×21を**192.0倍×21.0倍に拡大描画**している。1×1クリアスプライトの `160<<8`/`102<<8` だけが偶然正しい。等倍レイヤはすべて `0x0100` 固定に修正する
- **`penpal[4..7]` 未初期化**: `reset_scb` が4バイトしか書かない。scratch流用のためvoiceデータの残骸が残る。8バイト全て初期化する
- **voice scratchバッファ二重使用の契約明文化**: `title_voice_scratch_buffer` の先頭539BをSCB/HUDが使う設計は維持してよい(RAM節約として正当)が、「voice再生中に `static_layer_draw()` を呼ばない」を暗黙にせず、ヘッダコメント+デバッグビルドのアサートで明文化する

この修正はRAM中立(数十B程度)。**修正後の再計測をPhase 2の性能合否のベースラインとする**。修正なしにcadence 100 VBlankを「Suzy化の効果不足」と誤読してはいけない。

---

## 5. 改訂段階分割(各刻みでリンク成立+map実測をゲートにする)

v1のPhase 2/3/4を、**「回収と追加が同じ刻みに入る」よう再構成**する。各刻みの完了条件に「リンク成立」「mapのSegment list提出」「MAIN余剰の数値報告」を必ず含める。

### Phase 2R-1: リンク成立の回復(CODE縮小)

目標: 超過1,186B(cadence版1,224B)を解消し、**MAIN余剰 ≥ 256B** でリンク成立。

優先順位付きの縮小策(上から着手し、足りたら止める):

1. **`static_layer.o` CODE縮小(主策、目標▲1,200B)**: CODE 3,172Bのうち `build_hud`(グリフからパックド形式をランタイム合成)が支配的。合成ロジックをテーブル駆動化する、またはHUD文字を「1文字1SCB」方式(v1の元案、グリフデータを直接SCBのdataに向けるだけで合成不要)に変更してランタイム合成コード自体を消す。**どちらが小さいかは両案のCODE/データ増減を見積もってから選ぶ**(判断に迷ったらFable5へ)
2. **`tgi_outtextxy` 全廃(▲数百B、BSS 185B含む)**: HUDは既にSCB化済みで、残存はoverlay文字列のみ。これをPhase 2Rでglyph SCB描画に置換し、lynx.libの `tgi_vectorchar`+`text_bitmap`+フォントを落とす
3. ここまでで届かない場合は**着手を止めてFable5へ報告**(勝手に次の手段へ進まない。§6参照)

合否: (a) 通常・cadence両CFGでリンク成立、(b) map提出とMAIN余剰報告、(c) 既存ロジックテスト全PASS、(d) Phase 2R-0の修正を含むこと。

### Phase 2R-2: Phase 2の性能検収(v1 Phase 2の合否をここで判定)

- (a) 敵0体fixtureで **3 VBlank以下**(APS-051修理済みVBlankバッチ計測、独立2 batch)。敵0体には自機44run(旧TGI描画、約2 VBlank相当)が残存するため、未達の場合は**内訳(Suzyチェーン分と旧TGI残存分の分離計測)を添えて報告**し、Fable5が基準修正か追加対策かを判断する
- (b) 全3ステージ背景+HUDのpixel照合PASS(期待値再構築込み)
- (c) map実測提示(2R-1と同じ形式)

### Phase 3R: 可動オブジェクトのSuzy化(データ先行見積もりゲート付き)

**着手前ゲート(実装より先にやる)**:

1. `scripts/generate-stage-data.py` 側の4bpp/2bpp/1bpp変換だけ先行実装し、**全13スプライト・26フレームの実バイト数を確定**させる。bppはスプライトごとに実際の使用色数で最小化する(全部を4bppにしない)
2. SCBフォーマットの短縮設計: スケール1x固定(APS-050)なので、SPRCTL1の再ロード指定を落とせばHSIZE/VSIZEフィールド(4B)を省略でき、パレットを共有するスプライト間ではpenpal(8B)も省略できる。フル23B/個ではなく**11〜19B/個**を狙う。可動SCB置き場(約50個)の配置先(BSS新設か、既存バッファ流用か)を決める
3. 上記から**収支表(追加: データ+SCB置き場+コード係数2 / 回収: sprite_data.o 1,463B+main.o該当コード実測)を作成し、Fable5の承認を得てから実装に入る**

合否: (a) boss+敵4体+弾フルfixtureで **2 VBlank以下**、(b) 全13スプライト・26フレームpixel照合PASS、(c) アニメ・ペン色の目視証跡、(d) map実測でMAIN余剰 ≥ 512B(Phase 4の掃除でさらに増える見込みの確認)。

### Phase 4R: 掃除と契約gの引き締め(v1 Phase 4と同じ)

- 旧TGI run描画コード・run列データの完全削除、`tgi_bar`/`tgi_line` 依存の根絶(`tgi_updatedisplay`/`tgi_busy` のダブルバッファ同期のみ残す)
- (a) 全fixtureで display_request間隔 ≤ 1 VBlank を契約gに固定、(b) `make verify` 全PASS、(c) Gearlynx実プレイ確認、(d) 最終map提出

---

## 6. 最終手段の序列(勝手に実行しない)

Phase 2R-1の縮小策で届かない場合、以下の順でエスカレーションする。**いずれもdev-front/devの自己判断では実行しない**:

1. **C stack縮小(ユーザー判断)**: 実測high-water 312Bに対し予約1,920B(未使用約1.6KB)。v003で「成功条件にしない」と確定した経緯(v002での縮小が差し戻し要因)があるため封印中だが、他の全手段が尽きた場合の最終カードとしてのみユーザーへ提案する。提案時はhigh-water再計測値と安全マージン案(例: 予約1,024B=▲896B)を添える
2. **背景データのステージ単位カートロード**: 背景1,800Bのうちステージ固有分(sky系761B / cave系903B / space系8B)をカート側セグメントに移し、ステージ開始時に最大ステージ分のRAMバッファ(約900B)へロードする(常駐1,800B→約1,000B、▲800B)。VOICE領域のストリーミング機構と同系の仕組みだがロードコード追加が必要で複雑さが上がるため、C stack縮小より優先度は下
3. ~~音声圧縮~~ — **削除**(§1誤り4: VOICEはRAM外、効果ゼロ)

### 撤退基準

Phase 2R-1で縮小策1・2を実施してもリンク不成立、かつ最終手段1・2をユーザーが承認しない場合は、**案C(Phase 1)+Phase 2R-0の性能バグ修正のみで一旦確定**し、Suzy移行差分を退避ブランチに保全して停止する。判断はRyoko経由でユーザーに諮る。

---

## 7. dev-front委譲ブリーフ(転記用)

- 対象: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/`(作業ツリーのPhase 2未コミット差分を保持したまま継続)
- 正本設計書: 本書(`docs/plan/2026-08-12-suzy-sprite-migration-v2.md`)。v1の§4 RAM見積もりは無効
- 委譲単位: **Phase 2R-0+2R-1をまとめて1委譲**(2R-0はRAM中立の修理なので分けるとリンク不能状態で検証できない)。次いで2R-2、3R(着手前ゲートあり)、4R
- 判断済み事項(v1から維持): 案B不採用 / 全スプライト1x固定 / Suzyコリジョン不使用(理由が「COLLBAS=$A058がMAIN破壊」と明確化された) / ROM生成のたび `include/version.h` の `GAME_VERSION_STRING` 更新 / コミット・pushはユーザー明示承認後のみ / Phase順序は2R→3R→4R固定
- 報告様式: 各刻みで mapのSegment list(CODE/RODATA/DATA/BSSサイズとMAIN余剰)を数値で提示。「入ったはず」報告は不可。**リンク失敗時もSegment listは出力される**ので、失敗報告にも必ず添付する
- エスカレーション条件: (1) 縮小策1・2で届かない、(2) Phase 2R-2の3 VBlank未達、(3) Phase 3R着手前ゲートの収支表が赤字 — いずれもFable5(設計)へ。C stack・カートロードの最終手段は必ずユーザー判断

---

## 8. 参考: 今回の実測データの所在

- リンカー設定: `cfg/lynx-voice.cfg` / `cfg/lynx-voice-cadence.cfg`(`__STACKSIZE__` = `$0780` / `$0630`)
- map: `build/asteroid-patrol.map`(リンク失敗時もSegment listまで出力される)
- モジュール別MAIN消費上位: game.o 16,750 / main.o 7,528 / lynx.lib 6,831 / sound.o 3,521 / title_voice_stream.o 3,240 / **static_layer.o 3,173** / **static_layer_data.o 1,800** / sprite_data.o 1,463 / title_voice.o 1,398
- 背景データ内訳(計1,800B): mountain 189 / mid_cloud 270 / near_cloud 205 / cave_wall 264 / cave_rock 340 / cave_near 299 / planet 97 / glyph 90 / その他座標表等
- cadence実測(Phase 2現状): 敵0体 101.0/100.5 VBlank(Phase 1比7倍悪化 — §4のhsize/vsizeバグが最有力原因)、BOSS+4 BOSS 117.5/117.0
- TGIドライバのフレームバッファ/ブロッキング実装: `.cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s`(page0 `$E018` / page1 `$C038` / `COLLBAS $A058` / `draw_sprite` はSPRGO後にSuzy完了までブロック)
