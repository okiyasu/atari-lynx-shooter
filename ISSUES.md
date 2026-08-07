# ISSUES

最終更新: 2026-08-07(APS-026)

## 課題台帳

### APS-026: MIKEY integrateモード+音量エンベロープによる音色改善

- 状態: 実装完了・レビュー待ち(Dev、2026-08-07)
- 優先度: 中
- 起票日: 2026-08-07
- 基点: `69ce256`(APS-024完了時点のHEAD)。worktree `aps-026-timbre`(branch `feature/aps-026-timbre`)で作業。着手前`git status --short`はクリーン。
- 目的: APS-024の「きらきら星」差し替え後もユーザーから「BEEP音のまま」とフィードバック。APS-025の`scripts/verify-audio-gearlynx.py`でピッチ進行自体は正しいと確認済みで、RyokoがGearlynxソース(`mikey_inline.h`)を調査した結果、原因は(1)MIKEY制御レジスタのintegrateビット(0x20)未使用による鋭い矩形波、(2)音符にアタック/ディケイが無く音量が固定、の2点と判明した。
- スコープ: MIKEY integrateモードの有効化と簡易音量エンベロープの追加のみ。SFXの優先度・上書き規則、75Hz同期、5/4ロジックスケジューラ、既存BGM/SFXデータ(音程・duration)は変更しない。

#### APS-026実装実績(Dev、2026-08-07)

- 変更ファイル: `src/main.c`(`SOUND_INTEGRATE_MODE`定義追加、`sound_backend_apply()`の制御レジスタ書込みへOR)、`src/sound.c`(`envelope_volume()`新規、`set_step_output()`のシグネチャ変更と2箇所の呼び出し更新)、`ISSUES.md`(本項)、`.briefs/APS-026/v001.md`(新規、実施記録)。`include/sound.h`・音楽データ(`assets/music/*.mml`、`music_data`生成物)・テストデータテーブルは無変更。
- integrateモード: `sound_backend_apply()`の制御レジスタ完全書込み分岐で`pitch->prescaler | SOUND_TIMER_ENABLE | SOUND_INTEGRATE_MODE`を書き込むよう変更。**全チャンネル(BGM melody=A、BGM bass=C、SFX=B)で一律有効化**した。3チャンネル共通の1関数(APS-021で汎用化済み)であり、音色の要不要を分ける仕組みが元々無いため。
- 音量エンベロープ: `SoundStep`構造体は変更せず、`sound_tick()`側(`set_step_output()`経由)でステップ経過tick数から動的に`output->volume`を計算する方式を採用(既存データ構造・テーブルへの影響を避けるため)。最初の`duration/5`tick(最低1tick)で0→base、残りで base→70%baseへ線形減衰。`duration<=1`または`base==0`はenvelope無効(既存挙動のまま)。
- 検証結果(すべて終了コード0):
  - `make clean && ./scripts/verify.sh`: ゲーム524件PASS(無変更)、サウンド279件PASS(無変更、`step->volume`の生データを検査するテストはenvelope適用前のテーブル値をそのまま検査しているため期待値更新は不要だった)。cc65 2.19 `-W error`コンパイル・リンク、LNX検査すべて成功。
  - `scripts/verify-audio-gearlynx.py`(および同スクリプトのヘルパーを使った直接ポーリング)で`get_mikey_audio`のレジスタ生値を確認: 制御レジスタ(channel A `FD25`/channel C `FD35`)が`0x3B`(`=0x20|0x18|0x03`、integrateビット確認)、音量レジスタ(`FD20`/`FD30`)が0.15秒間隔ポーリングで固定値ではなく音符ごとに立ち上がり・減衰していることを確認(例: channel A `0F→0E→0D→0C→05→0B→11→...`)。ピッチ変化(`backup`レジスタ)も複数観測でき演奏継続を確認。
- ROM成果物: `dist/asteroid-patrol.lnx`、SHA-256 `293dcb08a0550549bfd174151214eb5eb30a1a6e0e74a4246987fe011196e4e3`。
- 設計との差分: なし。ブリーフ通り全チャンネル一律のintegrateモードと、`sound_tick()`側の動的volume計算方式(SoundStep非拡張)を選択した。
- 未確認事項: 実際の聴感評価(「BEEP感が軽減されたか」)はユーザーが行う。今回の検証はレジスタ値の機械的確認まで。
- コミット・push・他ブランチへの操作は実施していない(作業ツリーに変更を残している)。

### APS-025: Gearlynx MCPサーバーを使った自動音声検証ツール

- 状態: 実装・動作確認済み(Ryoko、2026-08-07)
- 優先度: 中
- 目的: これまでBGM実装のたびに「Gearlynxで起動確認はできるが、Screen Recording/アクセシビリティ権限が無く、実際の目視・聴感確認はユーザー任せ」という限界があった(APS-020/023/024で繰り返し発生)。ユーザーから「BEEP音のままです。エミュレータで動作確認できるようにして」との指示を受け、権限に依存しない検証手段を用意した。
- 発見: Gearlynx 1.2.21には`--mcp-http`/`--mcp-stdio`オプションがあり、内蔵MCPサーバー(`gearlynx-mcp-server`)がscreenshotのほか、`get_mikey_audio`(チャンネルごとのMikeyレジスタ・有効/無効・音量・ピッチ決定レジスタ`backup`等)、`get_mikey_registers`、`controller_button`等76個のツールを公開している。HTTPトランスポートの利用には`MCP-Protocol-Version`ヘッダが必須(無いと`tools/list`等が400を返す)。
- 実装: `scripts/verify-audio-gearlynx.py`(新規、Python3標準ライブラリのみ)。Gearlynxをheadless+`--mcp-http`で起動し、initializeハンドシェイク後にAボタンでゲーム開始、指定チャンネル(既定0=channel A/メロディ、`--channel 2`でchannel C/ベース)の`backup`レジスタ(ピッチ決定値)を一定間隔でポーリングし、値が変化した時刻・値・音量を記録する。2回以上の異なるピッチ変化を観測できればチャンネルが実際に演奏中と判定しOK、変化が無ければFAIL(無音・固着のバグを示唆)。スクリーンショットも`/tmp`へ保存し視覚確認も兼ねる。
- 検証結果(APS-024のきらきら星ROMに対して実行): channel 0(メロディ)は10秒間で3回のピッチ変化(`0xFA→0xB8→0xAC`、音量`0x11`=設計値`v17`と一致)、channel 2(ベース)は30秒間で1回のピッチ変化(`0xFA→0xC6`、音量`0x10`=設計値`v16`と一致)を観測。**両チャンネルとも設計どおり複数の異なるピッチを演奏していることを直接確認した**(ユーザーが感じた「BEEP音のまま」は、ピッチ進行自体のバグではなく、envelope(音量の立ち上がり/減衰)を持たない生の矩形波/パルス波という音色そのものに起因すると判断できる)。
- 既知の制約: headless+MCPポーリング下では実時間の進行が通常プレイより大幅に遅い(観測ではメロディ1音あたり実時間2.6〜3.6秒、想定ゲーム内200〜400msの約9〜13倍)。ロジックの正しさの検証には支障ないが、実際の再生速度・聴感のテンポ感はこの方法では確認できない(引き続き実機/通常起動でのユーザー確認が必要)。
- 今後の使い方: BGM関連の変更(曲差し替え、envelope追加等)のたびに`python3 scripts/verify-audio-gearlynx.py --seconds N --channel 0/2`を実行し、チャンネルが無音化・固着していないかをAI側で機械的に確認できる。

### APS-024: Stage1 BGMを「きらきら星」へ差し替え

- 状態: 実装完了・レビュー待ち(Dev、2026-08-07)
- 優先度: 中
- 起票日: 2026-08-07
- 基点: `f29fad7`(APS-023完了・push済み時点のHEAD)。着手前`git status --short`はクリーン。
- 目的: ユーザーが実際にGearlynxでAPS-023の多声化BGMを聴き「BGMが変わった気がするがBEEP音のままにも感じる」とフィードバック。既存曲(APS-020由来の単純アルペジオ)を、誰でも聴いてすぐ曲と分かる有名な旋律「きらきら星(Twinkle Twinkle Little Star / Ah vous dirai-je Maman、パブリックドメイン)」へ差し替えて確認する。
- スコープ: Stage1のBGMのみ(メロディ`assets/music/stage1.mml`+ベース`assets/music/stage1_bass.mml`)。Stage2/3・SFX・`tools/mml2c`の言語仕様・ゲームロジック・HUDは変更しない。

#### APS-024実装実績(Dev、2026-08-07)

- 変更ファイル: `assets/music/stage1.mml`(全面差し替え)、`assets/music/stage1_bass.mml`(全面差し替え)、`tests/test_sound.c`(stage1関連の固定回帰値を新曲用に更新)、`ISSUES.md`(本項)、`.briefs/APS-024/v001.md`(新規、実施記録)。`tools/mml2c.c`・`Makefile`・`src/`配下・Stage2/3の`.mml`は無変更。
- メロディ: ハ長調・o1のみ(度数1〜6、c〜a)で6フレーズ(ドドソソララソ/ファファミミレレド/ソソファファミミレ×2/ドドソソララソ/ファファミミレレド)。各フレーズ末尾の音のみ`t15`既定の2倍(`30`)に延長し、直後に既定長(`15`)の休符を1つ挟んでフレーズ感を出した。8ステップ×6フレーズ=48ステップ、合計810 tick。音量は`v17`・波形は`w0`(tone)で全編固定(APS-023でベースが独立チャンネルになったため、旧曲にあったw0/w3交互のアルペジオ疑似合奏は不要と判断)。
- ベース: 各フレーズの下でルート音を1音・フレーズ全長(135 tick)だけ保持する形(I→IV→V→V→I→IVのハ長調進行、C F G G C F)。6音×135 tick=810 tickでメロディの合計と完全一致させ、APS-023で確立した「メロディ/ベースの合計durationを一致させ両ボイスが同時にstep 0へ戻る」フェイズロック制約を維持した。音量`v16`・波形`w0`(既存stage1_bassの値を踏襲)。
- テスト更新(`tests/test_sound.c`、いずれもstage1関連のみ):
  - `test_bgm_exact_mml_migration()`: `expected_stage_one`を8要素→48要素へ差し替え、`sound_get_bgm_step_count(STAGE_ONE)`の期待値を`8u`→`48u`へ変更。
  - `test_bass_exact_mml_compile()`: `expected_stage_one_bass`を2要素→6要素へ差し替え、`expected_count[STAGE_ONE]`を`2u`→`6u`へ変更。
  - `test_sequence_tables()`: 新曲はo1のみ(度数1〜6)を使うため、旧来の「stage1がstage3より低音・stage2より低い」という前提の比較アサーションが成立しなくなった。stage2/stage3同士の比較(`cave range is lower and flight range is higher than each other`)へ差し替え、stage1については「o1の範囲(1〜7)に収まる」という新曲の設計意図に沿ったアサーションを新設した。フレーズ末の休符により`rests[STAGE_ONE]`が`0u`→`6u`、`bgm_length(STAGE_ONE)`が`120u`→`810u`に変化したため期待値を更新した。
  - `test_bgm_start_loop_stage_and_rest()`: ループ長が810 tickへ伸びたため、固定`240u`ティック分の`advance_sound`では周回してstep0に戻らない。`bgm_length(SOUND_BGM_STAGE_ONE) * 2u`(2周分)へ変更し、周回してstep0へ戻ることを検証する意図を保った。
  - Stage2/Stage3関連のテスト値は無変更。
- 検証結果(すべて終了コード0):
  - `make clean && ./scripts/verify.sh`: ゲーム524件PASS(無変更)、サウンド279件PASS(184件→279件、stage1回帰テストの内容拡張による自然増)、cc65 2.19 `-W error`コンパイル・リンク成功、shell lint成功、LNX検査`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=37627 bytes`成功。
  - ROMサイズ実測差分: 37,276 bytes(APS-023時点)→37,627 bytes(**+351 bytes、約+0.94%**)。stage1メロディ/ベースのテーブルがそれぞれ8→48/2→6ステップへ増えた分。
  - SHA-256: `10373b8853c1cf8f016c243a0ba912d990f8e624c8301731ea9524cd8ba631f4`
- design.mdとの差分: 本課題はブリーフの範囲(曲データ差し替えのみ)通りに実装し、`docs/plan/design.md`は更新していない(仕様変更を伴わないデータ差し替えのため)。
- 未確認事項: 実機/Gearlynxでの聴感確認はAI実装環境では実施不可のため、ユーザーが行う。生成されたメロディ・ベースのテーブル値(scale index・duration)は手計算とmml2c出力の突き合わせで検証済みだが、実際に「きらきら星と分かるか」はユーザーの聴感判断に依存する。
- コミット・pushは実施していない(作業ツリーに変更を残している)。

### APS-023: BGMの多声化(MIKEY channel C追加使用)

- 状態: 一次検収合格・コミット待ち(Dev Front、2026-08-07。GUI目視/聴感確認と3声化要否の判断はユーザー推奨として残存)
- 優先度: 中
- 起票日: 2026-08-07
- 基点: `655123e`(APS-022完了時点のHEAD)。起票時点で作業ツリーはクリーン。着手前`make clean && ./scripts/verify.sh`はゲーム523件・サウンド152件PASS、ROM `dist/asteroid-patrol.lnx` 36,587 bytes、SHA-256 `8d39d935599f91e6eae8c256397fb90144409a0b3809307381bf18dc12d1d7fb`。
- 目的: APS-022実装後にユーザーが実際に聴いたところ「BEEP音で曲ではない感じ」というフィードバックを受けた。原因はAPS-020以来BGM(channel A)が単声・和音/ベースラインが無いことにある。MIKEY未使用のchannel Cを新たに使い、ベースライン(第2ボイス)を追加して2声構成にすることで「曲らしさ」を改善する。
- 経緯: ユーザーへ改善案を2つ提示し、「MIKEY未使用channel C/Dを使い2〜3声構成にする」を選択された。これはAPS-020で明示した制約(channel C/D・attenuation/panning・`lynx_snd_*`に触れない)を明示的に覆す設計変更であり、ユーザーが承知の上での選択である。標準ルート(dev-front→dev)で進める。
- スコープ決定(Dev Front、2026-08-07): 本課題は**channel Cを使った2声(メロディ=channel A・ベース=channel C)化**を必須スコープとする。channel D(3声目・和音/パーカッション)追加は、2声化後のROM容量・実装コストが軽微であれば任意の追加スコープとして許容するが、必須ではない。理由: ユーザー報告の核心(単声・和音/ベースライン欠如)は2声化で直接解消でき、3声を最初から必須にすると設計・作曲・レジスタ配線・テストの手戻りリスクと見積り不確実性が増える。3声化が望ましいと判明した場合は聴感確認後に別途追いブリーフで指示する。
- 制約: 75Hz同期・`5/4`ロジックスケジューラ・cc65 C89・warnings-as-errors・固定小配列・動的確保無し・浮動小数無しは変更しない。SFXが最優先で単一chを完全に上書きする既存規則(channel B限定)は変更しない。attenuation/panning(`0xFD40`〜`0xFD44`)・Timer・IRQ・TGI表示制御・`lynx_snd_*`には触れない。git stashに退避済みの別方式MML実装(`stash@{0}`)には一切触れない(ユーザー確認待ち)。コミット・push・deployはユーザー承認後のみ。

#### APS-023完了条件

- `include/_mikey.h`のchannel Cレイアウト(`0xFD30`起点、channel A/Bと同一の8レジスタ/chブロック構成、DAC`+2`とCOUNT`+6`は既存同様未使用)を根拠に、`src/main.c`へ`SOUND_CHANNEL_C`(`(volatile unsigned char*)0xfd30u`)を追加し、既存の汎用`sound_backend_apply(channel, hardware, output)`ヘルパー(APS-021で統合済み)をそのまま追加チャンネルへ適用する。新規レジスタ書込みロジックの複製・追加実装はしない(既存ヘルパーの再利用のみ)。`sound_backend_init()`・`sound_backend_silence_channel()`呼び出しにもchannel C分を追加する。
- `include/sound.h`/`src/sound.c`へベースライン用の第2ボイスカーソル(例: `bass_step`/`bass_remaining`)と独立出力(例: `output_bgm_bass`)を追加する。既存`bgm_step`/`bgm_remaining`/`output_bgm`(メロディ)の意味・挙動は変更しない。ベースカーソルはメロディと同じ`bgm_active`・`freeze_bgm`(自機死亡中の凍結)に従い、`sound_init()`/`sound_set_stage()`でメロディと同時にStage先頭へ復帰し、`sound_stop_all()`で同時に停止する。カーソル前進ロジックの重複実装を避けるため、`advance_bgm()`相当の処理を共有ヘルパー化してメロディ・ベース両方から呼べる形を推奨する(必須ではないが、APS-021のDRY方針に沿うこと)。
- `assets/music/stage{1,2,3}_bass.mml`を新規追加し、`tools/mml2c`(変更不要、`MAX_TRACKS=8`で対応可能)・`Makefile`の`MUSIC_TRACKS`/`MUSIC_SOURCES`へ追加する。ベースは低音域(概ねo1)・メロディより疎な音符配置・メロディ/SFXと衝突しない音量帯(概ね14〜18)を目安とし、tone/pulse波形を基本にする(noise/metallicはSFXと衝突しやすいため避ける)。3曲のループ長をメロディと一致させるか独立ループにするかはDevの設計判断でよいが、決定と理由をISSUES.mdへ記録する。
- (任意・必須ではない) 上記が完了しROM容量・実装コストに余裕があれば、`SOUND_CHANNEL_D`(`0xfd38u`)を使った3声目(和音/パーカッション)を同じ枠組みで追加してよい。追加する場合は同様にテスト・design.mdへ反映する。追加しない場合はその判断もISSUES.mdへ記録する。
- `tests/test_sound.c`・`tests/test_game.c`へベース(および3声化した場合はその声部)の独立進行・死亡中凍結・Stage切替時の同時復帰・停止時の同時無音化を検証する回帰テストを追加する。既存523/152件の意味を壊さない。
- `docs/plan/design.md`へ多声化の仕様(声部構成、channel割当、既存規則との整合)を追記する。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査を成功させる。実装前後のROMサイズ差分を報告する(見積りでなく実測値)。
- 可能であればGearlynxで実際に起動し聴感を確認する(APS-020一次検収の実施例と同じ制約: 本環境はScreen Recording/アクセシビリティ権限が無くGUI目視・入力送出ができない場合がある。その場合は未確認事項として明記し、プロセスレベルの起動安定性確認で代替する)。
- 変更ファイル一覧、最終チェック総数、ROMサイズ・SHA-256、3声化の採否とその理由、design.mdとの差分、未確認事項(聴感の実際の改善度、実機での音量バランス)をISSUES.mdへ実装実績として追記する。

#### APS-023実装実績(Dev、2026-08-07)

- 変更ファイル: `include/sound.h`, `src/sound.c`, `src/main.c`, `Makefile`, `assets/music/stage1_bass.mml`(新規), `assets/music/stage2_bass.mml`(新規), `assets/music/stage3_bass.mml`(新規), `tests/test_sound.c`, `tests/test_game.c`, `docs/plan/design.md`, 本項(ISSUES.md)。`tools/mml2c.c`は変更不要(既存トラック仕様のまま6トラックまで対応、`MAX_TRACKS=8`の余裕内)。
- channel C配線: `src/main.c`へ`SOUND_CHANNEL_C`(`0xfd30u`)と`sound_hardware_bgm_bass`を追加し、既存`sound_backend_apply()`/`sound_backend_silence_channel()`をそのまま再利用した(新規レジスタ書込みロジックなし)。
- `SoundState`へ`bass_step`/`bass_remaining`/`output_bgm_bass`を追加。カーソルの読込・前進は`load_step_cursor()`/`advance_step_cursor()`という共有ヘルパーへ統合し、メロディ(`load_bgm_step`/既存`advance_bgm`)・ベース(`load_bass_step`)の両方から呼ぶ形にした(APS-021のDRY方針を踏襲)。`restart_bgm()`/`sound_stop_all()`/`sound_tick()`にベース分の同期処理を追加。
- ベースMML3曲を新規作成。設計判断: **各ステージのベースループ総durationをメロディのループ長と完全一致**させた(120/40/78 tick)。理由: 独立ループにすると毎回位相がずれて音楽的な一貫性が失われるため、フェイズロック(両ボイスが必ず同時にstep 0へ戻る)を優先した。音量帯14〜18・波形はtone/pulseのみ(noise/metallicは避けた)。
- 3声化(channel D)は**採用しなかった**。理由: ユーザー報告の核心(単声・和音/ベースライン欠如)は2声化で解消でき、スコープ決定(Dev Front、上記)通り2声化を優先し3声は聴感確認後の判断に委ねる。
- テスト追加: `tests/test_sound.c`に`test_bass_tables_bounds_and_phase_lock()`(値域・フェイズロック検証)、`test_bass_exact_mml_compile()`(生成ステップの固定回帰)、`test_bass_syncs_with_bgm_start_freeze_stage_and_stop()`(開始・凍結・Stage切替・停止の同期)を追加。`tests/test_game.c`の`test_sound_initial_phase_and_fire_integration()`へ`game_start()`経由でのベース有効化確認を1件追加。ベーステーブルをテストから読めるよう`sound_get_bgm_bass_step()`/`sound_get_bgm_bass_step_count()`を`sound.h`/`sound.c`へ追加(既存の`sound_get_bgm_step()`系と対称の最小API)。既存523/152件は変更していない(524/184件へ増加、差分は今回追加した1件+32件)。
- 検証結果(すべて終了コード0):
  - `make clean && ./scripts/verify.sh`: ゲーム524件・サウンド184件PASS、cc65 2.19 `-W error`、shell lint、LNX検査すべて成功。
  - ASan/UBSan付きホストテスト: `clang -fsanitize=address,undefined -fno-omit-frame-pointer`でゲーム524件・サウンド184件とも成功。
  - `make smoke-host`: 起動・操作スモーク7件成功。
  - `sh -n scripts/*.sh`、`git diff --check`: 成功。
  - `./scripts/inspect-lnx.sh`: `magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=37276 bytes` OK。
  - `make smoke-gearlynx`(ヘッドレス、プロセスレベル確認): `Gearlynx headless ROM launch OK` — ROM読み込み・クラッシュなしを確認。デバッグモニタに入力/状態プロトコルの文書が無いため`UNVERIFIED`終了(既知の制約、APS-020以降と同様)。本環境はScreen Recording/アクセシビリティ権限が無くGUI目視・音声確認は不可のため未確認事項として残す。
- ROMサイズ実測差分: 36,587 bytes → 37,276 bytes(**+689 bytes、約+1.9%**)。新規SHA-256: `1d805b7bf1e081cec7149e96cd5ec908844dda991f28d1afd7d4283fb8c85974`。
- design.mdとの差分: ブリーフ・完了条件通りに実装。設計からの逸脱はなし(共有ヘルパー化・API追加・ループ長一致は「推奨/任意/設計判断でよい」とされていた項目についての具体的選択)。
- 未確認事項: (1) 聴感上の実際の改善度(2声化で「曲らしく」聞こえるか)はAI実装では確認不能。(2) 実機/実エミュレータでのchannel A+C同時再生時の音量バランス・音色の衝突。(3) Gearlynx GUIでの目視・音声確認(環境の権限制約により未実施、ヘッドレスのプロセスレベル確認のみ)。
- コミット・push・deploy・`git stash`操作はいずれも実施していない(`stash@{0}`は未接触)。

#### APS-023一次検収(Dev Front、2026-08-07)

