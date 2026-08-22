# Asteroid Patrol

cc65公式Lynxターゲット向けの小さな横スクロール2Dシューティングです。外部画像素材は使わず、160x102・16色のTGI画面に固定水平ランの背景と3〜4色・2frameの生成run spriteを描きます。自機は12x10、通常敵9種は12x12のvisual canvasを使い、当たり判定は従来の8x6/8x8を維持します。Stage 1〜3の設定は`assets/stages/stages.json`を正本とし、hostで厳格検証して生成したC tableだけをROMへリンクします。各通常区間の後にデータ駆動のボス戦へ入り、Stage 1は宇宙、Stage 2は惑星上空、Stage 3は洞窟の固有背景・敵編成・ボス・環境ギミックを持ちます。メロディとベースの2voice BGM、7種の固定効果音、ローカルVOICEVOX Nemo男性2から生成したタイトル開始/GAME OVER音声を再生します。

## ビルドとテスト

macOSでXcode Command Line Tools、Git、Makeが利用できる状態で実行します。

```sh
make toolchain  # cc65 2.19を.cacheへ取得・検証・ローカルビルド
make verify     # clean、clangテスト、lint、ROMビルド、LNXヘッダ検査
./scripts/verify.sh  # make verifyの実出力を.cache/logs/verify.logにも保存
make perf-host  # 開発専用: 75Hz/無待機のホスト側スケジューラ計測
make frame-cadence-gearlynx  # Gearlynx: APS-052実logic/sound証跡＋APS-051 cadence契約（未最適化ROMはFAIL予定）
make voice-check  # 同梱IMA ADPCM・メタデータ・復号差分表・voice gain表を検証/解析
make stage-check  # JSON schema/ID/range/負性fixture/goldenを検証
python3 scripts/verify-title-voice-gearlynx.py --mode title
python3 scripts/verify-title-voice-gearlynx.py --mode game-over
```

ROMは`dist/asteroid-patrol.lnx`に生成されます。`.cache/`、`build/`、`dist/`はGit管理外です。ツールチェーンスクリプトは`V2.19`の固定コミットを検査し、`cl65 -t lynx`でROMを作ります。

`make frame-cadence-gearlynx`は通常ROMとは別に`dist/asteroid-patrol-cadence.lnx`を生成します。計測probeと16-byte interval BSSは計測ROM専用で、実`game_sound_tick()`戻り後counterはZPへ置き、通常配布ROMへ混入しません。4/8/boss+4のsound timingはproduction elapsedと実tickを比較して合否を記録し、未最適化ROMの描画契約g FAILは段階1の期待結果です。

Gearlynx音声検証は、タイトル音声の完了後に75 Hz基準38 tick（約0.507秒）だけTITLEで静止してからStage 1 BGMが始まること、および最終爆発SFXの最終stepからGAME OVER音声11,691 sampleを再生して停止し、A/Bのrelease→pressでタイトルへ一度だけ戻ることを実ROMで検査します。GAME OVER経路は固定時間待機ではなく、安定したTITLE状態、入力gate、TITLE復帰を`GameState`から期限付きで同期します。

VOICEVOXのraw WAVと800 sampleの無音尾部を正規化したPCMのSHA-256は、各生成runのprovenanceとしてmetadataへ記録します。VOICEVOXはraw PCMがrun間で変化しても最終IMA ADPCMが同一になる場合があるため、raw hashの完全一致は再現性条件にしません。`make voice-check`はraw hashの形式、WAV形式、固定query hash、PCM正規化条件、sample count、最終ADPCM hash、生成headerを検査し、ROMビルド後のcart検査がpayload一致を確認します。決定性境界はROMへ入る最終ADPCM、sample count、生成header、cart payloadです。

## Stage・sprite authoring

`assets/stages/stages.json`でStage 1〜3のtheme、初期4敵、respawn、enemy type/movement/fire、environment event、boss appearance/scriptと、自機・9通常敵・3ボスのcolor gridを編集します。runtimeの通常敵capacityは8です。同時combatantは通常敵1、活動boss 4、重み上限8として数え、4通常敵+bossと8通常敵を許可し、5通常敵+bossなど重み9以上を拒否します。既存Stageの初期/respawn活動数は難度維持のため4です。`make verify`はPython 3標準libraryのみのvalidator/generatorを実行し、`build/gen/stage_data.{c,h}`と`build/gen/sprite_data.{c,h}`を再生成します。JSONの重複/未知key、型・C整数域、ID参照、画面外spawn、event順、重み契約、sprite visual寸法・固定palette role、全26frameの固定274 run、sprite別の着色cell下限とAPS-047機種固有featureに違反するとROMビルド前に停止します。Stage挙動は`stage-data-v034.json`、APS-044 previewから再authoringした全13 sprite・2 frameの固定gridは`sprite-data-v047.json`のcanonical SHA-256で別々に固定します。ROMにJSON/hash/parserはありません。GUI editorは未実装です。

