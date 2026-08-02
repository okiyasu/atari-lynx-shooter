# ISSUES

最終更新: 2026-08-02

## 課題台帳

### APS-001: エミュレータ実行時の画面チラつき修正

- 状態: 修正・検証完了
- 優先度: 高
- 起票日: 2026-08-02
- 報告: Handy v0.9.11 と Gearlynx 1.2.21 の両方で、画面がチラついて内容を判別しづらい。
- 調査対象: `src/main.c` のTGI描画ループ、割り込み駆動ダブルバッファ、VBlank時の表示更新同期。
- 完了条件: 根拠となるコードを示して原因を特定し、安定表示となる修正を行う。`./scripts/verify.sh`でクリーンROMビルド・14件以上のロジックテスト・lint・LNXヘッダ検査をすべて通し、実行結果、設計との差分、目視確認項目を本項へ記録する。
- 制約: BIOSを取得・同梱しない。コミット・pushはユーザー承認後のみ。

#### 原因

- `src/main.c:79`の`tgi_updatedisplay()`は同期的な表示切替ではなく、cc65 2.19の`lynx-160-102-16.s:303-312`で`SWAPREQUEST`を立てて即座に戻る。
- 実際の表示ページ設定、描画ページの反転、要求解除は次のVBlank IRQ内（同`:488-502`）で行われる。修正前は次ループが完了を待たず`tgi_clear()`と再描画へ進むため、VBlankをまたいで描画先が切り替わり、表示対象ページの消去や未完成フレームの表示が起きていた。
- `lynx.sgml:199-224`も、このドライバが割り込み駆動ダブルバッファであり、前回swapの処理中判定に`tgi_busy()`を使う仕様だと説明している。描画プリミティブはドライバの`draw_sprite`（同ドライバ`:381-397`）で完了を待つため、今回の競合箇所は描画コマンド同士ではなくフレーム間のページswapだった。

#### 修正

- `src/main.c:97-98`で、次フレームの入力・`game_update()`・`tgi_clear()`より前に`tgi_busy()`が0になるまで待つようにした。
- 0が返るのはVBlank IRQが表示ページを前フレームの描画ページへ設定し、描画ページを反対側へ切り替えた後である。このため、次のclearと描画は表示中でないページだけに行われる。
- 同じ待機がゲームロジックも次のVBlankまで止めるため、無制限ループ速度で状態だけが進むことはなく、既存の75Hz設定、割り込み有効化、入力・ゲーム仕様は維持される。

#### APS-001検証実績

- `./scripts/verify.sh`: 成功。クリーン後にclangの`-std=c89 -pedantic -Wall -Wextra -Werror`、cc65の`-t lynx -Oirs --standard cc65 -W error`でビルド成功。`PASS: 14 game logic checks`、`sh -n scripts/*.sh`成功、`LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=7816 bytes`。
- `git diff --check`: 成功（出力なし）。
- ROM: `dist/asteroid-patrol.lnx`、7,816 bytes、SHA-256 `dc8042b6a23e941098fe43b036c22b1af27cb2f22fb71fbd86867d0bb485e7d3`。
- `git status --short`: 今回の実装対象は`src/main.c`と`ISSUES.md`。着手前から`ISSUES.md`のAPS-001起票差分と未追跡`.briefs/`が存在し、発行済み`.briefs/APS-001/v001.md`は変更していない。

#### APS-001設計差分

- 設計の「1フレームごとに入力、状態更新、描画、表示更新」は維持した。Lynx TGI固有の非同期swap完了待ちが設計書に明記されていなかったため、フレーム境界として明示的な`tgi_busy()`待機を追加した。ゲーム仕様・フレームレート・ツールチェーンの変更はない。

#### APS-001目視確認

- 環境確認: `/Applications/Handy.app` v0.9.11、`/Applications/Gearlynx.app` v1.2.21を確認。Handyは設定済みBIOSを使用し、両アプリへ再ビルドしたROMを`open -a`で渡した。BIOSの取得・探索・同梱は行っていない。
- Handy: `SCORE 00000`、自機、標的、HUD境界線を視認。1秒間隔の画面取得6回が同一SHA-256（`e9697fce4cdec5c127140367d4b38bfe35ca2a1edb9eb4647d837b3d6e389671`）となり、黒画面との点滅や途中描画はなかった。右入力の保持で自機が右へ移動することも確認した。
- Gearlynx: アプリを終了・再起動して修正ROMを新規ロードし、同じ表示内容を視認。1秒間隔の画面取得6回が同一SHA-256（`8544d0f2dd1f7ffa75a3f0a96eca52bc408f07c00dbc2e9fa9dbcdbc7d85a589`）となり、3秒の画面録画中にも激しいチラつきはなかった。方向入力で自機が移動し、A/B双方の射撃で命中、100点加算、標的再配置を確認した。
- 制約: Atari Lynx実機では未確認。画面取得は1秒間隔6回と3秒録画による確認であり、長時間連続プレイの耐久試験ではない。

