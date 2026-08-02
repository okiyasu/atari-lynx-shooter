# Asteroid Patrol

cc65公式Lynxターゲット向けの小さな2Dシューティングです。外部画像・音声素材は使わず、160x102・16色のTGI画面にコード生成の矩形と文字だけを描きます。

## ビルドとテスト

macOSでXcode Command Line Tools、Git、Makeが利用できる状態で実行します。

```sh
make toolchain  # cc65 2.19を.cacheへ取得・検証・ローカルビルド
make verify     # clean、clangテスト、lint、ROMビルド、LNXヘッダ検査
./scripts/verify.sh  # make verifyの実出力を.cache/logs/verify.logにも保存
```

ROMは`dist/asteroid-patrol.lnx`に生成されます。`.cache/`、`build/`、`dist/`はGit管理外です。ツールチェーンスクリプトは`V2.19`の固定コミットを検査し、`cl65 -t lynx`でROMを作ります。

## 操作

- 方向パッド: 自機移動（HUDより下の画面内に制限）
- AまたはB: 弾発射（押し続けると8フレーム間隔で連射）
- 赤い標的へ命中: 100点加算、標的が別の高さへ再出現

## macOSでの手動確認

第一候補はGearlynx 1.2.21です。`brew install --cask drhelius/geardome/gearlynx`または公式配布物を利用し、合法的に所有するBIOSをGearlynxの設定から指定して、生成ROMを開きます。GearlynxはBIOS必須で、公式READMEはMD5 `fcd403db69f54290b51035d82f835e7b`のオリジナルBIOSを推奨しています。キーボード割当はGearlynxのInput設定で方向・A・Bを確認してください。

代替はMednafen 1.32.1です。`brew install mednafen`後、合法的に所有する512バイトのLynx boot ROMを**ユーザー自身で**Mednafenベースディレクトリへ`lynxboot.img`として配置し、次を実行します。

```sh
mednafen dist/asteroid-patrol.lnx
```

Mednafen既定キーはW/S/A/Dが上下左右、テンキー3がA、テンキー2がBです。`Alt+Shift+1`でLynxパッド割当を変更できます。

本リポジトリは`lynxboot.img`その他のBIOSを取得・同梱・生成しません。BIOS不在時に実エミュレータ確認は行えませんが、ゲームロジックは`make test`、ROM形式は`make inspect`で独立に検証できます。

## 資料

設計は`docs/plan/design.md`、固定ツールチェーンとエミュレータ要件の調査は`docs/plan/toolchain-research.md`を参照してください。