V0.47.0の固定spriteは、APS-044で承認された自機Aのdelta wingと敵9種・boss3種のpreview概念を、既存12x10・12x12・boss canvasへ手作業で再authoringしています。A案の1px nose/canopy、テーパーした非連続delta wing、keel/notch、engine flare、通常敵のwedge・dome/rim・claw/pod・bank wing・armored bay・cargo lock・split wing・segmented drill・asymmetric chassis、bossのspires/reactor・bridge/nacelle/engine・facet/nucleus/fissureを2 frameで表現します。274 horizontal runを3 bytes/runにpackし、固定role、visual左上anchor、8x6/8x8/boss collisionを維持します。生成tableの共通run traversalをhost testと製品rendererの双方が使い、GearlynxではJSON、最終ROM table、GameState mapping、実framebuffer pixelを照合します。

## 操作

- 方向パッド: 自機移動（HUDより下の画面内に制限）
- AまたはB: 弾発射（押し続けると8フレーム間隔で連射）。武器Lv1は中央1発、Lv2は上下2発、Lv3は前方平行3発
- サウンド: MIKEY channel A/Cのメロディ/ベースBGMとchannel Bの全7 SFXは、論理table/envelopeを保ったままhardware出力だけを`floor(volume*3/4)`（非zero最低1）へ下げる。channel Dはタイトル開始とGAME OVERのIMA ADPCMを共通Timer 3 backup 125（1 us clock、126 us周期、実効7,936.508 Hz）で排他的に再生し、両音声だけへcenter-preserving +25% saturating gainを一度適用する。タイトルは17,408 samples・約2.193秒、GAME OVERは11,691 samples・約1.473秒
- ステージ進行: 描画・入力・`sound_tick()`は75Hzのまま、描画フレームごとに4ロジック更新（300Hz、基準75Hz比4.00倍）。Stage/phase進行、移動、弾、クールダウン、環境イベント、無敵を同じ比率で進める。BGMカーソルも非死亡時に1 sound tickあたり4回進め、SFXカーソルは1回のまま実時間長を維持する
- 自機移動: `PLAYER_SPEED=2`は75Hz描画基準の2px/描画フレーム（150px/s）として扱い、300Hzの各logic updateではX/Y別の符号付きfractional creditへ`±2`を加算し、creditが±4に達したときだけ1px反映する。通常の4 logic updatesで2px、低FPS catch-upのelapsed=1/2/3では2/4/6px、上限12 updatesでも6pxとなる。左右・上下同時入力は相殺し、neutral・方向転換・移動禁止phase・境界ではcreditを破棄する
- frame cadence: `tgi_setframerate(75u)`をhardware presentationの唯一のtiming sourceとする。各frameは前回swap待ちの間に入力1回→Timer 2 elapsedに応じたlogic catch-up→同じelapsed分のsound tick→sound apply 1回を進め、back buffer再利用の直前だけ`while (tgi_busy()!=0u)`で前回display completionを待ち、draw→display requestを各1回行う。製品frame終端の容量補償wait、delay、logic/input/sound skipはない。0/4/8通常敵と4通常敵+bossで同じevent回数・移動量を維持し、MCP wall-clockでなくhardware eventを正しさの基準とする
- HUD: 画面最上部の黒い帯に小型一行で`S<stage> <phase><progress> <score> L<lives> W<weapon>`を表示し、下端線から下だけをプレイ領域として使う。Stage 1導入の進行もこの行に集約する
- 非戦闘フェーズ: 導入・クリア中は背景とアニメーションのみ進行。`WARNING`中は移動だけ可能で射撃不可
- Stage 1背景: `SPACE`テーマの黒系配色。最背面の32x24ピクセル惑星、遠景星10個、近景星7個が8/4/2フレームに1pxの3速度で左へスクロール
- Stage 1敵編成: 最大4体がX=140/170/200/230、Y=47/23/70/38から時間差で進入。Scout/Saucer/Scout/Dropperを直進/上下波形/急降下折返し/直進へ割り当て、撃破後も`SPACE`編成の決定式で再配置
- Stage 1環境: 固定時刻に最大2個の8x8小惑星が右から流入。自機弾1発で破壊すると250点、接触すると残機を失う
- Stage 2背景: `SKY`テーマの低〜中彩度palette role 0/1/3/4を空・山・中景雲・近景雲へ使用。固定山並み、雲8群、より大きい雲5群が192/160/160px周期を8/4/2フレームに1pxでスクロール
- Stage 2敵編成: FIGHTER/BOMBER/FIGHTER/SUPPLYがX=144/180/212/244、Y=24/64/42/78から時間差進入。発射間隔は72/96/72/84、位相は0/18/36/54
- Stage 2環境: 点線と矢印の45フレーム予告後、上下方向の風帯が150フレーム発生。帯内では方向入力後に2フレームごと1px押されるが、損傷はない
- Stage 3背景: `CAVE`テーマのpalette role 0/1/3/4を奥壁・亀裂・天井床・鍾乳石/石筍へ使用。固定水平ランが192/160/160px周期を8/4/2フレームに1pxでスクロール
- Stage 3敵編成: CAVE_BAT/ROCK_WORM/CAVE_BAT/MINING_DRONEがX=148/184/216/248、Y=22/72/44/82から時間差進入。発射間隔は66/84/66/78、位相は0/16/32/48
- Stage 3環境: 固定Xの着地点を45フレーム予告してから最大2個の岩石が落下。岩石は破壊・得点化できず、接触または着地後は12フレームの着地表示になる
- 敵の攻撃: 各編成の固定間隔で最大16発の敵弾を左へ発射
- ボス: Stage順にHP 60/90/120。Stage 1は24x16の珊瑚要塞、Stage 2は28x14の琥珀母艦、Stage 3は24x24の紫/青緑ジオード生命体。最終ボスは静止バースト、静止挟撃、Y=21〜57の広域移動挟撃を330更新で循環する
- 敵へ命中: 1体ごとに100点加算し、撃破したスロットだけが決定的な種別・動き・高さで右側へ再出現
- 強化: Stage 1のDropper、Stage 2のSUPPLY、Stage 3のMINING_DRONE撃破時だけ4x4の強化アイテムを生成。取得するとHUDの`W<weapon>`が最大3まで上がり、自機弾が1/2/3発へ強化
- 敵本体・敵弾との接触または敵の左端到達: 同一更新では残機を1つだけ失い、BGMを停止して短いnoise主体の爆発SFXを再生する。SFX完了まで戦闘を凍結し、非最終ライフでは現StageのBGMを曲頭から再開して初期位置から再出撃する
- 再出撃: 60フレーム無敵。自機が4フレーム単位で点滅し、損傷条件成立時は4敵の初期編成へ戻して全敵弾を消去
- 残機0: 最後の爆発完了後にGAME OVER画面を先に表示し、「お前は弱かった」を一度だけ再生する。再生中はA/Bを無視し、完了後にA/Bを一度離してから再度押すとタイトルへ戻る
- ALL CLEAR: A/Bを一度離してから再度押すと、Stage 1・スコア0・残機3・武器Lv1から完全再開始

