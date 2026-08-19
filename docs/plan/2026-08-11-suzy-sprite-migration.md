# Suzyスプライト移行による描画高速化 設計書(APS-051後続)

> **[2026-08-12 改訂告知]** 本書§4のRAM見積もり(空き約2.2KB)は誤りと確定した(実際の空きは53B — C stack予約1,920Bを空きに誤算入)。Phase 2以降の正本は `docs/plan/2026-08-12-suzy-sprite-migration-v2.md`。Phase 1(logic catch-up)の設計のみ本書が引き続き有効。

- 作成: 2026-08-11 Fable5(設計担当)
- 対象プロジェクト: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/`
- 前提: APS-051でcadence測定を修理済み。合否判定はすべて修理後の測定(VBlankバッチ計測)を唯一のモノサシとする
- 本書は dev-front への委譲ブリーフを兼ねる。実装は Phase 単位で委譲し、Phase ごとに独立検収する

---

## 1. 背景と実測(なぜロジック見直しが必要か)

APS-051修理後の実測(TITLE校正シーンでのVBlankバッチ計測、独立2 batchで再現確認済み):

| fixture | 描画1フレームのVBlank数 | 増分 |
|---|---|---|
| 敵0体 | 14〜15(≈190ms) | ベースライン |
| 敵4体 | 23〜24 | +9 VBlank |
| 敵8体 | 33 | +9 VBlank |
| boss+敵4体 | 29〜35 | +6〜11 VBlank |

逆算した単価:

- 敵1体 ≈ 2.25 VBlank(30ms)。敵はスプライトrun 21〜44本/体なので、**TGI呼び出し(`draw_clipped_hline`→`tgi_setcolor`+`tgi_bar`)1回 ≈ 0.6〜1ms**
- 敵0体の固定費14 VBlankの内訳(概算): HUD `draw_tiny_text` 20文字×平均10ドット(1ドット=1 `tgi_bar`、`src/main.c:840-860`)≈200回、背景(惑星32run+星17個、`src/main.c:543-587`)≈50回、自機44run、`tgi_clear`。計≈300回×0.6ms ≈ 180ms — 実測と整合
- **敵数依存も固定費も犯人は同一: 「run/ドット1本ごとにTGIを呼ぶ」描画方式そのもの**

必要削減率: 75Hz(1 VBlank)に約15〜30倍。予算13.3msをTGI単価0.6msで割ると1フレームに許されるTGI呼び出しは十数回。**呼び出し回数の削減(HUDキャッシュ・run統合・差分描画)では2〜4倍が限界で原理的に届かない**ため、描画アーキテクチャの転換を行う。

### 検討した3案と判断

| 案 | 内容 | 期待効果 | コスト | 判断 |
|---|---|---|---|---|
| C: フレームレート適応 | 経過VBlank数に応じてlogic updatesをcatch-up | fpsは不変だがゲーム速度が実時間に一致 | 小 | **採用(Phase 1)** |
| A: Suzyスプライト全面移行 | run単位tgi_barを廃止、SCBチェーン+SPRGO一括描画 | 15〜30倍級、75Hz達成が現実的 | 大 | **採用(Phase 2〜4)** |
| B: TGI呼び出し削減 | HUD文字キャッシュ・run統合・差分描画 | 2〜4倍止まり | 中 | **不採用**(目標未達+成果物が案Aで捨てられる) |

---

## 2. 設計 — Phase 1: フレームレート適応(応急・恒久安全網)

### 現状の問題

`src/main.c:1199-1211` のメインループはlogicを描画フレームあたり固定4回実行する(`include/game.h:50-51` の `GAME_LOGIC_UPDATES_NUMERATOR 4 / DENOMINATOR 1`、`src/game.c:1474 game_logic_updates_for_draw_frame`)。wall-clockのcatch-upがないため、描画が13.3msを超えた分だけゲーム全体がスローになる。

### 変更内容

- `game_logic_updates_for_draw_frame` を「前回描画からの経過VBlank数」を入力に取る形へ拡張し、logic updates = 経過VBlank × 4(remainder方式は維持)
- 経過VBlankの取得手段はDev側で実装調査する: Timer2 VBlank IRQへのフック、またはMIKEYタイマーカウンタ読み出し。**TGIおよび `src/pcm_stream.s` / title voice のIRQ利用と干渉しないこと**
- 暴走防止の上限クリップを入れる(例: 1描画あたり40 updates)。超過分は切り捨てる(スパイラル防止)
- 当たり判定はlogic 1回ずつ進めて判定するため、catch-upによるトンネリングは発生しない

### 効果と位置づけ

fpsが低い間もゲーム内時間が実時間どおり進み、「敵が増えると遅くなる」体感を即解消する。Phase 2〜4完了後も負荷スパイク時の保険として恒久的に残す。

---

## 3. 設計 — Phase 2〜4: Suzy SCB直接描画への移行

Lynxの設計思想どおり描画をSuzyハードに任せ、CPUは毎フレームSCB(Sprite Control Block)の座標・データポインタ更新のみ行う。

### データパイプライン(`scripts/generate-stage-data.py`)

- preview grid → **Suzyネイティブ4bppスプライトデータ(packed/RLE)** を生成する。現行のrun列(2byte/run×480)は最終的に廃止
- frame1は現行のdelta方式(frame0上への重ね描き)をやめ、**完全な第2フレーム**を持たせる(Suzyは1発描画が前提。データ増は数百B)
- anchorはSCBのX/Yオフセットへ焼き込み。スケールは全スプライト1x固定(APS-050確定)なのでHSIZE/VSIZE=0x100固定

### ランタイム(`src/main.c` 描画層の置き換え)

- 敵8+boss+自機+弾12+敵弾16+アイテム+爆発+背景レイヤ+HUD文字 ≈ **70個前後のSCBを静的確保し、1本のチェーンにしてSPRGO 1回**で描画。非表示オブジェクトはSPRCTL1のSKIPビットで飛ばす
- **`tgi_clear`廃止**: 背景色は1×1画素をHSIZE/VSIZEで160×102へ拡大する塗りつぶしスプライト1枚に置換
- **背景レイヤ(惑星・山・雲・洞窟・星)**: 各レイヤをスクロール周期ぶん事前レンダした静的スプライトにし、X座標更新+2枚並べでラップスクロール(`draw_planet` / `draw_sky_background` / `draw_cave_background` / `draw_background` を置換)
- **HUD(`draw_tiny_text`)**: 3×5グリフを4bppスプライト化(8B/字)し1文字1SCB。「1ドット1 tgi_bar×約200回」を消す — 敵0体14 VBlankの最大の固定費削減
- **衝突は既存ロジックAABBを維持**し、SuzyコリジョンはSPRCOLLビットで無効化(collision buffer不要、RAM節約)
- `tgi_updatedisplay` / `tgi_busy` によるダブルバッファ同期は維持。Suzyの描画先を裏バッファへ向ける(TGI内部のスワップ状態との整合はDev実装課題。フレームバッファは0xC038系の既知アドレス)

### 期待効果の概算

総描画画素 ≈ 背景全画面16,320 + スプライト約4,000画素/フレーム。Suzyのblit速度なら数ms、SCB約70個のfetchオーバーヘッド込みで**13.3ms(1 VBlank)内に収まる見込みが高い**。CPU側はSCB更新のみで数千サイクル未満。

---

## 4. RAM制約(全Phase共通・最重要の注意喚起)

LynxはカートをRAM 64KBへ全ロードする方式。`build/asteroid-patrol.map` 実測(v0.50時点)で:

- BSS終端 `0xB791`、TGIフレームバッファ `0xC038` までの**空きは約2.2KB**
- 追加需要の概算: 4bppスプライトデータ+SCB群で2〜2.5KB
- 回収見込み: run列廃止で約1KB(RODATA)+旧run描画コード削除でCODE縮小

**成立見込みはあるが余裕はない。各Phaseの検収時に `build/asteroid-patrol.map` でBSS/RODATA/CODEの実測値を提示すること**(「入ったはず」報告は不可)。不足した場合は GAMEVOICE(5.8KB)/ TITLEVOICE(8.7KB)の圧縮を検討事項としてRyoko/Fable5へエスカレーションする(勝手に音声を削らない)。

---

## 5. Phase分割と合否基準(dev-front委譲単位)

各Phaseは独立に委譲・検収する。**合否判定はすべてAPS-051修理済みのVBlankバッチ計測**(独立2 batch以上で再現確認)による。

| Phase | 内容 | 合否基準 |
|---|---|---|
| **1** | フレームレート適応(logic catch-up) | (a) 敵4体fixtureで描画フレームが遅延してもゲーム内時間が実時間±5%以内で進行(logic update総数/実経過VBlankで検証)。(b) 既存ロジックテスト全PASS。(c) 上限クリップ動作のテスト追加 |
| **2** | 背景+HUD+`tgi_clear`のSuzy化 | (a) 敵0体fixtureで **14〜15 VBlank → 3 VBlank以下**。(b) 全3ステージ背景+HUDのpixel照合PASS(期待値生成の再構築込み)。(c) mapでRAM実測提示 |
| **3** | 敵・自機・boss・弾・アイテム・爆発のSuzy化(データパイプライン込み) | (a) boss+敵4体+弾フルfixtureで **2 VBlank以下**。(b) 全13スプライト・26フレームのpixel照合PASS。(c) アニメ(frame0/1)・ペン色の目視確認証跡。(d) mapでRAM実測提示 |
| **4** | 旧TGI run描画コードとrun列データの削除、契約gの引き締め | (a) 全fixture(敵0/4/8・boss+4)で **display_request間隔 ≤ 1 VBlank** を契約gの合否条件に固定。(b) `make verify` 全PASS。(c) 最終ROMのGearlynx実プレイ確認(敵4体戦闘で体感速度低下なし) |

### 委譲時の制約・判断済み事項(ブリーフへ転記すること)

- 案B(TGI呼び出し削減・差分描画)は不採用と確定済み。中間成果として実装しない
- スプライトは全て1x固定(APS-050)。boss 2xへ戻さない
- Suzyハード衝突は使わない(ロジックAABB維持)
- ROMを作成するたびに `include/version.h` の `GAME_VERSION_STRING` を必ず更新する(ユーザー恒久指示)
- コミット・pushはユーザーの明示承認後のみ
- Phase順序は 1→2→3→4 固定。Phase 2(静的スプライト)を可動オブジェクトより先に行い、Suzy化の技術検証を低リスクで済ませる

### 未確定事項(実装中に判断が必要になったらエスカレーション)

- 経過VBlankカウントの実装手段(Timer2 IRQフック vs タイマー読み出し)— Phase 1でDevが調査・提案
- TGI裏バッファアドレスの取得方法(TGI内部状態との整合)— Phase 2でDevが調査・提案
- RAM不足時の音声データ圧縮方針 — 発生時にユーザー判断

---

## 6. 参考(調査の経緯)

- 旧cadence測定(APS-049契約g)が速度低下を拾えなかった原因: (1) `US_PER_TICK` 較正が「display_request間=1フレーム」の誤仮定(実測はVBlank比2.9995、`evidence/APS-049/cadence-tick-calibration.json`)、(2) `debug_step_frame({frames:75})` が実際は1〜2 VBlank分しかCPUを進めていなかった(delta_ticksがVBlank間隔の1×/2×に量子化)、(3) 6502 total_ticksはSuzy blit中のバス停止時間を含まない
- ホスト側 `tests/perf_bench.c` は描画を含まずApple Siliconネイティブ実行のため、本件の検証には使えない(ロジック回帰専用として存続)
