# Asteroid Patrol 設計

## 目的

Atari Lynxの標準160x102・16色モードで動く、最小構成の横スクロール2Dシューティングを作る。Stageごとの最背面・中景・近景による3層パララックスで横方向の進行を表し、方向入力でピクセルキャラクターの自機を動かし、A/Bで最大3段階の前方弾を撃つ。形状と移動の異なる複数敵に当てると100点を加算して敵を再配置し、ドロップ能力を持つ敵の撃破では武器強化アイテムを出す。敵は種別ごとの間隔で敵弾を撃つ。敵本体・敵弾との接触または左端到達で残機を失うと、爆発後に再出撃し、最終残機では爆発完了後にゲームオーバーになる。

## 構成

- `src/game.c`: ハードウェア非依存の状態遷移。`assets/stages/stages.json`から生成した背景テーマID・通常敵編成ID・Boss設定/外観/攻撃手順・環境イベント表を参照し、Stage 1〜3の共通進行、移動、境界、12発の自機弾、符号付き速度を持つ16発の敵弾、3段階武器、8フレームの連射間隔、AABB、得点、4敵の再出現、敵ごとのドロップ能力と強化アイテム、残機、爆発・再出撃・無敵、ゲームオーバー、ALL CLEAR、完全再開始、3層背景、サウンドイベント発火を担当。
- `src/sound.c`: 75Hzのハードウェア非依存サウンド状態。3曲の固定BGM表と、7種SFX、優先度、固定1件保留を持つ。BGM・SFXは独立した論理出力（`output_bgm`/`output_sfx`）を持ち、`bgm_active`が真の間はBGMカーソルが常時BGM出力を生成し、SFXはアクティブな間だけ独立にSFX出力を生成する（APS-020で2ch復帰）。APS-036のgain helperは論理値を変更せずhardware投影値だけを返す。
- `src/main.c`: cc65/Lynxアダプタ。標準ジョイスティックドライバを読み、Stage遷移時だけ生成済み32-byte paletteをTGIへ設定する。固定水平ラン表の惑星・山・雲・洞窟地形、固定星、生成済み3〜4色水平runの自機・9通常敵・3ボス、両陣営の弾、Stage/フェーズ表示、ボスHPバー、HUDを背面から順に描く。純Cのメロディ/ベース/SFX論理出力を75% gain後にMIKEY channel A/C/Bへ反映し、cartridge-only音声は共有+25% saturating PCM gain後にchannel Dへ排他的に流す。
- `tests/test_game.c`と`tests/test_sound.c`: 同じゲーム/サウンドロジックをmacOS clangで実行する回帰テスト。

## APS-051 実時間cadence計測の是正（段階1）

APS-049契約gの換算基準`553,362/553,380 ticks`は誤りだった。Timer 2 VBLANKの同一ROM実測中央値`184,482 ticks`を1 VBlank=`13,333.333333333334us`の基準とし、`US_PER_TICK=13,333.333333333334/184,482`を使う。契約gは平均CPU tickやbulk frame-stepの実行量ではなく、連続する`_game_display_request`間隔を直接採取し、各`delta_ticks / 184,482`が全て`1.05`以下であることを要求する。各fixtureは独立2 batch（各75区間）、Timer 2 IRQ raw sample・run別中央値/最大値を保存する。

段階1では描画・Suzy/TGI・ゲームロジック・spriteデータを変更しない。通常配布ROMはprobe object/header/main hookを含まず、`make frame-cadence-gearlynx`だけが専用cfg・map・label付きの計測ROMを生成してprobeをリンクする。16-byte intervalは計測ROM専用BSSへ確保し、実`game_sound_tick()`戻り後counterはZPへ置いてBSSを増やさない。mapからBSS終端・C stack開始・残余・stack非重複を機械検査する。現行未最適化ROMの描画契約g FAILは正しい観測であり、`evidence/APS-052/logic-catchup-gearlynx.json`へ両ROM path/size/SHA、raw interval、実logic/sound tick、clip/discard、stack値を保存する。`tests/perf_bench.c`は実TGI/Suzy描画をリンクしないため、host性能値を実機cadenceの根拠にしない。

段階2ではSuzyハードスプライト（SCB直接）等による敵描画削減・背景全再描画削減を実装し、修理済み契約gでGearlynxの敵4体/8体を再測定する。最終受入にはAtari Lynx実機の敵4体/8体の速度実測と体感確認も必要で、cadence自動テスト単独PASSは受入条件にしない。

## APS-053 Phase 2R-0/2R-1 統合（v004）

`src/static_layer.c`は背景・clear・HUDをSCB chainへ構築する。通常spriteのHSIZE/VSIZEは8.8固定小数の`0x0100`（1x）とし、clearだけ画面全体の`160x102`へ拡大する。SCB再利用領域は`title_voice_scratch_buffer`先頭539 bytesで、SCBの`penpal[0..7]`を毎回初期化する。title/GAME OVER voice再生中はstatic layerの全描画APIをguardする。

タイトル・overlay・GAME OVER・HUDの文字はTGI vector textを使わず、生成literal spriteまたは4x5 compact glyphをSuzyへ渡す。固定文言は生成器のliteral asset、動的版番号/HUDは共有scratch内で構築する。`tgi_outtextxy`/`tgi_vectorchar`呼び出しはruntimeから除去し、ROM mapは通常MAIN spare 444 bytes、cadence MAIN spare 406 bytes（基準stack予約）まで回復した。Gearlynx cadence契約gは0/4/8/boss fixtureで未達のため、APS-053受入は継続中。

描画フレームごとに入力を一度取得し、画面クリアと再描画、`tgi_updatedisplay()`、MIKEYへのsound applyを各一回だけ行う。Timer 2 VBlank基準の`elapsed_vblanks`により、ロジックは`elapsed_vblanks × 4`回（1描画あたり128回上限）、サウンドは`elapsed_vblanks`回（1描画あたり2048回上限）進め、各上限超過分はproduction consume counterと実`game_sound_tick()`戻り後counterの差として証跡へ記録する。これにより低FPS時も300Hzロジックと75Hz基準のA/C/B音楽・SFX時間を、4/8/boss+4 fixtureの実測範囲内で実時間へ追従させる。APS-030最終仕様のゲーム内ロジックは剰余0からの`4/1`固定スケジューラで、通常の各描画フレームに4回、300Hz（基準75Hz比4.00倍）更新する。同じ描画フレーム内のcatch-up更新にも同一入力を渡すため、状態遷移、進行タイマ、移動、弾、クールダウン、敵発射、環境、無敵は決定的に経過VBlank分進む。各`game_sound_tick()`は論理出力を一回投影した後、非死亡時の共有BGMカーソル（メロディ/ベース）を4回進め、SFXカーソルを一回進める。自機死亡開始時はBGMを停止し、爆発SFXの完了を死亡状態の解除条件とするため、300HzロジックがSFXより先に再出撃やGAME OVERへ進むことはない。GAME OVER/ALL CLEARの解除・再押下判定を最優先とし、導入・警告・クリアは許可された背景・入力を一度更新してから境界判定する。NORMALは既存の通常戦闘順を維持し、BOSSは背景、自機、射撃、自機弾、ボス命中、既存敵弾、ボス移動/発射、自機損傷の順とする。HP0更新は直ちにクリアへ移って後続ボス処理を省略する。動的確保、外部アセット、外部音源を使わない。

## APS-019 75Hz同期と開発用性能計測

Lynxの初期化では、TGI/ジョイスティック初期化と`CLI()`後に前回表示要求がないことを`while (tgi_busy() != 0u)`で確認し、`tgi_setframerate(75u)`を設定する。各製品フレームは同じ`tgi_busy()`待機、入力1回、`game_logic_updates_for_draw_frame()`、戻り値回数の`game_update_logic()`、`game_sound_tick()`、MIKEY SFX反映、背面バッファへの`draw_game()`、内部の`tgi_updatedisplay()`1回の順で実行する。`draw_game()`はタイトル経路でも通常経路でも最後に一度だけ表示更新を要求する。

通常ROMを変えずに同じ更新順・`4/1`スケジューラを測るため、`tests/perf_bench.c`を`-DGAME_PERF_INSTRUMENT`付きのホスト専用でビルドする。`make perf-host`は75Hz待機、無待機、固定500万描画フレーム相当のワークロードを出力する。カウンタは通常ROMから完全に除外され、HUD、入力、`GameState`、ROM容量へ影響しない。ベンチの固定シナリオは衝突しない12自機弾・4敵・16敵弾を20ロジック更新ごとに再準備し、通常戦闘の固定配列走査を再現可能に比較する。TGI描画/VBlankを実装しないため、無待機の数値はLynx実機FPSではなく、入力・ロジック・SFX更新経路のホスト実測である。

前後比較では、`GAME_PERF_INSTRUMENT`と組み合わせたホスト限定の`GAME_PERF_LEGACY_HIT_RESCAN`により、最適化前の`hit_enemies`再走査を復元する。このフラグ単独のビルドは拒否し、通常cc65ビルドへ混入させない。`make perf-host`は旧経路の全ゲーム回帰を実行し、両版を固定500万描画フレームで各1回ウォームアップした後、旧/新の順序を交互に7組実行する。各組の経過時間と、中央値・最小/最大・対ごとの差を出力する。これにより、決定的な走査回数と、揺らぎを含むホスト計時を同じ条件で区別して記録できる。

`update_normal()`では自機弾処理が返すビット結果（強化アイテム生成/敵撃破）を使い、以前の`hit_enemies`再走査を廃止した。命中配列は敵移動・被弾判定の抑止に引き続き使用する。強化アイテム生成フラグは従来どおり最後に試みたドロップ生成の成否を保持する。従って、同一更新の複数撃破を1回の敵撃破SFXにまとめる規則、既存アイテムを保持した場合の同フレーム取得、敵再配置、決定性は変えない。開発専用カウンタで通常更新ごとの命中フラグ走査は8回から4回へ減る。主要な固定走査（自機弾12、敵候補最大48、敵弾32）は変更しない。

## 画面

## APS-050 3ボス1x統一+当たり判定中心整列

- 背景/ロジック/音声/サウンド契約はAPS-049の値を維持し、`assets/stages/stages.json`のboss visualのみを1xへ統一する。
- `SPRITE_CONTRACTS`の`coral_bastion`/`amber_carrier`/`violet_geode`の`boss_visual_scale`を`1`へ固定。`draw_sprite()`側の分岐描画も`origin.scale = 1u`固定へ戻し、当たり判定中心の`collision`と`visual`の重心を`SPRITE_CONTRACTS`共有ルール＋`sprite_anchor()`で整列させる。
- `scripts/verify-stage-visuals-gearlynx.py`は`boss`ごとの`boss_origin`で`boss_clipped_columns/rows`を算出し、`assert_sprite_not_clipped`で右端/下端クリップを停止位置起点で明示検証。全3ボスで`clipped=0`をPASS条件とし、`evidence/APS-050/runtime-sprite-gearlynx*.{json,png}`へ保存。
- `tests/golden/sprite-data-v050.json`を新規追加し、`GAME_SPRITE_*` 13種のpreview/frames+anchorを`tests/test_stage_data.py`に固定（`v043/v045/v047/v049`は履歴として保全）。
- ROM契約は`include/version.h`を`"0.50.0"`へ更新し、`tests/test_stage_data.py`/`scripts/verify-stage-visuals-gearlynx.py`のgolden参照をAPS-050に合わせる（`Makefile`の`SPRITE_GOLDEN`も更新）。

- 0〜9行: 黒いHUD帯。3x5の自作文字で`S<stage> <phase><progress> <score> L<lives> W<weapon>`を一行表示し、Stage 1導入の進行もここへ集約する。
- 10〜101行: HUD下端線で分離したプレイ領域。全戦闘物はこの領域へクリップする。
- 最背面惑星: 8フレームに1px、遠景星: 4フレームに1px、近景星: 2フレームに1pxで左へ進む。惑星は192px、星は160pxでラップする。
- 星はプレイ領域内の固定座標表から描き、遠景10個は暗い1px、近景7個は明るい1〜2pxとする。オフセットと間引きカウンタを`GameState`に保持し、乱数や符号なしアンダーフローを使わず0〜159で明示的に循環させる。
- 惑星は32x24px、基準位置(120,18)。オフセットを0〜191で循環し、符号付き描画X=`120-offset`が-32未満なら192を加える。丸い輪郭24本と内部の2クレーター8本を相対座標の固定水平ラン表で自作し、暗色2色、画面左右クリップ付きで星より先に描画する。
- 自機: 8x6、敵: 8x8、ボス: Stage別24x16/28x14/24x24の3〜4色水平run sprite。各2フレームを持ち8フレームごとに切り替える。自機弾は3x2矩形、敵弾は2x2矩形、強化アイテムは4x4の1bit行マスクを維持する。
- 自機、Scout、Saucer、Dropper、FIGHTER、BOMBER、SUPPLY、CAVE_BAT、ROCK_WORM、MINING_DRONEは互いに異なる独自シルエットを持ち、各キャラクターの2フレームも異なる。生成時に各runがcollision rect内、各frame最大20 run、3〜4色、role許可内であることを検査する。強化アイテムは固有4x4マスクと固定色で識別する。背景、弾、HUD、文字もTGIプリミティブとTGI内蔵文字だけを使う。
- 常時Stage番号を表示し、導入、WARNING、STAGE CLEAR、ALL CLEARと再開始案内をフェーズに応じて表示する。BOSS中はBoss外観IDでStage 1の24x16珊瑚要塞、Stage 2の28x14琥珀母艦、Stage 3の24x24紫/青緑ジオード生命体を選び、現在HP比率のバーを表示する。ゲームオーバー中は最終ゲーム画面を背景に`GAME OVER`を重ね、音声中は`VOICE...`、完了後は`A/B TO TITLE`を表示する。
- 爆発中は通常の自機の代わりに4段階の自作爆発マスクを各8ロジック更新表示し、最終段階で飽和させて配列境界内を保つ。爆発SFX完了後の再出撃では4ロジック更新単位の点滅で無敵時間を表す。