- 独立再実行: `make clean && ./scripts/verify.sh`を再実行し終了コード0(ゲーム524件、サウンド184件、cc65 `-W error`、shell lint、LNX検査`size=37,276 bytes`)を確認。`shasum -a 256 dist/asteroid-patrol.lnx`は報告値`1d805b7bf1e081cec7149e96cd5ec908844dda991f28d1afd7d4283fb8c85974`と一致。ASan/UBSan付きゲーム524件・サウンド184件も別途再実行し一致。
- `git status --short`で変更ファイルが報告どおり(`ISSUES.md`/`Makefile`/`docs/plan/design.md`/`include/sound.h`/`src/main.c`/`src/sound.c`/`tests/test_game.c`/`tests/test_sound.c`変更、`assets/music/stage{1,2,3}_bass.mml`新規)であること、`git stash list`が`stash@{0}`1件のまま未変更であることを確認した。
- コード検証: `src/main.c`のMIKEYアドレス定義を`rg`で確認し、`SOUND_CHANNEL_C=0xfd30u`のみが新規で、`0xFD38`(channel D)・`0xFD40`〜`0xFD44`(attenuation/panning)・`lynx_snd_*`への接触が無いことを確認。channel C配線が既存`sound_backend_apply()`/`sound_backend_silence_channel()`の再利用のみで新規レジスタ書込みロジックが無いことをコード直読で確認した。
- `src/sound.c`を全文読み、`load_step_cursor()`/`advance_step_cursor()`という共有ヘルパーへメロディ・ベース双方のカーソル前進が統合されていること、`advance_bgm()`が`bgm_active`ゲートの下で両カーソルを同時に進めること(`freeze_bgm`は呼び出し元`sound_tick()`が両方に等しく効かせる)、`restart_bgm()`/`sound_stop_all()`が両ボイスを同時に復帰・停止させることを確認した。
- `assets/music/stage{1,2,3}_bass.mml`の総durationを手計算で検証: Stage1メロディ8×15=120tick、ベース60+60=120tick。Stage2メロディ8×5=40tick、ベース20+20=40tick。Stage3メロディ18+9+18+9+12+12=78tick、ベース27+27+24=78tick。いずれも報告どおり完全一致(フェイズロック)しており、波形もベース側はtone/pulseのみでSFX的なnoise/metallicを避けていることを確認した。
- GUI確認の補完: Dev Frontの環境でも`open -na /Applications/Gearlynx.app --args <ROM絶対パス>`で新規起動し、約27秒観察(CPU約8%で安定、クラッシュ・フリーズなし)。APS-020と同様、本環境にはScreen Recording/アクセシビリティ権限が無く画面キャプチャ・キー入力送出ができないため、目視・聴感確認はできなかった。確認後は起動したプロセスのみ終了させた(観察開始前から起動していた別のGearlynxプロセスは本検証と無関係のため触れていない)。
- 判定: THOROUGH。コード・テスト・ハッシュ・ROMサイズ差分の独立再現はすべて報告と一致し、齟齬は無い。GUI目視・聴感確認のみ、AI実装環境の権限制約により未達のまま残る(実装の不備ではなく環境制約のため差し戻し不要)。ユーザー自身によるGearlynx GUIでの目視・聴感確認と、その結果に基づく3声化(channel D)要否の判断を推奨する。

### APS-022: MMLサウンドドライバ

