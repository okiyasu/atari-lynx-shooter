# APS-017 Gearlynx GUI 証跡

- 実行日時: 2026-08-04T22:25:54+09:00
- Gearlynx: 1.2.21
- 実行コマンド: `/Applications/Gearlynx.app/Contents/MacOS/gearlynx /Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`
- ROM: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`
- ROMサイズ: 36,037 bytes
- ROM SHA-256: `aa83ce74322a766e56cfea18083afc39a274a977d7d1a216fa8dca4d45c57491`

起動前にGearlynxの既存プロセスを終了し、上記絶対パスを引数として渡した新規GUIウィンドウで撮影した。BIOS、外部ROM、外部素材は証跡に含めない。

## 操作手順

1. 上記コマンドでROMをGearlynx GUIへ渡す。
2. 起動直後にA/Bを押さず、タイトルを確認する。
3. A/Bをいったん離した状態から、Gearlynxの現行Input設定でA/Bに割り当てられたキーを短く押す。撮影時は`z`を100ms注入した。

## 画像

- `title-boot.png`: 起動直後。`ASTEROID PATROL`、`A/B TO START`、移動・射撃案内が160x102画面内で判読できる。
- `stage1-after-a-or-b.png`: 上記の新規A/B入力後。`STAGE 1`導入とLives 3が表示され、Stage 1 `GAME_PHASE_STAGE_INTRO`への遷移を確認できる。
