# ISSUES

最終更新: 2026-08-02

## 実装状況

- [x] プロジェクト骨格と`docs/plan/`設計・調査文書
- [x] cc65安定版2.19（`V2.19`）の再現可能な取得・ローカル構築
- [x] TGI・ジョイスティックAPIを使うLynx向けゲーム実装
- [x] プラットフォーム非依存ロジックとmacOS clang自動テスト
- [x] 完全クリーンROMビルド、warnings-as-errors相当、LNXヘッダ検査
- [x] READMEのBIOS要件・最短手動確認手順・操作説明
- [ ] GearlynxまたはMednafenによる実画面・実入力確認（ローカル未導入）

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
  - header: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=7797 bytes`。

### ROM成果物

- パス: `dist/asteroid-patrol.lnx`
- サイズ: 7,797 bytes
- SHA-256: `9c3943e4f4253b75bd4a6fd60f7c25b4a72eee5d37fd12cdc424edba08b18499`

### エミュレータ環境

- コマンド: `command -v gearlynx; command -v mednafen`および`/Applications`確認。
- 結果: Gearlynx、Mednafenともに未導入。BIOSの取得や探索は行っていない。

## 設計との差分

- 現行cc65資料の`--warnings-as-errors`は固定版2.19で未実装のため、同版が提供する警告種別`-W error`を使用した。
- Lynx公式ヘッダが`//`コメントを含み厳格C89では解析不能なため、ROM側は`--standard cc65`を使用。共有ゲームロジックはclangの厳格C89で検査している。
- cc65タグ`V2.19`の実行時表示が`V2.18`のままであるため、表示上の版番号ではなくタグと完全コミットを検証する。
- エミュレータが未導入であり、BIOSを取得しない制約もあるため、画面確認は設計上の手動工程として残した。実装機能の削減はない。

## 未確認事項・懸念点

- Gearlynx 1.2.21またはMednafen 1.32.1上でのROM起動、色、文字配置、入力応答、描画速度は未確認。
- 最短確認は、合法的に所有するBIOSをGearlynxへ設定し、`dist/asteroid-patrol.lnx`を開いて方向入力とA/Bを試すこと。代替のMednafenは512バイトの`lynxboot.img`をユーザー自身でベースディレクトリへ配置して`mednafen dist/asteroid-patrol.lnx`を実行する。
- `lynxboot.img`を含むBIOSは著作権対象のため、本作業では取得・同梱・生成していない。