## 当たり判定

矩形の右端・下端を排他的境界とするAABB。自機弾はスロット昇順で最初に重なった敵1体だけに命中し、弾を消し、100点加算し、対象敵を決定的な列で再配置する。同じ更新の複数弾による複数撃破は許可する。敵状態の`drops_power`が有効なDropper、SUPPLY、MINING_DRONE撃破時は撃破前座標に強化アイテムを生成する。アイテムと自機のAABB重なりで武器レベルを最大3まで1上げる。命中処理は自機損傷より先だが、命中した敵以外の敵本体と既存敵弾は損傷源として残る。敵弾が自機へ重なった場合は敵弾を消して死亡シーケンスを開始する。すべてを決定的にしてホストテストを再現可能にする。

## 複数敵・敵弾・残機・再開始

敵は固定4スロットとし、矩形、種別、移動パターン、基準Y、間引き、位相、方向、発射間隔・カウンタを個別に持つ。Stage 1の`SPACE`編成表はX=140・170・200・230、基準Y=47・23・70・38、Scout/Saucer/Scout/Dropper、直進/上下波形/急降下折返し/直進、発射間隔90/60/90/75、発射位相0/15/30/45を固定スロットデータとして持つ。画面外右側は左移動だけを行い、描画・発射・衝突は画面内に入ってから有効にする。撃破されたスロットだけを`SPACE`編成設定のX=`180 + slot * 16`へ再配置し、増加後の出現列とslotを種としてslot 0〜2の敵種`% 2`、移動`% 3`、基準Y=`13 + seed * 17 % 78`を決める。slot 3は再配置後もDropperを維持する。再配置更新の移動・発射・接触は行わない。水平速度、垂直更新間隔、垂直幅、挙動種別は固定テーブルにまとめ、再配置時は間引き、位相、方向、発射カウンタを決定的な初期値へ戻す。

直進はXを毎フレーム1px左へ移動しYを維持する。上下波形はXを同様に進めながら3フレームに1px、基準Yの上下最大6pxを往復する。急降下折返しは2フレームに1px、基準Yから下へ最大12px降下し、基準Yへ戻る。すべてのY座標をHUD下端から画面下端の間に制限する。

敵弾は固定16スロットの2x2矩形で、弾ごとに符号付きX/Y速度を持つ。通常敵弾は(-2,0)とし、Scoutは画面内の90通常更新ごと、Saucerは60通常更新ごと、Dropperは75通常更新ごとに発射する。敵ごとの初期発射位相をスロット番号×15更新でずらす。空き弾スロットを昇順で確保し、X=159からの生成時は弾の生成Xを158へ制限する。満杯でも発射カウンタをリセットして後の集中発射を防ぐ。発射更新には生成だけを行い、次更新から弾を移動する。座標は`int`中間値で更新し、上下左右の画面外へ出た弾を符号なしアンダーフローなしで消去する。

武器レベルは1〜3。自機弾上限は12発で、Lv1は中央1発、Lv2はY=`player.y`と`player.y+4`の平行2発、Lv3はY=`player.y`・`player.y+2`・`player.y+4`の平行3発を1射として生成する。必要数の空きがある場合だけ空きスロット昇順へ全弾を生成し、成功時だけ8更新クールダウンを開始する。強化アイテムは固定1個の4x4マスクで、2更新に1px左へ動く。Dropper撃破前の座標からX+2/Y+2へ生成し、右端はX=156へ制限する。生成更新には移動も取得もしない。活動中の再ドロップは既存アイテムを置換せず、通常の移動を継続する。取得時は最大3までレベルを1上げ、Lv3でもアイテムは消費する。

敵本体との接触、敵のX=0到達、敵弾との接触で残機を1つ失い、全自機弾を消して死亡状態へ入る。同じ更新に複数条件が成立しても減る残機は1つだけとする。死亡開始時はメロディ/ベースBGMを即時停止し、17 sound tickの短いnoise主体・段階減衰する自機爆発SFXを開始する。公開状態の`explosion_timer`は0から31まで進めて飽和し、`timer / 8`で4段階を安全に選ぶ。爆発SFXが実際に完了するまで、惑星を含む3層背景・入力・4敵・両陣営の弾・強化アイテム・武器レベル・得点・各カウンタ・通常アニメーションを含む通常状態を凍結する。

残機があれば爆発SFX完了を最初に観測したロジック更新で、得点、惑星を含む3層背景座標、武器レベル、フェーズ経過を維持し、自機を初期座標へ戻して60戦闘更新の無敵で再出撃する。同時に現StageのBGMを曲頭から再開する。NORMALでは4敵編成と各発射カウンタを初期化し、BOSSではHPを維持してボス位置・移動・攻撃手順だけを初期化する。いずれも両陣営の弾と活動アイテムを全消去する。各戦闘更新の開始時に保護状態を確定してから残り時間を減らすため、60回目の更新中まで保護し、61回目から損傷可能になる。無敵中は3層背景を通常どおり進める。点滅は無敵の経過更新数から決定し、4ロジック更新ごとに表示・非表示を切り替える。

初期残機は3。最終残機の損傷でも即時GAME OVERにせず、爆発SFXの実完了後にだけGAME OVERへ入り、BGMは再開しない。同時にGAME OVER音声を一度だけpending化し、完了まではA/Bを無視して`restart_armed=0`を維持する。完了後も押下済み入力を利用せず、A/Bを離してから再押下するとタイトルへ戻り、その復帰押下は開始へ流用しない。GAME OVERではフェーズ、3層背景、キャラクターアニメーション、敵・ボス、両陣営の弾、武器レベル、強化アイテムを凍結する。タイトルでは再度A/Bを離してから新たに押下した場合だけStage 1導入へ完全な新規ゲームを開始する。ALL CLEARだけは画面成立後のA/B解除と再押下で直接Stage 1導入へ完全再開始する。いずれの完全新規開始でも、惑星オフセット/間引き0、武器Lv1、アイテムなし、得点、残機、自機、非活動の通常敵・ボス、両陣営の弾、各クールダウンとカウンタ、背景、アニメーション、死亡/無敵/進行状態を初期化し、その更新には発射しない。

## 制約と判断

ゲーム側はC89互換に保ち、固定小配列と基本整数型のみを使う。Lynx公式ヘッダ自身が`//`コメントを含むため、ROMコンパイルはcc65言語モード、ホストロジック検査はclangの厳格なC89モードとする。Lynx固有コードは`main.c`に限定し、ロジックの自動検証をエミュレータやBIOSから独立させる。

## APS-014 起動経路の安全性

`game_init()`は呼出し元のスタック内容に依存せず、公開・内部を問わず`GameState`の各フィールドを決定的に初期化する。起動直後は`GAME_PHASE_TITLE`、Stage 1、残機3、`game_over=0`、非死亡、敵・弾・アイテム・Boss・環境物は非活動、サウンド停止である。`game_start()`だけがStage 1の`GAME_PHASE_STAGE_INTRO`と曲頭を開始する。A/Bの入力は導入中に射撃や再開始へ流用しない。

Lynxアダプタは、各フレームでTGIの表示完了待機後に入力取得・ゲーム更新・サウンド反映・背面バッファ描画・`tgi_updatedisplay()`を一回だけ行う。MIKEYはchannel Aの許可済みレジスタだけをvolatileな8-bitアクセスで操作し、Timer、TGI表示制御、他音源、OUT/DAC、COUNTを変更しない。起動時のMIKEY初期化はゲーム・TGI・入力の初期化を破壊せず、必要最小限の停止状態に留める。これらはホスト回帰テストと、既存設定のGearlynxでのStage 1導入・移動・射撃により検証する。

実装では`GameState`を`main()`のローカルではなく`main.c`の静的BSSへ置く。cc65 2.19は終了しない`main()`のローカルをCスタック先頭へ置くため、315-byte超の状態をTGIのフレームバッファ先頭`0xC038`と共有させてはならない。`game_init()`は最初に構造体の全バイトをゼロ化してから、寸法・初期座標・タイトル・停止サウンドを設定し、`game_start()`がStage 1導入と曲頭を設定する。これにより未初期化フィールドと構造体パディングも呼出し元の内容から独立する。

## APS-016 タイトルとGAME OVER復帰

固定状態機械へ`GAME_PHASE_TITLE`を追加する。タイトルでは`ASTEROID PATROL`、開始案内、方向移動・A/B射撃の基本操作だけを描く。起動時タイトルは開始入力を未武装にし、A/Bを離してからの新規A/B押下だけで`game_start()`する。これにより起動時にA/Bが押されたままでも開始を誤受理せず、Stage 1 INTRO、スコア0、残機3、武器Lv1、戦闘物なし、Stage 1曲頭から始める。

最終死亡後のGAME OVERではロジックとサウンドを停止し、タイトルへ遷移するまで背景、HUD、プレイヤー、敵、弾などの最終状態を描き続け、その上に`GAME OVER`と`A/B TO TITLE`を重ねる。GAME OVERはA/Bが離れたことを`restart_armed`で確認してからの再押下だけでタイトルへ戻す。遷移直後は`title_start_armed=0`なので、同じ復帰押下が開始へ連鎖しない。タイトル中にA/Bが離れた時点で開始入力を武装し、次のA/Bで完全な新規ゲームを開始する。ALL CLEARは従来どおり、離してからのA/B再押下で直接Stage 1 INTROへ完全再開始する。

## APS-015 起動・操作スモーク

BIOS非依存の`make smoke-host`は、独立した`tests/test_smoke.c`で初期化からStage 1の90更新、`NORMAL`到達、方向入力による自機移動、A/B相当の`GAME_INPUT_FIRE`による自機弾有効化、各観測中の`game_over=0`を判定する。通常の`make verify`はこの外部エミュレータ非依存経路を変更しない。

任意の`make smoke-gearlynx`は既存のGearlynx 1.2.21を`--headless --debug-monitor`で実ROMとシンボルを指定して起動する。起動前に指定デバッグポートが待受中なら失敗し、起動後も待受PIDが今回起動したGearlynxまたはその子プロセスに属する場合だけ、20秒以内の待受を確認する。これにより別プロセスの待受を起動成功へ誤帰属しない。現時点のリポジトリにはこのモニタの入力注入・ゲーム状態読出しのプロトコル定義がないため、スクリプトは操作・状態の実ROM判定を成功として扱わず、終了コード3で未検証を返す。これはBIOSを探索・読出し・変更せず、無限待機もしない。

Lynxでは、終了しない`main()`の自動`GameState`（cc65で約317 bytes）をTGI第2フレームバッファ先頭`0xC038`へ重ねてはならない。`main.c`の静的BSS `game`を維持する。APS-014のリンクマップでは`_sound_hardware=0x8BC5`、`_game=0x8BC9`、BSSは`0x8BC5`〜`0x8E04`であり、表示バッファから分離される。ROMを変更した場合は`make rom`後に`build/asteroid-patrol.map`のBSS範囲を確認し、この分離を再確認する。

## APS-008 3ステージ共通進行とボス基盤

ゲーム全体をStage 1〜3と`STAGE_INTRO`、`NORMAL`、`WARNING`、`BOSS`、`STAGE_CLEAR`、`ALL_CLEAR`の共通状態機械で管理する。導入90更新、通常1125更新、警告120更新、クリア120更新はゲーム内ロジック更新で数え、現行の`4/1`スケジューラにより基準75Hz比4.00倍で進む。爆発・GAME OVER・ALL CLEARでは進行を凍結する。導入・警告・クリアでは戦闘物を消去し、背景とアニメーションを継続する。警告中は移動のみ可能とする。

通常区間から警告へ移る際に通常敵、両陣営の弾、活動アイテムを消去し、ボス戦開始時に固定1体のボスを設定表から生成する。ボス撃破後はStage 1/2なら次のStage導入へ、Stage 3ならALL CLEARへ進む。得点、残機、武器Lvはステージ間で維持し、一時オブジェクトと攻撃位相は持ち越さない。GAME OVERはA/B解除後の再押下でタイトルへ戻り、タイトルでさらにA/B解除後に再押下するとStage 1から完全な新規ゲームを開始する。ALL CLEARだけはA/B解除後の再押下で直接Stage 1から完全再開始する。

ボスはHP、24〜28px級の大型AABB、停止位置、撃破得点、移動方式、攻撃スクリプト範囲を固定設定表から取得する。最大HPはStage順に60、90、120、得点は2000、3000、5000。攻撃手順は直線、上下3方向扇状、上下砲門交互、上下挟撃、短周期バーストを固定データとして組み合わせる。敵弾は固定16発へ拡張し、各弾の速度を符号付き整数で保持する。通常敵弾は従来の左2px、ボス弾は左2pxと上下0〜1pxだけを使う。

