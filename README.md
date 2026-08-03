# Asteroid Patrol

cc65公式Lynxターゲット向けの小さな横スクロール2Dシューティングです。外部画像・音声素材は使わず、160x102・16色のTGI画面に固定星、コード内の1bit行マスクから作るピクセルキャラクター、矩形、内蔵文字を描きます。

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
- AまたはB: 弾発射（押し続けると8フレーム間隔で連射）。武器Lv1は中央1発、Lv2は上下2発、Lv3は前方平行3発
- 背景: 最背面の32x24ピクセル惑星、遠景星、近景星が8/4/2フレームに1pxの3速度で左へスクロール
- 敵: 最大4体が時間差で進入。slot 0〜2のScout/Saucerとslot 3固定のDropperが、直進・上下波形・急降下折返しで独立移動
- 敵の攻撃: Scoutは画面内90フレーム、Saucerは60フレーム、Dropperは75フレーム間隔で、最大6発の敵弾を左へ発射
- 敵へ命中: 1体ごとに100点加算し、撃破したスロットだけが決定的な種別・動き・高さで右側へ再出現
- 強化: Dropper撃破時だけ4x4の強化アイテムを生成。取得するとHUDの`PWR`が最大3まで上がり、自機弾が1/2/3発へ強化
- 敵本体・敵弾との接触または敵の左端到達: 同一フレームでは残機を1つだけ失い、4段階・32フレームの爆発後に初期位置から再出撃
- 再出撃: 60フレーム無敵。自機が4フレーム単位で点滅し、損傷条件成立時は4敵の初期編成へ戻して全敵弾を消去
- 残機0: 最後の爆発完了後にゲームオーバー。A/Bを一度離してから再度押すと最初から再開始

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