- 状態: 実装・全自動検証合格・コミット待ち(Fable、2026-08-07。ISSUES.md/design.md/.briefsはRyokoが検収時に追記)
- 優先度: 中
- 基点: APS-021完了時点
- 目的: BGMのステップテーブルをテキストのMML風表記から生成できるようにし、以後の作曲・曲差し替えをSoundStep配列の手書きなしで行えるようにする。
- 実装: 新規ホスト専用ツールtools/mml2c.c(C89)がassets/music/*.mmlを読み、const SoundStep配列を持つCソース(build/gen/music_data.{h,c}、.gitignore対象で非コミット)を生成し、ROM/ホストテスト双方がリンクする。Lynx ROM側はランタイムパーサを持たない。assets/music/stage1〜3.mmlはAPS-020の既存BGM(音程・duration・volume・波形)をバイト単位で忠実に移植したもので、聴感は変化しない(tests/test_sound.cのtest_bgm_exact_mml_migrationで固定回帰)。
- 検証: Ryokoが独立にmake clean && ./scripts/verify.shを実行し、ゲーム523件・サウンド152件PASS、cc65/LNXビルド成功、shell lint成功を確認。ROMはdist/asteroid-patrol.lnx 36,587 bytes、SHA-256 8d39d935599f91e6eae8c256397fb90144409a0b3809307381bf18dc12d1d7fb。
- 残課題: タイトル画面用BGM・Stage2/3向けのより長い曲は未着手(スコープ外)。実機・Gearlynxでの聴感確認は未実施。

### APS-021: コード整理(重複排除)

- 状態: 実装・全自動検証合格・コミット待ち(Fable、2026-08-07。ISSUES.md/design.md/.briefsはRyokoが検収時に追記)
- 優先度: 低
- 基点: APS-020完了時点(477d924)
- 目的: 外部から観測できる挙動(75Hz同期、5/4ロジックスケジューラ、ゲームプレイ、HUD、音)を変えずに、既知の重複コードを整理する。
- 実装: src/main.cのsound_backend_apply_bgm()/sound_backend_apply_sfx()(APS-020で意図的に複製)をsound_backend_apply(channel, hardware, output)へ統合。背景スクロール3レイヤーの分周・ラップ処理と水平ラン描画のクリップ処理を共通ヘルパーへ集約。src/game.cのenemy_fire_interval()を9分岐if連鎖から固定テーブル参照へ変更。src/sound.cのBGM/SFX出力コピー処理をset_step_output()へ統合(この関数自体はAPS-022コミットで導入)。
- 検証: make clean && ./scripts/verify.shで、ゲーム523件・サウンド152件PASS、cc65/LNXビルド成功、shell lint成功を確認(Ryoko独立実施)。
- 残課題: なし。純粋な内部整理のため追加の実機確認は不要と判断。

### APS-020: BGM曲化・2ch復帰

- 状態: 一次検収合格・コミット待ち（Dev Front、2026-08-06。GUI目視/聴感確認はユーザー推奨として残存）
- 優先度: 中
- 起票日: 2026-08-06
- 基点: `694d396`（APS-019完了時点のHEAD）。起票時点で作業ツリーはクリーン。originへ2 commits ahead。
- 目的: APS-018でBGMシーケンサとBGM由来のMIKEY出力を停止して以来、無音のままだったBGMを、SFXと独立した2ch構成（BGM=MIKEY channel A、SFX=channel B）で復帰させ、既存の3Stage分プレースホルダーBGM表を実際に聴こえる音楽として機能させる。
- 経緯: ローカルLLM（qwen3.6:27b）に実装を試させたが、35分・大量トークン消費の末に6ステップ中1ステップ（`sound.h`への構造体追加のみ）しか完了せず失敗した。使用した作業ツリー（`../atari-lynx-shooter-worktrees/bgm-local`、ブランチ`feature/aps-020-bgm-local`）には未完成の変更が残るが、本課題では参照不要。標準ルート（dev-front→dev）へ切り替える。
- スコープ決定（Dev Front、2026-08-06）: 本課題は**2ch構造の復帰**を主目的とする。既存の3Stage BGM表（`src/sound.c`の`stage_one/two/three_bgm`）をベース楽曲として扱い、SFXとの音量・音色衝突回避のための調整（音量帯・波形の選び直し等）は許容するが、**タイトル画面用BGMの新規追加は対象外**とする（既存にタイトルBGM用スロットが無く、追加はスコープ拡大のため）。必要なら別課題として起票する。
- 制約: 外部音源・権利不明素材・浮動小数・動的確保を使わない。固定小配列、整数、75Hzの決定的スケジュール、厳格C89、cc65 warnings-as-errors、ホストテスト可能なサウンド状態を維持する。コミット・push・deploy、BIOS・`lynxboot.img`・外部ROMの取得/探索/生成/同梱は禁止する。APS-018/019で確立した75Hz同期・`5/4`ロジックスケジューラは変更しない。

#### APS-020完了条件

- `include/sound.h`/`src/sound.c`の論理出力を、単一`SoundOutput output`から**BGM用・SFX用の独立した2出力**へ分離する。BGMは`bgm_active`時に常時ch A相当の出力を生成し、SFXはアクティブな間だけch B相当の出力を生成する。SFXがBGMを完全に上書きしていた旧仕様（`select_output()`の排他選択）を廃止し、両者が同時に鳴る構成へ変更する。
- `sound_init()`と`sound_set_stage()`で`bgm_active`を1へ戻し、BGMシーケンサの進行を再開する。`sound_tick(sound, freeze_bgm)`の`freeze_bgm`（自機死亡中はBGMカーソルのみ凍結・SFXは進行）、SFX優先度・同一以上の先頭再始動・低優先度破棄・Boss撃破中のSTAGE CLEAR保留1件という既存規則はSFX側だけの規則として維持する。Stage切替時の次曲頭切替、GAME OVER/ALL CLEAR時の停止、完全再開始時のStage 1曲頭復帰という既存仕様も維持する。
- `src/main.c`のLynxバックエンドへMIKEY channel B相当のレジスタ定義・書込み関数を追加する。アドレスは`include/_mikey.h`のchannel Bレイアウト（`0xFD20`起点の8レジスタ×4chのうち2番目、`0xFD28`〜`0xFD2F`）を根拠とし、既存channel A実装（`0xFD20/21/23/24/25/27`、公式順序control=0→shift-low/control-B/feedback→volume→reload→control=`prescaler|0x18`、音量のみ変更時はvolumeだけ再書込み）と同じレジスタオフセット・書込み規約・差分更新（同一note/waveならタイマ再起動しない）をch Bへ複製する。BGM出力はch A、SFX出力はch Bへ適用する。`MSTEREO`（`0xFD50`）は両ch unmute（0）を維持する。Timer 0/2/7、IRQ、TGI表示制御、channel C/D、attenuation/panning、`lynx_snd_*`へは一切触れない。
- 既存3Stage BGM表の音量を、SFX（現行22〜31）と常時同時に鳴らしても聴感上つぶれない帯域（目安14〜18程度）へ必要に応じて調整してよい。休符・ループ長・音程進行の骨格変更は不要（ただし明らかな改善であれば許容）。タイトル画面BGMの新規追加はしない。
- `tests/test_sound.c`・`tests/test_game.c`の`bgm_active`・`sound.output`関連アサーションを2出力構成（例: `output_bgm`/`output_sfx`、命名はDev裁量）に合わせて全面更新する。BGM常時進行、SFX同時再生、死亡中BGM凍結・SFX進行、Stage切替・停止・再開始時のBGM/SFX双方の状態を回帰させるテストを追加・更新する。
- `docs/plan/design.md`のAPS-018時点「BGM停止・SFXのみ75Hz」の記述を、2ch復帰後の実仕様（BGM常時ch A・SFX ch B同時進行）へ書き換える。APS-013の履歴設計値セクションは変更しない。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査を成功させる。実装後、既存のGearlynx GUI環境でタイトル→Stage 1導入→通常戦闘→敵撃破/被弾のひととおりを起動し、クラッシュ・フリーズ・表示異常が無いことを確認する（聴感確認はAI実装では不可能なため「未確認事項」として明記する。BIOSファイルの探索・読取はしない）。
- 変更ファイル一覧、最終チェック総数、ROMサイズ・SHA-256、設計との差分、未確認事項（聴感、Atari Lynx実機での音量・音質・処理負荷）を本項へ実装実績として追記する。

#### APS-020 実装・検証結果

- 変更ファイル: `include/sound.h`（`SoundOutput output`を`output_bgm`/`output_sfx`の2フィールドへ分離）、`src/sound.c`（`select_output()`を`update_bgm_output()`/`update_sfx_output()`へ分離して排他選択を廃止、`sound_init()`/`sound_set_stage()`で`bgm_active=1`へ復帰、`sound_tick()`で両出力を毎更新算出してから各カーソルを進行、Stage 1/2のBGM音量をSFXとの同時再生を前提にした14〜18帯へ調整）、`src/main.c`（channel Bレジスタ定義`SOUND_B_VOL/FEEDBACK/SHIFT_LOW/RELOAD/CONTROL_A/CONTROL_B`（`0xFD28`〜`0xFD2F`、`include/_mikey.h`の`channel_b`で確認）を追加、`sound_hardware`を`sound_hardware_bgm`/`sound_hardware_sfx`に分離、旧`sound_backend_apply()`を`sound_backend_apply_bgm()`に改称しchannel B用`sound_backend_apply_sfx()`を同一規約で複製追加、`sound_backend_init()`で両ch初期化、`main()`ループで両関数を呼び出し）、`tests/test_sound.c`・`tests/test_game.c`（`bgm_active`・`sound.output`関連アサーションを2出力構成へ全面更新し、BGM/SFX同時再生・死亡中BGM凍結とSFX進行・Stage切替・ALL CLEAR/GAME OVER時の停止・完全再開始の回帰を追加、サウンド側に`test_bgm_and_sfx_sound_together()`を新規追加）、`docs/plan/design.md`（構成節のsound.c/main.c要約とAPS-018節のBGM停止記述を実仕様へ更新し、新規「APS-020 BGM曲化・2ch復帰」節を追記。APS-013履歴設計値セクションは変更していない）。`src/game.c`は変更不要だった。`game_init()`終端の`sound_stop_all()`→`game_start()`内`sound_init()`という既存の二段初期化構造がそのまま「タイトル画面は無音・`game_start()`後のゲームプレイ中はBGM有効」という意図した挙動を成立させたため。
- 最終検証: `make clean && ./scripts/verify.sh`は終了コード0（ゲーム523件、サウンド129件、cc65 2.19 `-W error`、shell lint、LNX検査）。ASan/UBSan付きホストテスト（`clang -fsanitize=address,undefined -fno-omit-frame-pointer`、他フラグは`verify.sh`と同一）はゲーム523件・サウンド129件とも終了コード0。`sh -n scripts/*.sh`・`git diff --check`は終了コード0。`make smoke-host`は7件成功。`./scripts/inspect-lnx.sh`はLNXヘッダOK。
- ROM: `dist/asteroid-patrol.lnx` 37,550 bytes、SHA-256 `434b8ac0791cd77b41426a6a87ab0790a4cb50ba1b93afb2dfd18bde63fff27f`。
- 設計との差分: ブリーフ・完了条件からの逸脱はない。`SoundOutput`2出力のフィールド名は`output_bgm`/`output_sfx`（ブリーフの命名例をそのまま採用）。channel B書込みはブリーフの指示どおり既存channel A実装を関数ごと複製する方式とし、共有ヘルパー化はしていない。BGM音量調整はStage 1（旧20/18→17/15）とStage 2（旧20〜24→14〜18の昇順/降順）のみ実施し、Stage 3（18/17/16）は既に目標帯域内のため変更していない。
- 未確認事項: (1) 2ch同時再生時の聴感（音量バランス・音色の衝突）はAI実装では判定できない。(2) `make smoke-gearlynx`でGearlynx 1.2.21をheadless起動しROMがクラッシュなく起動しdebug-monitorが待受することは確認したが、そのプロトコルには入力送出・状態取得手段が無いため（スクリプト自身が`UNVERIFIED`と報告する既知の制約）、ブリーフが求めるタイトル→Stage 1導入→通常戦闘→敵撃破/被弾のインタラクティブなGUI確認はこのセッションでは実行できていない（GUI操作・画面目視の手段が無いため）。(3) Atari Lynx実機でのCPU負荷、2ch同時出力時の実機音質は未確認。

#### APS-020一次検収（Dev Front、2026-08-06）

- 独立再実行: `make clean && ./scripts/verify.sh`を再実行し終了コード0（ゲーム523件、サウンド129件、cc65 2.19 `-W error`、shell lint、LNX検査`size=37,550 bytes`）を確認。`shasum -a 256 dist/asteroid-patrol.lnx`は報告値`434b8ac0791cd77b41426a6a87ab0790a4cb50ba1b93afb2dfd18bde63fff27f`と一致。
- コード検証: `src/main.c`のMIKEYレジスタ定義を`rg`で確認し、`0xFD20/21/23/24/25/27`（channel A）・`0xFD28/29/2B/2C/2D/2F`（channel B）・`0xFD50`（MSTEREO）以外の新規ハードウェア書込みが無いことを確認した。`src/sound.c`の`update_bgm_output()`/`update_sfx_output()`/`sound_tick()`を読み、旧`select_output()`の排他選択（SFXがBGMを上書き）が廃止され、`freeze_bgm`によるBGMカーソル凍結、SFX優先度・保留STAGE CLEARの規則が変更されずSFX側だけの規則として残っていることを確認した。
- `src/game.c`は未変更（gitでも無変更）であることを確認。`game_init()`が末尾で`sound_init()`直後に`sound_stop_all()`を呼んで無音に戻し、`game_start()`が`game_init()`後に`sound_init()`を再度呼んでStage 1曲頭からBGMを開始する既存の二段構成を直接読み、報告どおり「タイトル無音・プレイ中BGM有効」が成立することをコードレベルで確認した。
- `docs/plan/design.md`の差分を確認し、旧APS-018節「BGM停止・SFXのみ75Hz」の記述が新仕様と矛盾なく書き換えられていること（reviewer指摘の修正を含む）を確認した。
- GUI確認の補完: Devの子セッションにはGUI操作手段が無く未実施だったため、Dev Front側で`open -na /Applications/Gearlynx.app --args <ROM絶対パス>`によりGearlynx 1.2.21を新規起動し、プロセスをおよそ44秒間観察した（`ps`でCPU 11〜12%を維持、状態は実行/スリープを継続、クラッシュ・異常終了なし）。ただし本環境には画面キャプチャ・キー入力送出の権限（Screen Recording/アクセシビリティ）が無く、`screencapture`・`System Events`とも権限エラーで失敗したため、タイトル/Stage 1導入/戦闘画面の目視やA/B入力によるシーン進行確認はできなかった。プロセス起動後のクラッシュ・即時フリーズが無いことまでは確認したが、ブリーフが求める視覚的な目視確認は依然未達のため、ユーザー自身によるGearlynx GUIでの目視・聴感確認を推奨する。
- 判定: THOROUGH。上記コード・テスト・ハッシュの独立再現はすべて一致し、報告と実装に齟齬は無い。GUIの目視・聴感確認のみ、AI実装環境の権限制約により未達のまま残る（新規ブリーフでの差し戻しは不要、環境制約であり実装の不備ではないため）。



- 状態: 実装・再現可能な性能比較・検証完了（Dev、2026-08-05）
- 優先度: 高
- 起票日: 2026-08-05
- 基点: `16549ed`（APS-017/018を単一コミット化したHEAD）。起票時は作業ツリーがクリーンであることを確認した。APS-019の成果はユーザーの追加許可があるまでコミット・pushしない。
- 目的: Lynx実機の75Hz表示同期を維持したまま、現在の待機・描画同期箇所と、待機を外した場合のロジック更新頻度・実効速度を計測可能な方法で明らかにする。計測でホットパスを特定し、可読性・決定性・既存挙動を保つ最小の性能改善を実装する。

#### APS-019完了条件

- `tgi_setframerate(75u)`、`tgi_busy()`待機、入力取得、`game_logic_updates_for_draw_frame()`、`game_update_logic()`、`game_sound_tick()`、描画、`tgi_updatedisplay()`の実行順と回数を、ソース位置・測定手順・実測値で説明する。無待機調査は製品既定を変更せず、75Hz待機時と同一条件で比較する。
- 無待機時の「1秒あたり描画フレーム数・ロジック更新数・ゲーム時間の実効倍率」を推測でなく再現可能に計測する。75Hz表示に対して無制限更新が入力のサンプリング/同一入力反復、描画欠落・ティアリング/表示非同期、CPU負荷、ゲーム内タイマ・SFX・実時間の乖離へ与える副作用を、測定結果と実装構造に分けて記録する。
- 75Hz同期を原則維持し、待機短縮・製品既定の無待機化は行わない。ホットパスをプロファイルまたは決定的な計数で比較し、衝突・エンティティ更新・描画等のうち根拠のある箇所だけを最小限に最適化する。最適化前後の同一シナリオの値、採否理由、再現手順を記録する。
- 統計・ベンチマークは開発専用のコンパイル時機能またはホスト用ツールに閉じ、通常のROMのUI、入力、ゲーム状態、容量制約を汚さない。固定配列、整数決定性、静的BSS/TGI二重バッファ分離、許可済みMIKEY書込み境界を維持する。
- APS-018の75Hz描画/入力、`5/4`ゲーム内ロジック、SFX 75Hz、BGM停止、HUD・敵弾・敵スプライト、タイトル/GAME OVER/ALL CLEAR/3ステージ進行を回帰させない。Gearlynx GUI、全テスト、ASan/UBSan、cc65/LNX、`git diff --check`を実行し、無待機値、前後比較、最適化内容、ROM SHA-256、残課題を記録する。

#### APS-019 実装・計測結果

- 実行順の根拠: `src/main.c`の初期化で`CLI()`後に初回`tgi_busy()`完了を待ち、`tgi_setframerate(75u)`を設定する。無限ループは`tgi_busy()`完了待ち→`read_input()`1回→`game_logic_updates_for_draw_frame()`→戻り値回（4描画フレームで`1,1,1,2`）の`game_update_logic()`（同一入力を反復）→`game_sound_tick()`1回→MIKEY SFX反映→`draw_game()`→`tgi_updatedisplay()`1回の順。描画関数はタイトル/通常のどちらも表示更新を1回だけ要求する。
- 計測手順: `make perf-host`（clang、`-O2 -DGAME_PERF_INSTRUMENT`）をmacOSホストで実行した。開発専用の`tests/perf_bench.c`は通常ROMへリンクせず、固定の通常戦闘ワークロードで75Hz待機/無待機を各実時間1秒測る。最終実行は75Hz: 1,002,742µs、描画75、ロジック93、SFX tick 75、ロジック92.75Hz、ゲーム時間0.99倍。無待機: 1,000,141µs、描画9,107,409、ロジック11,384,261、SFX tick 9,107,409、ロジック11,382,656.05Hz、ゲーム時間121,415.00倍。75Hzの理論93.75ロジック更新/秒を前者の実測確認値、後者の倍率基準とした。
- 無待機の副作用: 実測上、入力相当のサンプリングとSFX tickも描画フレーム相当回数で増加し、同一入力は各フレーム内の追加ロジック更新へ反復される。ゲーム内タイマ・移動・クールダウンはロジック更新に従うため、実時間から大幅に乖離する。`tgi_updatedisplay()`はVBlankへ非同期の表示要求であり、`tgi_busy()`を外すと次のクリア/描画がswap完了前に進むため、表示欠落・ティアリング相当の危険がある。待機なしのLynx実機CPU負荷、実際のティアリング、入力デバイス固有のサンプル挙動はこのホストベンチでは未測定であり、断定しない。
- ホットパスと最適化: 開発用の決定的カウンタでは、通常更新あたり自機弾スロット12、敵衝突候補48、敵弾スロット32を処理する。`hit_enemies`の集計だけが8スロットだったため、自機弾結果フラグへ集約して4スロットへ削減した。固定500万描画フレーム（625万ロジック更新）5回の中央値は、旧集計463,597µsから最適化後455,610µs（約1.7%短縮）となった。ホストのばらつきはあるため、採否の主根拠は決定的な集計走査50%削減であり、Lynx実機の速度向上値ではない。
- 通常ROMへの影響: `GAME_PERF_INSTRUMENT`は性能ベンチだけで定義し、通常のcc65ビルドではカウンタ、API、状態を含まない。`5/4`、75Hz SFX、BGM停止、TGI二重バッファ、MIKEY書込み境界、HUD/UIは変更していない。コミット、push、deploy、reset、checkout、stash、BIOS・外部ROM/素材の取得・探索・読取・生成・同梱は行っていない。
- 最終検証: `make clean && ./scripts/verify.sh`は終了コード0（ゲーム523件、サウンド127件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査）。`make smoke-host`は7件、ASan/UBSan付きゲーム523件・サウンド127件・スモーク7件も各終了コード0。`sh -n scripts/*.sh`、`git diff --check`、LNX再検査は終了コード0。ROMは36,914 bytes、SHA-256 `393a2436d26184526c27ba02b4bd8427dc11d644a2d73c3512dfc645968f4533`。
- GUI: 既存設定のGearlynx 1.2.21で最終ROMの絶対パスを新規起動し、タイトルの`ASTEROID PATROL`と`A/B TO START`、およびStage 1のHUD/敵/敵弾を伴うGAME OVER画面を目視した。BIOSファイルは探索・読取・変更していない。長時間連続プレイとAtari Lynx実機での75Hz維持、CPU負荷、入力、ティアリング、音量は未確認として残す。
- THOROUGH再検証（Dev Front）: 機能・Sanitizer・cc65/LNX・差分検査と製品ROMの75Hz維持は独立再実行で合格した。一方、最適化後の固定500万描画フレームを5回再測定すると461,688 / 468,780 / 608,011 / 556,993 / 475,680µsとホスト揺らぎが大きく、記録済みの旧463,597µs→新455,610µs（1.7%）だけでは前後差を再現可能に立証できない。v002で旧8回走査を**開発専用**の比較対象として同一ワークロード・交互実行・複数回測定へ補強し、中央値・範囲・各実測値を記録するまで性能数値は確定扱いにしない。
- v002比較経路: `GAME_PERF_LEGACY_HIT_RESCAN`は`GAME_PERF_INSTRUMENT`と同時にだけ許可するホスト専用フラグで、最適化前の`update_normal()`における`hit_enemies`4スロット再走査と、それ以前の自機弾結果返却を復元する。最適化版は自機弾のビット結果で敵撃破を集約する。両版は同じ`tests/test_game.c`（523件）を通し、複数撃破の敵撃破SFX集約、既存アイテム保持時のドロップ/取得、敵再配置、命中敵の同一更新での移動/被弾判定抑止を含む既存回帰を照合した。通常cc65ビルドではフラグ、カウンタ、追加状態はいずれも存在しない。
- v002再現手順・環境: `make perf-host`を実行する。Apple Silicon（arm64）/ macOS 26.6（25G72）/ Apple clang 21.0.0（`-O2 -std=c89 -pedantic -Wall -Wextra -Werror`）で、75Hz/無待機を各実時間1秒測定し、固定500万描画フレーム（625万ロジック更新）を旧/新各1回ウォームアップ後、実行順を交互にした7組を測定する。各組後に中央値・範囲・対ごとの差を出力するため、同じコマンドで再計測できる。
- v002実測: 75Hzは1,003,381µs、描画75、ロジック93、SFX tick 75、ロジック92.69Hz、ゲーム時間0.99倍。無待機は1,000,000µs、描画10,077,092、ロジック12,596,365、SFX tick 10,077,092、ロジック12,596,365.00Hz、ゲーム時間134,361.23倍。固定ワークロードの決定的計数は旧/新とも通常更新6,250,000、自機弾スロット75,000,000、敵衝突候補300,000,000、敵弾スロット200,000,000で、命中フラグ走査だけが旧50,000,000（8/更新）から新25,000,000（4/更新）へ半減した。
- v002交互比較（旧µs / 新µs / 差=旧-新µs）: 1=489,898 / 459,198 / +30,700、2=483,857 / 453,204 / +30,653、3=490,405 / 477,785 / +12,620、4=484,758 / 459,552 / +25,206、5=475,465 / 461,539 / +13,926、6=504,076 / 450,832 / +53,244、7=504,506 / 454,390 / +50,116。旧の中央値489,898（475,465〜504,506）、新の中央値459,198（450,832〜477,785）、対ごとの差は中央値+30,653、最小+12,620、最大+53,244、平均+30,923.57µsだった。全7組で新が短縮したため、この固定ホストワークロードでは中央値で約6.3%短縮した。ただしOSスケジューリング等の影響を含むホスト測定であり、Lynx実機の速度向上率・FPSではない。
- v002採否: 走査回数の決定的50%削減に加え、交互比較の全組で正の差を確認できたため、最適化を維持する。75Hz待機、`5/4`、SFX 75Hz、通常ROMの入力/HUD/UI/状態は変更していない。未確認はAtari Lynx実機での処理時間・CPU負荷・入力・ティアリング・音量、および長時間連続プレイである。
- v002最終検証: `make clean && ./scripts/verify.sh`はゲーム523件、サウンド127件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査を通過した。`make smoke-host`は7件、ASan/UBSan付きゲーム523件・サウンド127件・スモーク7件、`sh -n scripts/*.sh`、`git diff --check`、LNX再検査もすべて終了コード0。ROMは36,914 bytes、SHA-256 `393a2436d26184526c27ba02b4bd8427dc11d644a2d73c3512dfc645968f4533`。既存のGearlynx 1.2.21 GUIで最終ROMを新規起動し、タイトルの`ASTEROID PATROL`、`A/B TO START`、操作案内を目視した。BIOSファイルは探索・読取・変更していない。コミット、push、deploy、reset、checkout、stashも行っていない。

### APS-018: 戦闘UI・視認性・敵スプライト演出の改修

- 状態: 実装・検証完了（Dev、2026-08-04）
- 優先度: 高
- 起票日: 2026-08-04
- 目的: BGMを当面無効化して既存の効果音を維持し、ゲームの体感速度を上げる。同時に、敵弾と背景の星を色・形・描画順で明確に区別し、Stage 1開始までの進行表示とHUDを画面最上部の小さい一行へ集約する。HUD帯とプレイ領域を明確に分け、通常敵を個別シルエットを持つグラフィカルなスプライト風表現へ改修する。
- 保全基点: 着手前に`HEAD`と`origin/main`がともに`617f3f4c383ae68925eaec2a4c159a8bbfa3b272`であること、APS-017の未コミット差分（`ISSUES.md`、`README.md`、`docs/plan/design.md`、`src/game.c`、`tests/test_game.c`、`tests/test_smoke.c`、`.briefs/APS-017/`、`evidence/`）が存在することを確認した。この差分をreset、checkout、stash、削除、改変してはならない。
- 確定速度仕様: 描画・入力は75Hzを維持し、ゲーム内の決定的な進行・移動・クールダウン・環境イベントを**1.25倍**へ統一する。浮動小数は使わず、4描画フレームごとに計5ロジック更新（`5/4`）を行う。入力は当該描画フレームで取得した値をそのフレーム内の全ロジック更新へ適用し、`tgi_updatedisplay()`は描画フレームごとに一回だけにする。
- 確定BGM無効化範囲: `sound.c`のBGMシーケンサとBGM由来のMIKEY出力だけを停止し、射撃・撃破・被弾・取得・WARNING・Boss撃破・Stage Clearの既存SFXは維持する。BGMデータは削除せず、将来の復帰可能性を保つ。外部音源・BIOS・`lynxboot.img`・外部ROM/素材は取得、探索、読取、複製、生成、同梱しない。

#### APS-018完了条件

- 速度倍率を台帳・設計書・README・回帰テストへ明記し、Stage導入、通常、WARNING、BOSS、STAGE CLEAR、死亡、GAME OVER、ALL CLEAR、タイトルの時間・入力・凍結境界を一貫して扱う。SFX・操作・タイトル、GAME OVER→タイトル、3ステージ進行を壊さない。
- BGMは無音で、全既存SFXは鳴ることをホストのサウンド回帰で確認する。BGMを再開するための範囲を局所化し、BGMデータを無断で削除しない。
- 背景星と敵弾は色、最小形状、描画順が異なり、Stage 1の実GUI画面で一目で区別できる。HUD帯はプレイ領域と境界線または配色で分離し、本文文字を縮小してStage 1導入までの状態・HUDを最上部の一行に収める。
- 全通常敵は敵種ごとに異なる自作スプライト風の水平ラン/マスク表現とアニメーションを持ち、当たり判定・既存の敵種別・移動・発射・ドロップを変えない。
- `make clean && ./scripts/verify.sh`、`make smoke-host`、ASan/UBSan付きゲーム・サウンド・スモークテスト、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査を終了コード0で通し、件数、ROMサイズ、SHA-256を記録する。
- Gearlynx **GUI**でタイトル、A/B後のStage 1導入、開始後のHUD帯・敵・敵弾・背景星を同一GUI画面で目視確認し、Git管理対象の`evidence/APS-018/`へキャプチャと再現手順を残す。ヘッドレスやホスト検査をGUIの代替にしない。
- `ISSUES.md`、`README.md`、`docs/plan/design.md`、`.briefs/APS-018/v001.md`を更新し、設計との差分・未確認事項・禁止操作不実施を記録する。コミット、push、deployは行わない。

#### APS-018実装・検証結果

- 速度: `game_logic_updates_for_draw_frame()`を追加し、Lynxアダプタは各75Hz描画フレームで入力を一度だけ取得する。剰余スケジューラは4フレームで`1, 1, 1, 2`回、計5回の`game_update_logic()`を実行し、同じ入力を追加更新へ渡す。`tgi_updatedisplay()`は引き続き描画フレームごとに一回だけ。SFX tickは描画フレームごとに一回に分離し、SFXの長さ・優先順位・開始回数を75Hzのまま保つ。
- サウンド: BGMデータ・ステージID・取得APIは残した。`sound_init()`と`sound_set_stage()`はBGMをアクティブ化せず、シーケンサ・BGM由来の論理出力・MIKEY出力を停止する。射撃、敵撃破、自機爆発、取得、WARNING、Boss撃破、Stage Clearの既存SFXは同じ優先順位と保留処理で維持した。
- UI/視認性: HUDを0〜9行の黒い帯へ集約し、3x5の自作文字で`S<stage> <phase><progress> <score> L<lives> W<weapon>`を一行表示する。導入の中央`STAGE`文字は廃止してこの行へ統合し、下端線とHUD下クリップを追加した。Stage 1の背景星は低コントラストの背景のまま、敵弾は白色の短横ラン+下端ドットで前景に描く。敵弾のAABB、16発上限、速度、発射ロジックは不変。全9種の通常敵は8x8・2フレームの自作行マスクを保ち、Scout/Saucer/Dropperも先端・リム・貨物ポッドとして明確なスプライト風シルエットへ更新した。
- 回帰: ホストの5/4スケジューラ回帰を追加し、4描画フレームで5ロジック更新、導入タイマの進行、75Hz SFX tickの無音BGM境界を確認した。BGM回帰は、無音・非進行・SFX完了後の無音、および全SFXの再生・優先順位・保留Stage Clearを確認するよう更新した。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0（ゲーム523件、サウンド127件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査）。`make smoke-host`終了コード0（7件）。ASan/UBSan付きゲーム523件、サウンド127件、スモーク7件も各終了コード0。`sh -n scripts/*.sh`、`git diff --check`は終了コード0。LNXヘッダは`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=36933 bytes`、SHA-256は`2fb2ac6f4b16173e29eb01e7fef972c1b44dec973f9581d115cddc0292c0d8e0`。
- GUI: Gearlynx GUI 1.2.21で上記最終ROMの絶対パスを明示した新規ウィンドウを起動し、タイトル、A/B後のStage 1導入、通常戦闘のHUD帯/境界・敵・敵弾・背景星を目視した。`evidence/APS-018/title-boot.png`、`stage1-intro.png`、`stage1-hud-combat.png`と同ディレクトリのREADMEに再現手順・SHAを保存した。
- 設計差分: SFX tickのみをロジック速度倍率から外して75Hzのままにした。これは音の消失・二重開始を防ぎ、BGM停止中も既存SFXの実時間長を保つためであり、設計書へ明記した。その他の確定仕様との差分なし。
- 未確認: Atari Lynx実機での表示・音量・入力状態、長時間連続プレイは未確認。Gearlynx GUIでのタイトル、Stage 1導入、通常戦闘画面は確認済み。
- 禁止操作: コミット、push、deploy、stash、reset、checkoutは行っていない。BIOS、`lynxboot.img`、外部ROM、外部画像・音声素材の取得・探索・読取・複製・生成・同梱は行っていない。APS-017の既存差分・証跡と発行済み`.briefs/APS-018/v001.md`は変更していない（実装依頼は発行済み`v002.md`により確定）。
- 文書整合是正（v003）: `docs/plan/design.md`の現行仕様を、BGM停止・SFXのみ75Hz、描画/入力/表示更新75Hz、ゲーム内ロジック`5/4`（4描画フレームで`1,1,1,2`）へ統一した。APS-013のBGM再生記述は履歴設計値として明示し、現行ではSFX後にBGMへ復帰しないことを明記した。`README.md`の旧HUD `PWR`表記は実装どおり`W<weapon>`へ修正した。v003では`src/`、`include/`、`tests/`、`evidence/APS-018/`、発行済みブリーフを変更していない。再検証の実測は本項へ追記する。
- v003再検証: 文書のみの更新後に`make clean && ./scripts/verify.sh`、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査を再実行し、すべて終了コード0。ゲーム523件、サウンド127件、スモーク7件、cc65 2.19 `-W error`、clang厳格C89/warnings-as-errors、shell lintを確認した。ROMは36,933 bytes、SHA-256は`2fb2ac6f4b16173e29eb01e7fef972c1b44dec973f9581d115cddc0292c0d8e0`。ASan/UBSan付きゲーム523件・サウンド127件・スモーク7件はv002で終了コード0を確認済みであり、コード非変更のv003でも有効である。
- v004は未実施: ブリーフ前提のHUD実測（21文字、開始X=2、右端X=84、表示幅83px）が誤っていることをDevが`src/main.c`の`hud_text[0]`〜`[20]`への代入と`draw_tiny_text(2u, 2u, ...)`から検出したため、v004に基づく文書変更・検証は行っていない。
- 文書整合是正（v005）: `docs/plan/design.md`のHUDを実装どおり、NULを除く20文字（`hud_text[0]`〜`[19]`、`[20]`はNUL）、3x5文字・4pxピッチ・開始X=2・最終文字右端X=80・表示幅79pxへ訂正した。MIKEYバックエンドの更新経路も、Lynx main loopが直接呼ばない`game_update()`後ではなく、各描画フレームの`game_update_logic()`群と75Hzの`game_sound_tick()`後へ訂正した。BGM停止、ゲーム内ロジック1.25倍、SFX 75Hzの現行記述とも照合済み。変更は本台帳と設計書のみである。
- v005再検証: `make clean && ./scripts/verify.sh`、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`、`./scripts/inspect-lnx.sh dist/asteroid-patrol.lnx`はすべて終了コード0。ゲーム523件、サウンド127件、スモーク7件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lintを確認した。LNXは`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=36933 bytes`、SHA-256は`2fb2ac6f4b16173e29eb01e7fef972c1b44dec973f9581d115cddc0292c0d8e0`。ASan/UBSan付きゲーム523件・サウンド127件・スモーク7件はv002で終了コード0を確認済みで、コード非変更のv005でも有効である。

#### APS-018 THOROUGH検収

- Dev Frontがv002〜v005の差分を独立確認した。Lynx main loopは75Hzで入力を一度だけ取得し、剰余スケジューラで`1,1,1,2`回のロジック更新を繰り返すため、ゲーム内だけが決定的に1.25倍となる。SFX tickと表示更新は各描画フレーム一回で、BGMは`bgm_active=0`のまま、7種SFXの優先順位とBoss撃破→Stage Clearの保留処理を維持する。
- Gearlynx 1.2.21のGUI証跡を目視した。タイトルは判読可能で、Stage 1導入では中央の大文字進行表示を使わず最上部HUDへ集約し、通常戦闘では黒いHUD帯・境界線、低コントラストの星、高コントラストの白い短横ラン+下端ドットの敵弾、敵種別ごとのスプライト風シルエットを同一画面で識別できる。証跡と再現手順は`evidence/APS-018/`にあり、Git除外されていない。
- 独立実測: `./scripts/verify.sh`、`make smoke-host`、ASan/UBSan付きゲーム・サウンド・スモーク、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査は全て終了コード0。ゲーム523件、サウンド127件、スモーク7件、最終ROMは36,933 bytes、SHA-256 `2fb2ac6f4b16173e29eb01e7fef972c1b44dec973f9581d115cddc0292c0d8e0`。BSSは`0x9132`〜`0x9372`でTGI第2バッファ`0xC038`から分離している。
- 文書の現行仕様を再照合した。BGM停止・SFX 75Hz、`5/4`ロジック、HUD実測（NULを除く20文字、開始X=2、右端X=80、幅79px）、Lynx側の`game_update_logic()`群と`game_sound_tick()`の更新経路を実装と一致させた。v004の誤った前提は未反映である。
- `HEAD`と`origin/main`はいずれも`617f3f4c383ae68925eaec2a4c159a8bbfa3b272`のまま、既存APS-017差分を含む全成果は未コミットで保全した。コミット、push、deploy、BIOS/外部ROM/外部素材の取得・探索・読取・同梱は行っていない。残課題はAtari Lynx実機の表示・音量・入力状態と長時間連続プレイのみ。

### APS-017: Gearlynx GUIでのタイトル起動不良の再現・修正

- 状態: 一次検収合格（Dev Front、2026-08-04）
- 優先度: 緊急
- 起票日: 2026-08-04
- 報告事象: ユーザーがエミュレータで確認したところ、タイトル画面が表示されない。ホスト検証・ヘッドレス起動だけでは合格とせず、Gearlynx GUIで実際に起動されるROMを特定して、起動直後のタイトル表示とA/BによるStage 1開始を確認する。
- 基点・照合値: 基点は`617f3f4c383ae68925eaec2a4c159a8bbfa3b272`。ローカル`dist/asteroid-patrol.lnx`は36,055 bytes、SHA-256 `53c1839270dbc55085cb83c6576bace013a886d785e3924219b9c916685d6202`。起票時点で`origin/main`は同じ`617f3f4`を指すことを確認した。実際にGUIへ渡す絶対パス・SHA・起動経路を再検証し、古いROMの起動、初期フェーズ遷移、文字描画、初期入力処理のどれが原因かを根拠とともに切り分ける。
- 制約: `CLAUDE.md`と設計書の固定状態機械、静的BSS/TGI二重バッファ境界、MIKEY書込み境界を保つ。コミット、push、BIOS・`lynxboot.img`・外部ROM/素材の取得・探索・読取・複製・生成・同梱は禁止する。既存の発行済みブリーフを上書きしない。

#### APS-017完了条件

- Gearlynx **GUI**で`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`を明示して起動し、起動直後に`ASTEROID PATROL`と開始案内を読み取れる形で表示する証跡を残す。ヘッドレス、ホストテスト、デバッグモニタのみをGUI確認の代替にしない。
- GUI上でAまたはBを一度離してから押し、Stage 1 `GAME_PHASE_STAGE_INTRO`開始を画面で確認する。入力注入を使う場合も、同じGUIウィンドウの遷移画面をキャプチャする。
- 古いROM、初期フェーズ、文字描画、初期入力を順に切り分け、原因・修正・非該当の根拠を記録する。修正時は該当ホスト回帰を追加し、全自動検証を再実行する。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`、LNXヘッダ検査を実行し、終了コード・件数・ROMサイズ/SHA-256を記録する。設計との差分、未確認事項、禁止操作不実施を記す。
- GUIキャプチャと再現手順はGit管理対象の`evidence/APS-017/`へ保存し、実行環境に依存する操作はREADMEで明示する。BIOSその他の秘密・外部ファイルを証跡へ含めない。

#### APS-017実装・GUI検証実績

- 原因: `game_init()`が起動直後に`title_start_armed=1`としていた。このためGearlynx起動時にA/Bが押下状態として観測された場合、離してからの新規入力を待たずにタイトルを通過していた。最初のGUI確認では、8月3日から残っていたGearlynxプロセスが旧ROMセッションを再利用し、現行ソースと異なる`A/B TO RESTART`画面を表示した。対象プロセスを終了して最終ROMを新規GUI起動した後に切り分けた。
- 修正: `game_init()`で`title_start_armed=0`とし、タイトルはA/B解除で武装してからの新規A/B押下だけで`game_start()`するようにした。GAME OVERからタイトルへの復帰も同じ初期化を使うため、復帰押下の開始への連鎖防止を維持する。`src/main.c`のタイトル描画と各フレーム一回の`tgi_updatedisplay()`は正しかったため変更していない。
- 回帰: `tests/test_game.c`へ、起動時のA/B押しっぱなしがタイトルを通過も発射もせず、解除後の新規A/BだけがStage 1 INTROを開始する検証を追加した。`tests/test_smoke.c`にも同じ起動入力境界を追加した。
- ROM照合: 基点`617f3f4c383ae68925eaec2a4c159a8bbfa3b272`、`HEAD`、`origin/main`は着手時に一致した。着手前の候補ROMは36,055 bytes、SHA-256 `53c1839270dbc55085cb83c6576bace013a886d785e3924219b9c916685d6202`。最終GUI対象は`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、36,037 bytes、SHA-256 `aa83ce74322a766e56cfea18083afc39a274a977d7d1a216fa8dca4d45c57491`。
- Gearlynx GUI 1.2.21で、最終ROMを上記絶対パス引数として新規ウィンドウへ渡して確認した。`evidence/APS-017/title-boot.png`は`ASTEROID PATROL`、`A/B TO START`と操作案内を判読可能に示す。A/Bに割り当てられた`z`を100ms注入した後、`evidence/APS-017/stage1-after-a-or-b.png`で`STAGE 1`導入、Lives 3を確認した。再現手順・コマンド・SHAは同ディレクトリのREADMEに記録した。
- 自動検証: `make clean && ./scripts/verify.sh`（終了コード0）はゲーム517件、サウンド130件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査に成功した。`make smoke-host`（終了コード0）は7件成功。ASan/UBSan付きゲーム517件、サウンド130件、スモーク7件も各終了コード0。`sh -n scripts/*.sh`、`git diff --check`は終了コード0。LNXヘッダは`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=36037 bytes`。
- 設計差分: APS-016の「起動時タイトルは即時開始」という記述を、起動時のA/B押しっぱなしを無視して解除・再押下を必要とする安全な開始条件へ更新した。タイトル文言・状態機械・TGI二重バッファ分離・MIKEY書込み境界・サウンドは変更していない。
- 未確認事項: Atari Lynx実機での起動入力状態、実機のキーマッピング、長時間連続プレイは未確認。Gearlynx GUIでの起動直後タイトルとA/B後のStage 1導入は確認済み。
- 禁止操作: コミット、push、deploy、stash、reset、checkoutは行っていない。BIOS、`lynxboot.img`、外部ROM、外部素材の取得・探索・読取・複製・生成・同梱は行っていない。

#### APS-017 THOROUGH検収

- Dev Frontが差分を独立確認した。`game_init()`は`title_start_armed=0`でタイトルを未武装化し、`game_update_logic()`はA/B解除でのみ武装、次のA/Bだけで`game_start()`する。起動時のA/B押しっぱなしでタイトルを飛ばす経路を遮断し、GAME OVERからのタイトル復帰は同じ未武装初期化を使う。タイトル描画は`ASTEROID PATROL`、`A/B TO START`、操作案内を表示し、タイトル分岐・通常分岐ともに`draw_game()`内の`tgi_updatedisplay()`は一回だけであることを確認した。
- GUI証跡を目視した。`evidence/APS-017/title-boot.png`にはGearlynx 1.2.21のGUIウィンドウと`asteroid-patrol.lnx`、判読可能なタイトル・開始/操作案内があり、`stage1-after-a-or-b.png`にはA/B後の`STAGE 1`導入とLives 3がある。再現用READMEは新規GUI起動コマンド、最終ROMの絶対パス、サイズ、SHA-256、入力手順を記録しており、証跡は`.gitignore`で除外されていない。
- 独立実測: `make clean && ./scripts/verify.sh`、`make smoke-host`、ASan/UBSan付きゲーム・サウンド・スモーク、`sh -n scripts/*.sh`、LNXヘッダ検査、`git diff --check`はすべて終了コード0。ゲーム517件、サウンド130件、起動スモーク7件、LNXは36,037 bytesで、最終ROM SHA-256は`aa83ce74322a766e56cfea18083afc39a274a977d7d1a216fa8dca4d45c57491`と一致した。
- GitHub `origin/main`と着手時`HEAD`はともに`617f3f4c383ae68925eaec2a4c159a8bbfa3b272`を指すことを再確認した。最終ROMと修正は未コミットの作業ツリーにあり、コミット・push・BIOS/外部ROM操作は行っていない。実機の入力状態・キーマッピング・長時間プレイは未確認として残す。

### APS-016: タイトル画面とGAME OVERからの復帰導線

- 状態: 一次検収合格（Dev Front、2026-08-04）
- 優先度: 高
- 起票日: 2026-08-04
- 目的: 起動時をStage 1導入ではなくタイトル画面とし、A/Bで新規ゲームを開始する。最終ゲーム画面を背景として保持したGAME OVERからは、A/Bを一度離してから再押下した場合だけタイトルへ戻り、再び新規開始できるようにする。
- 確定仕様: タイトルは`ASTEROID PATROL`、開始案内、方向移動とA/B射撃の基本操作を読みやすく表示する。タイトルでのA/B押下は即時にStage 1 `GAME_PHASE_STAGE_INTRO`を開始する。GAME OVERでは進行・描画同期を止めずに最終ゲーム画面を背景として描き、`GAME OVER`と`A/B TO TITLE`を重ねる。GAME OVERへ入った時点の押下を復帰入力に使わず、必ず離して再押下する。タイトルへ戻るとサウンドを停止し、タイトルからの開始はStage 1・スコア0・残機3・武器Lv1・曲頭へ完全初期化する。
- 互換性: 既存ALL CLEARの「A/Bを離して再押下でStage 1から完全再開始」は維持する。固定状態機械、整数/C89、静的BSS、TGI待機→入力→更新→音→描画→表示更新、MIKEY書込み境界、既存のステージ進行・サウンド優先度を壊さない。

#### APS-016完了条件

- ホスト回帰で、起動→タイトル、タイトルのA/B→Stage 1導入、開始後の初期値、GAME OVER中の離す→再押下→タイトル、タイトルからの再開始、ALL CLEAR再開始の既存挙動を検証する。
- タイトル、GAME OVERオーバーレイと凍結背景の描画を追加し、READMEと設計書へ入力・状態遷移とメモリ境界を記録する。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、cc65 2.19 warnings-as-errors、`sh -n scripts/*.sh`、LNXヘッダ検査、`git diff --check`を実行し、結果・ROMサイズ/SHA-256・設計差分・未確認事項を記録する。コミット、push、BIOS/外部ROM/素材の取得・探索・読取・同梱は禁止。

#### APS-016実装・検証結果

- 変更: 固定状態機械に`GAME_PHASE_TITLE`を追加し、`game_init()`を静音タイトル初期化、`game_start()`をStage 1 INTRO・曲頭からの完全新規開始として分離した。タイトルには`ASTEROID PATROL`、`A/B TO START`、方向移動とA/B射撃を描画する。GAME OVERはゲーム画面を引き続き描き、`GAME OVER`と`A/B TO TITLE`だけを重ねる。`restart_armed`で離してからの復帰入力を要求し、タイトル復帰直後の`title_start_armed=0`により同じ押下が開始へ連鎖しないようにした。タイトルで離してからA/Bを押すと、Stage 1・スコア0・残機3・武器Lv1・戦闘物なし・Stage 1曲頭へ完全初期化する。ALL CLEARの従来の離す→再押下による直接完全再開始は維持した。
- 回帰: 起動タイトル、タイトル開始、導入中入力無効、GAME OVER中の完全凍結、GAME OVERの離す→再押下→静音タイトル、復帰入力の非連鎖、タイトルからの完全新規開始、ALL CLEAR再開始をホスト検査した。ゲームロジックは515件、サウンド130件、起動・操作スモーク5件が成功した。
- 文書: `README.md`へ画面と入力導線を、`docs/plan/design.md`へタイトル状態、入力アーム、GAME OVERの凍結描画、サウンド境界を記録した。`GameState`は静的BSSを維持し、ROMリンクマップのBSSは`0x8DC4`〜`0x9004`（`0x241` bytes）で、TGI第2バッファ先頭`0xC038`から分離している。
- 検証: `make clean && ./scripts/verify.sh`、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`はいずれも終了コード0。cc65 2.19の`-W error`、clang厳格C89、LNX検査も成功した。ASan/UBSan付きのゲーム515件・サウンド130件・スモーク5件も終了コード0。ROMは`dist/asteroid-patrol.lnx`、36,055 bytes、SHA-256 `53c1839270dbc55085cb83c6576bace013a886d785e3924219b9c916685d6202`。
- 設計差分・未確認: 仕様との差分なし。タイトルとGAME OVERオーバーレイの実機/GUI目視、音の聴感、長時間動作は未確認。コミット、push、deploy、stash、reset、checkout、BIOS・`lynxboot.img`・外部ROM・素材の取得・探索・読取・複製・生成・同梱は行っていない。

#### APS-016 v002 文書仕様是正

- `README.md`の残機0説明、`docs/plan/design.md`の画面・再開始総則・Stage進行記述を現行仕様へ統一した。GAME OVERは最終ゲーム画面を背景に`A/B TO TITLE`を表示し、A/B解除後の再押下でタイトルへ戻る。復帰押下は開始へ流用せず、タイトルで再度解除後に押下すると新規開始する。ALL CLEARだけは解除後の再押下で直接Stage 1 INTROへ完全再開始する。
- コードおよびテストは変更していないため、APS-016の既存自動検証結果（ゲーム515件、サウンド130件、スモーク5件、ASan/UBSan、cc65 `-W error`、LNX検査）は不変である。本v002では`sh -n scripts/*.sh`と`git diff --check`が終了コード0で、READMEと設計書を対象に旧`A/B TO RESTART`・GAME OVERからの直接再開始記述が残っていないことを再検索で確認した。設計差分なし。コミット、push、BIOS/外部ROM/素材の操作は行っていない。

#### APS-016一次検収

- Dev Frontが状態遷移・描画・文書を独立確認した。`GAME_PHASE_TITLE`は起動時の静音タイトル、`game_start()`はStage 1 INTROと曲頭の新規開始、GAME OVERは離す→再押下→タイトル、復帰入力は`title_start_armed=0`で開始へ非連鎖、ALL CLEARだけは直接Stage 1再開始となる。タイトルとGAME OVERのTGI描画はいずれも`tgi_updatedisplay()`を一回だけ行い、既存の待機→入力→更新→音→描画順を維持する。
- 独立実測: `make clean && ./scripts/verify.sh`は終了コード0（ゲーム515件、サウンド130件、cc65 2.19 `-W error`、shell lint、LNXヘッダ検査）。ASan/UBSan付きゲーム515件・サウンド130件・スモーク5件、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`も終了コード0。ROMは36,055 bytes、SHA-256 `53c1839270dbc55085cb83c6576bace013a886d785e3924219b9c916685d6202`。
- 静的BSSは`0x8DC4`から`0x241` bytesでTGI第2フレームバッファ先頭`0xC038`から分離している。Gearlynx GUI/実機のタイトル・GAME OVER目視、音の聴感、長時間動作は未確認。コミット、push、BIOS/外部ROM操作は行っていない。

### APS-015: 起動・操作スモーク検証の自動化

- 状態: 一次検収合格・実ROM操作自動検証は未確認（Dev Front、2026-08-04）
- 優先度: 高
- 起票日: 2026-08-04
- 目的: APS-014で解消したCスタックとTGI描画バッファの衝突を再発させないため、通常の`make verify`とは独立して、ROM起動後のStage 1 `NORMAL`到達、方向入力、自機弾発射、`GAME OVER`への誤遷移なしをGearlynxまたは再現可能な同等手段で確認できるスモーク検証を整備する。
- 前提: APS-014の未コミット修正（`GameState`の静的BSS移動、全バイト初期化、512件ゲーム回帰）は保全対象である。着手時差分のSHA-256は`f15faa89bbbf358f51d985377948b7f905008a2561c392a8c6f6ee5f881d29a8`。この差分をreset、checkout、stash、改変、除去してはならない。
- 環境: Gearlynx 1.2.21は`/Applications/Gearlynx.app/Contents/MacOS/gearlynx`に導入済みで、`--headless`とMCP/デバッグモニタの起動引数を提供する。BIOSは取得・同梱・探索・読取しない。既存設定で実行不能なら、失敗理由と再現コマンドを明記する。

#### APS-015完了条件

- 起動・入力・状態を確認するスモーク手段と実行手順を追加し、通常の`make verify`の成功経路・外部BIOS非依存性を壊さない。可能な場合に既存設定のGearlynxで実ROMを検証し、不可能なら明確に失敗して理由を表示する。
- Stage 1 `NORMAL`到達、方向入力による自機移動、自機弾発射、観測中に`GAME OVER`へ誤遷移しないことを再現可能に判定する。Hostロジック検査はこの不変条件を回帰としてカバーする。
- Lynxメモリ配置制約（自動`GameState`をTGI第2バッファ先頭`0xC038`と重ねないこと、静的BSSの根拠）を設計書と利用手順に文書化する。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、cc65 2.19のwarnings-as-errors、`sh -n scripts/*.sh`、LNXヘッダ検査、`git diff --check`を通し、終了コード、件数、ROMサイズ/SHA-256、エミュレータ確認の有無を記録する。コミット、push、BIOS/外部ROMの取得・同梱は禁止。

#### APS-015実装・検証結果

- 変更: `tests/test_smoke.c`を追加し、初期化→Stage 1 INTROの90更新→`NORMAL`、右入力による自機X移動、`GAME_INPUT_FIRE`による自機弾有効化、全観測中の`game_over=0`を4項目で独立検証した。`Makefile`へ`smoke-host`と任意の`smoke-gearlynx`を追加した。通常の`verify`経路にGearlynx依存は加えていない。
- 実ROM: v002で`smoke-gearlynx.sh`は起動前に指定ポートの既存待受を`lsof`で拒否し、起動後も待受PIDが今回のGearlynxまたはその子プロセスに属する場合だけ成功候補とするよう修正した。任意の`GEARLYNX_DEBUG_PORT`、20秒タイムアウト、終了時の起動Gearlynx清掃は維持した。空きポート16502でGearlynx 1.2.21を`--headless --debug-monitor --debug-monitor-port 16502`で起動し、今回のプロセス所有の待受を確認した。占有したポート16503では起動前に`nc`のPIDを表示してスクリプト終了コード1で拒否し、誤成功しないことを確認した。デバッグモニタの入力注入・ゲーム状態読出しプロトコルは未定義のため、空きポートのスクリプト実行は終了コード3で操作・状態を**未検証**と明示する（`make smoke-gearlynx`経由ではmakeが終了コード2として報告）。BIOSの探索、読出し、変更、取得は行っていない。
- 文書: `README.md`に両スモークの用途・実行方法・未検証の意味を、`docs/plan/design.md`に静的BSSを使う理由と確認手順を追加した。終了しない`main()`の約317-byte自動`GameState`をTGI第2バッファ先頭`0xC038`と重ねず、`main.c`の静的BSS `game`（APS-014時点`0x8BC9`）を維持する。リンクマップのBSSは`0x8BC5`〜`0x8E04`であり、表示バッファから分離する。
- 検証: v002で`sh -n scripts/*.sh`、`make clean && ./scripts/verify.sh`、`make smoke-host`、`git diff --check`は各終了コード0（cc65 2.19 `-W error`、ゲーム512件、サウンド130件、起動・操作スモーク4件、shell構文、LNX検査）。ASan/UBSan付きゲーム512件、サウンド130件、起動・操作スモーク4件も各終了コード0。空きポートの`make smoke-gearlynx`は上記未検証を表すmake終了コード2、ポート競合はスクリプト終了コード1を確認した。ROMは`dist/asteroid-patrol.lnx`、35,544 bytes、SHA-256 `c9d7afc15a2445e8157848128a9f0110131603c9af411a211fa077b36adabd2f`。
- 設計差分・未確認: 状態機械・ROM実装の仕様差分はない。Gearlynxの実ROMは、ポート競合を除外したヘッドレス起動だけを確認し、自動入力・メモリ読出し、GUI目視、実機、音の聴感は未確認。コミット、push、deploy、stash、reset、checkout、BIOS/外部ROM/素材の取得・探索・読出し・複製・同梱は行っていない。

#### APS-015一次検収

- Dev Frontがv001/v002を独立検収した。`make clean && ./scripts/verify.sh`は終了コード0（ゲーム512件、サウンド130件、cc65 2.19 `-W error`、shell lint、LNXヘッダ検査）。ASan/UBSan付きゲーム512件・サウンド130件・スモーク4件、`make smoke-host`、`sh -n scripts/*.sh`、`git diff --check`も各終了コード0を確認した。ROMは35,544 bytes、SHA-256 `c9d7afc15a2445e8157848128a9f0110131603c9af411a211fa077b36adabd2f`。
- Gearlynx 1.2.21では実ROMをヘッドレス起動し、空きポート16504/16506で今回のGearlynxプロセスに属するデバッグ待受を確認した。事前に`nc`で占有したポート16505はスクリプト終了コード1で拒否し、誤成功しないことを確認した。デバッグモニタの入力注入・状態読出しプロトコルは未定義なので、実ROMのStage 1 NORMAL・方向入力・射撃・GAME OVER非遷移はホストの4項目スモークで検証し、実ROM操作自動検証は未確認のままとする。
- APS-014の`src/game.c`、`src/main.c`、`tests/test_game.c`の未コミット差分は変更されていない。BSSは`0x8BC5`から`0x240` bytesで、TGI第2フレームバッファ先頭`0xC038`から分離している。コミット、push、BIOS/外部ROM操作は行っていない。

### APS-014: 起動時GAME OVERループの緊急修正

- 状態: 一次検収合格（Dev Front、2026-08-04）
- 優先度: 緊急
- 起票日: 2026-08-04
- 報告事象: ユーザーの実機相当ROM起動で、`GAME OVER`表示だけがちらつき、Stage 1導入・移動・射撃へ進めない。
- 基点: `850211a`（APS-013: 効果音とStage別BGM）。着手前の作業ツリーはクリーン。サウンド追加で`GameState`へ`SoundState`（ホストclangでは328 bytes）を追加し、`src/main.c`にMIKEY channel Aと`MSTEREO`への直接アクセスを導入している。
- 調査範囲: `game_init()`と全GameStateフィールドの初期化、スタック/メモリ境界、A/B再開始入力エッジ、TGI二重バッファと`game_update()`・描画・`tgi_updatedisplay()`の同期、MIKEY channel A / `MSTEREO`の書込み先・順序・Timer/割り込みとの競合を重点確認する。原因を推測で確定しない。
- 制約: 基点からの既存ゲーム仕様を保持し、固定配列・決定的整数・厳格C89を維持する。コミット・push・deploy、BIOS・`lynxboot.img`・外部ROMの取得/探索/読取/生成/複製/同梱は禁止する。

#### APS-014完了条件

- Gearlynx 1.2.21を既存設定だけで起動し、起動直後に`GAME OVER`へ遷移しないこと、Stage 1導入後に方向入力で移動し、A/Bで射撃できることを確認する。BIOSファイル自体を探索・読取しない。GUI自動化不能部分は確認方法と未確認理由を残す。
- 原因を根拠（再現手順、差分、該当コード、必要ならエミュレータログ/画面）とともに記録し、修正後に同じ起動経路を再確認する。起動状態・初期化完全性・入力・描画/MIKEY安全境界をホスト回帰テストとして追加する。
- `make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、cc65 2.19 warnings-as-errors、`sh -n scripts/*.sh`、LNXヘッダ検査、`git diff --check`を実行し、終了コードと件数、ROMサイズ/SHA-256を記録する。
- `ISSUES.md`、`docs/plan/design.md`、`README.md`、`.briefs/APS-014/v001.md`を更新し、設計差分・Gearlynx確認有無・未確認事項・禁止操作不実施を記録する。

#### APS-014実装・検証結果

- 原因: cc65 2.19が終了しない`main()`のローカル`GameState`をCスタック先頭へ置いていた。生成アセンブリでは`game_init()`/`game_update()`/`draw_game()`へ`sp`を渡し、初期スタック先頭はTGIの第2フレームバッファ先頭`0xC038`である。`GameState`はcc65で317 bytes（ホストclangで328 bytes）なので、状態更新とTGI描画が同じ領域を相互に破壊していた。旧ROMをGearlynxで動かした際、`0xC038`から317 bytesが全てゼロになることを読出し、再現を確認した。
- 修正: `src/main.c`の状態を静的BSSの`game`へ移した。修正ROMのリンクマップでは`_sound_hardware`が`0x8BC5`、`_game`が`0x8BC9`、BSS合計`0x240`であり、TGIバッファと分離される。`game_init()`は全バイトを先にゼロ化してから既存の決定的初期設定を適用する。TGI待機→入力→更新→サウンド反映→描画→表示更新、MIKEY channel A/MSTEREOの書込み先・順序は変更していない。
- 回帰: 汚染値の異なる2個の`GameState`を`game_init()`して全バイト一致を確認する検査、起動時Stage 1 INTRO・GAME OVER非成立、導入中の方向/A/Bが移動・射撃にならない検査、90更新後のNORMAL移行、NORMALでの移動/A/B射撃を追加した。ゲームロジックは507件から512件になり、既存サウンド130件は維持した。
- Gearlynx 1.2.21: 既存設定だけで修正ROMをヘッドレス起動し、MCPデバッグ読出しで`_game=0x8BC9`の状態が表示バッファから独立して持続すること、Stage 1の`NORMAL`（phase timer 42、`game_over=0`）まで到達することを確認した。右入力後の自機X=12、A入力後の先頭弾スロット有効も確認し、フレーム画面の取得に成功した。Timer 2はTGIのVBlank設定のまま有効で、channel A以外・Timer 0/7・OUT/DAC・COUNTへ本修正から新規書込みはない。GUIの目視・実機・聴感は未確認。
- 検証: `make clean && ./scripts/verify.sh`は終了コード0（clang厳格C89、cc65 2.19 `-W error`、ゲーム512件、サウンド130件、shell構文、LNX検査）。ASan/UBSan付きゲーム512件とサウンド130件、`sh -n scripts/*.sh`、`git diff --check`も各終了コード0。ROMは`dist/asteroid-patrol.lnx`、35,544 bytes、SHA-256 `c9d7afc15a2445e8157848128a9f0110131603c9af411a211fa077b36adabd2f`。
- 設計差分: 状態保管場所をローカルCスタックから静的BSSへ変更した以外はなし。コミット・push・deploy・stash・reset・checkout、BIOS/`lynxboot.img`/外部ROM/素材の探索・取得・複製・同梱は行っていない。Gearlynxは既存設定で起動しただけで、BIOSファイルそのものは操作していない。

#### APS-014一次検収

- Dev Frontが修正差分を独立確認した。`main()`の自動`GameState`を静的BSSへ移す変更は、cc65リンクマップのBSS `0x8BC5`〜`0x8E04`とTGIフレームバッファ先頭`0xC038`を分離する。`game_init()`の全バイト初期化、起動時INTRO、導入中入力無効、90更新後のNORMAL、NORMALでの移動/射撃の512件回帰テストを確認した。
- `make clean && ./scripts/verify.sh`を独立再実行し、終了コード0、ゲーム512件・サウンド130件、cc65 2.19 `-W error`、shell lint、LNX検査を確認した。ASan/UBSan付きゲーム512件・サウンド130件、`git diff --check`も終了コード0。ROMは35,544 bytes、SHA-256 `c9d7afc15a2445e8157848128a9f0110131603c9af411a211fa077b36adabd2f`でDev報告と一致した。
- MIKEY書込みは既存のchannel A (`0xFD20/21/23/24/25/27`) と`MSTEREO` (`0xFD50`) のみで、Timer、OUT/DAC、COUNT、他チャンネルへの新規書込みがないことを確認した。DevのGearlynx 1.2.21ヘッドレス確認では、Stage 1 NORMAL到達、右入力でX=12、A入力で弾生成を観測済み。GUI目視、実機、音の聴感・長時間動作は未確認として残す。コミット・push・BIOS操作はしていない。

### APS-013: 効果音とStage別BGM

- 状態: 一次検収合格（Dev Front、2026-08-03）
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 無音の現状を解消し、7種の重要イベント効果音と、Stage 1宇宙・Stage 2惑星上空・Stage 3洞窟で異なる短いオリジナルBGMを、既存の3Stage進行・死亡・再開始へ統合する。
- 基点: `1f019609f9aa68966c7f34b97d3e950bb206e146`。着手前の`make clean && ./scripts/verify.sh`は終了コード0、`PASS: 474 game logic checks`、ROM 32,215 bytes、SHA-256 `4dbe9a77594316e1d53e5875f8475aa52f75372766c950bd811cd2cc0a26a87d`。
- 制約: 外部音源・権利不明素材・浮動小数・動的確保を使わない。固定小配列、整数、75Hzの決定的スケジュール、厳格C89、cc65 warnings-as-errors、ホストテスト可能なサウンド状態を維持する。コミット・push・deploy、BIOS・`lynxboot.img`・外部ROMの取得/探索/生成/同梱は禁止する。

#### APS-013音源境界の確認

- 固定cc65 2.19の`include/lynx.h`は`lynx_snd_init/play/stop/...`と、`MIKEY`疑似変数によるハードウェアアクセスを公開する。`include/_mikey.h`では4音源チャンネルを`0xFD20`、`0xFD28`、`0xFD30`、`0xFD38`から各8レジスタ、attenuation/panningを`0xFD40`〜`0xFD44`、stereo制御を`0xFD50`として定義する。
- 標準`libsrc/lynx/lynx-snd.s`はTimer 7を240Hz IRQへ設定し、4チャンネルと独自コマンドストリーム/エンベロープを管理する。一方、現行TGIはTimer 0/2とVBlank IRQを使う割り込み駆動ダブルバッファである。
- 本課題はサウンド進行をホスト側と同じ75Hzで完全再現するため、標準サウンドドライバのTimer 7/独自ストリームを使わない。純Cのサウンド状態が1フレームごとの論理出力を決め、Lynx側は初期化時にcrt0のmute値を解除する`MSTEREO`（`0xFD50`）=0を一度設定し、その後はchannel Aの`0xFD20`〜`0xFD27`だけへ反映する。Timer 0/2/7、割り込み、表示、他の3音源チャンネル、attenuation/panningへは触れない。

#### APS-013確定仕様

- `include/sound.h`と`src/sound.c`へプラットフォーム非依存の固定シーケンサを新設し、`GameState`から観測できる`SoundState`として保持する。BGM/SFXの固定ステップ表は音程ID、長さ、音量、波形種別だけを小配列で持ち、出力はactive、音程ID、音量、波形種別として公開する。乱数、時刻、浮動小数、動的確保は使わない。
- Stage 1は遅く広がる宇宙アルペジオ、Stage 2は短い上昇音型を持つ速い飛行モチーフ、Stage 3は低音と休符を多くした洞窟モチーフとし、テンポ・音域・音型が明確に異なる自作ループにする。Stage 1初期化で曲頭から開始し、INTRO/NORMAL/WARNING/BOSS/STAGE CLEARでは同Stageの曲位置を維持する。Stage移行時だけ次曲の曲頭へ切り替え、GAME OVER/ALL CLEARで停止し、完全再開始でStage 1曲頭へ戻す。
- 自機死亡32更新中だけBGMカーソルを凍結するが、自機爆発SFXは進める。通常のSFX中はBGMカーソルを無音で進め、SFX終了後はその時点のBGM位置へ戻す。非最終再出撃後は死亡開始時のBGM位置から再開する。
- SFXは射撃、敵撃破、自機爆発、アイテム取得、WARNING、ボス撃破、ステージクリアの7種。成功した1斉射だけで射撃、通常敵命中撃破と小惑星破壊で敵撃破、実損傷の死亡開始だけで自機爆発、Lv3時を含む実取得でアイテム取得、`enter_phase(WARNING)`でWARNING、HP0確定でボス撃破、`enter_phase(STAGE_CLEAR)`でステージクリアを各1回発火する。失敗射撃、無敵損傷、単なる生成/表示更新では鳴らさない。同一更新の複数通常敵/小惑星撃破は敵撃破音1回へ集約する。
- SFX優先度は低い順に射撃1、敵撃破2、アイテム取得3、WARNING 4、自機爆発5、STAGE CLEAR 6、Boss撃破7とする。同一以上の優先度は現在音を破棄して新音を先頭から開始し、同一IDも再発火なら再始動する。低優先度要求は破棄するが、Boss撃破中のSTAGE CLEARだけは固定1件の専用保留へ一度保存し、Boss撃破終了後に再生する。Boss撃破+STAGE CLEARの合計長は120更新未満、PLAYER EXPLOSIONは32更新以下とする。
- GAME OVER/ALL CLEAR成立、Stage切替、完全再開始ではactive SFXと保留を必ず破棄する。Stage切替は次曲の曲頭、再開始はStage 1曲頭から開始する。Boss撃破→STAGE CLEAR連鎖は120更新内に完了させ、通常のStage切替/ALL CLEARで切断されないことをテストする。
- Lynxバックエンドは`src/main.c`だけに置き、`game_update()`後・描画前に公開出力をvolatileな8-bitアクセスで反映する。初期化時は`MSTEREO=0`、channel Aのvolume/control=0とする。停止/休符はvolume=0、control=0。再設定はcontrol=0→shift-low/control-B/feedback→volume→reload→control=`prescaler|0x18`の公式順序とし、channel AのOUT/DAC（`0xFD22`）とCOUNT（`0xFD26`）へは書かない。レジスタ値は固定表と整数だけで生成し、cc65 2.19で警告ゼロにする。

#### APS-013完了条件

- APS-012の474チェックの意味を維持し、純Cサウンド単体テストとゲーム統合テストを追加する。3曲のID/曲頭/ループ/差異、休符、BGM継続/死亡凍結/Stage切替/停止/再開始、7 SFXの正しい一度だけ発火、同時イベントの優先・保留・復帰、失敗射撃/無敵接触の無音、全固定上限を境界前後で検証する。
- `Makefile`へ共有`sound.c`のホスト/ROMビルドとテストを統合し、`make clean && ./scripts/verify.sh`、ASan/UBSan付き全ホストテスト、`sh -n scripts/*.sh`、LNX検査、`git diff --check`を成功させる。最終チェック総数、ROMサイズ/SHA-256、変更ファイル、設計差分、未確認事項を本項へ追記する。
- Gearlynxは既存導入・設定済み環境だけを使える場合に限り、音が出ること、3曲の差、7 SFX、SFX優先、遷移時の停止/再開を可能な範囲で聴感確認する。BIOSファイル自体は探索・読取・取得・複製・同梱しない。
- 実装・文書・実測差分をDev FrontがVERIFY以上で独立検収する。コミット・push・deployは行わない。

#### APS-013実装実績

- 変更ファイルは`Makefile`、`include/game.h`、新規`include/sound.h`、`src/game.c`、`src/main.c`、新規`src/sound.c`、`tests/test_game.c`、新規`tests/test_sound.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。発行済み`.briefs/APS-001`〜`.briefs/APS-013/v002.md`、`CLAUDE.md`、`.gitignore`、`scripts/`、リンカ設定、`docs/plan/toolchain-research.md`は変更していない。
- `SoundState`を`GameState`へ統合し、BGM/SFXそれぞれの固定カーソルと残り更新、Boss撃破中のSTAGE CLEAR専用保留1件、active/note/volume/waveの論理出力を公開した。状態と表は固定長の`unsigned char`中心で、乱数、時刻、浮動小数、動的確保を使わない。
- Stage 1は8ステップ・各15更新・全120更新の宇宙アルペジオ、Stage 2は8ステップ・各5更新・全40更新の上昇飛行モチーフ、Stage 3は低音3音と休符3個からなる全78更新の洞窟モチーフとして実装した。初期化はStage 1曲頭、同Stageの5フェーズでは位置維持、Stage切替は次曲頭、GAME OVER/ALL CLEARは停止、完全再開始はStage 1曲頭とした。
- SFX全長は射撃8、敵撃破12、取得15、WARNING 32、自機爆発32、STAGE CLEAR 36、Boss撃破48更新。指定の優先度1〜7、同一以上による先頭再始動、低優先度破棄、Boss撃破中のCLEARだけを冪等保留する規則を一つの要求関数へ集約した。Boss→CLEARは合計84更新で完了する。
- ゲーム側の集中発火点へ7種を統合した。成功した1斉射、同一更新に集約した通常敵/小惑星撃破、実死亡開始、Lv3を含む実アイテム消費、`enter_phase(WARNING)`、Boss HP0確定、`enter_phase(STAGE_CLEAR)`だけが発火する。失敗射撃、アイテム生成、無敵接触は無音とした。
- `game_update()`を全経路共通のサウンドtickで包み、通常SFX中はBGMを進め、死亡開始後の32死亡更新だけはBGMカーソルを固定した。GAME OVER/ALL CLEAR、Stage切替、完全再開始ではactive SFXと保留を明示的に破棄する。
- `src/main.c`にだけMIKEYバックエンドを追加した。初期化時に`MSTEREO=0`とchannel AのVOL/CTLA=0を設定し、以後は`0xFD20/21/23/24/25/27`だけへvolatile 8-bitで書く。音程/波形変更時はCTLA停止→SHIFTLO/CTLB/FEEDBACK→VOL→RELOAD→CTLA=`prescaler|0x18`、音量だけの変更時はVOLだけ、休符/停止はVOL/CTLA=0とした。OUT/DAC、COUNT、Timer、他チャンネル、attenuation/panningには書かず、`lynx_snd_*`もリンクしていない。
- `Makefile`へ共有`sound.c`のホスト/ROMオブジェクトと`test_sound`を統合した。既存474ゲームチェックの意味を保ち、ゲーム統合を33件追加して507件、純Cサウンド単体130件、合計637件とした。

#### APS-013検証実績

- 着手前の`make clean && ./scripts/verify.sh`: 終了コード0。`PASS: 474 game logic checks`、LNX 32,215 bytes、SHA-256 `4dbe9a77594316e1d53e5875f8475aa52f75372766c950bd811cd2cc0a26a87d`で指定基点を再確認した。
- 実装後の`make clean && ./scripts/verify.sh`: 終了コード0。`PASS: 507 game logic checks`と`PASS: 130 sound logic checks`、clang `-std=c89 -pedantic -Wall -Wextra -Werror`のホストビルド/構文検査、cc65 2.19 `-t lynx -Oirs --standard cc65 -W error`の全C/リンク、`sh -n scripts/*.sh`、LNX検査が成功した。
- ASan/UBSan game: `clang -std=c89 -pedantic -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -Iinclude -o build/test-game-sanitize tests/test_game.c src/game.c src/sound.c && ./build/test-game-sanitize`は終了コード0、507チェック成功。
- ASan/UBSan sound: `clang -std=c89 -pedantic -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -Iinclude -o build/test-sound-sanitize tests/test_sound.c src/sound.c && ./build/test-sound-sanitize`は終了コード0、130チェック成功。
- `sh -n scripts/*.sh`: 終了コード0。`git diff --check`: 終了コード0、出力なし。LNX再検査は`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=35478 bytes`。
- MIKEY境界: `src/main.c`のアドレス定義・書込を`rg`で再確認し、`0xFD20/21/23/24/25/27/50`以外の新規ハードウェア書込がないこと、map/labelに`lynx_snd`シンボルがないことを確認した。
- ROMは`dist/asteroid-patrol.lnx`、35,478 bytes、SHA-256 `40924836bfd0d1fe4aa5d1db36a81f7127c1946b3ecabdd6285ae5f022e0d9cf`。
- Dev Front独立検収（2026-08-03）: `make clean && ./scripts/verify.sh`を再実行し、ゲーム507件＋サウンド130件、cc65 2.19の`-W error`、shell lint、LNX検査を確認した。別途ASan/UBSan付きゲーム・サウンド全テストも成功し、`git diff --check`と新規サウンド3ファイルの整形検査、MIKEY書込み範囲（`0xFD20/21/23/24/25/27/50`のみ）および`lynx_snd`未リンクを再確認して一次検収を合格とした。
- コミット・push・deploy・stash・reset・checkoutは行っていない。BIOS、`lynxboot.img`、外部ROM、外部画像/音声素材の取得・探索・読取・生成・複製・同梱・操作も行っていない。

#### APS-013設計差分

- 確定仕様との差分なし。仕様内で未指定だった固定実測値として、3曲のループ長を120/40/78更新、7 SFXの長さを8/12/15/32/32/36/48更新、論理音量上限を31、波形をtone/metallic/noise/pulseの4種に確定した。論理音程1〜16のprescaler/reloadはcc65 2.19標準ドライバの固定表から連続16音を採用した。

#### APS-013未確認事項

- 自動実行環境では聴感を判定できないため、Gearlynxでの実発音、3曲の音域・テンポ・音型の差、7 SFXの聴き分け、優先割込み、Boss→CLEAR連鎖、死亡/Stage切替/終了/再開始時の聴感は未確認。BIOSファイルの探索・読取を避けるためエミュレータは起動していない。
- Atari Lynx実機での音量、波形、音程、ノイズ特性、TGI描画と同時動作した際の聴感・処理負荷、長時間連続プレイは未確認。

### APS-012: 3Stage固有環境ギミック

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 通常区間だけで動作するStage固有環境ギミックとして、Stage 1の破壊可能な小惑星、Stage 2の予告付き上下風帯、Stage 3の予告付き落石を追加し、既存の背景・敵・Boss・死亡・進行・再開始を維持する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。新規共有C/Hと`Makefile`変更は不要だった。
- 制約: APS-011一次検収済みの420チェック、通常敵4体、敵弾16、自機弾12、強化アイテム1、3Stage背景/敵/Boss、通常1125更新、死亡/GAME OVER/ALL CLEARを維持する。固定配列、決定的整数、厳格C89、cc65 warnings-as-errorsを維持し、外部素材、BIOS・外部ROM・エミュレータ操作、コミット・pushは禁止する。

#### APS-012確定仕様

- Stage設定へ環境IDを追加し、Stage 1/2/3を`ASTEROIDS`/`WIND`/`ROCKFALL`へ対応させる。イベント、移動、衝突、得点はNORMALだけで更新し、通常区間へ入るたび初期化する。WARNING以降と再開始では全環境状態を消去し、死亡爆発32更新中は完全凍結する。
- Stage 1は固定2スロット、8x8、1HP、250点の小惑星を通常経過60/240/420/600/780/960更新にX=152、Y=22/70/44/84/30/60へ生成する。生成更新は移動・衝突を省略し、以後1px/更新で左へ動かす。通常敵命中を先に解決し、自機弾1発で破壊する。自機接触では無得点で消去して共通損傷へ渡し、無敵中も小惑星は消去する。
- Stage 2は150/510/870更新に上端Y=18/58/36、高さ24、方向=上/下/上の風帯を開始する。45更新の予告中は無作用で、その後150更新だけ自機AABBへ作用する。既存方向入力後、2更新ごとに1px押し、Y=10〜96へクランプする。自機以外へ作用せず損傷を与えない。
- Stage 3は固定2スロットで90/240/390/540/690/840/990更新にX=24/72/120/48/136/96/16、着地点Y=94の45更新予告を開始する。予告後にY=10へ8x8岩石を生成し、次更新からX固定・Y+2で落下する。Y=94でも先に自機AABBを評価し、接触/着地後は12更新の着地表示へ移る。自機弾では破壊できず無得点とする。
- 各固定2スロットは空き番号昇順で確保し、満杯イベントは蓄積・再試行せずカーソルを進める。複数環境物・敵・敵弾の同時損傷も残機減少を1回へ集約する。描画は背景/HUD境界より後、通常戦闘物より前とし、非NORMALでは描画しない。

#### APS-012完了条件

- APS-011の420チェックの意味を維持し、全Stageの環境ID、通常区間開始/終了/死亡/GAME OVER/ALL CLEAR再開始での初期化・凍結・無害をホストテストする。
- Stage 1の6境界、固定座標、昇順スロット、満杯破棄、生成更新省略、1px移動、画面外消去、通常敵優先、1発1対象、250点一度だけ、接触・無敵・同時損傷をテストする。
- Stage 2の3境界、45/150更新、帯座標/向き、帯外無作用、入力後2更新/1px、上下クランプ、終了、死亡凍結/再開をテストする。
- Stage 3の7境界、固定X、45更新予告、生成更新省略、2px落下、Y=94衝突、12更新表示、非破壊/無得点、昇順スロット、満杯破棄、無敵/複数同時損傷をテストする。
- `make clean`後の`./scripts/verify.sh`、ASan/UBSan付き同一テスト、`git diff --check`を成功させ、ROMサイズ/SHA-256、設計差分、未確認事項を記録する。

#### APS-012実装実績

- 状態: 実装・自動検証完了。変更ファイルは`include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有C/Hと`Makefile`変更は不要だった。発行済み`.briefs/APS-001`〜`.briefs/APS-012/v001.md`は変更していない。
- `GameStageConfig`へ環境ID、`GameState`へ小惑星2スロット、落石2スロット、風帯状態、共有イベントカーソルを追加した。全状態は固定長・整数で、既存敵/弾/アイテムプールと分離した。
- Stage 1は固定6イベント、X=152、Y固定表、1px左移動、1HP/250点を実装した。通常敵命中後に活動中の弾だけを小惑星へ判定し、生成スロットはその更新の弾/移動/接触から除外する。接触時は小惑星を消去して既存損傷集約へ渡す。
- Stage 2は固定3イベント、45更新予告、150更新有効、2更新/1pxの押し間引きを実装した。入力後に風を適用し、自機AABBが帯内の時だけY=10〜96内で押す。予告/有効の点線・流線と上下矢印を色6/14で描く。
- Stage 3は固定7イベント、45更新予告、Y=10生成、Y+2落下、Y=94着地判定、12更新着地表示を実装した。着地点8pxマーカー/疎な縦ガイドと8x8・2フレーム岩マスクを色14および5/13で描く。自機弾判定へは加えず非破壊・無得点とした。
- NORMALの更新順を入力→イベント/風→射撃→通常敵命中→小惑星命中→既存戦闘物→既存損傷検出→小惑星/落石接触→損傷1回集約へ固定した。通常区間終了と全非戦闘遷移で環境を消去し、死亡中は更新を迂回して凍結、非最終再出撃後は同じ状態から再開、最終爆発完了時はGAME OVER表示前に消去する。
- 回帰テストを420から474チェックへ拡張した。全イベント表、固定上限/昇順確保/満杯破棄、生成更新省略、得点/優先順位、風の境界/入力順/クランプ、落石の着地/非破壊/表示期間、無敵/複数同時損傷、死亡凍結/再開、WARNING/GAME OVER/ALL CLEAR初期化を追加した。

#### APS-012検証実績

- `make clean && ./scripts/verify.sh`: 終了コード0。ホストテスト`PASS: 474 game logic checks`、clang `-std=c89 -pedantic -Wall -Wextra -Werror`、cc65 `-t lynx -Oirs --standard cc65 -W error`の全C/リンク、`sh -n scripts/*.sh`、LNX検査が成功した。
- ASan/UBSan: `clang -std=c89 -pedantic -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -Iinclude -o build/test-game-sanitize tests/test_game.c src/game.c && ./build/test-game-sanitize`を実行し、終了コード0、`PASS: 474 game logic checks`。
- `git diff --check`: 終了コード0、出力なし。
- LNX検査: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=32215 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、32,215 bytes、SHA-256 `4dbe9a77594316e1d53e5875f8475aa52f75372766c950bd811cd2cc0a26a87d`。
- コミット・push・stash・reset・checkout、BIOS・`lynxboot.img`・外部ROM・外部画像/音声素材の取得・探索・生成・同梱・操作、エミュレータ起動は行っていない。

#### APS-012設計差分

- 確定仕様との差分なし。小惑星と落石は各8x8・2フレームの固定1bitマスク、風は全幅の疎な点線/流線と4組の矢印、落石予告は8px着地線と疎な縦ガイド、着地表示は2本の水平線とした。

#### APS-012未確認事項

- 指示どおりエミュレータを起動していないため、Stage 1小惑星の背景/敵との識別性、Stage 2のSKY背景上での予告/有効風帯の視認性と密度、Stage 3の落下ガイド/岩石/着地表示の視認性、通常戦闘との重なり、描画負荷、操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

#### APS-012一次検収

- Dev Frontが`make clean && ./scripts/verify.sh`を独立再実行し、終了コード0、`PASS: 474 game logic checks`、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ検査の成功を確認した。ROMは32,215 bytes、SHA-256は`4dbe9a77594316e1d53e5875f8475aa52f75372766c950bd811cd2cc0a26a87d`でDev報告と一致した。
- clang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも474チェックで合格した。固定イベント表、専用2スロット、生成更新省略、通常敵命中優先、風の入力後適用、落石の着地判定、損傷1回集約、死亡凍結、非通常フェーズ消去、文書整合、禁止範囲と発行済みブリーフ不変を差分で確認し、一次検収合格とした。

### APS-011: Stage 3洞窟・洞窟敵編成・岩石コアボス

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: Stage 3を洞窟テーマへ置換し、天井・床・鍾乳石・奥壁の多層背景、洞窟生物/採掘ドローン編成、守護生物状の岩石コアボスを共通Stage基盤へ統合する。撃破後はALL CLEARへ進み、解除後のA/B再押下で完全初期化する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。新規共有C/HとMakefileは明確な必要がある場合だけ許可する。
- 制約: APS-010一次検収済みの378チェック、Stage 1宇宙、Stage 2惑星上空、共通状態機械を維持する。固定配列、決定的整数、厳格C89、cc65 warnings-as-errors、16色TGI水平ラン、ホストテスト可能な共有ロジックを維持する。地形は背景のみで衝突判定を追加しない。外部素材、BIOS・外部ROM・エミュレータ操作、コミット・pushは禁止する。

#### APS-011確定仕様

- 背景テーマ`CAVE`、敵編成`CAVE`、ボス外観`ROCK_GUARDIAN`を追加し、Stage 3だけへ設定する。Stage 1の`SPACE`とStage 2の`SKY`、各編成・ボス外観を不変とする。Stage 2 CLEARからStage 3導入へ入る時に3層背景offset/counterを0へ戻す。
- `CAVE`は奥壁色1、最背面の岩陰/亀裂色3、中景の天井・床岩肌色5、近景の鍾乳石/石筍色13を基本とする。固定水平ラン/座標表で、奥壁模様を192px周期・8更新/1px、天井/床岩肌を160px周期・4更新/1px、鍾乳石/石筍を160px周期・2更新/1pxで左へ動かす。背景はプレイ領域を視覚的に囲うが、地形衝突・可動地形・乱数・浮動小数・動的確保を追加しない。
- 洞窟敵として8x8・各2フレームの`CAVE_BAT`、`ROCK_WORM`、`MINING_DRONE`を追加する。BATは羽ばたく翼、WORMは節状の生物、DRONEは箱形機体とドリル/ランプを持たせ、既存6種とも相互にも識別できる固定マスクと専用色12/9/14を使う。
- `CAVE`初期4枠はX=148/184/216/248、Y=22/72/44/82、種別CAVE_BAT/ROCK_WORM/CAVE_BAT/MINING_DRONE、移動wave/dive/straight/wave、発射間隔66/84/66/78、位相0/16/32/48とする。撃破は各100点。slot 3 MINING_DRONEだけが強化アイテムを落とす。
- Stage 3撃破後再配置はX=`188 + slot * 18`、Y=`16 + seed * 23 % 74`とし、slot 0〜2はCAVE_BAT/ROCK_WORMと3移動を循環、slot 3はMINING_DRONEを維持する。時間差進入、発射上限、再配置更新省略、`drops_power`判定を既存データ境界で扱う。
- Stage 3ボスは既存設定のHP120、24x24、停止位置(132,39)、撃破5000点を維持する。`ROCK_GUARDIAN`は24x24内・2色以内・2フレームの固定水平ランで、大きな岩殻、中央の発光コア、上下の牙/鉤爪を表し、Stage 1要塞・Stage 2母艦と明確に異なる守護生物/岩石コア形状にする。
- Stage 3ボス攻撃を3つの固定手順とする。手順1は90更新静止し10更新ごとに中央から速度(-2,0)の周期バースト、手順2は120更新静止し40更新ごとに上から(-2,+1)・下から(-2,-1)の上下挟撃、手順3は120更新の広域移動中に60更新ごと同じ上下挟撃を行う。広域移動は2更新に1pxでY=21〜57を往復し、方向に応じX=128/132を切り替える。330更新で手順1へ戻る。
- 16敵弾上限、満杯時非蓄積、HP0優先、死亡後のBoss HP保持と位置/移動/攻撃初期化、爆発・無敵・GAME OVERを維持する。Stage 3 Boss撃破後は5000点を一度だけ加え、CLEAR 120更新後にALL CLEARへ進む。得点・残機・武器Lvは保持し、ALL CLEAR成立後のA/B解除→再押下だけでStage 1・得点0・残機3・武器Lv1・全背景/戦闘/進行状態を初期化する。

#### APS-011完了条件

- APS-010の378チェックの意味を維持し、Stage 3のCAVE設定、Stage 3導入時背景0初期化、8/4/2速度・192/160/160ラップ、爆発/GAME OVER/ALL CLEAR凍結、非最終死亡保持をホストテストする。
- CAVE 4枠の全フィールド、時間差進入、撃破再配置式、BAT/WORM循環、MINING_DRONE固定と限定ドロップ、Stage 1 Dropper・Stage 2 SUPPLY回帰をテストする。
- Boss HP/AABB/座標/得点、2フレーム外観ID、バースト10境界、挟撃40境界、移動フェーズ60境界、90/120/120切替と330循環、Y=21/57・X=128/132、弾満杯、HP0優先、死亡後HP保持、ALL CLEAR遷移と解除後再押下の完全初期化をテストする。
- コードレビューで洞窟専用4色、奥壁・天井床・鍾乳石の3層固定表、洞窟敵3種各2フレーム、24x24岩石コア2フレーム・2色以内・クリップ、Stage 1/2との差異を確認できる。
- `make clean`後の`./scripts/verify.sh`、`git diff --check`を成功させ、実測値・設計差分・未確認事項を記録する。

#### APS-011実装実績

- 状態: 実装・自動検証完了。
- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有C/Hと`Makefile`変更は不要だった。発行済み`.briefs/APS-001`〜`.briefs/APS-011/v001.md`は変更していない。
- Stage 3設定を`CAVE`背景、`CAVE`編成、Boss設定2、`ROCK_GUARDIAN`外観へ置換した。Stage 1の`SPACE`/`SPACE`/`SPACE_FORTRESS`、Stage 2の`SKY`/`AIR`/`AIR_CARRIER`は維持した。Stage 2 CLEARからStage 3導入へ入る境界で3層offset/counterを0へ戻す。
- `CAVE`描画へ奥壁1、岩陰/亀裂3、天井床5、鍾乳石/石筍13を固定した。奥壁亀裂18本を192px周期、中景の天井床22本と近景の鍾乳石/石筍26本を160px周期の固定水平ランとし、共通の符号付き左右クリップを通して8/4/2更新に1pxでスクロールする。乱数・浮動小数・動的確保・地形衝突は追加していない。
- CAVE_BAT/ROCK_WORM/MINING_DRONEを8x8・各2フレームの自作マスクと専用色12/9/14で追加した。CAVE初期4枠をX=148/184/216/248、Y=22/72/44/82、BAT/WORM/BAT/DRONE、wave/dive/straight/wave、間隔66/84/66/78、位相0/16/32/48へ固定し、時間差進入を維持した。
- CAVE撃破後はX=`188 + slot * 18`、Y=`16 + seed * 23 % 74`、slot 0〜2のBAT/WORM・3移動循環、slot 3 MINING_DRONE固定を編成設定から実行する。MINING_DRONEだけに`drops_power`を設定し、Stage 1 DropperとStage 2 SUPPLYも維持した。
- `ROCK_GUARDIAN`を24x24内・色13/5の36固定水平ラン×2フレームで追加した。大きな岩殻、中央の発光コア、左上/左下の牙・鉤爪を別外観IDで描き、全ランを既存の符号付きクリップ処理へ通す。中央コアの砲口はBoss左端2px前・Y+12、上下砲口は同X・Y+2/Y+20へ合わせた。
- Stage 3 BossはHP120、24x24、停止(132,39)、5000点を維持した。90更新の静止バーストを10ごと、120更新の静止挟撃を40ごと、120更新の広域移動挟撃を60ごとに発射して330更新で循環する。広域移動は2更新に1pxでY=21〜57を往復し、下降X=128・上昇X=132へ切り替える。死亡後はHPを保持して位置・方向・移動位相・手順・攻撃タイマーを初期化する。
- Stage 3撃破で5000点を一度だけ加算し、CLEAR 120更新後にALL CLEARへ進める。得点・残機・武器Lvを保持し、ALL CLEAR中は戦闘物・背景・進行を凍結する。成立後のA/B押しっぱなしを拒否し、解除後の再押下だけで`game_init()`相当のStage 1・得点0・残機3・武器Lv1・全状態初期化を行う。
- 回帰テストを378から420チェックへ拡張した。Stage 3の4 ID、CAVE全枠/時間差進入/再配置/限定ドロップ、8/4/2境界・192/160/160ラップ・導入初期化・爆発/ALL CLEAR凍結、岩石コアのHP/AABB/外観/得点、10/40/60境界、90/120/120切替・330循環、Y=21/57・X=128/132、弾満杯非蓄積、死亡リセット、撃破からALL CLEAR、解除後再押下の完全初期化を追加し、既存378チェックの意味を維持した。

#### APS-011検証実績

- `make clean`: 終了コード0。その後の`./scripts/verify.sh`: 終了コード0。clang `-std=c89 -pedantic -Wall -Wextra -Werror`のホストビルド/構文検査、cc65 `-t lynx -Oirs --standard cc65 -W error`の全コンパイル/リンク、`sh -n scripts/*.sh`、LNX検査がすべて成功した。
- ホストテスト: `PASS: 420 game logic checks`。clang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも420チェックで合格した（ビルド/実行とも終了コード0）。
- `git diff --check`: 終了コード0、出力なし。
- LNX検査: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=26815 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、26,815 bytes、SHA-256 `a1d494e14ba503b160aeaee16087525962c528c0d2595da69116b4abe96b865f`。
- コミット・push、BIOS・`lynxboot.img`・外部ROM・外部画像/音声素材の取得・探索・生成・同梱・操作、エミュレータ起動は行っていない。

#### APS-011設計差分

- 確定仕様との差分なし。仕様で未指定だった固定表の本数は奥壁亀裂18本、天井床22本、鍾乳石/石筍26本、岩石コア36本×2フレームとした。岩石コアは既存Boss色13/5を用い、下降時X=128・上昇時X=132として方向とXを対応させた。

#### APS-011未確認事項

- 指示どおりエミュレータを起動していないため、Gearlynx/Handyでの洞窟4色の視認性と奥行き、天井床の囲い、鍾乳石/石筍のクリップ、洞窟敵3種の識別性、岩石コアの岩殻・発光コア・牙/鉤爪、2フレーム点滅、砲口と弾の視覚的接続、16敵弾時の描画負荷と操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

#### APS-011一次検収

- Dev Frontが`make clean && ./scripts/verify.sh`を独立再実行し、終了コード0、`PASS: 420 game logic checks`、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ検査の成功を確認した。ROMは26,815 bytes、SHA-256は`a1d494e14ba503b160aeaee16087525962c528c0d2595da69116b4abe96b865f`でDev報告と一致した。
- clang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも420チェックで合格した。Stage 1/2回帰、CAVE固定表/配色/クリップ、洞窟敵3種×2フレーム、MINING_DRONE限定ドロップ、ROCK_GUARDIAN 36ラン×2フレーム/2色、90/120/120更新攻撃と広域移動、ALL CLEAR凍結・A/B解除後再押下の完全初期化、禁止範囲と発行済みブリーフ不変を差分で確認し、一次検収合格とした。

### APS-010: Stage 2惑星上空・航空機編成・空中母艦ボス

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: Stage 2をStage 1宇宙と明確に異なる惑星上空テーマへ置換し、空・雲・山並みの多層背景、航空機系通常敵、大型空中母艦ボスをAPS-008/009のデータ境界へ統合する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。新規共有C/HとMakefileは明確な必要がある場合だけ許可する。
- 制約: APS-009一次検収済みの343チェック、Stage 1宇宙、共通状態機械を維持する。固定配列、決定的整数、厳格C89、cc65 warnings-as-errors、16色TGI水平ラン、ホストテスト可能な共有ロジックを維持する。地形は背景のみで衝突判定を追加しない。外部素材、BIOS・外部ROM・エミュレータ操作、コミット・pushは禁止する。

#### APS-010確定仕様

- 背景テーマ`SKY`、敵編成`AIR`、ボス外観`AIR_CARRIER`を新設し、Stage 2設定だけがこれらを参照する。Stage 1の`SPACE`/宇宙編成/`SPACE_FORTRESS`を不変とし、Stage 3はAPS-011まで暫定`SPACE`を利用してよい。
- Stage 2開始時に3層背景オフセット/間引きカウンタを0へ戻し、Stage固有背景を決定的な同じ位置から始める。非最終死亡、無敵、同一Stage内のフェーズ遷移では背景状態を保持し、爆発/GAME OVER/ALL CLEAR中は凍結する。
- `SKY`は空色の単色背景、最背面の山/地平線、中景雲、近景雲の3層とする。山並みは固定の高さ/水平ラン表を192px周期・8更新に1px、中景雲は固定8群を160px周期・4更新に1px、近景雲は中景より大きい固定5群を160px周期・2更新に1pxで左へ動かす。既存のback/mid/near相当の整数状態を再利用または一般化し、浮動小数・乱数・動的確保を使わない。
- Stage 2専用配色は空8、山/地平線4、中景雲7、近景雲15を基本とし、Stage 1の黒0・惑星1/3・星2/7と視覚的に分離する。雲と山はコード内の固定水平ラン/座標表で自作し、画面クリップを通す。地形衝突や可動地形は実装しない。
- 航空機系敵として8x8・各2フレームの`FIGHTER`、`BOMBER`、`SUPPLY`を追加する。FIGHTERは細い機首と後退翼、BOMBERは幅広い双発翼、SUPPLYは箱形胴体/輸送翼で、宇宙敵3種とも互いともシルエットを明確に変え、Stage 2専用色を使う。
- `AIR`初期編成は4枠をX=144/180/212/244、Y=24/64/42/78、種別FIGHTER/BOMBER/FIGHTER/SUPPLY、移動straight/wave/dive/wave、発射間隔72/96/72/84、位相0/18/36/54とする。撃破は各100点。slot 3 SUPPLYだけがDropper相当の強化アイテムを出す。
- 敵状態または敵種データへ`drops_power`相当を持たせ、ドロップ判定を`type == DROPPER`の直接比較からデータ駆動へ移す。Stage 1 slot 3 Dropperの既存ドロップを維持する。Stage 2撃破後再配置はX=`184 + slot * 18`、Y=`14 + seed * 19 % 76`、slot 0〜2はFIGHTER/BOMBERと3移動を循環し、slot 3はSUPPLYを維持する。
- Stage 2ボスはHP90、28x14、停止位置(128,44)、撃破3000点を維持する。`AIR_CARRIER`は平たい飛行甲板/船首、中央船体、上中下3砲門、後部エンジンを持つ28x14以内・2色以内・2フレームの固定水平ランで描き、宇宙要塞と明確に異なる。
- 空中母艦は2更新に1px、初期Y=44の上下±12pxを往復し、X=128を維持する。3砲門を上→中→下の順で循環し、前半120更新は20更新ごと、後半120更新は15更新ごとに直線弾を交互発射して240更新で繰り返す。砲口は外観に対応し、弾速度(-2,0)、16弾上限、満杯時非蓄積、HP0優先を維持する。
- Stage 2ボス撃破後は3000点を一度だけ加え、CLEAR 120更新後にStage 3導入へ進む。得点・残機・武器Lvを保持し、一時オブジェクトを消去する。死亡後はBoss HPを保持して位置・移動・砲門位相・攻撃手順を初期化する。

#### APS-010完了条件

- APS-009の343チェックの意味を維持し、Stage 2のSKY/AIR/AIR_CARRIER設定、Stage 2開始時背景0初期化、8/4/2速度・ラップ、死亡/フェーズ別保持・凍結をホストテストする。
- AIR 4枠の座標・種別・移動・発射間隔/位相、時間差進入、撃破再配置、SUPPLY限定ドロップとStage 1 Dropper回帰をテストする。
- Boss HP/AABB/座標/得点、上下±12の境界、3砲門循環、20/15更新発射、120/240更新手順、弾満杯、HP0優先、死亡後HP保持、Stage 3導入をテストする。
- コードレビューでSKY専用4色、山/地平線・雲2層、8/4/2速度、航空機3種各2フレーム、28x14空中母艦2フレーム・2色以内・クリップ、Stage 1との差異を確認できる。
- `make clean`後の`./scripts/verify.sh`、`git diff --check`を成功させ、実測値・設計差分・未確認事項を記録する。APS-011へ着手しない。

#### APS-010実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有C/Hと`Makefile`変更は不要だった。発行済み`.briefs/APS-001`〜`.briefs/APS-010/v001.md`は変更していない。
- Stage 2設定を`SKY`背景、`AIR`編成、Boss設定1、`AIR_CARRIER`外観へ置換した。Stage 1の`SPACE`/`SPACE`/Boss設定0/`SPACE_FORTRESS`とStage 3の暫定設定は維持した。Stage 1 CLEARからStage 2導入へ入る時だけ既存3層offset/counterを0へ戻し、死亡・無敵・同一Stageフェーズでは保持する。
- `SKY`描画へ空8、山4、中景雲7、近景雲15を固定した。31本の192px山/地平線ラン、固定8群×5本の中景雲ラン、固定5群×7本の近景雲ランを符号付き中間座標と左右クリップで描き、既存8/4/2更新スクロールを再利用した。乱数・浮動小数・動的確保・地形衝突は追加していない。
- FIGHTER/BOMBER/SUPPLYを8x8・各2フレームの自作マスクと専用色14/6/11で追加した。AIR初期4枠をX=144/180/212/244、Y=24/64/42/78、FIGHTER/BOMBER/FIGHTER/SUPPLY、straight/wave/dive/wave、間隔72/96/72/84、位相0/18/36/54へ固定し、時間差進入を維持した。
- 編成設定へ再配置X/間隔、Y最小/範囲/乗数、循環2種、slot 3固定種、発射位相間隔を持たせた。AIR撃破後はX=`184 + slot * 18`、Y=`14 + seed * 19 % 76`、slot 0〜2のFIGHTER/BOMBER・3移動循環、slot 3 SUPPLY固定を実装した。敵状態へ`drops_power`を追加し、命中時の直接的な敵種比較を廃止してStage 1 DropperとStage 2 SUPPLYだけを有効にした。
- `AIR_CARRIER`を28x14内・色13/5の27固定水平ラン×2フレームで追加した。平たい甲板、左向き船首、中央船体、上中下3砲門、後部双発エンジンを描き、宇宙要塞と別外観ID・別ラン表に分離した。全ランは共通の符号付きクリップ処理を通す。
- Stage 2 BossはHP90、28x14、(128,44)、3000点を維持し、X=128固定、2更新に1pxでY=32〜56を往復する。専用3砲門ショットで上→中→下を循環し、前半120更新を20ごと、後半120更新を15ごと、速度(-2,0)で発射する。弾満杯でも砲門位相・攻撃手順を進め、240更新で循環する。
- 回帰テストを343から378チェックへ拡張した。Stage 2の4 ID、AIR全フィールド/時間差進入/再配置/限定ドロップ、SKYの8/4/2境界・ラップ・Stage 2導入初期化・爆発凍結・非最終死亡保持、空中母艦のHP/AABB/座標/得点/Y境界/X固定/3砲門/20・15境界/120・240循環/満杯非蓄積/HP0優先/死亡リセット/Stage 3導入を追加し、既存343チェックの意味を維持した。

#### APS-010検証実績

- `make clean`: 終了コード0。その後の`./scripts/verify.sh`: 終了コード0。clang `-std=c89 -pedantic -Wall -Wextra -Werror`のホストビルド/構文検査、cc65 `-t lynx -Oirs --standard cc65 -W error`の全コンパイル/リンク、`sh -n scripts/*.sh`、LNX検査がすべて成功した。
- ホストテスト: `PASS: 378 game logic checks`。clang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも378チェックで合格した。
- `git diff --check`: 終了コード0、出力なし。
- LNX検査: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=25861 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、25,861 bytes、SHA-256 `b24e3338c6e9a95a537aba0b229162642a922371b8bdb7c24f15bf2a9f83d7aa`。
- コミット・push、BIOS・`lynxboot.img`・外部ROM・外部画像/音声素材の取得・探索・生成・同梱・操作、エミュレータ起動は行っていない。APS-011の起票・設計・ブリーフ・実装にも着手していない。

#### APS-010設計差分

- 確定仕様との差分なし。仕様で未指定だった航空機色はFIGHTER 14、BOMBER 6、SUPPLY 11、空中母艦色は既存Boss系の13/5を採用した。空中母艦の砲口はBoss左端2px前のY+2/Y+7/Y+10へ置き、外観ラン上の上中下砲門へ合わせた。

#### APS-010未確認事項

- 指示どおりエミュレータを起動していないため、Gearlynx/Handyでの空・山・2層雲の配色と奥行き、航空機3種の識別性、空中母艦の甲板・船首・3砲門・後部エンジン、2フレーム点滅、砲口と弾の視覚的接続、16敵弾時の描画負荷と操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

#### APS-010一次検収

- Dev Frontが`make clean && ./scripts/verify.sh`を独立再実行し、終了コード0、`PASS: 378 game logic checks`、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ検査の成功を確認した。ROMは25,861 bytes、SHA-256は`b24e3338c6e9a95a537aba0b229162642a922371b8bdb7c24f15bf2a9f83d7aa`でDev報告と一致した。
- clang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも378チェックで合格した。Stage 1回帰、SKY固定表/配色/クリップ、AIR 3種×2フレーム、データ駆動ドロップ、AIR_CARRIER 27ラン×2フレーム/2色、Boss移動・3砲門・攻撃手順、禁止範囲と発行済みブリーフ不変を差分で確認し、一次検収合格とした。

### APS-009: Stage 1宇宙背景・宇宙敵編成・宇宙要塞ボス

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: APS-008の共通進行基盤へStage 1専用の宇宙テーマ、敵編成、大型宇宙要塞/戦艦ボスのピクセル表現を統合し、通常敵・背景・ボス・攻撃をStage固有データとして識別可能にする。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。新規共有C/HとMakefileは明確な必要がある場合だけ許可する。
- 制約: APS-008一次検収済みの324チェックと3ステージ状態機械を維持する。固定配列、決定的な整数処理、厳格C89、cc65 warnings-as-errors、16色TGI水平ラン、ホストテスト可能な共有ロジックを維持する。外部素材、地形衝突、サウンドは対象外。BIOS・外部ROM・エミュレータ操作、コミット・pushは禁止する。

#### APS-009確定仕様

- Stage設定を背景テーマID、通常敵編成ID、ボス設定ID、ボス外観IDで参照できる固定データへ拡張する。Stage 1は`SPACE`テーマ/編成と`SPACE_FORTRESS`外観を明示し、攻撃・描画へStage番号の直接分岐を散在させない。Stage 2/3はAPS-010/011まで既存宇宙テーマを暫定利用してよいが、後続で別IDへ置換可能な境界を作る。
- Stage 1背景は現行の黒系背景、32x24惑星、遠景星10個、近景星7個、8/4/2更新の3層パララックス、既存2色惑星を維持する。宇宙テーマの配色値と描画器選択を固定データ/定数として明示し、導入・通常・WARNING・BOSS・クリアでAPS-008どおり進行、爆発/GAME OVER/ALL CLEARで凍結する。
- Stage 1通常敵は既存のScout、Saucer、Dropperを宇宙専用3種として維持し、相互に異なる8x8・2フレームの自作マスクを使う。初期4スロットはX=140/170/200/230、Y=47/23/70/38、種別Scout/Saucer/Scout/Dropper、移動は直進/上下波形/急降下折返し/直進、発射間隔90/60/90/75更新とする。
- 上記編成を固定のStage編成表から初期化する。撃破後もStage 1用決定式を編成設定から選び、slot 0〜2はScout/Saucerと3移動を循環、slot 3はDropperを維持し、APS-006のドロップ/武器強化を保つ。時間差進入、100点、再配置更新の移動・発射・接触省略を変えない。
- Stage 1ボスは24x16の大型AABB、HP60、停止位置(132,43)、撃破2000点をAPS-008設定から維持する。外観は宇宙要塞/戦艦として、前方砲塔、中央装甲/コア、後部エンジンがシルエットで分かる24x16以内の固定水平ラン表を新設し、2色以内、2フレームのエンジンまたはコア点滅を8更新アニメーションへ同期する。
- 宇宙要塞マスクは通常敵3種やAPS-008共通仮形状と明確に異なり、ボスAABB内だけを描く。変動座標は符号付き中間値とクリップを通し、160x102外をTGIへ渡さない。外部画像、生成画像、1bitごとの大量描画を使わない。
- Stage 1ボス攻撃はAPS-008の固定スクリプトを宇宙要塞用として明示し、120更新の直線連射区間（20更新ごと1発）と120更新の上下3方向扇状区間（60更新ごと3発）を循環する。砲口座標を外観上の前方砲塔/中央砲口に対応させるが、弾速度(-2,-1/0/+1)、16弾上限、満杯時非蓄積、HP0更新優先は変えない。
- Stage 1導入/通常/WARNING/BOSS/クリア、死亡、GAME OVER、次Stage導入の全遷移で得点・残機・武器Lv保持と一時オブジェクト消去をAPS-008どおり維持する。Stage 1ボス撃破後はStage 1 CLEARを経てStage 2導入へ進める。

#### APS-009完了条件

- APS-008の324チェックの意味を維持し、Stage 1設定ID、宇宙編成4スロット、時間差進入、撃破再配置、Dropper固定/ドロップ、各発射間隔をホストテストで明示する。
- Stage 1ボスのHP/AABB/座標/得点、直線20更新と扇状60更新、手順120更新切替・循環、16弾満杯、HP0優先、死亡後HP保持、Stage 2導入への遷移をテストする。
- コードレビューで宇宙背景3層と色、通常敵3種各2フレーム、24x16宇宙要塞2フレーム、2色以内、砲口対応、水平ランとクリップ、Stage設定IDによる選択を確認できる。
- `make clean`後の`./scripts/verify.sh`、`git diff --check`を成功させ、チェック総数、ROMサイズ、SHA-256、変更ファイル、設計差分、未確認事項を本項へ記録する。APS-010/011へ着手しない。

#### APS-009実装実績

- 状態: 実装・自動検証完了。
- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有C/Hと`Makefile`変更は不要だった。発行済み`.briefs/APS-008/v001.md`・`.briefs/APS-009/v001.md`は変更していない。
- 公開`GameStageConfig`を背景テーマID・通常敵編成ID・Boss設定ID・Boss外観IDの4項目へ拡張した。Stage 1は`SPACE`/`SPACE`/Boss設定0/`SPACE_FORTRESS`、Stage 2/3は後続課題まで`SPACE`背景・編成と共通仮外観を選ぶ。Stage設定と編成スロットの安全な公開参照関数を追加し、範囲外をNULLで拒否する。
- Stage 1の初期4敵をX/Y、Scout/Saucer/Scout/Dropper、直進/波形/急降下/直進、発射間隔90/60/90/75、位相0/15/30/45を持つ固定`SPACE`編成表へ移した。各敵は編成由来の発射間隔を状態に保持し、初期化・死亡再出撃・撃破後再配置はStageの編成IDを経由する。slot 0〜2の種別/移動循環、slot 3 Dropper固定、100点、ドロップ、再配置更新省略を維持した。
- `SPACE`背景テーマへ背景0、惑星1/3、遠景星2、近景星7の色を固定データ化した。Stage設定の背景テーマIDから描画器と配色を選び、32x24惑星、遠景10、近景7、8/4/2更新の3層状態と全フェーズの進行・凍結を変更していない。
- Stage 1 Bossへ`SPACE_FORTRESS`外観IDを保持させ、24x16内の固定水平ラン26本×2フレームを追加した。左前方双砲塔、中央装甲/コア、右後部エンジンを色13/5だけで構成し、既存の8更新アニメーションでコア/エンジン詳細を切り替える。各ランは符号付き中間座標で160x102へクリップしてからTGIへ渡す。Stage 2/3は外観ID経由でAPS-008共通仮形状を維持する。
- Stage 1の直線弾を要塞前方砲塔(130,47)、扇状弾を中央砲口(130,51)へ合わせた。120更新の直線区間を20更新ごと、120更新の扇状区間を60更新ごとに発射し、240更新で循環する既存設定、速度(-2,-1/0/+1)、16弾上限、満杯時非蓄積、HP0優先、HP60/AABB24x16/(132,43)/2000点を維持した。
- 回帰テストを343チェックへ拡張した。4 Stage IDと範囲外拒否、`SPACE`編成全4スロットと発射間隔/位相、各敵状態の編成由来間隔、Stage 1 Boss外観/座標/砲口、直線20・扇状60の直前/境界、120更新切替と240更新循環を追加し、APS-008の324チェックの意味を維持した。

#### APS-009検証実績

- `make clean`: 終了コード0。その後の`./scripts/verify.sh`: 終了コード0。clang `-std=c89 -pedantic -Wall -Wextra -Werror`のホストビルド/構文検査、cc65 `-t lynx -Oirs --standard cc65 -W error`の全コンパイル/リンク、`sh -n scripts/*.sh`、LNX検査がすべて成功した。
- ホストテスト: `PASS: 343 game logic checks`。追加でclang AddressSanitizer/UndefinedBehaviorSanitizer付き同一テストも343チェックで合格した。
- `git diff --check`: 終了コード0、出力なし。
- LNX検査: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=23661 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、23,661 bytes、SHA-256 `280c84d636643aecc9ef3b393991d97c262547650d0f2c7174439bf492cf7290`。
- コミット・push、BIOS・`lynxboot.img`・外部ROM・外部画像/音声素材の取得・探索・生成・同梱・操作、エミュレータ起動は行っていない。APS-010/011の起票・設計・ブリーフ・実装にも着手していない。

#### APS-009設計差分

- 確定仕様との差分なし。仕様で未指定だった色は既存値の背景0、惑星1/3、遠景星2、近景星7、要塞13/5を固定した。外観上の前方を画面左として直線砲口をBoss左端の2px前・Y+4、中央砲口を同X・Y+8へ置いた。Stage 2/3は確定仕様どおり`SPACE`背景/編成と共通仮外観を暫定参照する。

#### APS-009未確認事項

- 指示どおりエミュレータを起動していないため、Gearlynx/Handyでの宇宙要塞シルエット、前方砲塔・中央コア・後部エンジンの識別性、2フレーム点滅、砲口と弾の視覚的接続、3層配色、16敵弾時の描画負荷と操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

#### APS-009一次検収

- Dev Frontが`make clean && ./scripts/verify.sh && git diff --check`を独立再実行し、終了コード0、343チェック、cc65 warnings-as-errors、LNX 23,661 bytes、SHA-256 `280c84d636643aecc9ef3b393991d97c262547650d0f2c7174439bf492cf7290`の一致を確認した。
- clang AddressSanitizer/UndefinedBehaviorSanitizer付き343チェック、Stage/編成ID、宇宙要塞26ラン×2フレームの範囲・2色・クリップ、砲口と240更新攻撃循環、禁止範囲不変を確認し、一次検収合格とした。

### APS-008: 3ステージ共通進行・データ駆動ボス基盤

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: `STAGE表示 → 通常区間 → WARNING → ボス戦 → クリア`を共通状態機械として実装し、Stage 1から3、最終ALL CLEAR、GAME OVER、完全再開始を一つの決定的な進行モデルへ統合する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。新規共有CソースとMakefile変更は、既存2ファイルでは明確に保守不能な場合だけ許可する。
- 制約: 基点コミット`366cce209b7517bcf8deae112de9bf59e13343a9`のAPS-007機能と215チェックの意味を維持する。固定上限、決定的な整数処理、厳格C89、cc65 warnings-as-errors、ホストテスト可能な共有ロジック、TGI描画を維持する。地形衝突、外部素材、サウンドは対象外。BIOS・外部ROMの取得・探索・操作、コミット・pushは禁止する。

#### APS-008確定仕様

- 公開状態としてStage番号1〜3と進行フェーズ`STAGE_INTRO`、`NORMAL`、`WARNING`、`BOSS`、`STAGE_CLEAR`、`ALL_CLEAR`、各フェーズの経過タイマーを持つ。初期状態はStage 1の`STAGE_INTRO`。表示90更新、通常1125更新、WARNING 120更新、クリア120更新とし、75Hzの通常更新だけで決定的に進める。
- 爆発32更新、GAME OVER、ALL CLEAR中はフェーズ・背景・攻撃を凍結する。導入、WARNING、クリア中は戦闘オブジェクトを消去し、背景と通常アニメーションだけを進める。WARNING中は自機移動を許可するが射撃は行わない。NORMALとBOSSだけ既存の入力・射撃・損傷を有効にする。
- 導入完了時に通常敵編成を初期化してNORMALへ入る。NORMAL完了時は通常敵、両陣営の弾、活動アイテムを消去してWARNINGへ入る。WARNING完了時にボスを初期化してBOSSへ入る。ボス撃破時は敵弾・自機弾・アイテムを消去してSTAGE_CLEARへ入れ、ボス得点を一度だけ加算する。Stage 1/2のクリア完了時はStageを1増やして次のSTAGE_INTROへ、Stage 3ではALL CLEARへ入る。
- 得点、残機、武器Lvはステージ間で維持する。活動アイテム、両陣営の弾、通常敵、ボス攻撃位相はフェーズ境界で持ち越さない。通常区間の残り時間は非最終死亡をまたいで保持し、爆発中は進めない。BOSS中の非最終死亡ではボスHPを保持し、位置・移動位相・攻撃スクリプトだけを初期値へ戻す。60更新無敵と武器Lv保持を維持する。
- ボス状態は固定1体とし、活動、矩形、現在/最大HP、設定ID、攻撃手順、攻撃タイマー、移動位相・方向を共有`GameState`へ置く。Stage設定とBoss設定は固定テーブルで参照し、ステージ番号の分岐を攻撃処理へ散在させない。
- Stage 1/2/3のボス最大HPは60/90/120、当たり判定は24x16、28x14、24x24、画面右寄りの停止Xは132/128/132とする。撃破得点は2000/3000/5000。すべて`unsigned char`範囲の整数と固定データで表現する。
- ボス攻撃は固定長スクリプト表と手順データで構成し、直線単発、上下3方向扇状、上下砲門交互、上端・下端から内向きの挟撃、短周期バーストを共通ショット種として扱う。Stage 1は直線連射と3方向扇状、Stage 2は上下砲門交互と上下往復、Stage 3は周期バースト・挟撃と移動フェーズを別スクリプトとして設定する。弾枠満杯でも手順を遅延・蓄積しない。
- 敵弾上限を固定16へ拡張し、各弾へ符号付き整数のX/Y速度を持たせる。通常敵弾は従来どおり(-2,0)。ボス弾は(-2,-1)、(-2,0)、(-2,+1)等の整数速度だけを使い、画面外へ出たら安全に消去する。浮動小数、除算ベースの角度、動的確保、符号なしアンダーフローを使わない。
- BOSS中は自機弾1発につきHPを1減らし、同一更新の複数弾命中は各1ダメージとする。HPが0になった更新は撃破とクリア遷移を優先し、ボス移動・発射・接触を行わない。ボス本体の大型AABBとボス弾は既存死亡シーケンスへ統合し、無敵中は既存どおり残機を減らさない。
- GAME OVERとALL CLEARの再開始は、画面成立後にA/Bを一度離し、その後の新たな押下だけを受け付ける。再開始は`game_init()`相当でStage 1導入、得点0、残機3、武器Lv1、背景、通常敵、ボス、アイテム、全弾、死亡/無敵/進行タイマーを完全初期化し、その更新には射撃しない。
- 描画はフェーズに応じて`STAGE 1`〜`STAGE 3`、`WARNING`、`STAGE CLEAR`、`ALL CLEAR`と再開始案内を表示する。BOSS中は現在HP/最大HPを画面内の固定バーまたは数値で示し、ボスは外部素材を使わない大きな共通ピクセル仮形状で描く。APS-009〜011で各ステージ固有形状へ置換できるデータ境界を保つ。

#### APS-008完了条件

- 既存215チェックの意味を維持し、全フェーズの初期値と境界直前/直後、Stage 1→2→3→ALL CLEAR、ステージ間の得点・残機・武器Lv保持、境界での一時オブジェクト消去をホストテストで明示する。
- 3組のBoss設定、HP・大型AABB・撃破得点、各攻撃スクリプト、固定16敵弾、符号付き移動・画面外消去・満杯時非蓄積、複数弾によるHP減少、撃破更新優先をホストテストする。
- NORMAL/BOSS中の被弾、爆発中の進行凍結、非最終再出撃、ボスHP保持と攻撃リセット、最終爆発後GAME OVER、GAME OVER/ALL CLEAR双方のA/B押しっぱなし防止と完全初期化をテストする。
- `make clean`後の`./scripts/verify.sh`で全ホストテスト、clang厳格C89、cc65 `-W error`、shell lint、ROMビルド、LNXヘッダ/サイズ検査を成功させ、`git diff --check`も通す。結果の終了コード、チェック総数、ROMサイズ、SHA-256を本項へ記録する。
- READMEと設計書を実装に一致させ、設計差分、未確認事項、変更ファイルを本項へ記録する。APS-009〜011の起票・ブリーフ・実装には着手しない。

#### APS-008実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有C/Hファイルと`Makefile`変更は不要だった。発行済み`.briefs/APS-008/v001.md`は変更していない。
- `GameState`へStage番号、6フェーズ、`unsigned int`フェーズ経過、固定1体のボス状態を追加した。Stage 1導入から開始し、導入90、通常1125、警告120、クリア120更新の直前/遷移更新を明示した。導入・警告・クリアでは戦闘物を消去して背景/アニメーションを進め、警告のみ自機移動を許可した。
- Stage設定、Boss設定、固定長攻撃手順をテーブル化した。HP 60/90/120、AABB 24x16・28x14・24x24、停止X 132/128/132、撃破得点2000/3000/5000を設定から初期化し、直線、3方向扇状、上下砲門交互、上下挟撃、短周期バーストと停止/上下往復/広域移動を共通処理で実行する。
- 敵弾を固定16枠の`GameEnemyBullet`へ拡張し、弾ごとの`signed char` X/Y速度と`int`座標中間値で上下左右の画面外消去を実装した。通常敵弾は(-2,0)、ボス弾はX=-2とY=-1/0/+1を使い、満杯でも攻撃タイマーと手順を進める。
- BOSS更新を背景、自機、射撃、自機弾/HP、敵弾、ボス移動/発射、自機損傷の順に分離した。同一更新の複数命中を各1HPとして処理し、HP0なら得点を一度だけ加算して後続ボス処理を省略する。BOSS死亡後はHPとフェーズ経過を保持し、位置・移動・攻撃手順だけを初期化して60戦闘更新無敵で再出撃する。
- GAME OVER/ALL CLEAR共通の解除後再押下処理を最優先し、再開始更新は`game_init()`だけを実行する。Stage 1導入、得点0、残機3、武器Lv1、背景、通常敵、ボス、アイテム、両弾、死亡/無敵/進行状態を完全初期化し、同更新の射撃を抑止する。
- 描画へ常時Stage番号、導入、WARNING、STAGE CLEAR、ALL CLEAR、再開始案内、ボスHPバーを追加した。ボスは外部素材なしの共通大型仮形状をTGI水平ランで描き、ロジック側のBoss設定境界と描画関数をStage固有形状への置換点として分離した。

#### APS-008検証実績

- 基点確認: 編集前の`./scripts/verify.sh`は終了コード0、`PASS: 215 game logic checks`、ROM 15,687 bytesだった。
- 最終検証: `make clean`は終了コード0。その後の`./scripts/verify.sh`は終了コード0。clang `-std=c89 -pedantic -Wall -Wextra -Werror`のホストビルド/構文検査、cc65 `-t lynx -Oirs --standard cc65 -W error`の全コンパイル/リンク、`sh -n scripts/*.sh`、LNX検査がすべて成功した。
- ホストテスト: `PASS: 324 game logic checks`。既存215チェックの意味を維持し、Stage/全フェーズ境界、Stage 1→2→3→ALL CLEAR、境界消去と継続状態、3 Boss設定/手順、16弾上限、満杯時非蓄積、符号付き移動と全方向消去、複数命中、HP0優先、NORMAL/BOSS死亡、爆発凍結、BOSS HP保持、60/61更新無敵、GAME OVER/ALL CLEAR再開始を追加した。
- `git diff --check`: 終了コード0、出力なし。
- LNX検査: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=22135 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、22,135 bytes、SHA-256 `ede312d2d788a61ffd6b8ebb7bac91e50a0a66ebe3a4f6880b9f7313ffaf42fb`。
- コミット・push、BIOS・`lynxboot.img`・外部ROM・外部画像/音声素材の取得・探索・生成・同梱・操作、エミュレータ起動は行っていない。APS-009〜011の起票・設計・ブリーフ・実装にも着手していない。

#### APS-008設計差分

- 確定仕様との差分なし。仕様で未指定だった具体値として、Bossは設定済み停止Xへ直接初期化し、Stage 1は直線20更新/扇状60更新、Stage 2は交互砲門20・15更新、Stage 3はバースト10更新/挟撃40更新の固定周期とした。移動は2更新に1pxで、Stage 2は初期Y±12、Stage 3は初期Y±18とX 4px幅を往復する。これらは攻撃手順/設定表へ集約し、Stage番号分岐を攻撃処理へ追加していない。
- NORMAL最終更新と損傷が競合した場合、その更新をフェーズ経過へ一度加算して爆発中は1125で凍結し、非最終爆発の32回目にWARNINGへ遷移する決定順とした。

#### APS-008未確認事項

- 指示どおりエミュレータを起動していないため、Gearlynx/HandyでのStage/Warning/Clear/ALL CLEAR文言、HUD下のボスHPバー、24〜28px共通ボス仮形状、16敵弾時の描画負荷、操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

#### APS-008一次検収

- Dev Frontが`make clean && ./scripts/verify.sh && git diff --check`を独立再実行し、終了コード0、324チェック、cc65 warnings-as-errors、LNX 22,135 bytes、SHA-256 `ede312d2d788a61ffd6b8ebb7bac91e50a0a66ebe3a4f6880b9f7313ffaf42fb`の一致を確認した。
- clang AddressSanitizer/UndefinedBehaviorSanitizer付きの同一ホストテストも324チェックで合格した。確定仕様、変更許可範囲、発行済みブリーフ不変、禁止操作不実施を差分で確認し、一次検収合格とした。

### APS-007: 最背面ピクセル惑星・3層パララックス

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 星より遅い大きな自作ピクセル惑星を最背面へ追加し、惑星・遠景星・近景星の3層パララックスを構成する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。
- 制約: 惑星32x24、8通常更新に1px、192px周期の固定整数処理と水平ラン表を使う。既存の全ゲームロジック、厳格C89、cc65 warnings-as-errors、ホスト検証を維持する。BIOS・外部ROM・外部素材の取得・操作、コミット・pushは禁止する。

#### APS-007確定仕様

- `GameState`へ惑星オフセットと間引きカウンタを追加する。初期値は両方0。通常状態でカウンタを進め、8更新ごとに惑星オフセットを1増やし、191の次は0へ明示的に戻す。乱数、浮動小数、符号なしアンダーフローは使わない。
- 惑星は32x24px、基準位置(120,18)。描画Xは`120 - offset`とし、左端が-32未満になった場合は192を加えて右側へ循環させる。符号付き中間値で計算し、画面外部分を水平にクリップする。
- `src/main.c`に外部素材を使わない自作惑星データを置く。Lynx負荷を抑えるため1bitずつの描画ではなく、輪郭・リング・クレーター等を相対座標の固定水平ラン表として表現し、暗い本体色と明暗差のある細部色の最大2色で描く。
- 描画順は最背面の惑星、本来の遠景星、近景星、HUD・自機・敵・弾・アイテムの順とする。惑星1px/8更新、遠景星1px/4更新、近景星1px/2更新の速度差をロジック状態で明示する。
- 爆発32更新中は惑星オフセットと間引きカウンタを含む通常状態を凍結する。非最終爆発後は惑星状態を保持し、再出撃後の最初の通常更新からスクロールを再開する。無敵中は通常どおり進む。
- GAME OVER中も惑星状態を凍結する。A/B解除後の再押下による完全再開始では惑星オフセットとカウンタを0へ戻す。背景は衝突や得点などゲームロジックへ影響しない。

#### APS-007完了条件

- APS-006の204チェックの意味を維持し、惑星の8更新境界、0〜191の循環、遠景/近景との速度差、爆発中の全32更新凍結、非最終再出撃後の保持・再開、無敵中進行、GAME OVER凍結、完全再開始0初期化をホストテストで明示検証する。
- 惑星が32x24の固定水平ラン表で自作され、2色以内、基準位置・192周期・画面左右クリップ・最背面描画順が安全であることをコードレビューで確認する。
- `make clean`後の`./scripts/verify.sh`でホストテスト、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ/サイズ検査が成功し、`git diff --check`も通る。
- READMEと設計書を実装に一致させ、本項へ変更内容、実測コマンド/終了コード、チェック総数、ROMサイズ・SHA-256、設計差分、実機/エミュレータ未確認事項を記録する。

#### APS-007実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。Makefile、検証スクリプト、リンカ設定、`.gitignore`、`CLAUDE.md`、ツールチェーン調査、発行済みブリーフは変更していない。
- 公開定数として惑星32x24、基準位置(120,18)、8通常更新/1px、192px周期を追加し、`GameState`へ`planet_offset`と`planet_counter`を追加した。初期値は0で、通常更新冒頭に惑星・遠景・近景の各カウンタを1回ずつ進め、惑星はoffset 191の次を明示的に0へ戻す。
- `src/main.c`へ暗色2色だけを使う固定32本の自作水平ラン表を追加した。24本で丸い32x24輪郭、8本で大小2個のクレーターを構成する。描画Xは符号付き`120 - planet_offset`とし、`x < -32`時だけ192を加算する。各ランのX/Yを符号付きで求め、完全画面外を除外して0〜159へ左右クリップする。
- 描画順を画面クリア、惑星、遠景星、近景星、HUD、自機/爆発、敵、アイテム、両陣営の弾とした。GAME OVER中も凍結した惑星を描画する。惑星は当たり判定、得点、敵、弾、アイテム、武器状態へ関与しない。
- 爆発32更新とGAME OVERでは惑星状態を既存通常状態とともに凍結する。非最終爆発後はoffset/counterを保持し、次の通常更新から再開する。無敵60通常更新と無敵中編成リセットでも継続し、解除後の再押下による完全再開始だけ両値を0へ戻す。

#### APS-007検証実績

- `make clean`（終了コード0）後の`./scripts/verify.sh`（終了コード0）で、clang `-std=c89 -pedantic -Wall -Wextra -Werror`、cc65 `--standard cc65 -W error`、`sh -n scripts/*.sh`、LNXリンク・ヘッダ検査をすべて通した。
- ホストテスト: `PASS: 215 game logic checks`。APS-006の204チェックを維持し、惑星の初期値/公開定数、7/8更新境界、3層の8/4/2速度差、190→191→0循環、Dropper撃破・アイテム生成更新での1回進行、爆発32更新とGAME OVERの凍結、非最終再出撃後の保持・再開、無敵60更新と編成リセット中の進行、完全再開始0初期化を明示検証した。
- コードレビュー: 水平ラン32本、論理範囲X=0〜31/Y=0〜23、色値1/3の2色、基準(120,18)、`x < -32`時の+192、符号付き中間値、左右クリップ、惑星→遠景→近景の描画順を確認した。乱数、浮動小数、動的確保、符号なし負方向減算、外部素材は追加していない。
- `git diff --check`: 成功（終了コード0、出力なし）。LNXヘッダ: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=15687 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、15,687 bytes、SHA-256 `8cb850a8106ca502410ce92652359b5afb5baead9f9ff32968a5d25c55d399de`。
- コミット・push、BIOS・外部ROM・外部素材の取得・探索・生成・同梱、エミュレータ操作は行っていない。

#### APS-007設計差分

- 確定仕様との差分なし。内部ディテールは許可された「リングまたはクレーター」のうち、大小2個のクレーターを固定8ランで実装した。

#### APS-007未確認事項

- 指示に従いエミュレータは起動していない。惑星の輪郭・2クレーターの視認性、星・敵・弾より背面に見える暗色2色、3層の速度差、左右循環時の見え方はGearlynx等で未確認。
- Atari Lynx実機での32本の固定水平ラン追加後の描画性能、フレーム維持、入力応答、他オブジェクトが重なる場面の視認性は未確認。

### APS-006: ドロップ敵・強化アイテム・3段階武器

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 専用ドロップ敵の撃破で強化アイテムを出し、取得により自機の前方射撃を最大3段階へ強化する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。
- 制約: 自機弾12発・強化アイテム1個の固定上限、整数処理、厳格C89互換、既存TGI水平ラン/矩形描画、ホストテスト可能な共有ロジックを維持する。BIOS・外部ROM・外部素材の取得・操作、コミット・pushは禁止する。

#### APS-006確定仕様

- 自機弾の固定上限を3発から12発へ拡張し、武器レベルを1〜3で保持する。Lv1は自機中央から1発、Lv2は上下に離した平行2発、Lv3は自機の高さへ均等配置した前方3発を同時発射する。全弾は既存どおり3x2矩形・右4px/通常更新とし、斜め移動や浮動小数は導入しない。
- 1回の射撃は必要弾数分の空きがある場合だけ全弾を原子的に生成する。空き不足時は部分発射せず、発射クールダウンも開始しない。成功時だけ既存8更新クールダウンを開始する。
- 敵スロット3を専用Dropperとし、初期・死亡後・撃破後もDropper種を維持する。初期X/Yと移動パターンはAPS-005のslot 3（230/38/直進）を維持し、再配置時は既存slot 3の決定式でX/Y/移動を決める。Dropperの決定的な発射間隔は75画面内通常更新とする。
- DropperはScout/Saucerと異なる8x8の自作1bitピクセルマスクを2フレーム持つ。撃破得点は他敵同様100点。Dropper撃破時だけ、撃破前の座標を中心に4x4の強化アイテムを1個生成する。
- 強化アイテムは固定1スロット。すでに活動中なら新しいDropper撃破で置換・位置変更しない。アイテムは2通常更新に1px左へ進み、画面左外へ出たら消える。生成更新には移動・取得判定を行わない。
- アイテムは4x4の自作1bitマスクをTGI水平ランで描き、自機との排他的境界AABBで取得する。取得時は武器レベルを1だけ上げ、最大3に制限する。Lv3でも取得すればアイテムは消えるがレベルは3のままとする。
- 更新順はAPS-005を基礎に、自機弾の敵命中でDropper撃破時にアイテム生成、既存敵弾、敵移動/発射、既存アイテム移動・取得、自機損傷の順とする。新規生成アイテムは次の通常更新から処理する。
- 爆発32更新中は武器レベル、アイテム状態/座標/間引きカウンタ、自機弾12発も凍結対象とする。ただし被弾開始時に全自機弾を消す既存仕様は維持する。
- 非最終死亡後は活動アイテムを消し、その移動カウンタを0へ戻すが、武器レベルは保持する。60更新無敵、4敵/敵弾の初期化はAPS-005どおりとする。無敵中の損傷条件による編成リセットではアイテムと武器レベルを変更しない。
- 最終爆発とGAME OVER中は武器レベルとアイテムも凍結する。A/B解除後の再押下による完全再開始では武器レベルを1、アイテムを非活動、全12自機弾を空へ戻す。

#### APS-006完了条件

- APS-005の144チェックの意味を維持し、12発上限、Lv1/2/3の正確な発射数・Y配置・8更新クールダウン、空き不足時の原子的な非発射、Dropper固定種/75更新発射/固有2フレーム、Dropper限定ドロップ、活動中アイテム非置換、2更新移動・左外消去、AABB取得・最大Lv3、死亡中凍結、非最終死亡でアイテム消去/武器保持、無敵中維持、GAME OVER凍結、再開始Lv1をホストテストとコードレビューで検証する。
- `make clean`後の`./scripts/verify.sh`でホストテスト、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ/サイズ検査が成功し、`git diff --check`も通る。
- READMEと設計書を実装に一致させ、本項へ変更内容、実測コマンド/終了コード、チェック総数、ROMサイズ・SHA-256、設計差分、実機/エミュレータ未確認事項を記録する。

#### APS-006実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。Makefile、検証スクリプト、リンカ設定、`.gitignore`、`CLAUDE.md`、ツールチェーン調査、発行済みブリーフは変更していない。
- 自機弾の正本を固定12スロットへ拡張し、公開状態`weapon_level`を1〜3で保持する。Lv1/2/3の1/2/3発を指定Yへ空き番号昇順で生成し、必要スロット数を事前確認して空き不足時の部分発射とクールダウン開始を防いだ。既存の3x2矩形、右4px/通常更新、成功時8更新クールダウンを維持した。
- 敵種へDropperを追加し、slot 3を初期化・撃破再配置・非最終死亡後・無敵中編成リセット・完全再開始のすべてで固定した。既存の初期X=230/Y=38/直進と再配置座標・移動・基準Y式を維持し、画面内75通常更新発射、slot 3の初期位相45を追加した。
- 固定1個の`GamePowerItem`を追加した。Dropperを自機弾で撃破した場合だけ撃破前座標のX+2/Y+2（X最大156）へ4x4アイテムを生成し、生成更新の移動・取得を除外した。活動中の再ドロップは置換せず、そのアイテムは通常の2更新に1pxの移動周期を継続する。X=0の移動タイミングでは減算せず非活動化する。
- アイテム取得を自機損傷より前に排他的境界AABBで処理し、武器Lvを最大3まで増加して常にアイテムを消費する。同時被弾でも強化を確定してから死亡へ入る。被弾開始時は自機弾12発を全消去し、32更新爆発と最終爆発後GAME OVERでは武器・アイテムを含む通常状態を凍結する。
- 非最終死亡完了時は武器Lvを保持しつつアイテムと間引きカウンタを消去する。無敵中の損傷リセットでは武器・アイテムを維持し、敵編成と敵弾だけを初期化する。A/B解除後の完全再開始は武器Lv1、アイテムなし、12自機弾なしへ戻し、再開始更新には発射しない。
- `src/main.c`へScout/Saucerと異なり、相互にも異なるDropper用8x8マスク2フレーム、4x4強化アイテムマスク、専用固定色を追加した。既存8更新アニメーションを共有し、HUDの画面内空き領域へ`PWR`とレベル1桁を描画する。全可変描画座標を画面内へ制限または水平ラン描画でクリップした。

#### APS-006検証実績

- `make clean`（終了コード0）後の`./scripts/verify.sh`（終了コード0）で、clang `-std=c89 -pedantic -Wall -Wextra -Werror`、cc65 `--standard cc65 -W error`、`sh -n scripts/*.sh`、LNXリンク・ヘッダ検査をすべて通した。
- ホストテスト: `PASS: 204 game logic checks`。APS-005の144チェックの意味を維持し、12自機弾の寸法・移動・全消去、Lv1/2/3の発射数/Y/スロット順、原子的な空き不足、Dropper固定種/再配置式/75更新発射、限定ドロップ/右端クリップ/生成更新除外/活動中非置換、2更新移動/X=0消去、取得AABB/Lv上限/同時被弾順、爆発・GAME OVER凍結、非最終死亡/無敵/完全再開始を明示検証した。
- `git diff --check`: 成功（終了コード0、出力なし）。LNXヘッダ: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=15004 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、15,004 bytes、SHA-256 `28450b8ba750f942d545aacd77538a2306871285fdadaa8b1314fb6504bd6c91`。
- コミット・push、BIOS・外部ROM・外部素材の取得・探索・生成・同梱、エミュレータ操作は行っていない。

#### APS-006設計差分

- 確定仕様との差分なし。活動中アイテムがある状態でDropperを再撃破した更新では、再ドロップ処理自体は既存アイテムの活動/X/Y/間引きカウンタを変更せず、確定更新順に従って既存アイテムの通常移動・取得だけを継続する。

#### APS-006未確認事項

- 指示に従いエミュレータは起動していない。Dropperの2フレームシルエット、強化アイテム色、HUD `PWR`、Lv2/3の平行弾配置、他オブジェクトとの識別性はGearlynx等で未確認。
- Atari Lynx実機での描画速度・入力応答・操作感、12自機弾と6敵弾が同時に存在する際の視認性・弾密度・難易度、長時間プレイ時のバランスは未確認。

### APS-005: 複数敵・敵弾攻撃・死亡シーケンス統合

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 固定上限の複数敵を同時管理し、既存2種・3移動パターンと決定的な敵弾攻撃をAPS-004の死亡・再出撃へ統合する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。
- 制約: 敵4体・敵弾6発の固定配列、整数処理、厳格C89互換、75Hz、TGI水平ラン描画、ホストテスト可能な共有ロジックを維持する。BIOS・外部ROM・外部素材の取得・操作、コミット・pushは禁止する。

#### APS-005確定仕様

- `GameEnemy`相当の状態を固定4スロットで保持する。各スロットは矩形、敵種別、移動パターン、基準Y、位相、方向、移動間引き、発射カウンタを独立して持つ。動的確保は使わない。
- 初期編成と死亡後の再出撃編成は4体すべてを有効にし、Xを140・170・200・230、基準Yを47・23・70・38にずらす。敵種別は`slot % 2`、直進・上下波形・急降下折返しは`slot % 3`で選び、画面進入時期と高さを分散する。画面外右側の敵は描画・発射・衝突対象にせず左移動だけ行い、Xが画面内へ入ると通常動作へ移る。
- 各自機弾は1更新に1回だけ移動し、敵スロット番号の昇順で最初に重なった1体だけへ命中する。命中したスロットだけをX=`180 + slot * 16`へ戻し、増加後の`respawn_sequence + slot`を種として敵種 `% 2`、移動 `% 3`、基準Y=`13 + seed * 17 % 78`を決め、100点を加算する。複数の自機弾による同一更新内の複数撃破は許可するが、1発で複数敵を倒さない。
- 自機弾命中処理は敵移動・敵発射・自機損傷より先に行う。命中して再配置された敵はその更新では移動・発射・接触しない。他の敵と、すでに存在する敵弾は通常どおり処理するため、別の損傷源まで無効にはしない。
- 敵種別ごとの発射間隔はScout 90通常更新、Saucer 60通常更新とする。敵ごとの発射カウンタはスロット番号から15更新刻みで位相をずらし、画面内にいる通常状態でのみ進める。間隔到達時は敵弾スロットの空きを昇順で1つ確保して発射し、満杯でもカウンタを0へ戻して後日の集中発射を防ぐ。
- 敵弾は固定6スロット、2x2矩形、左へ2px/通常更新とする。敵の左端・縦中央から生成し、生成更新では移動させず、次更新から移動する。左端を完全に出た弾は非活動化する。自機とのAABB重なり時は当該弾を消してAPS-004と同じ死亡シーケンスを開始する。
- 同一更新に複数の敵本体・敵弾・左端到達が成立しても減る残機は1だけとする。自機死亡開始時は既存自機弾を消し、敵・敵弾・背景を含む通常状態を32更新凍結する。非最終爆発後は自機と4敵編成を初期化し、敵弾を全消去して60更新の無敵で再出撃する。最終残機は爆発後GAME OVERとする。
- 無敵中に敵本体・左端・敵弾の損傷条件が成立しても残機と無敵時間を変えない。当該敵弾を消し、再接触を避けるため4敵編成を初期配置へ戻し、敵弾を全消去する。
- GAME OVER中は4敵と6敵弾も凍結する。A/B解除後の再押下による再開始では全敵、全敵弾、各発射カウンタ、出現列を含む全状態を初期化する。

#### APS-005完了条件

- APS-004の91チェックの意味を維持し、固定上限、4体の独立状態、初期の時間差進入、3移動パターン、敵2種の90/60更新発射境界、発射位相差、敵弾満杯時、敵弾移動・画面外消去・AABB、1弾1敵、複数同時撃破、同時損傷1残機、爆発中凍結、再出撃/無敵/GAME OVER/再開始の全初期化をホストテストで明示検証する。
- `make clean`後の`./scripts/verify.sh`でホストテスト、clang厳格C89、cc65 warnings-as-errors、shell lint、LNXヘッダ/サイズ検査が成功し、`git diff --check`も通る。
- READMEと設計書を実装に一致させ、本項へ変更内容、実測コマンド/終了コード、チェック総数、ROMサイズ・SHA-256、設計差分、実機/エミュレータ未確認事項を記録する。

#### APS-005実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。Makefile、検証スクリプト、リンカ設定、`.gitignore`、発行済みブリーフは変更していない。
- 単一敵状態を廃止し、矩形・活動状態・種別・移動・基準Y・間引き・位相・方向・発射カウンタを持つ`GameEnemy`の固定4スロットを正本とした。初期・再出撃時はX=140/170/200/230、Y=47/23/70/38、種別`slot % 2`、移動`slot % 3`へ戻す。画面外右側ではXだけを1減らし、画面内へ入った次の通常更新から移動・発射・衝突を有効にした。
- 自機弾を各1回移動後、画面内敵をスロット昇順で検査し、1発につき最初の1体だけを撃破する。更新内の撃破済みフラグにより再配置敵の再命中・移動・発射・接触を除外しつつ、別弾による別敵の同時撃破と各100点加算を維持した。対象スロットだけをX=`180 + slot * 16`、増加後の出現列とslotによる種別・移動・基準Yへ再配置する。
- 2x2の固定6敵弾を追加し、既存弾を左へ2px移動・左外消去してから敵を更新する。Scout 90更新、Saucer 60更新とslot×15の発射位相を持たせ、空きスロット昇順で生成する。満杯時も発射カウンタを0へ戻し、新規弾は生成更新に移動しない。
- 通常更新末尾で敵本体接触・X=0・敵弾AABBを集約し、同時成立でも死亡開始を1回に限定した。爆発32更新中は4敵の全フィールドと6敵弾を含む通常状態を凍結する。非最終爆発後と無敵中損傷時は4敵編成と発射位相を初期化し、全敵弾を消去する。60/61更新の無敵境界、最終爆発後GAME OVER、解除後再押下による完全初期化を維持した。
- 描画は画面内の活動敵を0〜3の順に既存2種・2フレームのマスクで描き、活動敵弾を自機弾と異なる固定色の2x2矩形で描く。爆発中は凍結した敵・両陣営の弾を維持し、GAME OVER表示は従来どおりとした。

#### APS-005検証実績

- `make clean`（終了コード0）後の`./scripts/verify.sh`（終了コード0）で、clang厳格C89、cc65 warnings-as-errors、`sh -n scripts/*.sh`、LNXリンク・ヘッダ検査をすべて通した。
- ホストテスト: `PASS: 144 game logic checks`。APS-004の91チェックの意味を配列モデルへ移行し、初期4敵、時間差進入、独立3移動、単一/複数撃破、再配置式と出現列ラップ、90/60更新発射境界、15更新位相、6弾満杯、敵弾移動・消去・AABB、損傷集約、爆発凍結、再出撃、60/61無敵境界、GAME OVER凍結、完全再開始を明示検証した。
- `git diff --check`: 成功（終了コード0、出力なし）。LNXヘッダ: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=13806 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、13,806 bytes、SHA-256 `adf240c2e1b4be9c8d0480d0c91cfc87d3ac3669ba41599a5505b19f3d28a425`。
- コミット・push、BIOS・外部ROM・外部素材の取得・探索・生成・同梱、エミュレータ操作は行っていない。

#### APS-005設計差分

- 確定仕様との差分なし。

#### APS-005未確認事項

- BIOSや外部ROMを必要とするエミュレータ操作は行っていない。4敵の時間差進入、敵弾色の識別性、複数敵・敵弾が同時表示された際の視認性、爆発中の凍結表示、再出撃後の操作感はGearlynx等で未確認。
- Atari Lynx実機での描画速度、入力応答、長時間プレイ時の敵弾密度と難易度は未確認。

### APS-004: 被弾爆発・再出撃・無敵時間

- 状態: 一次検収合格
- 優先度: 高
- 起票日: 2026-08-03
- 目的: 現行の即時残機減少・即時再配置を、自機爆発、停止時間、敵出現状態のリセット、再出撃、短い無敵時間を持つ死亡シーケンスへ拡張する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。
- 制約: APS-003の2層背景、ピクセル形状、敵2種・3移動パターン、弾命中優先、得点、残機、A/B解除後再押下を維持する。固定小配列・整数処理のみ、厳格C89互換、75Hz、`tgi_busy()`同期を維持する。BIOS・外部ROM・外部素材を取得・探索・同梱しない。コミット・pushはしない。

#### APS-004確定仕様

- 通常時の損傷条件は現行どおり「敵とのAABB接触」または「敵のX=0到達」とする。弾命中と損傷条件が同フレームに成立した場合は、引き続き命中を優先して死亡を開始しない。
- 損傷開始時に残機を1だけ減らし、自機弾をすべて消去して爆発状態へ入る。残機は0未満にせず、爆発中の追加判定で重複減少させない。得点は維持する。
- 爆発は32フレーム。コード内の8x8以内の1bit行マスク4段階を8フレームごとに進め、元の自機座標を中心にTGI水平ランで描画する。画面外座標はクリップする。
- 爆発中は入力、自機、敵、弾、得点、発射クールダウン、敵移動位相、2層背景オフセット/間引き、通常キャラクターアニメーションを凍結する。更新するのは爆発タイマーと爆発表示段階のみとする。
- 残機が1以上残る場合は、32フレーム完了後に自機を初期座標(10, 48)へ戻す。敵出現状態は`respawn_sequence=0`、敵種0、直進、X=140、基準Y=47、位相/間引き/方向初期値へ戻す。弾なし、発射クールダウン0で再出撃し、得点と背景座標は保持する。
- 再出撃後は60通常フレームの無敵とする。この間も入力・射撃・弾・敵・背景・通常アニメーションは更新する。自機は4フレーム単位で表示/非表示を切り替えて無敵を視認可能にする。
- 無敵中の損傷条件では残機を減らさず、無敵残り時間も延長しない。自機と重なった敵やX=0の敵が残らないよう、敵出現状態だけを上記初期値へ戻す。
- 残機が0の場合は、32フレームの爆発を最後まで表示してからGAME OVER状態へ入る。爆発中はGAME OVER表示や再開始を有効にしない。GAME OVER後のA/B解除・再押下でのみ`game_init()`相当の完全初期化を行う。
- 将来のAPS-005の敵弾でも同じ死亡シーケンスを使えるよう、損傷開始・死亡更新・再出撃初期化を局所化し、プラットフォーム非依存の状態遷移に保つ。

#### APS-004完了条件

- APS-003の70チェックの意味を維持し、損傷開始時の1残機減少・全弾消去・得点維持、32フレームの通常状態凍結、非最終残機の敵出現リセット・再出撃、60フレームの正確な無敵期間と無敵中損傷無視、最終残機の爆発後GAME OVER、A/B再開始をホストテストで明示検証する。
- 爆発マスク4段階がそれぞれ異なり、爆発中は通常自機の代わりに適切な段階が描画されることをコードレビューで確認できる。無敵点滅もタイマーから決定的に描画される。
- `./scripts/verify.sh`でクリーンROMビルド、clang厳格C89 warnings-as-errors、cc65警告エラー化、全ホストテスト、shell lint、LNXヘッダ検査が成功する。`git diff --check`も成功する。
- `README.md`と`docs/plan/design.md`を実装に合わせ、本項へ変更ファイル、実測テスト結果、ROMサイズ・SHA-256、設計差分、エミュレータ・実機の未確認事項を追記する。

#### APS-004実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。Makefile、検証スクリプト、リンカ設定、発行済みブリーフは変更していない。
- `GameState`へ死亡状態、0〜31の爆発タイマー、無敵残り時間を追加した。損傷開始、死亡更新、敵初期シーケンス復元を共有ロジック内の局所関数へ分け、被弾時の1残機減少・全3弾消去・得点維持と、爆発中の重複損傷防止を実装した。
- 32回の死亡状態更新では爆発タイマーだけを進め、入力、自機、敵、弾、得点、クールダウン、背景2層、通常アニメーション、敵移動状態を凍結する。非最終残機は32回目で自機(10, 48)、敵sequence 0・種別0・直進・X=140・基準Y=47、弾なし、クールダウン0へ戻し、得点と背景状態を維持する。
- 再出撃後の更新開始時に無敵判定を保存して残り時間を減らすことで、最初の60通常更新を保護し61回目から損傷可能にした。弾命中の早期returnでも1更新を消費する。無敵中の損傷条件は残機と無敵時間を変えず、敵出現状態だけを初期シーケンスへ戻す。
- `src/main.c`へ異なる8x8の1bit爆発マスク4段階を追加し、`explosion_timer / 8`で各8フレームを選ぶ。既存の水平ラン描画を符号付き座標対応にして上下左右をクリップし、通常自機を死亡位置中心の爆発へ置換した。無敵点滅は無敵経過更新数から4フレーム単位で決定する。
- 最終残機は残機0のまま32回の死亡更新を終えてからGAME OVERへ遷移する。爆発中のA/B入力を無視し、GAME OVER成立後の解除・再押下でのみ`game_init()`による完全初期化を行う既存仕様を維持した。

#### APS-004検証実績

- `make clean`（終了コード0）後の`./scripts/verify.sh`（終了コード0）で完全クリーン検証に成功した。clang `-std=c89 -pedantic -Wall -Wextra -Werror`、cc65 `-t lynx -Oirs --standard cc65 -W error`の警告エラー化コンパイル、`sh -n scripts/*.sh`、LNXリンク・ヘッダ検査がすべて成功した。
- ホストテスト: `PASS: 91 game logic checks`。APS-003の70チェックの意味を維持し、損傷開始、弾命中優先、32更新凍結と8更新ごとの4段階、再出撃初期化と状態保持、60/61更新の無敵境界、無敵中敵リセット、最終爆発後GAME OVER、押しっぱなし防止、完全再開始初期化を追加検証した。
- `git diff --check`: 成功（終了コード0、出力なし）。
- LNXヘッダ: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=11622 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、11,622 bytes、SHA-256 `ecd0ec4e4ac4cc6d756ecefdc3dcb40ef76fe5d9463ccd66e3cad6dd10302425`。
- マスク自己レビュー: 爆発4段階は全配列値が異なる。タイマー0〜31だけを描画インデックスに使うため範囲は0〜3であり、爆発時は通常自機を描かない。水平ランは負座標と160x102超過の双方をクリップしてから`tgi_bar()`へ渡す。
- コミット・push、BIOS・外部ROM・外部素材の取得・探索・生成・同梱、エミュレータ操作は行っていない。

#### APS-004設計差分

- 確定仕様との差分なし。

#### APS-004未確認事項

- BIOSや外部ROMを必要とするエミュレータ操作は行っていない。爆発4段階の視認性、死亡位置との中心合わせ、60フレーム点滅、再出撃の操作感、GAME OVERへの見た目の遷移はHandy・Gearlynxで未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

### APS-003: 横スクロール背景・ピクセルキャラクター・敵移動パターン

- 状態: 実装・自動検証完了
- 優先度: 高
- 起票日: 2026-08-02
- 目的: Asteroid Patrolを横スクロールシューティングとして読み取れる画面と敵挙動へ拡張し、APS-002の弾・衝突・得点・残機・ゲームオーバー・再開始を維持する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`Makefile`（新規共有ソースが必要な場合のみ）、本項。
- 制約: 浮動小数、動的確保、外部画像・フォント・音声は使わず、固定小配列と決定的な整数処理だけを使う。共有ロジックの厳格C89互換、75Hz、`tgi_busy()`同期、AABBの排他境界を維持する。BIOS・外部ROM・外部素材を取得・探索・同梱しない。コミット・pushはしない。

#### APS-003確定仕様

- 背景は固定座標表による2層の星とする。遠景は4フレームに1px、近景は2フレームに1pxずつ左へ移動し、160pxで決定的にラップする。遠景は暗い1px、近景は明るい1〜2pxの形で速度差を視認可能にする。背景オフセットと進行カウンタは共有`GameState`で更新する。
- 自機は8x6、敵は8x8の現行AABBを維持し、矩形の塗りつぶしではなく、コード内の1bit行マスクから自作ピクセル形状を描画する。自機1種と形状の異なる敵2種（Scout系とSaucer系）を用意し、色だけに依存せず識別できるものとする。各キャラクターは2フレームの行マスクを持ち、8ゲームフレームごとに切り替える。
- ピクセル形状は`src/main.c`または新規のC89互換共有ソースに固定`unsigned char`配列として保持する。描画は各行の連続した1bitを`tgi_bar()`の水平ランにまとめ、1bitごとの大量API呼び出しを避ける。弾は現行の3x2矩形のままでよい。
- 敵の種類と移動は`respawn_sequence`に応じた固定テーブルまたは等価の決定表で選択し、各数値を設定データとして切替可能にする。初期は敵種0・直進、以後は敵種を0/1、移動を直進/上下波形/急降下折返しの順で独立に循環させる。再配置ごとに移動フェーズと上下方向を初期化する。
- 直進は毎フレームXを1px左へ移動しYを維持する。上下波形はXを毎フレーム1px左へ移動し、3フレームに1px、基準Yの上下最大6pxまで三角波で往復する。急降下折返しはXを毎フレーム1px左へ移動し、2フレームに1px、基準Yから下へ最大12px降下した後、基準Yまで上昇して繰り返す。いずれもHUD下端〜画面下端にクランプする。
- 1フレームの更新順序は「GAME OVER・再開始処理 → 背景/アニメーション更新 → 入力・自機・発射・弾 → 弾命中なら敵再配置して終了 → 敵移動 → 自機接触/左端到達」とする。APS-002の弾命中優先と再配置フレームの敵移動省略を維持する。
- GAME OVER中は自機・敵・弾・得点・クールダウンに加え、背景オフセット、アニメーションカウンタ、敵移動フェーズも凍結する。A/B解除後の再押下で再開始した際は、これらのAPS-003追加状態も初期化する。

#### APS-003完了条件

- APS-002の37チェックの意味を維持し、2層背景の更新速度差・160pxラップ・GAME OVER凍結・再開始初期化、敵2種の決定的循環、3移動パターンの座標遷移・上下端制御・再配置時初期化、弾命中優先と残機・ゲームオーバー統合をホストテストで明示検証する。
- コード内マスクは自機と敵2種で形状が異なり、各種別の2フレームも完全同一ではないことをコードレビューで確認できる。描画ランは画面境界外を指定しない。
- `./scripts/verify.sh`でクリーンROMビルド、clang厳格C89 warnings-as-errors、cc65警告エラー化、全ホストテスト、shell lint、LNXヘッダ検査が成功する。`git diff --check`も成功する。
- `README.md`と`docs/plan/design.md`を実装に合わせ、本項へ変更ファイル、実測テスト結果、ROMサイズ・SHA-256、設計差分、エミュレータ・実機の未確認事項を追記する。

#### APS-003実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。新規共有ソースと`Makefile`変更は不要だった。
- 遠景・近景のオフセットと間引きカウンタを`GameState`へ追加し、固定星座標表を遠景10個・近景7個で描画した。近景2フレーム、遠景4フレームごとに1px進め、159から0への明示分岐で循環させた。
- 自機8x6、Scout系8x8、Saucer系8x8の各2フレームを`src/main.c`の1bit行マスクとして自作した。各キャラクターの2フレームは異なり、敵2種も別シルエットである。連続bitを水平ラン単位の`tgi_bar()`へまとめ、X/Yを画面境界内へクリップした。弾は3x2矩形を維持した。
- 水平速度、垂直更新間隔、垂直幅、挙動種別を持つ固定移動設定テーブルを共有ロジックへ追加した。`respawn_sequence % 2`で敵2種、`respawn_sequence % 3`で直進・上下波形・急降下折返しを独立循環し、再配置時に基準Y、位相、間引きカウンタ、方向を初期化した。
- 更新順序をGAME OVER処理、背景・アニメーション、自機・発射・弾、弾命中、敵移動、接触・左端到達とした。APS-002の100点、命中フレームの早期return、同時被弾時1残機のみ減少、非最終被弾時の得点・自機位置維持、全弾消去、A/B押しっぱなし防止付き再開始を維持した。
- GAME OVER中は背景・アニメーション、敵移動位相・方向を含む全追加状態を凍結し、解除後のA/B再押下でAPS-003追加状態も初期化するようにした。

#### APS-003検証実績

- `./scripts/verify.sh`: 完全クリーン検証成功。`rm -rf build dist`後、clangの`-std=c89 -pedantic -Wall -Wextra -Werror`、cc65の`-t lynx -Oirs --standard cc65 -W error`で警告エラー化ビルドに成功した。`sh -n scripts/*.sh`も成功した。
- ホストテスト: `PASS: 70 game logic checks`。APS-002の37チェックの意味を維持し、背景速度差・ラップ、8フレームアニメーション、敵種別と移動の独立循環、3パターンの座標列・上下端クランプ、命中・残機喪失後の移動状態初期化、命中優先、GAME OVER凍結・再開始初期化を追加検証した。
- `git diff --check`: 成功（出力なし）。作業ツリーにはAPS-002から継続する上記7ファイルの未コミット差分と、未追跡`.briefs/APS-002/`・`.briefs/APS-003/`が存在する。発行済みブリーフは変更していない。
- LNXヘッダ: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=10850 bytes`。
- ROM: `dist/asteroid-patrol.lnx`、10,850 bytes、SHA-256 `e67751cdee710e9982c91a5d7320538bd41a4e384eec09379f087eaee59de83b`。
- マスク自己レビュー: 自機2フレーム、Scout系2フレーム、Saucer系2フレームはいずれも配列値が異なり、Scout系とSaucer系も外周・中央・上下端の形が異なる。描画は1bitごとの`tgi_setpixel()`を使わず、水平ランごとに1回の`tgi_bar()`を呼ぶ。行YとランX終端を160x102内にクリップし、画面外座標を渡さない。
- コミット・push、BIOS・外部ROM・外部素材の取得・探索・生成・同梱、エミュレータ操作は行っていない。

#### APS-003設計差分

- 確定仕様との差分なし。行マスクはホストテスト対象の共有ソースへ分離せず`src/main.c`内に置いたため、形状差と描画ランの安全性はコードレビューで確認した。

#### APS-003未確認事項

- BIOSや外部ROMを必要とするエミュレータ操作は行っていない。遠景・近景の目視速度差、自機・敵2種の識別性、2フレームアニメーション、敵移動の見え方、HUDとの重なり、操作感はHandy・Gearlynxで未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

### APS-002: 敵移動・残機・ゲームオーバー・再開始

- 状態: 実装・自動検証完了
- 優先度: 高
- 起票日: 2026-08-02
- 目的: 現行の右側固定標的を左へ進む敵に拡張し、3残機、ゲームオーバー、A/Bによる再開始を追加する。
- 実装対象: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、本項。
- 制約: 既存の矩形描画のみ、共有ロジックの厳格C89互換、Lynx依存処理の`src/main.c`限定、75Hzと`tgi_busy()`によるダブルバッファ同期、決定的な敵Y座標列を維持する。BIOS・外部ROM・外部素材を取得・探索・同梱しない。コミット・pushはしない。

#### APS-002確定仕様

- 通常状態で敵は1フレームに1px左へ移動する。初期・再配置時のX座標は現行どおり140とし、Y座標は現行の決定的な列を使う。
- 初期残機は3。敵が自機とAABB接触するか、左端へ到達すると残機を1だけ減らす。両条件が同一フレームで成立しても1機だけ減らす。符号なし値を0未満にアンダーフローさせない。
- 残機を失った際は全弾を消去する。残機が残っていれば敵を右端の次の決定的Y座標へ再配置し、得点と自機位置は維持する。
- 1フレーム内では弾の敵命中を先に解決する。命中したフレームは100点加算と敵再配置のみとし、再配置後の敵移動・自機接触・左端到達判定は次フレームまで行わない。
- 残機が0になった直後にゲームオーバー状態へ移る。その間は自機、敵、弾、得点、発射クールダウンの通常更新を停止し、HUDに残機、プレイ領域に`GAME OVER`と再開始案内を内蔵文字で表示する。
- 再開始はゲームオーバー後にA/B入力を一度解除し、その後の新たなA/B押下でのみ行う。ゲームオーバー成立時から押し続けているA/Bでは即時再開始しない。
- 再開始時は得点0、残機3、自機・敵の初期座標、弾なし、発射クールダウン0、敵再配置列0の初期状態へ完全に戻す。再開始に使った押下で同フレームに弾を発射しない。

#### APS-002完了条件

- 上記仕様と既存の14件をすべて自動検証するホストテストが存在し、特に「ゲームオーバー時からA/Bを押し続けても即時再開始せず、解除後の再押下でのみ再開始」を回帰テストする。
- `./scripts/verify.sh`でクリーンROMビルド、clang厳格C89 warnings-as-errors、cc65警告エラー化、全ロジックテスト、shell lint、LNXヘッダ検査がすべて成功する。あわせて`git diff --check`が成功する。
- `README.md`と`docs/plan/design.md`に敵移動、被弾条件、残機、ゲームオーバー、再開始操作を反映する。
- 作業後に本項へ変更ファイル、実測検証結果、ROMサイズとSHA-256、設計との差分、エミュレータ・実機の未確認事項を追記する。自画面の目視確認は実装完了条件に含めない。

#### APS-002実装実績

- 変更ファイル: `include/game.h`、`src/game.c`、`src/main.c`、`tests/test_game.c`、`README.md`、`docs/plan/design.md`、`ISSUES.md`。
- v002差し戻し対応では`tests/test_game.c`へ、非最終の残機喪失後も0以外の得点と初期値以外の自機X/Y座標が維持される明示assert、およびGAME OVER中に区別可能な状態を設定した全3発の弾が移動・発射入力付きの複数フレーム更新でも凍結される明示assertを追加した。共有ロジックの変更は不要だった。
- 敵の毎フレーム1px左移動、接触・左端到達時の残機喪失、全弾消去、決定的な敵再配置、3残機とゲームオーバーを共有ロジックへ追加した。
- 弾命中を被弾より先に解決し、命中フレームは再配置直後に処理を返すことで、同一フレームの敵移動・被弾を抑止した。
- ゲームオーバー成立後のA/B解除を記録し、その後の新規押下だけで完全初期化する再開始処理を追加した。再開始フレームの発射は行わない。
- HUDへ残機、ゲームオーバー中のプレイ領域へ`GAME OVER`と`A/B TO RESTART`をTGI内蔵文字で追加した。75Hz、割り込み駆動ダブルバッファ、フレーム先頭の`tgi_busy()`待機は維持した。

#### APS-002検証実績

- `./scripts/verify.sh`: v002再検証成功。クリーン後にclangの`-std=c89 -pedantic -Wall -Wextra -Werror`、cc65の`-t lynx -Oirs --standard cc65 -W error`でビルド成功。`PASS: 37 game logic checks`、`sh -n scripts/*.sh`成功、`LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=8384 bytes`。
- ホストテストでは既存35チェックを維持し、v002で非最終の残機喪失後の得点・自機X/Y維持と、GAME OVER中の全3発の弾状態凍結を追加した計37チェックを通過した。A/B押しっぱなし防止、解除後の再押下、完全初期化の回帰テストも成功した。
- `git diff --check`: 成功（出力なし）。
- ROM: `dist/asteroid-patrol.lnx`、8,384 bytes、SHA-256 `5683b479c9ac842621c00b47dc2d4b1fb02f729263f2e83fc244eee825907a53`。
- 作業完了時の変更範囲は上記7ファイル。v002差し戻し対応による追加変更は`tests/test_game.c`と本項のみ。未追跡`.briefs/APS-002/`内の発行済みブリーフは変更していない。コミット・pushは行っていない。

#### APS-002設計差分

- 確定仕様との差分なし。`README.md`と`docs/plan/design.md`を実装済みの敵移動、残機、ゲームオーバー、押しっぱなし防止付き再開始に合わせて更新した。

#### APS-002未確認事項

- BIOSや外部ROMを必要とするエミュレータ操作は行っていないため、Handy・GearlynxでのHUD配置、ゲームオーバー文言、操作感は未確認。
- Atari Lynx実機での表示、入力応答、描画速度、長時間連続プレイは未確認。

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
- [x] 3残機、ゲームオーバー、A/B押しっぱなし防止付き再開始
- [x] 2層星背景、自機・敵2種の2フレームピクセル形状、3種のデータ駆動敵移動
- [x] APS-001時点のHandy・Gearlynx実画面確認、方向入力、GearlynxでのA/B射撃・命中確認

## 要件対応表

| 要件 | 対応 | 検証 |
|---|---|---|
| ROM起動形式 | `cl65 -t lynx`でLNXカートイメージ生成 | LNX magic/version/page size検査成功 |
| 160x102・16色 | cc65標準TGIドライバ、固定星、1bit行マスク、矩形弾、内蔵文字 | Lynx向けコンパイル・リンク成功 |
| 2層横スクロール | 近景2フレーム、遠景4フレームで1px左移動、160pxラップ | 速度差・ラップ・GAME OVER凍結テスト成功 |
| 方向入力移動 | 標準ジョイスティックの上下左右をロジック入力へ変換 | clangテスト成功 |
| A/B発射 | `JOY_BTN_1_MASK`と`JOY_BTN_2_MASK`を同じ発射入力へ変換 | cc65コンパイル成功、発射ロジックテスト成功 |
| 連射制御 | 押下継続時8フレーム間隔、最大3発 | cooldown/repeatテスト成功 |
| 画面境界 | X両端、HUD下端、画面下端で自機をクランプ | 四辺テスト成功 |
| 敵・再出現 | 8x8の2種ピクセル形状、直進・上下波形・急降下折返し、決定的再配置 | 種別循環・3パターン座標列・再初期化テスト成功 |
| AABB・得点 | 排他的端のAABB、命中時100点、HUDを再描画 | AABB端・命中・scoreテスト成功 |
| 残機・終了・再開始 | 3残機、通常更新凍結、A/B解除後の再押下で完全初期化 | 凍結・押しっぱなし防止・再開始テスト成功 |
| 外部素材なし | TGI図形・コード内固定マスク・内蔵文字のみ | リポジトリ内容とROMビルドを確認済み |
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
  - ロジック: `PASS: 70 game logic checks`。
  - cc65: `-t lynx -Oirs --standard cc65 -W error`で2ソースの警告エラー化コンパイル成功。
  - link: `cl65 -t lynx`で成功。map上の標準ライブラリはローカルinstall配下を参照。
  - shell: `sh -n scripts/*.sh`成功。
  - header: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=10850 bytes`。

### ROM成果物

- パス: `dist/asteroid-patrol.lnx`
- サイズ: 10,850 bytes
- SHA-256: `e67751cdee710e9982c91a5d7320538bd41a4e384eec09379f087eaee59de83b`

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
- APS-001時点ではHandyの方向入力、Gearlynxの方向入力・A/B射撃・命中・得点・敵再配置を確認した。APS-002/003追加画面と操作は未確認。
- APS-003の背景2層の速度差、ピクセル形状の識別性、2フレームアニメーション、3種の敵移動、描画速度と操作感はHandy・Gearlynxで未確認。
- `lynxboot.img`を含むBIOSは著作権対象のため、本作業では取得・同梱・生成していない。