## 実装状況

- [x] プロジェクト骨格と`docs/plan/`設計・調査文書
- [x] cc65安定版2.19（`V2.19`）の再現可能な取得・ローカル構築
- [x] TGI・ジョイスティックAPIを使うLynx向けゲーム実装
- [x] プラットフォーム非依存ロジックとmacOS clang自動テスト
- [x] 完全クリーンROMビルド、warnings-as-errors相当、LNXヘッダ検査
- [x] READMEのBIOS要件・最短手動確認手順・操作説明
- [x] HandyとGearlynxによる修正ROMの実画面確認、方向入力、GearlynxでのA/B射撃・命中確認

## 要件対応表

| 要件 | 対応 | 検証 |
|---|---|---|
| ROM起動形式 | `cl65 -t lynx`でLNXカートイメージ生成 | LNX magic/version/page size検査成功 |
| 160x102・16色 | cc65標準TGIドライバ、コード生成矩形・文字のみ | Lynx向けコンパイル・リンク成功 |
| 方向入力移動 | 標準ジョイスティックの上下左右をロジック入力へ変換 | clangテスト成功 |
| A/B発射 | `JOY_BTN_1_MASK`と`JOY_BTN_2_MASK`を同じ発射入力へ変換 | cc65コンパイル成功、発射ロジックテスト成功 |
| 連射制御 | 押下継続時8フレーム間隔、最大3発 | cooldown/repeatテスト成功 |
| 画面境界 | X両端、HUD下端、画面下端で自機をクランプ | 四辺テスト成功 |
| 敵・再出現 | 右側の8x8標的、命中後に決定的なY列へ再配置 | 再出現テスト成功 |
| AABB・得点 | 排他的端のAABB、命中時100点、HUDを再描画 | AABB端・命中・scoreテスト成功 |
| 外部素材なし | TGI図形・内蔵文字のみ | リポジトリ内容確認済み |
| BIOS非同梱 | BIOS/ROMを取得・生成せず、READMEに両エミュレータ要件記載 | リポジトリ内容確認済み |

## 検証実績

### ツールチェーン構築

- コマンド: `make toolchain`
- 結果: Gitタグ`V2.19`を`.cache/cc65-2.19/source`へ取得、完全コミット`555282497c3ecf8b313d87d5973093af19c35bd5`を照合し、`.cache/cc65-2.19/install`へビルド・インストール成功。
- 上流の表示: `cl65 V2.18 - Git 5552824`。タグ`V2.19`のソース自体がこの文字列を返すため、タグと完全コミットを正として固定している。

### 完全クリーン検証

- コマンド: `./scripts/verify.sh`
- ログ: `.cache/logs/verify.log`（Git管理外）
- 結果:
  - `rm -rf build dist`後に再構築成功。
  - clang: `-std=c89 -pedantic -Wall -Wextra -Werror`でビルド・構文検査成功。
  - ロジック: `PASS: 14 game logic checks`。
  - cc65: `-t lynx -Oirs --standard cc65 -W error`で2ソースの警告エラー化コンパイル成功。
  - link: `cl65 -t lynx`で成功。map上の標準ライブラリはローカルinstall配下を参照。
  - shell: `sh -n scripts/*.sh`成功。
  - header: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=7816 bytes`。

### ROM成果物

- パス: `dist/asteroid-patrol.lnx`
- サイズ: 7,816 bytes
- SHA-256: `dc8042b6a23e941098fe43b036c22b1af27cb2f22fb71fbd86867d0bb485e7d3`

### エミュレータ環境

- コマンド: `/Applications`、アプリの`Info.plist`、実行プロセス、ウィンドウ一覧を確認。
- 結果: Handy v0.9.11とGearlynx v1.2.21が導入・起動済み。HandyはBIOS設定済み。BIOSの取得・探索・同梱は行っていない。

## 設計との差分

- 現行cc65資料の`--warnings-as-errors`は固定版2.19で未実装のため、同版が提供する警告種別`-W error`を使用した。
- Lynx公式ヘッダが`//`コメントを含み厳格C89では解析不能なため、ROM側は`--standard cc65`を使用。共有ゲームロジックはclangの厳格C89で検査している。
- cc65タグ`V2.19`の実行時表示が`V2.18`のままであるため、表示上の版番号ではなくタグと完全コミットを検証する。
- Lynx TGIの非同期swap完了待ちをフレーム境界へ追加した。HandyとGearlynxで修正後の表示を確認済みで、実装機能の削減はない。

## 未確認事項・懸念点

- Atari Lynx実機での表示・入力応答・描画速度と、エミュレータでの長時間連続プレイは未確認。
- Handyでは方向入力まで、Gearlynxでは方向入力とA/B射撃・命中・得点・標的再配置まで確認した。
- `lynxboot.img`を含むBIOSは著作権対象のため、本作業では取得・同梱・生成していない。