## macOSでの手動確認

第一候補はGearlynx 1.2.21です。`brew install --cask drhelius/geardome/gearlynx`または公式配布物を利用し、合法的に所有するBIOSをGearlynxの設定から指定して、生成ROMを開きます。GearlynxはBIOS必須で、公式READMEはMD5 `fcd403db69f54290b51035d82f835e7b`のオリジナルBIOSを推奨しています。キーボード割当はGearlynxのInput設定で方向・A・Bを確認してください。

起動時はタイトル画面です。起動時にA/Bが押されたままでも開始しないため、一度離してから`A/B TO START`を押すと「わしは宇宙の帝王ザカリテ」を再生し、完了後に75 Hz描画基準38 tick静止してから新規ゲームを始めます。0.5秒は37.5 tickのため短縮せず切り上げ、待機時間は38/75=約0.506667秒です。約2.193秒の再生中と続く静止待機中はタイトル画面を保持し、A/Bを無視してゲームプレイ・Stage timer・BGMを開始しません。待機は300 Hzロジック更新ではなく各描画フレームで1回だけ進みます。A/Bは重複開始しません。`STAGE 1`の導入を約90更新表示してから通常戦闘へ入ります。タイトルには方向移動とA/B射撃の基本操作を表示し、導入中の方向・A/Bは移動・射撃に使いません。最終爆発SFXの実完了後はGAME OVER画面を先に表示して「お前は弱かった」を一度だけ再生します。再生中はA/Bを無視して`VOICE...`を表示し、完了後だけ`A/B TO TITLE`へ切り替えます。完了時に押下済みのA/Bは使わず、離してからの再押下でタイトルへ戻ります。その復帰入力は開始に流用せず、タイトルで離してから再度A/Bを押すとタイトル音声と38 tick待機の完了後に完全な新規ゲームを始めます。ゲーム状態はTGIの二重フレームバッファとは重ならない静的BSSに保持します。

同梱音声は公式VOICEVOX Nemo 0.24.0の男性2（エンジン表記`男声2`、style ID `10000`）から同一Mac内で生成しています。確認日2026-08-09のNemo規約に基づき、固定クレジット`VOICEVOX:Nemo（男性2）`をタイトル画面と文書へ表示する条件で商用・非商用利用が可能です。生成条件、公式配布物のSHA-256、一次資料URL、禁止事項は`assets/voice/README.md`と`assets/voice/LICENSE.md`を参照してください。