BOSS中は自機弾1発をHP1として解決し、HP0になった更新では撃破を優先してボスの追加移動・射撃・接触を行わない。非最終死亡では現在のステージとフェーズ、通常区間経過、ボスHP、得点、武器Lvを保持する。ボス戦ならボス位置・移動位相・攻撃手順を初期化し、通常区間なら敵編成を初期化して60更新無敵で再出撃する。Stage固有の背景、通常敵編成、ボス外観はAPS-009〜011からこの共通設定境界へ追加する。

## APS-009 Stage 1宇宙

Stage 1は`SPACE`背景テーマ、`SPACE`宇宙敵編成、Boss設定0、`SPACE_FORTRESS`ボス外観を4 IDからなる固定Stage設定で参照する。Stage 2は`SKY`/`AIR`/`AIR_CARRIER`、Stage 3は`CAVE`/`CAVE`/`ROCK_GUARDIAN`を同じ設定境界から参照する。背景は黒0、惑星1/3、遠景星2、近景星7の配色と、32x24惑星・遠景星10個・近景星7個による8/4/2更新の3層パララックスをStage 1専用テーマとして確定する。

宇宙敵はScout、Saucer、Dropperの3種とし、既存の相互に異なる8x8・2フレームマスクを維持する。初期編成はX=140/170/200/230、Y=47/23/70/38、Scout/Saucer/Scout/Dropper、直進/上下波形/急降下折返し/直進。発射間隔90/60/90/75、時間差進入、撃破後の決定的再配置、slot 3のDropper固定と強化アイテムをStage 1編成データから初期化する。

Stage 1ボスはHP60、24x16、停止位置(132,43)、撃破2000点の宇宙要塞/戦艦とする。24x16内の各26本の固定水平ラン2フレームで、左端の前方双砲塔、中央装甲/コア、右端の後部エンジンを色13/5だけで描き、共通アニメーションと同じ8更新ごとにコア/エンジンを点滅させる。各ランは符号付き中間座標で160x102へクリップしてからTGIへ渡す。攻撃は前方砲塔(130,47)から120更新の直線連射（20更新ごと）、中央砲口(130,51)から120更新の上下3方向扇状（60更新ごと）を撃ち、240更新で循環する。Stage 2/3のボス描画・攻撃とは設定/外観IDで分離する。

## APS-010 Stage 2惑星上空

Stage 2は`SKY`背景、`AIR`航空機編成、`AIR_CARRIER`ボス外観を固定Stage設定から参照する。Stage 2導入時に背景3層のoffset/counterを0へ戻す。空8を背景、山/地平線4、中景雲7、近景雲15とし、最背面の固定山並みを192px周期・8更新/1px、中景雲8群を160px・4更新/1px、近景雲5群を160px・2更新/1pxで動かす。すべて背景描画だけで地形衝突を持たない。

航空機はFIGHTER、BOMBER、SUPPLYの8x8・各2フレームを追加する。初期編成はX=144/180/212/244、Y=24/64/42/78、FIGHTER/BOMBER/FIGHTER/SUPPLY、straight/wave/dive/wave、発射72/96/72/84、位相0/18/36/54。slot 3 SUPPLYだけが強化アイテムを落とし、再配置はX=`184 + slot * 18`、Y=`14 + seed * 19 % 76`を使う。ドロップ能力は敵状態/設定データとして扱い、Stage 1 Dropperも維持する。

Stage 2ボスはHP90、28x14、停止(128,44)、撃破3000点の空中母艦とする。28x14・2色・2フレームの水平ランで飛行甲板、船体、3砲門、後部エンジンを描く。Xを128に保ち、2更新に1pxでY=32〜56を往復する。上・中・下砲門を順に使い、120更新の20更新間隔区間と120更新の15更新間隔区間を240更新で循環する。

## APS-011 Stage 3洞窟

Stage 3は`CAVE`背景、`CAVE`洞窟敵編成、`ROCK_GUARDIAN`ボス外観を固定Stage設定から参照する。Stage 3導入時に背景3層のoffset/counterを0へ戻す。奥壁1を背景に、岩陰/亀裂3、天井・床岩肌5、鍾乳石/石筍13を固定水平ラン/座標表で描く。奥壁模様は192px・8更新/1px、天井床は160px・4更新/1px、鍾乳石/石筍は160px・2更新/1pxで移動する。地形は視覚表現だけとし衝突を持たない。

洞窟敵はCAVE_BAT、ROCK_WORM、MINING_DRONEの8x8・各2フレームを追加する。初期編成はX=148/184/216/248、Y=22/72/44/82、BAT/WORM/BAT/DRONE、wave/dive/straight/wave、発射66/84/66/78、位相0/16/32/48。slot 3 MINING_DRONEだけが強化アイテムを落とし、再配置はX=`188 + slot * 18`、Y=`16 + seed * 23 % 74`を使う。slot 0〜2はBAT/WORMと3移動を循環し、slot 3はDRONEを維持する。

Stage 3ボスはHP120、24x24、停止(132,39)、撃破5000点の岩石守護生物とする。24x24・2色・2フレームの水平ランで岩殻、中央コア、上下の牙/鉤爪を描く。攻撃は90更新の静止周期バースト（10更新ごと中央弾）、120更新の静止上下挟撃（40更新ごと2発）、120更新の広域移動付き上下挟撃（60更新ごと2発）を330更新で循環する。移動フェーズは2更新に1pxでY=21〜57を往復し、方向に応じX=128/132を切り替える。撃破後はStage 3 CLEARを経てALL CLEARへ進み、画面成立後のA/B解除と再押下でStage 1から全状態を初期化する。

## APS-012 Stage固有環境ギミック

Stage固定設定へ環境IDを追加し、`NORMAL`だけで固有ギミックのイベント、移動、衝突、得点を更新する。既存の敵・両陣営弾・アイテムとは別に環境用固定2スロットを持ち、イベントカーソルは満杯時も進めて再試行しない。通常区間へ入るたびに全環境状態を初期化し、WARNINGへ出る境界、Stage移行、GAME OVER、ALL CLEAR、完全再開始では全活動物を消去する。死亡開始から爆発SFX完了までは環境状態、イベントカーソル、持続タイマー、間引き位相を凍結し、非最終再出撃後に同じ位置から再開する。

Stage 1の`ASTEROIDS`は8x8・1HP・最大2個で、通常経過60/240/420/600/780/960更新にX=152、Y=22/70/44/84/30/60へ生成する。生成更新は移動・衝突を省略し、以後1px/更新で左へ進む。通常敵への命中を先に解決し、まだ活動中の自機弾だけを小惑星へ当てる。破壊時は弾と小惑星を消して250点を一度だけ加算する。自機接触では小惑星を消して共通損傷集約へ渡し、無敵中も小惑星だけは消える。

Stage 2の`WIND`は150/510/870更新に上端Y=18/58/36、高さ24px、方向=上/下/上の3イベントを開始する。45更新の点線・矢印予告は無作用で、その後150更新だけ流線・矢印を表示する。有効帯と自機AABBが交差した場合、既存の2px方向入力を適用した後に2更新ごと1px押し、Y=10〜96へクランプする。風は自機以外を動かさず、損傷を与えない。イベント開始、予告→有効、有効→終了、押し間引きの位相は固定カウンタで決定する。

Stage 3の`ROCKFALL`は最大2スロットで、90/240/390/540/690/840/990更新にX=24/72/120/48/136/96/16、着地点Y=94の45更新予告を開始する。予告終了時に8x8岩石をY=10へ生成し、その更新は移動・衝突を省略する。以後X固定、Y+2px/更新で落下し、Y=94へ到達する更新も自機AABBを先に評価してから12更新の着地表示へ移る。落下中の接触も同じ着地表示へ進め、共通損傷集約へ渡す。岩石は自機弾で破壊できず得点を持たない。

NORMALの順序は、自機入力、環境イベント開始と風、自機発射、自機弾移動と通常敵命中、小惑星命中、敵弾・通常敵・アイテム更新、既存損傷検出、小惑星/落石移動と接触、損傷の1回集約、通常経過更新とする。ギミックは背景とHUD境界の後、通常戦闘物より前に描き、死亡中は凍結表示を許可する。それ以外の非通常フェーズでは描画しない。

## APS-013 効果音とStage別BGM（履歴設計値）

サウンドは純Cの75Hz固定シーケンサとLynx専用出力を分離する。純C側は音程ID、長さ、音量、波形種別からなる固定小配列、現在のBGM/SFXステップ、残り更新、固定1件の保留SFX、active/音程/音量/波形の論理出力だけを持つ。Stage 1は遅い宇宙アルペジオ、Stage 2は速い上昇飛行モチーフ、Stage 3は低く疎な洞窟モチーフを短い自作ループとし、曲ごとにテンポ・音域・音型を変える。

実装するBGMはStage 1が8ステップ・各15更新・全120更新、Stage 2が8ステップ・各5更新・全40更新、Stage 3が低音18更新、休符9更新、低音18更新、休符9更新、ノイズ音12更新、休符12更新の全78更新とする。論理音程は休符0と1〜16、音量は0〜31、波形はtone/metallic/noise/pulseの4種に固定する。SFX全長は射撃8、敵撃破12、取得15、WARNING 32、自機爆発32、STAGE CLEAR 36、Boss撃破48更新で、Boss撃破と保留CLEARの合計84更新とする。

この段落はAPS-013時点のBGM再生仕様である。APS-018でテンポ調整のため`sound_init()`と`sound_set_stage()`がBGMステップ・BGM由来のMIKEY出力を停止する期間があったが、APS-020でBGMシーケンサを復帰させ、SFX（channel B）と独立にBGM（channel A）が常時進行する構成へ戻した（詳細は下記「APS-020 BGM曲化・2ch復帰」）。

SFXは成功射撃、通常敵/小惑星撃破、実損傷開始、自機によるアイテム取得、WARNING突入、Boss HP0確定、STAGE CLEAR突入の7種。失敗射撃と無敵中の損傷条件では鳴らさない。同一更新に複数の通常敵または小惑星を破壊した場合は敵撃破音を1回へ集約する。SFXはBGMより常に優先して単一出力を完全に上書きする。優先度は射撃1 < 敵撃破2 < 取得3 < WARNING 4 < 自機爆発5 < STAGE CLEAR 6 < Boss撃破7。同一以上は現在音を破棄して新音を先頭から始め、低優先度は破棄する。同一更新のBoss撃破→STAGE CLEARだけはCLEARを固定1件保留し、Boss終了後に一度再生する。両音の合計を120更新未満、自機爆発を32更新以下に収める。GAME OVER/ALL CLEAR、Stage切替、完全再開始ではactive/保留を破棄する。

cc65 2.19は`lynx_snd_*` APIと4チャンネルの`MIKEY`音源レジスタを提供するが、標準音源ドライバはTimer 7の240Hz IRQと独自ストリームを使う。本作はホストと同じ75Hzを正本にするためこれを起動しない。`src/main.c`の薄いバックエンドは初期化時にcrt0のmute値を解除する`MSTEREO`（`0xFD50`）=0を一度設定し、その後は各描画フレームで同一入力による`game_update_logic()`群と75Hzの`game_sound_tick()`を終えた後に、channel Aの`0xFD20`〜`0xFD27`だけをvolatileな8-bitアクセスで更新する。`game_update()`はホスト互換ラッパーであり、Lynxのmain loopは直接呼ばない。停止時はvolume/controlを0とし、再設定はcontrol=0→shift/control-B/feedback→volume→reload→control=`prescaler|0x18`の公式順序を守る。OUT/DACとCOUNT、Timer 0/2/7、IRQ、表示、channel B〜D、attenuation/panningへは触れず、TGIのVBlank/ダブルバッファ動作を変えない。

論理音程1〜16はcc65 2.19標準音源ドライバの固定prescaler/reload表から連続16音を選んだ小表へ写像する。波形4種もfeedback、shift-low、control-Bの固定値だけを持つ。音程または波形が変わらない更新ではタイマーを再起動せず、音量だけが変わった場合はvolumeだけを更新する。

## APS-018 戦闘UI・速度・視認性

描画、入力取得、TGI表示更新、SFX tickは75Hzの描画フレームごとに一回だけ行う。Lynxアダプタは剰余0から`5/4`の固定分数スケジューラを進め、連続する4描画フレームで`1, 1, 1, 2`回、計5回の`game_update_logic()`を実行する。同じ描画フレーム内の追加更新にも、最初に一度だけ取得した同一入力を渡す。これにより状態遷移、進行タイマ、移動、弾、クールダウン、敵発射、環境、死亡、無敵はすべて1.25倍で決定的に進む。音のSFX tickはロジック追加更新には追従させず75Hzに固定するため、SFXは消失・二重開始・BGM化せず、既存の実時間長を保つ。

BGMテーブルとステージIDは、APS-018時点では`sound_init()`と`sound_set_stage()`が`bgm_active=0`としてBGMステップの進行・MIKEY出力を停止していたが、APS-020でBGMシーケンサを復帰させた（詳細は下記「APS-020 BGM曲化・2ch復帰」）。SFXの優先順位、保留Stage Clear、停止境界は変更していない。

