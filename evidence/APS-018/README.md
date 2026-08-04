# APS-018 GUI証跡

最終ROMは`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`です。

- サイズ: 36,933 bytes
- SHA-256: `2fb2ac6f4b16173e29eb01e7fef972c1b44dec973f9581d115cddc0292c0d8e0`
- GUI: Gearlynx 1.2.21
- 使用ROM起動: `open -na /Applications/Gearlynx.app --args /Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`

## 再現手順

1. `make clean && ./scripts/verify.sh`を完了し、上記SHA-256を確認する。
2. 以前のGearlynxプロセスを終了してから、上記の絶対パスを引数に新規GUIウィンドウで起動する。既存のBIOS設定だけを使用し、BIOSその他の外部ファイルは取得・読取・複製しない。
3. 起動直後のタイトルを`title-boot.png`に記録する。
4. A/Bに割り当てた`z`を一度離した後に押して、導入時の最上部HUD（`S1 I....`）と背景を`stage1-intro.png`に記録する。
5. 通常戦闘へ進め、`z`を短く押して、最上部HUD帯・下端線、背景星、通常敵、自機弾、高コントラストの短横ラン+下端ドットの敵弾を同じGUIウィンドウで`stage1-hud-combat.png`に記録する。

## 目視結果

- `title-boot.png`: `ASTEROID PATROL`と開始/操作案内を表示。
- `stage1-intro.png`: 導入の進行を中央の大文字ではなく、HUD一行の`S1 I....`へ統合し、HUD帯とプレイ領域の境界線を表示。
- `stage1-hud-combat.png`: `S1 N....`のHUD、HUD下の敵、自機弾、低コントラスト背景星、高コントラストで別形状の敵弾を目視確認。
