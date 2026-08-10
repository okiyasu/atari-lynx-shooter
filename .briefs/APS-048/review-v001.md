# APS-048 / design-review-v001

- 課題: APS-047受入不合格の独立デザイン/runtime差異レビュー
- 作成: 2026-08-10 Asia/Tokyo
- 前版: なし
- 対象: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/`

## 最初に読むもの

`CLAUDE.md`、`ISSUES.md`、`docs/plan/design.md`のAPS-044〜047、次の正本と現行runtime証跡を読むこと。

- `assets/previews/aps044-player-preview.json` — A/B各16x16の1px preview正本
- `assets/previews/aps044-enemy-preview.json` — 通常敵9種・boss3種の16x16 preview正本
- `assets/stages/stages.json`、`scripts/generate-stage-data.py`、生成sprite dataとmapping
- `scripts/generate-aps044-player-preview.py`、`scripts/generate-aps044-character-sheets.py`
- `evidence/APS-045/`、`evidence/APS-047/`のROM実表示証跡

## 背景・受入失敗

ユーザー実見でROM内キャラクターがAPS-044 previewと異なり、旧来の横帯／簡略化gridに見える。APS-047の「既存12x10等canvasへの再authoring」は不採用。次番APSではA案自機、敵9種、boss3種を、preview生成元からROM投入元まで単一ソースで一対一に採用し直す。collision寸法はplayer 8x6、normal 8x8、boss既存寸法のまま厳守する。

## 依頼内容（レビューのみ）

ソースを編集せず、次を短く具体的に報告する。

1. preview JSONの各13 designと、現行ROMが参照するauthoring grid / packed run / type→sprite mapping / 描画経路との差分。canvas、非空cell、色、run、anchor、frameのどこでA案等が失われたかをファイル・関数・ID単位で特定する。
2. preview正本をROMに正確に採るcanonical設計案。16x16 previewをruntime visual canvasとして直接採る可否を判断し、別canvasへ変換するなら「一対一」を満たす根拠を明示する。2 frameでpreviewが単一frameの場合の正確性を壊さないframe方針を提案する。
3. player / 9 normal / 3 bossをユーザーが判別可能にするGearlynx実ROM captureの構成案。preview画像やhost描画は不可。必要なら実ROM内の受入専用showcase経路を提案するが、ゲームルール・collision・音声開始待機を変えない根拠を示す。
4. source hash、cell/run、type→sprite mapping、ROM sprite bytes、ROM hash、capture pixelを結ぶ最低限の契約テスト一覧。
5. 描画負荷への注意点。ユーザーは敵数で遅くなる実感を報告している。少数敵を待たせる補償は禁止で、敵数非依存75Hz VBL cadenceと16x16 artの性能リスクを分離して評価する。

## 禁止・完了条件

- 編集、生成物更新、コミット、push、stash/reset/checkout禁止。
- 実装は後続Devが直列に担当する。本レビューは設計判断と差異の事実のみ。
- `ISSUES.md`は更新しない（レビューのみ）。
- 報告に採用案、直接確認済みファイル/行・未確認事項、後続実装が満たすべき受入条件を含めること。