HUDは0〜9行の黒い帯に3x5の自作文字で一行表示する。`S<stage> <phase><4桁進行> <5桁score> L<lives> W<weapon>`はNULを除く20文字で、4pxピッチ・開始X=2から最終文字の右端X=80まで、表示幅79px（160px画面の一行）に収まる。導入中のStage 1進行も中央表示ではなく同じphase/progress欄に出す。帯の下端は明色線で区切る。戦闘物のマスク、弾矩形、敵弾の描画はHUD下へクリップする。Stage 1の背景星は低コントラストの1px/2px背景レイヤーのままとし、その後に前景の高コントラスト白色・短横ラン+下端ドットで敵弾を描く。敵弾のAABB、16発上限、速度、発射順は変更しない。

通常敵は全9種を8x8の自作行マスク・2フレームで描く。Scoutは先端と尾翼、Saucerはリムとドーム、Dropperは貨物ポッドとハッチ、Stage 2/3の各敵も翼・機体・生物・ドリルが異なる水平ランで識別する。外観だけを変更範囲とし、既存AABB、座標、移動、発射、ドロップ、固定スロット上限、自機、ボスは不変とする。

## APS-020 BGM曲化・2ch復帰

APS-018でテンポ調整のため停止していたBGMシーケンサとBGM由来のMIKEY出力を復帰させ、BGM（MIKEY channel A）とSFX（channel B）を独立2ch構成にした。`SoundState`は単一の`SoundOutput output`ではなく`output_bgm`/`output_sfx`の独立2出力を持ち、`sound_tick()`は毎更新`update_bgm_output()`と`update_sfx_output()`を両方呼んでからBGMカーソルとSFXカーソルをそれぞれ進める。旧`select_output()`の「SFXがアクティブならSFXを、無ければBGMを選ぶ」排他選択（BGMを完全に上書きする実装）は廃止した。

`sound_init()`と`sound_set_stage()`は`bgm_active=1`に戻し、呼び出し時点のBGMをその曲の先頭から即座に鳴らす。APS-020時点の`sound_tick(sound, freeze_bgm)`は自機死亡中にBGMカーソルだけを凍結してSFXを進めていたが、APS-030で死亡開始時のBGM停止と、爆発SFX完了後の曲頭再開へ置換した。SFX優先度・同一以上先頭再始動・低優先度破棄・Boss撃破中のSTAGE CLEAR保留1件、Stage切替時の次曲頭切替、`sound_stop_all()`によるGAME OVER/ALL CLEAR時の停止は維持する。`game.c`の呼び出し構造（`game_init()`が末尾で`sound_stop_all()`を呼びタイトル画面を無音にし、`game_start()`がその後に`sound_init()`を呼び直してBGMを有効化する二段構成）はAPS-018以前からの既存構造のままで変更していない。この結果、タイトル画面は無音（新規タイトルBGMはスコープ外）、`game_start()`後のゲームプレイ中（Stage導入〜通常戦闘〜警告〜Boss〜Stage Clear）はBGMが鳴り、死亡中だけ停止する。ALL CLEARからの再開始（`game_start()`を再度呼ぶ）でもBGMは即座に復帰し、GAME OVER後は`return_to_title()`（`game_init()`のみ呼ぶ）でタイトルに戻るため無音のままである。

`src/main.c`はMIKEY channel B相当（`include/_mikey.h`の`channel_b`、`0xFD28`〜`0xFD2F`: `SOUND_B_VOL=0xFD28`, `SOUND_B_FEEDBACK=0xFD29`, `SOUND_B_SHIFT_LOW=0xFD2B`, `SOUND_B_RELOAD=0xFD2C`, `SOUND_B_CONTROL_A=0xFD2D`, `SOUND_B_CONTROL_B=0xFD2F`）のレジスタ定義と`sound_backend_apply_sfx()`を追加した。これは既存channel A実装（`sound_backend_apply_bgm()`、旧`sound_backend_apply()`を改称）と同一のレジスタオフセット・書込み規約（note/waveが変わる更新だけcontrol=0→shift-low/control-B/feedback→volume→reload→control=`prescaler|0x18`のフル再設定、volumeだけの変更はvolumeのみ再書込み）を持つ意図的な複製であり、共有ヘルパー化はしていない。`sound_backend_apply_bgm()`はBGM出力をchannel Aへ、`sound_backend_apply_sfx()`はSFX出力をchannel Bへ適用する。`MSTEREO`（`0xFD50`）は両ch unmute（0）のままで、Timer 0/2/7、IRQ、TGI表示制御、channel C/D、attenuation/panning、`lynx_snd_*`へは触れていない。

既存3Stage BGM表のうちStage 1（旧20/18）とStage 2（旧20〜24）の音量は、SFX（射撃22〜STAGE CLEAR/Boss撃破31）と常時同時に鳴っても聴感上つぶれない帯域（14〜18）へ調整した（Stage 1: 17/15、Stage 2: 14〜18の昇順/降順）。Stage 3（18/17/16）は既に同帯域内のため変更していない。休符配置・ループ長・音程進行そのものは変更していない。タイトル画面用BGMの新規追加はスコープ外のため行っていない。

聴感（実際に2ch同時再生した際の音量バランス・音色の衝突）とAtari Lynx実機でのCPU負荷・音質はAI実装では確認できず、未確認事項として残す。

## APS-021 コード整理(重複排除)

外部から観測できる挙動(75Hz同期、5/4ロジックスケジューラ、ゲームプレイ、HUD、音)を変えない前提で、以下の重複を排除した。

- src/main.cのサウンドバックエンドは、APS-020で意図的に複製していたsound_backend_apply_bgm()/sound_backend_apply_sfx()を、channel先頭アドレス(SOUND_CHANNEL_A/SOUND_CHANNEL_B)とレジスタオフセット定数を引数に取る単一のsound_backend_apply(channel, hardware, output)へ統合した。レジスタ書込み順・volume-onlyの差分更新規則は変更していない。
- src/main.cの背景スクロールは、3レイヤーで繰り返していた「分周カウンタを進めてピクセルオフセットを周期内でラップする」処理を1つの補助関数へまとめた。水平ラン描画(惑星地表、空/洞窟境界、ボス弾等)の画面クリップも共通のヘルパーへ集約した。
- src/game.cの敵発射間隔enemy_fire_interval()は9分岐のif連鎖から、GAME_ENEMY_TYPE_*で添字付けした固定テーブル参照へ変更した。ボスステップ数などのマジックナンバーには名前付き定数を与えた。
- src/sound.cのupdate_bgm_output()/update_sfx_output()も、ステップ値を論理出力へコピーする処理を共有ヘルパーset_step_output()へ統合した(この関数自体はAPS-022のコミットで導入している)。
## APS-022 MMLサウンドドライバ

BGMのステップテーブルを、テキストのMML風表記から生成する仕組みを追加した。