channel Dは停止したpolynomial generatorを介さず、CPUがsigned 8-bit値を`AUD3OUT`へ直接書くDAC経路です。`AUD3VOL`はpolynomial出力の振幅源でありdirect DAC書込を後段増幅しないため、音声gainは復号後のDAC byteへ適用します。signed byteを`u = byte XOR 0x80`でunsigned center 128へ見立て、中心からの絶対振幅を`floor(5/4)`（0方向へ丸め）し、`-128..127`へ飽和してからsigned byteへ戻します。256-byte table lookupだけをTimer 3 IRQの共通`decode_complete`へ置くため、zero/silenceは`0x00`のまま、正負はclamp前まで対称、両voiceで一回だけ適用されます。`make voice-check`は生成tableとhost referenceの一致、両ADPCM全sampleのgain前後peak・center・clamp比・silent tail・asset SHA-256を検査します。

代替はMednafen 1.32.1です。`brew install mednafen`後、合法的に所有する512バイトのLynx boot ROMを**ユーザー自身で**Mednafenベースディレクトリへ`lynxboot.img`として配置し、次を実行します。

```sh
mednafen dist/asteroid-patrol.lnx
```

Mednafen既定キーはW/S/A/Dが上下左右、テンキー3がA、テンキー2がBです。`Alt+Shift+1`でLynxパッド割当を変更できます。

本リポジトリは`lynxboot.img`その他のBIOSを取得・同梱・生成しません。BIOS不在時に実エミュレータ確認は行えませんが、ゲームロジックと75Hzサウンドシーケンサは`make test`、ROM形式は`make inspect`で独立に検証できます。

## 起動・操作スモーク検証

```sh
make smoke-host      # BIOS不要: Stage 1 NORMAL、右移動、射撃、GAME OVER非遷移
make smoke-gearlynx # 任意: 既存Gearlynx設定でROMをヘッドレス起動する
```

`smoke-host`は90更新後の`NORMAL`到達、方向入力、自機弾の有効化、その観測中の`game_over=0`を独立して判定します。`smoke-gearlynx`は、起動前にデバッグポートの未使用を確認し、起動後も待受PIDが今回のGearlynxプロセス（またはその子）に属する場合だけヘッドレス起動を確認します。ポート競合や別プロセスの待受は失敗（終了コード1）です。リポジトリ内には同モニタの入力・状態読出しプロトコル定義がないため、操作・状態の実ROM自動検証は終了コード3の**未検証**として明示します。通常の`make verify`にはGearlynxを含めません。

## 開発専用の性能計測

`make perf-host`は通常ROMへ入らない`GAME_PERF_INSTRUMENT`付きホストベンチを作る。`--sync`は実時間75Hzで1秒間、`--unthrottled`は同じ1秒間に待機なしで、Lynx main loopと同じ「描画フレームごとの入力相当 → `4/1`ロジック → BGM/SFX tick」順を実行する。出力の`draw_frames`、`logic_updates`、`sound_ticks`、`game_speed_x`は実測値であり、ゲーム時間はロジック更新数（75Hz時300更新/秒を基準75Hz比4倍）から算出する。

同じターゲットは、最適化前の4スロット`hit_enemies`再走査を`GAME_PERF_LEGACY_HIT_RESCAN`でだけ復元した旧経路もビルドする。このフラグは`GAME_PERF_INSTRUMENT`なしではコンパイルエラーになり、cc65/通常ROMには含まれない。旧経路の全ゲーム回帰を先に実行した後、固定500万描画フレームを各1回ウォームアップし、旧/新の実行順を交互にした7組を測定する。各組、中央値、最小/最大、対ごとの差を出力するため、同一ホスト上で再比較できる。実測値とその解釈は`ISSUES.md`のAPS-019に記録する。

このベンチはTGI描画やVBlank自体をエミュレートしないため、無待機値はホスト上のロジック更新速度であってLynxの描画性能ではない。通常ROMは必ず`src/main.c`の`tgi_busy()`待機と`tgi_setframerate(75u)`を使う。詳細な実測値、ホットパス計数、無待機の副作用は`ISSUES.md`のAPS-019を参照する。

終了しない`main()`へ大きな自動`GameState`を置かないでください。cc65 2.19ではCスタック先頭とTGI第2フレームバッファ先頭`0xC038`が衝突し得ます。`src/main.c`の静的BSS `game`を使い、ROMビルド後に`build/asteroid-patrol.map`のBSS範囲（APS-014時点では`0x8BC5`〜`0x8E04`、`game`は`0x8BC9`）が表示バッファから分離していることを確認します。

## 資料

設計は`docs/plan/design.md`、固定ツールチェーンとエミュレータ要件の調査は`docs/plan/toolchain-research.md`を参照してください。