- 新規ホスト専用ツールtools/mml2c.c(C89、動的確保・浮動小数なし)が、assets/music/*.mmlを読み、const SoundStep配列と対応するカウント定数を持つCソース(build/gen/music_data.{h,c})を生成する。Lynx ROMはランタイムのテキストパーサを持たず、生成済みの固定配列だけをリンクする。
- MML言語は75Hzロジックtick単位のdurationを持つ簡易記法(t=既定長、v=音量、w=波形、o/>/<=オクターブ、c〜b=音階、n=直接インデックス、r=休符、;=コメント)。include/sound.hの16段階スケール・4波形(tone/metallic/noise/pulse)にそのまま対応する。
- assets/music/stage1.mml〜stage3.mmlは、APS-020で確定した既存3ステージBGM(音程・duration・volume・波形)をそのままMML表記へ移植したもので、生成されるSoundStep列はAPS-020のハードコード値とバイト単位で一致する(tests/test_sound.cのtest_bgm_exact_mml_migrationで固定回帰する)。したがってこのコミットではBGMの聴感は変化しない。タイトル画面用BGMの新規追加はスコープ外。
- Makefileはbuild/mml2cのビルドとbuild/gen/music_data.{h,c}の生成をROM/ホストテスト双方のビルド依存へ追加した。生成物はbuild/配下(.gitignore済み)でリポジトリにはコミットしない。
- 今後新曲を追加する場合はassets/music/*.mmlを書き足すかテキストを差し替えるだけでよく、SoundStep配列を手で書く必要がなくなる。Stage 2/3用のより長い曲やタイトル曲への展開は本コミットのスコープ外。


## APS-023 BGMの多声化(MIKEY channel C追加使用)

ユーザーがAPS-022完了時点のBGMを実際に聴き「BEEP音で曲ではない感じ」とフィードバックした。原因はBGM(channel A)が単声で和音・ベースラインを持たないことにあり、MIKEY未使用のchannel Cを新たに使いベースライン(第2ボイス)を追加して2声構成にした。これはAPS-020の「channel C/D・attenuation/panning・lynx_snd_*に触れない」制約を明示的に覆す設計変更(ユーザー承知の上)。3声目(channel D)は追加していない――2声化でユーザー報告の核心(単声・和音欠如)が解消されるため、聴感確認前に3声目まで踏み込むと設計・作曲・テストの手戻りリスクが増えると判断した(ISSUES.md APS-023のスコープ決定と同一理由)。

- `src/main.c`へ`SOUND_CHANNEL_C`(`0xfd30u`起点、`include/_mikey.h`のchannel Cレイアウトに基づく)を追加し、APS-021で統合済みの`sound_backend_apply(channel, hardware, output)`をそのまま第3チャネルへ適用した。新規レジスタ書込みロジックは実装していない(既存ヘルパーの再利用のみ)。`sound_backend_init()`が呼ぶ`sound_backend_silence_channel()`にもchannel C分(`sound_hardware_bgm_bass`)を追加し、main loop末尾の`sound_backend_apply()`呼び出しにもchannel C分を追加した。
- `include/sound.h`の`SoundState`へベース用の第2ボイスカーソル`bass_step`/`bass_remaining`と独立出力`output_bgm_bass`を追加した。既存の`bgm_step`/`bgm_remaining`/`output_bgm`(メロディ)の意味・挙動は変更していない。ベースカーソルはメロディと同じ`bgm_active`・`freeze_bgm`に従い、`sound_init()`/`sound_set_stage()`でメロディと同時にStage先頭へ復帰し、`sound_stop_all()`で同時に無音へ戻る。APS-030以降の死亡中は両voiceを停止し、非最終復帰時に両方を現Stage曲頭へ戻す。カーソル前進・読込のロジックはメロディ・ベースで完全に重複していたため、`load_step_cursor()`/`advance_step_cursor()`という2つの共有ヘルパーへ統合し(APS-021のDRY方針を踏襲)、`load_bgm_step()`/`load_bass_step()`と`advance_bgm()`(内部でメロディ・ベース両カーソルを進める)がそれらを呼ぶ形にした。
- `assets/music/stage{1,2,3}_bass.mml`を新規追加し、`tools/mml2c`(変更不要、`MAX_TRACKS=8`で6トラックまで対応可能)・`Makefile`の`MUSIC_TRACKS`/`MUSIC_SOURCES`へ追加した。ベースはo1中心の低音域・音量14〜18・tone/pulse波形のみ(noise/metallicはSFXやメロディの効果音的アクセントと衝突するため避けた)。各ステージのベースループの総duration(120/40/78 tick)はメロディのループ長と完全に一致させている――メロディより疎な(ステップ数が少なく1ステップが長い)構成にしつつ、両ボイスが毎ループ必ず同時にstep 0へ巻き戻る「フェイズロック」を保証するための設計判断で、独立ループ(非同期)は採用していない。具体的にはStage 1はメロディのg/d・a/eの2和音区間ごとにルート音(g→a)を1音ずつ保持、Stage 2はメロディの高速パルスラン全体を通してd→gの2音、Stage 3はメロディの休符混じりの不気味な動機に対しc→f→cの緩やかな低音ドリフトを充てた。
- `include/sound.h`/`src/sound.c`へ`sound_get_bgm_bass_step()`/`sound_get_bgm_bass_step_count()`を追加した。既存の`sound_get_bgm_step()`/`sound_get_bgm_step_count()`と対になるAPIで、ベーステーブルをテストから検証できるようにするための最小限の追加。
- `tests/test_sound.c`へ、ベーステーブルの値域(volume 14〜18・wave tone/pulse限定・note非休符)とメロディとのフェイズロック(ループ長一致)を検証する`test_bass_tables_bounds_and_phase_lock()`、生成された全ベースステップをMMLソースへ固定回帰する`test_bass_exact_mml_compile()`、開始・凍結・Stage切替・停止の同期挙動を検証する`test_bass_syncs_with_bgm_start_freeze_stage_and_stop()`を追加した。`tests/test_game.c`にも`game_start()`経由でベース出力がメロディと同時に有効化されることを1件追加した。
- 実装前後のROMサイズは36,587 bytes → 37,276 bytes(+689 bytes、+約1.9%)。ベーステーブル3曲分のデータと`sound.c`/`main.c`の追加ロジックによる増分。

聴感(実際にchannel A+Cの2声を同時再生した際に「曲らしく」聞こえるか、音量バランス・音色の衝突)とAtari Lynx実機での動作はAI実装では確認できず、未確認事項として残す。Gearlynxはヘッドレス起動でのプロセスレベル確認(ROM読み込み・クラッシュなし)のみ行った――本環境はScreen Recording/アクセシビリティ権限が無くGUI目視・音声確認ができない(APS-020以降の既知の制約と同一)。

### APS-023 コミット前リファクタ(ボイス数非依存化)

コミット前の見直しで、上記実装のメロディ/ベース並列構造をボイス数非依存の形へ整理した(挙動・公開API・`SoundState`レイアウト・生成される曲データは不変。全テストで回帰確認済み)。

- `src/sound.c`: ボイスごとの並列関数(`load_bgm_step()`/`load_bass_step()`/`update_bgm_output()`/`update_bass_output()`)を廃止し、`MusicVoiceRef`(あるボイスのシーケンス・カーソル・論理出力への参照ビュー)を`music_voice(sound, voice, ref)`で構築して共有ヘルパー`load_voice_step()`/`advance_voice_step()`へ渡す構造にした。`restart_bgm()`/`advance_music()`(旧`advance_bgm()`)/`update_music_outputs()`/`sound_stop_all()`は`MUSIC_VOICE_COUNT`のループで全ボイスを回す。公開アクセサの表引き(`sound_get_bgm_step()`系)も`music_sequence_tables[voice]`経由の共有ヘルパー`music_table_step()`/`music_table_step_count()`へ統合した。
- `src/main.c`: (MIKEYチャンネル先頭アドレス, `SoundHardwareState`, 論理出力)の3つ組を`sound_channel_map[]`テーブルへ集約し、`sound_backend_init()`とメインループ(`sound_backend_apply_all()`)はテーブルを反復する。レジスタ書込み順は従来のA→C→Bをテーブル行順で維持。
- 3声目(channel D)の追加は「`SoundState`へカーソル/出力フィールド追加+`music_voice()`に1分岐+`music_sequence_tables`/`sound_channel_map`に1行+カウント2箇所の更新」で済む構造になった(channel D自体の実装は引き続きスコープ外)。
- `tools/mml2c.c`は元よりトラック数非依存(`MAX_TRACKS=8`)で多声化による重複が生じていないため変更していない。
- このリファクタによるROMサイズ増は+175 bytes(37,276 → 37,451 bytes)。ヘルパー抽出とループ化に伴うコード生成の差分で、データ(曲テーブル)は不変。

## APS-026/027 音色設計(integrateモードとDC平衡LFSR)

APS-024の「きらきら星」差し替え後も「BEEP音のまま」、APS-026(integrateビット全チャンネル一律有効化+音量エンベロープ)後は「ブー、という唸り音」とユーザー評価が続いた。APS-027でGearlynx(`mikey_inline.h`の`AdvanceLFSR()`)を基に原理を確定し、音色設計を次のとおり改めた。

MIKEYのintegrateモード(controlレジスタbit5)は波形を滑らかにするフィルタではなく、タイマーunderflowごとに出力レジスタへ`±volume`を累積する(±127/-128でクランプ)累積器である。したがってintegrateが成立する必要十分条件は、LFSR出力ビット列の1周期内の1と0の個数が等しいこと(DC平衡)。APS-013由来の4波形はすべて不平衡(TONE -1/7、METALLIC -1/63、NOISE +4/6、PULSE +1/9)で、integrate下では累積器が数十tickでクランプ端に張り付き、低く歪んだドローン(=「ブー」)へ退化していた(`scripts/sim-mikey-lfsr.py`によるシミュレーションと、`scripts/verify-audio-output-acc.py`によるGearlynx実測の両方で確認)。

APS-027の設計:

- integrateは波形ごとの属性(`SoundWaveRegister.integrate`)とし、DC平衡な波形だけが立てる。
- TONEは`feedback=0x04`(tap2のみ)+`shift_low=0x07`、PULSEは`feedback=0x08`(tap3のみ)+`shift_low=0x0f`。単一タップkと下位k+1ビット均一シードの組はtwisted ring counter(1がk+1個→0がk+1個の完全平衡列)へ退化し、integrateと合わせて振幅`(k+1)*volume`のクリーンな三角波になる。旧矩形波の周期(7/9)から周期6/8への変更に伴い、一律+2.7/+2半音の移調が生じる(旋律内の音程関係は不変。曲データ・音程表は無変更)。タップはfeedback bits0-5のみを使う(bits6-7のtap10/11とcontrol bit7のtap7は、本作が初期化しないLFSR上位ビットを読むため使用しない)。
- METALLIC/NOISEはAPS-013の擬似ランダムパターンのまま非integrate。不平衡列のintegrateはドローンを再現するため。硬い音色はSFXアクセントとして意図的に残す。
- フル再設定時とサイレンス時に出力レジスタ(offset 2、`SOUND_REG_OUTPUT`)を0へ書く。integrate累積器の残留レベルの持ち越しと、無効チャンネルの残留出力がDCとしてミックスされ続けることを防ぐ。APS-013の「OUT/DACへ触れない」制約はこの目的に限り明示的に緩和する(任意波形PCM再生には引き続き使わない)。
- 音量エンベロープ(APS-026、`duration/5`tickで立ち上がり→70%へ減衰)は維持。三角波では振幅がvolumeに線形比例するため、エンベロープが初めて聴感へ反映される。

タイトル画面には`include/version.h`の`GAME_VERSION_STRING`(単一定義)を`"V" GAME_VERSION_STRING`として操作説明の下(x=52, y=90)に常時表示する。表示はタイトルフェーズのみで、ゲームロジック・入力・HUD・表示タイミングへは影響しない。

聴感の最終評価はユーザーの領分として残す(機械検証は「クランプ張り付きゼロの三角波が出ている」ことまで)。

## APS-030 全体4倍速化・自機爆発SFX完了同期

- 描画・入力・`game_sound_tick()`は75Hzのまま、`GAME_LOGIC_UPDATES_NUMERATOR/DENOMINATOR`を`4/1`とし、1描画あたり4ロジック更新・300Hz・基準75Hz比4.00倍で実行する。
- メロディ/ベースの共有BGMカーソルは非死亡時の1 sound tickで4回進める。両voiceの同一ループ長と共有進行を維持し、SFXカーソルは1回だけ進める。MML、生成音楽データ、ベースのnote/wave/volume/rest/durationは変更しない。
- 自機爆発SFXだけを、2 tickのmetallic初期衝撃と4/5/6 tickのnoise減衰尾部（音量31→27→21→13、合計17 tick）へ変更する。他6種SFXの全ステップ、優先度、Boss撃破→Stage Clear保留規則は不変とする。
- `sound_stop_bgm()`はBGMメロディ/ベースだけを即時無音化し、活動中SFXを保持する。`sound_sfx_is_active()`は指定SFXの活動状態だけを返す。死亡開始時にBGMを停止して自機爆発を開始し、死亡ロジックは同SFXが活動中である限り戦闘・環境・入力を凍結する。
- `explosion_timer`は描画側の既存4段階マスクを守るため31で飽和させるが、復帰条件には使わない。非最終ライフは爆発SFX完了後に現Stage BGMを曲頭から再開して再出撃し、最終ライフはBGMを再開せずGAME OVERへ遷移する。

## APS-031 タイトル短音声の実現性プロトタイプ

MIKEYにADPCM専用decoderはなく、4本の8-bit DAC `AUD0OUT`〜`AUD3OUT`へCPUが
sampleを書き込む方式を採る。現行A=melody、C=bass、B=SFXは保全し、タイトル専用
PCM候補を未使用channel Dへ割り当てる。Timer 3の8 kHz IRQでresident signed 8-bit
PCMを送る独立backendと、4-bit IMA ADPCMのC89 host/cc65 codecを追加したが、実音声と
game flow統合は行わない。方式比較、RAM上限、根拠URL、将来の入力/完了状態機械は
[`docs/plan/aps-031-audio-feasibility.md`](aps-031-audio-feasibility.md)を正本とする。

## APS-032 タイトル開始音声統合

タイトルのarmed後FIREは即`game_start()`せず`title_voice_pending`へ入り、ローカル
VOICEVOX Nemo男性2由来の「わしは宇宙の帝王ザカリテ」を8 kHz mono IMA ADPCMで
channel Dへ再生する。
再生中入力は無視し、完了観測一回でStage 1 INTROへ進む。自然長8,704-byte assetは
resident余地を超えるため、Lynx cartridge directory entry 1に保持し、2本の128-byte
compressed bufferへ先読みする。Timer 3 IRQ内の65SC02 assemblyが事前計算difference tableで
1 sampleずつ復号する。A/C=BGM、B=SFX、75Hz描画/入力/SFX、300Hz logic、BGM4倍は不変。
APS-037後の現行assetは17,408 samples・8,704 bytes。生成条件、ライセンス、cart layout、
容量、復号検証は
[`docs/plan/aps-032-title-voice.md`](aps-032-title-voice.md)を正本とする。

## APS-033 タイトル音声の16 kHz再生レート化

APS-032の8 kHz生成済みIMA ADPCM asset（17,555 samples、8,778 bytes、SHA-256
`2c8e8402f6b059de5e746b7513be97626f3301a0aba6f2644da62b82d5b30c6a`）と
cartridge layout、IMA形式を変更せず、Timer 3/channel Dの消費レートを2倍にする。
MIKEY Timer 3はcontrol Aのclock select 0で1 us tickとなり、counterはbackupから0まで進んだ
次のtickでborrowするため周期は`(backup + 1) us`である。APS-032のbackup 125は実効126 us
（7,936.508 Hz）だった。APS-033はbackup 62を選び、63 us（15,873.016 Hz、16 kHzに対し
-0.7937%、APS-032の実効rateの正確な2倍）とする。17,555 samplesの計算上の再生時間は
1.105965秒。backup 61/62を交互にする62.5 us平均（16 kHz exact）はIRQごとの分岐・書込を増やし、
固定reloadよりIRQ安全性を悪化させるため採用しない。

16 kHz化に対する最初のreload変更だけでは、cc65の共通IRQ walkを含む復号がsample周期を超え、
producerも128-byte 2-bufferのqueue切替期限へ間に合わずunderrunした。採用実装は音声再生中だけ
元のIRQ vectorを保存してタイトル音声専用vectorへ切り替え、復号code別のindexed jump table、
predictor加減算、次step index tableで1 nibbleを処理する。Timer 2等が同時pendingなら`callirq`へ
委譲するが、そこで生じたTimer 3 borrowは消さず同じIRQ内で復号する。完了/stop時はTimer 3と
channel Dを停止して元vectorを復元する。Gearlynx traceで17,555 Timer 3 IRQに対し17,555 sampleを
欠落なく出力し、全DAC列がC89 IMA referenceと一致した。

cartridge producerは128-byte compressed chunkのresident bufferを5本使う。current 1本、assemblyの
3段queue、mainline prefetch 1本に分け、queue境界の63 us raceとcart読込の揺らぎを吸収する。
開始入力受理後の約1.106秒はタイトル遷移gate内で`title_voice_pump()`を連続実行し、通常の描画・
logic/inputを進めない。Timer 2/VBlankは専用IRQから共通handlerへ委譲するため表示swapは停止しない。
再生中FIREを無視する既存仕様と開始後一回だけ`game_start()`する意味は不変で、音声外の75 Hz描画・
入力、300 Hz logicも不変。これは16 kHzでunderrunを避けるためのbuffer/実行方式差分であり、
asset、IMA codec、cart entry配置、A/C/B音声backend、Timer 0/2/7には変更を加えていない。

音声dataをtime-stretch・再合成していないため、再生時間が約半分になる代わりにピッチも約1 octave
上がる。pitchを保つ自然な速度変更ではない。タイトルのarmed→一回だけ再生→完了一回だけ
`game_start()`、再生中FIRE無視、非title/stopでTimer 3/channel Dを停止する状態機械、
A/C=BGM、B=SFX、Timer 0/2/7は維持する。

## APS-035 タイトル音声の再生レート復帰

APS-033の15,873.016 Hz再生が早すぎるというユーザー確認を受け、Timer 3/channel Dの
消費レートだけを半分へ戻す。Timer 3は1 us clock、backup 125、周期126 us、実効
7,936.508 Hzとする。17,555 samplesの計算再生時間は2.211930秒で、APS-033の高ピッチ化を
取り消したV0.33相当の設定である。8 kHz exactではなく、8 kHz生成済みassetを7,936.508 Hzで
消費する。

ADPCM asset（8,778 bytes、SHA-256
`2c8e8402f6b059de5e746b7513be97626f3301a0aba6f2644da62b82d5b30c6a`）、IMA codec、TTS/変換、
cart entryは変更しない。APS-033で導入した専用IRQ、128-byte 5 buffer、3段queue、連続pumpと
title gateも維持する。armed→一回開始→再生中FIRE無視→完了一回だけ`game_start()`、終了時の
Timer 3/channel D停止、A/C=BGM・B=SFX、Timer 0/2/7、75 Hz描画/入力/SFX・300 Hz logicは不変。

## APS-036 出力gainとGAME OVER音声

BGMメロディ/ベースと全7 SFXは、MML/SFX table、note、wave、duration、priority、envelopeの論理値を変更せず、`src/main.c`がMIKEY channel A/C/Bへ書く直前だけ`floor(volume*3/4)`を適用する。非zero入力は最低1とし、境界は`0→0, 1→1, 2→1, 3→2, 4→3, 31→23`。channel Dのsigned DAC sampleにはこのgainを適用しない。

APS-036では「お前は弱かった」の8 kHz mono IMA ADPCMをcartridge directory entry 2へ追加し、entry 1のタイトルassetと128-byte 5 buffer、3段queue、専用IRQ、Timer 3 backup 125（126 us、7,936.508 Hz）、channel Dを共有する構成にした。APS-037で両assetだけをVOICEVOX Nemo男性2へ差し替えたが、このcart/runtime構成と再生中start拒否による排他は不変。

最終ライフの爆発SFXを`sound_sfx_is_active()`が非活動として観測した更新だけが`game_over_voice_pending=1`へ進む。非最終死亡は再出撃し音声を開始しない。main loopはGAME OVER画面を先に表示してからblocking pumpで一度だけ再生し、完了APIがpendingをclearしてcompleteを立てる。complete前はA/Bを無視し、完了時にFIREが押下済みでも`restart_armed=0`のままなので、従来どおりrelease→press後だけタイトルへ戻る。

GearlynxのGAME OVER回帰は、実ROMが安定したTITLEへ到達したことを`stage=1`・`phase=TITLE`で確認してpauseし、cc65の現行`GameState`/`SoundState`レイアウトに対応する`lives=0`、`dying=1`、爆発SFX最終stepを注入する。その後はROM自身の`update_player_death()`でpending化し、現行assetの全Timer 3 IRQと全DAC sample、停止、入力gateを検査する。release→press確認はhost側の固定waitを合否条件にせず、`restart_armed=1`と`game_over=0`・`phase=TITLE`を期限付きpollで同期する。復帰押下を保持したままTITLEが8 poll安定し、`title_voice_pending=0`を維持することも確認して、同じ押下の再利用を防ぐ。

## APS-037 VOICEVOX Nemo公開可能音声

タイトルとGAME OVERの生成元を公式VOICEVOX Nemo 0.24.0の男性2（エンジン表記`男声2`、UUID `7ecc7a17-1465-4b22-a3b5-842a110ff55e`、`ノーマル` style ID `10000`）へ統一する。合成設定はspeed 0.9、pitch -0.08、intonation 0.9、volume 1.0。localhost限定の公式arm64 engineから8 kHz mono signed 16-bit PCM WAVを生成し、既存C89 encoderでIMA ADPCM low-nibble-firstへ変換する。既定post-phoneme 0.1秒は既存decoder回帰に合わせて800 sampleのexact zeroへ正規化する。タイトルは17,408 samples・8,704 bytes・SHA-256 `99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2`、GAME OVERは11,691 samples・5,846 bytes・SHA-256 `848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f`。

公式VOICEVOX 0.25.2 arm64 DMGとNemo Engine 0.24.0 arm64 VVPPをrepo外へ導入し、配布APIのSHA-256と取得ファイルを照合した。実行はarm64 nativeでRosettaを使わず、外部API・外部送信・Personal Voice・第三者音声素材は使わない。`scripts/generate-title-voice.py`はversion、speaker UUID/name、style ID/nameを生成前に照合し、8 kHz mono 16-bit WAV以外を拒否する。offline strict verifyはinstaller/engine/editor version、license、credit、固定query hash、WAV format、PCM正規化条件、sample count、最終ADPCM hash、metadata/headerを検査する。raw WAVと正規化PCMのSHA-256は各生成runのprovenanceとして形式だけを検査し、run間完全一致を要求しない。VOICEVOXのraw PCMは変動してもlossy IMA ADPCMが同一になる実測があるため、決定性境界はROM同梱の最終ADPCM、sample count、生成header、cart payloadとする。host回帰でも異なるPCM hashが同じADPCM/sample count/headerへ収束する量子化境界を固定する。

Timer 3 backup 125、channel D、gain非適用、5 buffer/3段queue、cart 3 entry、title完了遷移、GAME OVER release→press gateは変更しない。タイトルには操作行とversionの間へ固定クレジット`VOICEVOX:Nemo（男性2）`を表示する。ASCII部分はTGI font、ASCII非対応の日本語suffixは5x7 bitmapで描き、160x102内のy=82..88に収めてversion y=90と重ねない。

最終LNXは59,867 bytes、SHA-256 `e5b619b56eadb1fff3fe8655db1f9314b64b2e6bc06ea25d06bb07ae6a109d32`。BSSは`0xB1E2..0xB6CE`、C stack開始`0xB838`、残余361 bytes。title entryはblock 44/offset 197/cart offset 45,253、GAME OVER entryはblock 52/offset 709/cart offset 53,957で、両payloadはchecked-in assetと一致する。

2026-08-09確認のNemo規約はクレジットを条件に生成音声の商用・非商用利用を許諾する。禁止事項、ソフトウェア規約、再許諾時の遵守条件、一次資料URLは`assets/voice/LICENSE.md`へ固定し、ROMには公式software/modelではなく最終ADPCMだけを同梱する。

## APS-038 共有voice center-preserving +25% saturating gain

title/GAME OVERの共有streamだけを大きくし、BGM/SFXの75% hardware gain、両ADPCM asset、
VOICEVOX生成条件、Timer 3 backup 125、channel D、queue/IRQ、状態機械を変更しない。
Lynx Sound Overviewは`AUDxOUT`を直接書ける独立8-bit DACとし、`AUDxVOL`はpolynomial bitを
通常モードで正負volumeへ変換、integrateモードでrunning totalへ加算する値と説明する。
cc65 V2.19のaddress定義とGearlynx main `f0be31d2c33da1e9b5d4cb1fe93c34b6dc34af70`
（volume/outputを別registerとして保持し、mixerはoutputを直接読む）も一致する。このため、
停止したpolynomial generatorの`AUD3VOL`を増やしてもCPUの`AUD3OUT`直書きは増幅されず、
PCM側gainを採用する。

復号後signed DAC byteを`u = byte XOR 0x80`でunsigned center 128へ移し、中心からの振幅を
`floor(abs(u - 128) * 5 / 4)`（端数は絶対値を0方向へ丸め）として元の符号を戻し、
`-128..127`へsaturateしてから`u' XOR 0x80`相当のsigned byteへ戻す。0は必ず0、clamp前の
正負同振幅は対称である。`scripts/generate-title-voice-gain.py`が256-byte tableを生成し、
C89 referenceとassembly includeの全entry一致、両asset全sampleのgain前後範囲・peak・center・
clamp・silent tailを検査する。IRQの共有`decode_complete`はpredictor high byteをindexに
1回lookupするだけで、title/GAME OVERへ同じgainを一度だけ適用する。

## APS-034 カラーspriteとJSON stage authoring

`assets/stages/stages.json`をStage 1〜3のauthoring正本とする。Python 3標準libraryだけを使う
`scripts/generate-stage-data.py`が、重複JSON key、未知/欠落key、型、C整数域、ID参照と未参照定義、
3 stage・4 slot、画面外spawn、respawnの`unsigned char` wrap、発射位相、boss rectangle/script、
environment eventのkind別範囲とstrict order、sprite grid寸法/文字/色role/run上限をfail-fast検査する。
検証後に`build/gen/stage_data.{c,h}`と`build/gen/sprite_data.{c,h}`だけをROMへリンクし、JSON parser・
文字列ID・外部dependencyはROMへ入れない。文字列IDは入力順の密なC IDへ変換し、boss scriptの
offset/countとenvironment eventのoffset/countもgeneratorが算出する。

移行対象はStage設定、3 formationの初期4 slotとrespawn式パラメータ、9 enemy type/movement/fire、
3 bossのcollision/HP/score/appearance/script、7 boss step、3 environmentの全16 eventである。
`tests/golden/stage-data-v034.json`はこれら全値のcanonical snapshot SHA-256を固定し、authoring値が
0.34.0挙動から逸脱すると生成前に失敗する。既存ゲーム回帰は同じ生成C tableをリンクし、Stage設定、
formation、respawn、boss、environmentの既存固定値検査を継続する。phase尺、移動運動学、画面/HUD、
4敵/16敵弾/12自機弾、操作、score、75Hz描画・入力1回/描画・300Hzロジックはengine固定のままである。

palette index 0〜5はStage別背景theme、6〜15は全Stage固定roleとする。固定roleは6=`DANGER` `$F2C`、
7=`PLAYER_GLOW` `$9FE`、8=`PLAYER_HULL` `$F64`、9=`PLAYER_DEEP` `$348`、
10=`ENEMY_HULL` `$E93`、11=`ENEMY_DARK` `$842`、12=`GLOW_YELLOW` `$FD5`、
13=`MINERAL_VIOLET` `$84D`、14=`MINERAL_TEAL` `$3CB`、15=`WHITE` `$FFF`である。
generatorはLynx TGIの16個のhigh nibble + 16個のlow byteからなる32-byte paletteへ変換する。
`src/main.c`は起動後の最初のStage描画とStage番号変化時だけ`tgi_setpalette()`を呼ぶ。

自機、9通常敵、3 bossはすべてauthoring gridから生成した2-frame水平run spriteで、各frameは3〜4色、
最大20 run、collision rectangle内に限定する。自機は淡青glow/珊瑚hull/深青、Stage 1/2通常敵は
琥珀hull/暗褐outline/黄glow、Stage 3通常敵と最終bossは紫/青緑の鉱物生命体として描く。
既存のenemy type、AABB、攻撃、移動、drop、boss HP/攻撃手順は変更しない。

APS-040では同じ13 spriteのID・順序・寸法・roleを保ったまま固定gridだけを詳細化した。自機は右向きの
機首、canopy、engine flare、Stage 1/2通常敵は迎撃drone、rim付きsaucer、開閉claw、bankするfighter、
engine pod付きbomber、container droneとして輪郭を分離する。Stage 3通常敵はdown/upstrokeのbat、
曲がる鉱物worm、drill/coreを持つmining droneとする。bossはcoral bastionの反応炉/command slit、
amber carrierの薄い横長nacelle/bridge、violet geodeの非対称facet/nucleusをframe間で変える。
`tests/golden/sprite-data-v040.json`は`sprite`配列だけのcanonical SHA-256を固定し、Stage挙動goldenとは
独立に意図しないgrid変更を拒否する。host C回帰は全26 frameのrun数、dense offset、寸法、role、
3〜4色、20 run上限、frame差を固定する。JSON/hash/parserはROMへ入れず、runtime描画とAABBは不変である。

## APS-041 タイトルvoice完了後の静止待機

タイトル開始voiceの全sample再生と`title_voice_stop()`後もTITLEを保持し、Stage 1へ遷移する前に
75 Hz描画tick基準で38 tick静止する。0.5秒は37.5 tickなので短縮せず`ceil(0.5 * 75) = 38`へ
切り上げ、実時間は`38 / 75 = 0.506666...`秒とする。公開定数
`GAME_TITLE_POST_VOICE_WAIT_TICKS`を38とし、TITLE開始gateの既存1-byte fieldsを待機状態と残りtick数に再利用する。
GameStateのレイアウトとGearlynx検証器の既存offsetは変更しない。

`game_title_voice_complete()`はvoice pendingを待機状態へ変えて残り38 tickを設定するが、
`game_start()`は呼ばない。300 Hzの`game_update_logic()`は待機中の全FIREを無視して状態を進めず、
main loopが4 logic updateの後に各outer draw frameで一度だけ呼ぶ既存`game_sound_tick()`だけが
残数を減らす。最初の37回はTITLE、BGM停止、player/enemy/bullet/score/Stage timer凍結を維持し、
38回目だけが`game_start()`を一度呼んでStage 1 INTROとBGMを開始する。voice開始失敗時もmainの
既存complete経路から同じ待機へ入る。boot TITLEのrelease→press、voice中FIRE無視、GAME OVERの
voice/release→press TITLE復帰、ALL CLEAR再開始、Timer 3/queue/IRQ/DAC、A/C BGMとB SFXは不変とする。

## APS-042 固定sprite高解像度化

rendererと固定horizontal-run RLE（`x0,x1,y,color`）は変更せず、`GameSpriteDefinition`のvisual
canvasだけを自機12x10、通常敵9種12x12へ拡大する。既存`GameRect.x/y`をvisual左上anchorとし、
追加pixelは右/下側へ描く。collisionは自機8x6・通常敵8x8、bossは従来どおり24x16 / 28x14 /
24x24であり、AABB、移動境界、spawn、発射、難易度、攻撃、drop、boss scriptは変更しない。
class別run上限はplayer 16、normal enemy 18、boss 28、全26frame合計上限524とする。

| sprite | visual / collision | palette roleとStage背景からの分離 | 左scroll時の輪郭・2frame差 | run(frame 0/1) |
|---|---|---|---|---:|
| player | 12x10 / 8x6 | `9`深青outline、`8`珊瑚hull、`7`淡青canopy/flare | 右向き機首と後部keel、flare/翼端位置を交互化 | 7/7 |
| scout | 12x12 / 8x8 | `B`暗褐outline、`A`琥珀胴、`C`黄sensor | 進行側visorと後端灯、翼tip/sensorを交互化 | 10/10 |
| saucer | 12x12 / 8x8 | `B`rim、`A`dome、`C`beacon | 横長rimを維持しbeacon/prong位置を交互化 | 9/9 |
| dropper | 12x12 / 8x8 | `B`claw、`A`cargo body、`C`core | 上部sensorと下向きclaw、claw開閉を交互化 | 12/12 |
| fighter | 12x12 / 8x8 | `B`尾翼、`A`hull、`C`cockpit/engine | 右向き長い機首、上下bank位置を交互化 | 9/9 |
| bomber | 12x12 / 8x8 | `B`pod/bay、`A`重装胴、`C`engine | 幅広胴と左右pod、flare/bay間隔を交互化 | 10/10 |
| supply | 12x12 / 8x8 | `B`container rim、`A`cargo、`C`識別灯 | 縦長containerと吊下部、antenna/beaconを交互化 | 10/10 |
| cave_bat | 12x12 / 8x8 | `B`翼outline、`D`紫膜、`E`青緑eye | 左右翼のdownstroke/upstrokeを大きく切替 | 9/9 |
| rock_worm | 12x12 / 8x8 | `B`seam、`D`紫鉱体、`E`青緑facet | 右端headから続くS字の節曲がりを交互化 | 8/8 |
| mining_drone | 12x12 / 8x8 | `B`drill/arm、`D`装甲、`E`採掘core | 中央drillとside arm/core位置を交互化 | 8/8 |
| coral_bastion | 24x16 / 24x16 | `B`装甲、`A`shell、`C`reactor、`F`slit | 高い要塞輪郭、reactor幅/slit位置を交互化 | 15/15 |
| amber_carrier | 28x14 / 28x14 | `B`nacelle、`A`hull、`C`engine、`F`signal | 薄い横長carrier、左右engine/signalを交互化 | 14/14 |
| violet_geode | 24x24 / 24x24 | `B`edge、`D`plate、`E`fissure、`F`nucleus | 非対称facetのoffsetとnucleus幅を交互化 | 20/20 |

実run総数は282でAPS-040から不変。authoring実値の通常画面worst-caseはplayer 7 + 4 enemies x 12 =
55 calls/draw、boss画面はplayer 7 + boss 20 = 27 calls/draw。class上限での予算88/44以内でもある。
`tests/golden/sprite-data-v042.json`が
全13 sprite/26 frameのcanonical authoring SHA-256を固定する。host generator/testはvisual canvasと
collision定数を別契約として検査し、全runのcanvas内、固定role、2frame差、dense offsetを検証する。
JSON/hash/parser、raster展開buffer、動的確保、runtime圧縮解除はROMへ追加しない。

## APS-043 固定sprite密度化

APS-042のvisual/collision分離、左上anchor、fixed horizontal-run RLEを維持し、全13種・2 frameを
外周だけではない密度ある1px dot artへ再設計する。visualはplayer 12x10、通常敵12x12、boss
24x16 / 28x14 / 24x24、collisionは8x6 / 8x8 / boss同寸法のままとする。各frameは3〜4 roleを使い、
outlineとshadowの暗部、主面、highlightまたは発光機能部を行ごとの1px輪郭変化で分ける。

| sprite | visual / collision | cells(frame 0/1) | 使用色・silhouette / outline / highlight / shadow / 構造 | 2frame差・左scroll識別 | run |
|---|---|---:|---|---|---:|
| player | 12x10 / 8x6 | 55/55 | `9`上下/側面outlineとshadow、`8`hull/翼面、`7`canopy highlight。右端まで伸びる機首と段差keel | 上面outlineを1px右へ移し、右端の長い機首を維持 | 7/7 |
| scout | 12x12 / 8x8 | 49/49 | `B`sensor外殻/shadow、`A`装甲面、`C`進行側visor highlight。左右非対称の偵察艇 | B/A/Cの前後を反転し、scroll中のvisor blinkを明示 | 10/10 |
| saucer | 12x12 / 8x8 | 50/50 | `B`dome/rim outline、`A`上下殻、`C`発光rim。B/A/Bで囲む横長円盤 | domeと上下殻を反転し中央rimを固定 | 9/9 |
| dropper | 12x12 / 8x8 | 50/50 | `B`claw/外殻shadow、`A`cargo胴、`C`core/投下口highlight。B/A/Bの中央pod | C/Bの上下位置を反転し、下側投下口をblink | 12/12 |
| fighter | 12x12 / 8x8 | 50/50 | `B`尾翼/outline、`A`細長hull、`C`canopy/engine highlight。右向き非対称bank翼 | silhouetteを左右へ2px振り、長い進行側機首を維持 | 9/9 |
| bomber | 12x12 / 8x8 | 64/68 | `B`上下面pod/shadow、`A`重装hull、`C`bay/engine highlight。6層の幅広胴 | B/Cの前後位置と外形幅を交互化 | 10/10 |
| supply | 12x12 / 8x8 | 49/49 | `B`container rim/shadow、`A`cargo面、`C`識別灯/lock highlight。左右非対称の輸送箱 | B/C端部を反転し、scroll中の識別灯をblink | 10/10 |
| cave_bat | 12x12 / 8x8 | 48/48 | `B`翼端outline/body shadow、`D`紫翼膜、`E`青緑内膜highlight。左右分離した翼端 | split wingを2px gapから4px gapへ広げるstroke差 | 9/9 |
| rock_worm | 12x12 / 8x8 | 55/55 | `B`節seam/head shadow、`D`紫鉱殻、`E`青緑facet。斜行する6層segment | B/D/Eの左右headを反転し、帯状の節を識別 | 8/8 |
| mining_drone | 12x12 / 8x8 | 52/52 | `B`外殻/drill shadow、`D`装甲、`E`採掘core highlight。先端を絞ったdrill body | 上下を反転しdrill tipとcore面を交互化 | 8/8 |
| coral_bastion | 24x16 / 24x16 | 134/134 | `B`砲郭outline、`A`珊瑚shell/shadow、`C`reactor highlight、`F`command slit。B/A/F/A/B中央砲塔 | C reactorとF slitを左右へずらし、上下砲郭を維持 | 15/15 |
| amber_carrier | 28x14 / 28x14 | 154/154 | `B`nacelle/bridge outline、`A`hull面/shadow、`C`engine highlight、`F`signal。薄い大型母艦 | C engineとF bridgeを左右へずらし、長いhullを維持 | 14/14 |
| violet_geode | 24x24 / 24x24 | 144/144 | `B`facet edge、`D`紫plate/shadow、`E`青緑fissure、`F`nucleus highlight。B/D/E/F/E/D/B多層結晶 | 上部facetを左右へずらし、中央nucleusと裂け目を固定識別点にする | 20/20 |

run列は`7/7,10/10,9/9,12/12,9/9,10/10,10/10,9/9,8/8,8/8,15/15,14/14,20/20`、
合計282でAPS-042と同一とする。通常画面worst-case 55、boss画面27 draw call/drawも不変である。
`tests/golden/sprite-data-v043.json`のcanonical SHA-256とhost generator/C testで、ID、visual/collision、
run数、3〜4 role、上表cell下限、canvas内run、2frame差、dense offsetを固定する。runtime renderer、
GameState、AABB、stage/formation/boss/environment/palette、sound/voice/cartは変更しない。

GUI editorは対象外で、後続実装に残す要件は、schema-aware form/grid編集、ID rename時の参照一括更新、
palette role preview、2-frame onion-skin、run数/rect/rangeの入力中表示、formationとenvironment timeline、
生成前validation結果のpath付き表示、canonical JSONの安定した整形とatomic保存である。GUIがJSON以外の
独自正本やROM parserを増やすことは禁止する。

Gearlynx headless表示回帰は、TITLE到達をpollしてpauseし、`GameState`のINTRO/WARNING終端を
注入した後、`phase` write breakpointで正規NORMAL/BOSS遷移を捕捉する。さらに
`_game_update_logic` execute breakpointを8回捕捉し、300 Hz logicの2描画分とdouble-buffer
swapを完了してから、Stage 1〜3のNORMAL/BOSS、`boss.active`、生成32-byte palette、front
buffer PNGを検査する。host固定sleepをphase判定に使わない。これは状態注入地点からの遷移・
描画回帰であり、Stage 1開始からStage 3までの連続playthroughや通常phase全尺の代替ではない。

## APS-044 自機16x16単体A/Bプレビュー

APS-043のplayerを変更せず、採用判断だけに使うpreview正本を
`assets/previews/aps044-player-preview.json`へ分離する。A/Bとも16x16・右向き・単一frameで、
hardware role `9=#334488`（outline/shadow）、`8=#FF6644`（hull）、
`7=#99FFEE`（canopy）、`C=#FFDD55`（engine）のみを使う。外部素材、生成画像、
`assets/stages/stages.json`からの流用、runtime/ROMへの取込みは行わない。

### A: delta-wing

```text
................
................
.....999........
....98889.......
...98888899.....
..9888887779....
C988888977789...
C9.8888988889...
.9.88888988889..
..9..8888988889.
...9...888998889
....9....88889..
.....99....99...
................
................
................
```

- 94 cells（`9=32, 8=54, 7=6, C=2`）、外接16x11、fill 53.4%、44 horizontal run。
- 上下段差を持つdelta主翼、1pxの右端機首、3x2 canopy、左端1x2 flare、後部切り欠き。
- 原寸判読性: 3x2 canopyと細い機首を固定識別点とする。右向き: 右端3列の着色数4/2/1。
- 部位分離: canopy/engine/nose/main wing/nozzle notchの5点をhostで検査。背景耐性: 透明と
  `#111122`の両方で同じ94 foreground pixelを照合する。
- 12x10移植概算: 直接縮約では約58〜62 cells・27〜31 run。player上限16 runへ収めるには、
  採用後に翼内shadowと下側段差を統合する別authoringが必要。
- 既存fighterとの差: player固有の淡青canopy/黄engine、幅広delta主翼、下側keelを持ち、
  `A/B/C`色の細いbank fighterや左側engine表現のない敵silhouetteと分離する。

### B: twin-boom-heavy

```text
................
................
....999.........
...988899.......
..9888888999....
.988888997799...
CC988889877889..
CC9.8889888899..
.9..8889..88889.
..9.88899.888889
...988898..889..
....98899...9...
.....999...9....
......9.........
................
................
```

- 100 cells（`9=41, 8=51, 7=4, C=4`）、外接16x12、fill 52.1%、49 horizontal run。
- 上側主胴と下側boomを透明gapで分離した重装輪郭、1px機首、2x2 canopy、左端2x2 flare、
  下側垂直尾翼。上下非対称をAより強くする。
- 原寸判読性: 2x2 canopy、2x2 flare、中央gapを固定識別点とする。右向き: 右端3列の
  着色数5/2/1。部位分離と背景耐性はAと同じpixel単位検査を使う。
- 12x10移植概算: 直接縮約では約62〜66 cells・30〜35 run。player上限16 runへ収めるには、
  採用後に上下boomの内部色分割を減らす別authoringが必要。
- 既存fighterとの差: twin-boom、2x2 engine、下側垂直尾翼による重装量感とplayer paletteで、
  単胴・bank翼・敵paletteのfighterから分離する。

評価対象は原寸での人間の判読性とA/B選択である。host検証は16x16、palette、4 role、
同色hull run最大6、3種以上のrow span、右端taper、機尾notch、上下非対称、5部位、PNG RGBA、
透明/暗色背景、8x nearest-neighbor、全pixel、SHA-256、独立一時directoryへの再生成byte一致までを
保証する。ゲーム画面、Gearlynx、ROM/LNX、runtime性能、12x10での最終見栄えは本課題の保証外とする。

### APS-044 v002 敵9種・boss3種16x16比較sheet

自機A/Bの正本・generator・既存8 PNGを変更せず、敵9種とboss3種のpreview専用正本を
`assets/previews/aps044-enemy-preview.json`へ分離する。全12体は16x16・単一frameで、ゲーム正本
`assets/stages/stages.json`のgridを参照・変換・流用しない。Stage 1/2通常敵は`B/A/C`、Stage 3通常敵は
`B/D/E`、coral/amber bossは`B/A/C/F`、violet bossは`B/D/E/F`の既存hardware palette roleだけを使う。
各gridは輪郭/暗部、主面、機種固有機能部、highlightを1px単位で分け、着色row span 3種以上、外形taper
または切り欠き、上下非対称、同色run 12px未満、bbox fill 85%以下を固定契約とする。

| ID / grid name | Cells / role cells | 1px silhouette・機能部・陰影 | normal sheet | boss sheet | all sheet |
|---|---:|---|---:|---:|---:|
| `scout` / `aps044_scout_preview` | 73 / `A40 B30 C3` | sensor wedge、前端sensor、段階taper、B shadow | 0,0 | - | 0,2 |
| `saucer` / `aps044_saucer_preview` | 65 / `A28 B27 C10` | offset dome、黄rim、下側B shadow/tail | 0,1 | - | 0,3 |
| `dropper` / `aps044_dropper_preview` | 65 / `A29 B33 C3` | cargo pod、C投下口、左右長の異なるclaw | 0,2 | - | 1,0 |
| `fighter` / `aps044_fighter_preview` | 68 / `A39 B27 C2` | bank wing、長い右nose、左下nozzle/keel shadow | 1,0 | - | 1,1 |
| `bomber` / `aps044_bomber_preview` | 92 / `A47 B41 C4` | 上部armored pod、C bomb bay、段差装甲shadow | 1,1 | - | 1,2 |
| `supply` / `aps044_supply_preview` | 69 / `A32 B34 C3` | cargo frame、中央C lock、非対称antenna/foot | 1,2 | - | 1,3 |
| `cave_bat` / `aps044_cave_bat_preview` | 53 / `B23 D22 E8` | swept split wing、D membrane、E body/eye、片側尾 | 2,0 | - | 2,0 |
| `rock_worm` / `aps044_rock_worm_preview` | 47 / `B24 D11 E12` | 斜行segment、B seam、E drill、屈曲shadow | 2,1 | - | 2,1 |
| `mining_drone` / `aps044_mining_drone_preview` | 66 / `B30 D27 E9` | asymmetric chassis、E core、右伸長drill、下部shadow | 2,2 | - | 2,2 |
| `coral_bastion` / `aps044_coral_bastion_preview` | 135 / `A75 B48 C8 F4` | coral spires、中央turret、C reactor/F slit、下部砲郭shadow | - | 0,0 | 2,3 |
| `amber_carrier` / `aps044_amber_carrier_preview` | 85 / `A43 B36 C4 F2` | offset bridge、上下nacelle、C engine、帯状でない段差hull | - | 0,1 | 3,0 |
| `violet_geode` / `aps044_violet_geode_preview` | 98 / `B28 D46 E16 F8` | offset facet、F nucleus、E fissure、B下端shadow | - | 0,2 | 3,1 |

sheet cellはrow,columnの0始まりである。`normal-enemies-sheet.png`は3x3・432x456、
`bosses-sheet.png`は3体横並び・432x152、`all-characters-sheet.png`はplayer A/Bを先頭にした14体の
4x4比較配置・576x608（末尾2 cellは背景のみ）とする。各tileは144x152、sprite boxはtile内
`x=8..135,y=8..135`、labelは3x5 bitmapを2倍した高さ10pxで`y=138..147`へ置き、spriteと重ねない。
全spriteは原寸gridを各source pixel 8x8 blockへ複製するnearest-neighborだけで拡大し、背景はexact
`#111122`、labelは白だけを使う。host validatorは12 ID/寸法/role/run/fill/span/非矩形/非対称/feature、
3 sheetの構成・寸法・全pixel・label領域・8x block、独立再生成byte一致に加え、v001正本/generator/8 PNGの
固定SHA-256とpixelを同時検証する。人間の16x16原寸判読性、実機LCD残像、採用後の12x10 runtime再設計・
run予算・2frame化は未確認であり、previewをゲームへ取り込まない。

### APS-044 v004 player/sheet検証の所有境界

v002で同じ`evidence/APS-044/`へ3 sheetを追加したため、player generatorがdirectory内PNGを
8枚だけに限定する検証は成立しない。player `--check`の所有対象を明示8 player PNGへ限定し、
他所有者の3 sheetとsheet generator所有の共有READMEは許容する。8 PNGについては存在、全pixel、
SHA-256、独立temporary directory再生成のbyte一致を従来どおり維持する。sheet generatorはplayer
generatorをPNG codec/raster helperとしてimportする前にsource hashを固定検証するため、その固定値だけを
新hashへ追従する。依存方向はsheet→playerの一方向であり、player側からsheet正本・generator・PNGを参照しない。

- `scripts/generate-aps044-player-preview.py`: `6209bc1e86e725232613c8b2b6dcb905dc3b5390bc9a437ce40f1e106ecab45b`
- `scripts/generate-aps044-character-sheets.py`: `6e7a4c0c0493d5ff6c86475dfbd3ed20f1ad82c4da84161ec5619d145fca40e4`

全11 PNGの固定SHA-256は以下で、v002からpixel/byteとも不変とする。

| Artifact | SHA-256 |
|---|---|
| `a-dark-8x.png` | `579e14a45713807261e025ae50b11e0008489a14fc61f0cd2a492aae68dcd9e1` |
| `a-dark.png` | `4dea3d93f42883368b6b1e28eaaba1e971906f2e0c669ccd0e4980c221b43926` |
| `a-transparent-8x.png` | `db9f98b72cb92c4622bcf9762d81d487001a84d6e8a9e40367b4d7720f37881d` |
| `a-transparent.png` | `429bd28826eab556f03f5e2e2263a1d3f1f89551169189f63d61ad35a86dbc01` |
| `b-dark-8x.png` | `6d31169b439aa5104655d72adf6608e3d9b39709e06c59ba0defb7f4d0daa613` |
| `b-dark.png` | `d37ca7ad659673ac0faa6469b9c58b28a5c4eceb050a21b8b4ab30db37ace7e5` |
| `b-transparent-8x.png` | `e06db89085ec0656ee065e1e98ae21ebbd4c6aca58f71fc8e1a9002830d7b078` |
| `b-transparent.png` | `89cd83951a3b9428db061a8a9ba740bcb401eec29c734219ccf040a5ff4a3523` |
| `normal-enemies-sheet.png` | `59ebddfaa534a8ea527d0f7a6864ac27da9f7d8758b40c648bf03ffc359dd01c` |
| `bosses-sheet.png` | `a5273b14231c43c3b0b239b256e2ec88c57c97b8116649dbfa341e3642fff66d` |
| `all-characters-sheet.png` | `c83f80e8b57052816ae7bb46a2a057b4eb9f81acc454845938798ff21326866b` |

## APS-045 承認previewの固定runtime canvas再authoring

APS-044の自機A案と敵9種・boss3種の16x16 previewを概念・配色・部位分離の正本とし、縮小変換を使わず、既存runtime canvasへ1px単位で手作業再authoringする。visual/collisionはplayer `12x10 / 8x6`、normal enemy `12x12 / 8x8`、boss `24x16 / 24x16`・`28x14 / 28x14`・`24x24 / 24x24`、左上anchorのまま。runtime renderer、AABB、移動、spawn、発射、難度、stage/boss config/script、state、sound/voice/cartを変更しない。

| sprite | cells(frame 0/1) / role cells | APS-044から固定する識別部位 | 2frame差 | run |
|---|---|---|---|---:|
| player | 50/50; `7=5/5 8=37/36 9=8/9` | A案の右向きdelta wing、先細りnose、上面canopy、下側keel、左engine | canopy/outline/keelを右へ1px移動 | 7/7 |
| scout | 49/49; `A25 B15 C9` | sensor wedge、前後sensor、段階shadow | sensor/wedgeの向きを左右反転 | 10/10 |
| saucer | 51/51; `A19 B21 C11` | offset dome、中央に切れ目を持つrim、下側shadow | dome/rim/tailを左右反転 | 9/9 |
| dropper | 50/50; `A36 B11 C3` | cargo pod、左右非対称claw、C drop port | claw/port位置を左右反転 | 12/12 |
| fighter | 48/48; `A27 B17 C4` | bank wing、長いnose、下側nozzle | bank/nozzle/noseを左右反転 | 9/9 |
| bomber | 64/64; `A35 B21 C8` | armored pod、分離bay、段差shadow | armor/bay/podを左右反転 | 10/10 |
| supply | 48/48; `A27 B16 C5` | cargo frame、C lock、非対称antenna | lock/cargo張出しを左右移動 | 10/10 |
| cave_bat | 54/54; `B20 D24 E10` | split swept wing、D membrane、E eye | wing gapを左右反転 | 9/9 |
| rock_worm | 52/52; `B18/19 D21/19 E13/14` | diagonal segment、B seam、E drill | 節列を逆傾斜へ変更 | 8/8 |
| mining_drone | 52/52; `B15 D23 E14` | asymmetric chassis、E core、伸長drill | drillを下側右端から上側右端へ移動 | 8/8 |
| coral_bastion | 149/149; `A83 B33 C19 F14` | 3 spire、分離turret、C reactor、F slit | 全部位を右へ1px移動 | 15/15 |
| amber_carrier | 145/145; `A84 B38 C19 F4` | bridge、分離nacelle、3 engine、段差hull | bridge/nacelle/engineを右へ移動 | 14/14 |
| violet_geode | 148/146; `B21 D101/99 E15 F11` | 3 facet、F nucleus、3条E fissure、段階plate | facet/nucleus/fissureを右へ1px移動 | 20/20 |

`scripts/generate-stage-data.py`は全13 ID、canvas、role、frame差、cell下限、run列と合計282に加え、上表のnose/canopy/engine/keel、sensor/wedge、dome/rim、claw/port、wing/nozzle、armor/bay、cargo/lock、split wing/membrane/eye、segment/seam/drill、boss spire/reactor/slit・bridge/nacelle/engine・facet/nucleus/fissureのframe別pixel座標を検査する。`tests/golden/sprite-data-v045.json`のsprites-only canonical SHA-256が残り全pixelを固定する。rendered pixelはGearlynxのhardware palette/front bufferと照合し、run/data容量はAPS-043と同一に保つ。

## APS-046 8体基準frame pacing・combatant上限

`GAME_MAX_ENEMIES=8`をruntime capacity、`GAME_STAGE_ACTIVE_ENEMIES=4`を既存Stageのauthoring/respawn数とする。combatantはNORMALの`active && rect.x < GAME_SCREEN_WIDTH`通常敵とBOSSのactive bossだけで、player、弾、environment、画面外pre-spawnは含めない。通常敵+bossの注入契約は8以下であり、8 normalまたは7 normal+1 bossを許可し、9を拒否する。Stage JSONはroot `combatant_limit=8`と各Stage `boss_coexists_with_normal_enemies=false`を持ち、既存formationは4枠のままなので難度/goldenを変えない。

Lynx側は8個の`GameEnemy` backingを静的BSSへ分離し、`GameState`はpointerだけを保持する。`GameEnemy`からstage dataで導出可能なfire interval/drop flagを除き、寸法固定のenemy bullet/power/environmentは`GamePosition`と外部定数でAABBを計算する。このpackingによりenemy capacityを倍増してもBSSは`0x4ED`を維持し、後続state fieldがcc65の256-byte境界を越えて生成codeを膨張させる問題も避ける。hostでは最初の4枠と追加4枠を分割inline保持し、`game_enemy_at()`で同じ8枠契約を検査する。動的確保は使わない。

各製品frameは入力1回、`4/1`ロジック、sound tick/MIKEY反映、draw/voice処理の後、`GAME_FRAME_END_WAIT(tgi_busy())`でhardware frame完了を待つ。`tgi_setframerate(75u)`だけをtiming sourceとし、敵数が少ないときの余剰をframe終端waitへ吸収する。8体時に処理が超過してもwaitが短縮または即完了するだけでlogic/input/soundをskipしない。75 Hzの理論間隔は13,333.333 us、12,000〜15,000 us wall-clockはadvisoryであり、hardware completionを合否基準とする。Gearlynx verifierは終端wait直後のmarkerを0/4/8体で各75回停止し、Timer 0/2状態、活動数readback、9体拒否をJSONへ保存する。

## APS-047 重み付き容量・75 Hz cadence・runtime sprite実証

APS-046の単純な頭数契約を重み付き容量へ置換する。公開定数はnormal=1、boss=4、limit=8で、通常敵は`active && rect.x < GAME_SCREEN_WIDTH`、bossは`active`だけを数える。player、弾、environment、画面外pre-spawnは非算入。4 normal+boss=8と8 normalを受理し、5 normal+boss=9、8 normal+boss=12、9 normalを拒否する。JSON rootの3定数と各Stageのcoexistence指定をgeneratorが同じ式で検査し、生成headerの値とruntime公開定数はpreprocessorで一致させる。既存Stageは4 normalのままなので難度・spawn・respawn・boss scriptを変えない。

製品loopの順序は`input poll -> logic x4 -> sound tick/hardware apply -> previous display completion sync -> draw -> display request`とする。Lynx TGI driverの`SWAPREQUEST`は`tgi_updatedisplay()`で立ち、VBLANKで解消されるため、前回swap pending中にinput/logic/soundを進め、completed back bufferを再利用する直前だけ`GAME_DISPLAY_READY_WAIT(tgi_busy())`で同期する。APS-046のframe終端waitと容量補償意図は撤去し、delay、logic/input/sound skip、敵数別更新数を持たない。`game_input_poll`、各logic、`game_sound_tick`、`game_display_sync_complete`、`game_display_request`をGearlynx breakpointで直接数え、0/4/8 normalと4 normal+bossの各75 drawで75/300/75/75/75を要求する。4 normal+bossはNORMALとBOSSを各75 draw測り、player +8px、bullet +16px、normal -4px、boss +2px/attack timer +4を同じcadenceとして固定する。MCP往復を含むwall-clockはadvisoryで、Timer 0/2とhardware event列を合否正本とする。

全13 sprite・26 frameはAPS-044 previewの識別部位を既存canvasへ1px単位で再authoringする。playerは12x10内に1px nose、canopy、テーパー/非連続delta wing、keel/notch、engine flareをrole別に持ち、旧stripe mutationを拒否する。通常敵9種とboss3種もwedge、dome/rim、claw/port、wing/nozzle、armor/bay、cargo/lock、split wing、segment/drill、asymmetric chassis、spire/reactor、bridge/nacelle、facet/nucleus/fissureを固定する。run列は`12/12,8/8,8/8,10/10,8/8,11/11,9/9,9/9,9/9,9/9,14/14,15/15,15/15`、合計274/予算524。各runを3 bytesへpackし、sprite RODATAを`0x3AB`に収める。

生成Cの`game_sprite_visit_runs()`をhost testと製品`draw_sprite()`が共有し、packed run decode、座標translation、color、frame、type→sprite、appearance→boss spriteを同じ経路で検査する。Gearlynx verifierは最終ROMからrun 822 bytes、definition 104 bytes、enemy/boss mappingを直接読み、JSONから再packしたcanonical値と照合する。その後にTITLEでAをrelease→pressしてStage 1 NORMALへ入った実プレイ画面、およびStage 1〜3 NORMAL/CAST/BOSSをheadless/GUIでcaptureし、GameState readbackとhardware palette framebuffer pixelを照合する。sync marker時点のGameStateは直前front bufferよりlogic 1 draw分先行し得るため、実プレイの移動敵だけはreadback originから±4pxを探索し、実際に一致したrender originを証跡へ併記する。これはstate injectionやpreview照合の代替ではない。
