# APS-053 evidence

## v027 実機Suzy文字化け診断ROM（2026-08-13）

v025のSHA-256 `40346dd9a9280b0d55ad25ba9bea4aaa296c3cd3ee386fb69bb702865904a15a`を実機へ再転送してもTITLE/version文字化けが再現したため、旧ROMだけを原因とする説明はv025について除外した。v027は通常ROMの`GAME_VERSION_STRING`を`0.53.6`へ更新し、TITLEへ固定literal assetの`L/R BIT TEST`（x=58,y=28）と、動的`static_layer_text()`の`A V 0 5 6`（x=62,y=34）を追加した。両方とも左右端bit・非対称glyphを含み、左右反転、1pixel欠落、行崩れ、全面欠落を実機LCDで分類できる。

実機投入対象は`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`60092` bytes、SHA-256=`3e3c539a5419022a7b6bbf37bf9f5f9de5dd3768a74619985a7f3db8fb5d3dfb`、表示version=`V0.53.6`。LNX headerは`magic=LYNX version=1 bank0_page=1024 bank1_page=0`、header後payload=`60028` bytes、version payload offset=`0x92CC`（絶対=`37580`）に1箇所。通常ROMのみを実機へ渡し、cadence ROMは投入しない。

byte根拠はcc65 2.19一次ソースの`SCB_REHV_PAL=23` bytes、`LITERAL`/`PACKED`、行count+1、high-nibble-first、行終端、末尾duplicate workaround、`penpal[value >> 1]` nibble規則。v027では診断assetを通常ROM専用objectへ分離し、cadence ROMはCODE/RODATA/BSS=`37140/7890/1358`、MAIN余剰=`264` bytesを維持。TITLEは10 SCB chain、GAME OVERは各状態21/1/1/1 submissions。

Gearlynx独立renderer/readbackはTITLE、GAME OVER voice、GAME OVER complete全sceneでPASS。各sceneの`vidbas`/`dispadr`/screenshot pixel mismatch=`0`、両physical page一致。TITLE期待nonzero=`607`、diagnostic verifierは固定6文言・version一意性・固定/動的mask・SCB診断配線を検査。証跡は`diagnostic-rom-v027.json`、`title-game-over-v027.json`、`phase-2r-v027.json`。

現時点の分類:

- `confirmed`: v025実機再現、v027のLNX/header/payload/version、固定assetと動的assetの独立生成・readback整合。
- `ruled_out`: v025事象を「旧ROMを転送しただけ」とする単独説明。ユーザーがv025 exact SHAを再転送して再現済み。
- `likely`: 物理Suzyまたはwriter経路に依存する差異。ただしSCB形式のどのfieldが原因かは未確定。
- `not determinable locally`: 実機Suzyのliteral 1bpp解釈、実機LCDの診断表示、writerへ渡したv027ファイルの実SHA・転送ログ。

実機判定: writerへ渡すファイルSHAが上記値と一致し、TITLEが`V0.53.6`を示すこと。`L/R BIT TEST`のL/R端線、`A V 0 5 6`のA/V/0/5/6輪郭が期待どおりなら転送・表示経路は一致。versionまたはSHA不一致ならSuzy差異判定を保留し、writer名・投入path・転送ログを保存する。

## v026 実機投入識別・Suzy差異切り分け（2026-08-13）

v025は文字maskを修正したが`GAME_VERSION_STRING`を更新していなかったため、実機に残っている旧ROMとv025 ROMを画面だけで区別できなかった。v026では診断目的の最小変更として`include/version.h`を`0.53.5`へ更新し、通常ROMを再生成した。ゲームロジック、scheduler、Timer/IRQ、audio/voice、Phase 3R、背景/可動object、SCB構造は変更していない。

投入対象は`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`59903` bytes、SHA-256=`333fdfbec6f28b3d898d2646f8f1ba8eefd20aee519f9b210c1dbca3d60c5ba9`、表示version=`V0.53.5`。LNX headerは`magic=LYNX version=1 bank0_page=1024 bank1_page=0`、header後payload=`59839` bytes、version payloadはROM内offset=`0x9251`（絶対offset=`37457`）に1箇所。source/generator/生成dataのhash、生成UTC、検査結果は`diagnostic-rom-v026.json`に固定した。

cc65 2.19のローカル一次ソース（`.cache/cc65-2.19/source/include/_suzy.h`、`libsrc/lynx/tgi/lynx-160-102-16.s`、`src/sp65/lynxsprite.c`）で、使用中の`SCB_REHV_PAL`=`23` bytes、`PACKED`/`LITERAL`、packed streamのhigh-nibble-first、行byte countと終端、末尾bit時の重複byte、`penpal[value >> 1]`のlow/high nibbleを確認した。GearlynxのTITLE/GAME OVER/static layer readbackは全てPASSだが、期待rendererとGearlynxが同じSuzy解釈を共有する自己同型検証を含むため、実機Suzy差異の否定根拠にはしない。

分類:

- `confirmed`: v025まで旧ROMを一意識別できなかったこと。現行ROMのLNX/header/payload/version、固定5文言の生成data、動的文字の`8 >> column`、独立compact renderer整合性。
- `likely`: 実機へ旧ROMまたは別ファイルが転送された可能性。現行artifactと異なる実機投入ファイルのSHAが未取得のため確定しない。
- `not determinable locally`: 物理カートリッジ書込み装置の転送結果、実機LCD上の表示version、実機SuzyのSCB/1bpp/penpal挙動。リポジトリ内に転送ツール・手順・転送ログはない。

実機確認は、(1) writerへ渡すファイルのSHA-256が上記値と一致、(2) reset/reload後にTITLEが`V0.53.5`、(3) writer名・転送ログ・投入ファイルpathを保存、の3点で十分。SHAまたはversionが不一致なら実機ハード差の調査へ進めない。

## v025 TITLE/GAME OVER Suzy文字文字化け修正（2026-08-13）

原因確定どおり、5bit font rowを`(value >> 1) & 0x0f`でcompact化した後のbit testを、生成器`text_line_data()`とruntime `build_text_line()`の両方で`4 >> column`から`8 >> column`へ修正した。HUDの別形式3bit glyph表現は変更していない。`src/static_layer_data.c`/`include/static_layer_data.h`は生成器を再実行して更新した。`GAME_VERSION_STRING=0.53.4`、ゲーム挙動、scheduler、Timer/IRQ、背景/SCB方式、voice再生は変更なし。

専用target `make title-game-over-readback-gearlynx` と `scripts/verify-title-game-over-readback-gearlynx.py`を追加。外部画像や被検証helperを使わない独立compact-5x7 rendererでTITLEの固定文言・VOICEVOX:Nemo・versionを生成し、GAME OVERはGearlynxのstatic SCB層を独立decodeした基底へ`GAME OVER`、`VOICE...`、voice完了後`A/B TO TITLE`を独立overlayして照合した。TITLEは8 SCB、GAME OVERは各状態とも`[21,1,1,1]` submissions。3 sceneすべてで`vidbas`/`dispadr`/screenshotのpixel mismatch=`0`、両physical page一致、screenshot一致。証跡JSONは`title-game-over-v025.json`、PNGは`title-{vidbas,dispadr,screen}.png`、`game-over-{voice,complete}-{vidbas,dispadr,screen}.png`。

ROM/mapは通常LNX=`59903` bytes、SHA-256=`40346dd9a9280b0d55ad25ba9bea4aaa296c3cd3ee386fb69bb702865904a15a`、Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰=`450` bytes。cadence LNX=`60331` bytes、SHA-256=`006ca98e09b3a5e50665a9955a4a486bad20d36040eefda55fbe309d4cb57517`、Segment=`109/37140/7890/308/1358`、MAIN余剰=`264` bytes。cadence余剰`>=256B`を維持。

検証: `make clean && ./scripts/verify.sh`（stage155/game625/sound351/IMA14949/sprite1647、LNX59903）、`make title-game-over-readback-gearlynx`、`make static-layer-readback-gearlynx`（stage1/2/3 PASS、SCB21/9/9）、`make smoke-host`（19）、`make perf-host`（終了コード0）、`make debug-contract`、`make phase-2r-audio-diagnostics-gearlynx`（channel0/1/2 PASS）、`verify-title-voice-gearlynx.py --mode title/game-over`（title/GAME OVER voice PASS）、対象`py_compile`、`git diff --check`を実施。実機LCD・speaker・長時間playthroughは未確認。コミット・push・stash・reset・checkoutなし。

## v024 Phase 3R到達可能性 Timer2 tick→VBlank 校正（2026-08-13）

`make phase-3r-tick-calibration-gearlynx`をPASSした。`scripts/calibrate-cadence-ticks-gearlynx.py`はROM動作コードを変更せず、GearlynxのTimer 2 IRQ (`irq=2`, `TIMER2_INTERRUPT`=`VBL_INTERRUPT`)をVBlank境界として、独立2 batch×18 hitを収集した。各隣接hitはVBlank差分1、0差分0。各hitで`get_mikey_timers(timer=2)`のbackup/currentを保存し、全34区間で`0x68/0x68`、backup周期105 tick、wrapなし・安定値を確認した。

CPU `total_ticks`はTimer2 counter tickと混同せず、汚染クロスチェックとして記録した。batch中央値は`184668/184680` CPU ticks/VBlank、CV=`0.000753/0.000777`で、独立batch間の安定性とdebugger汚染判定はPASS。v016のlogic純増（0敵18、4敵86）から`68` Timer2 tickを固定し、`logic_min_vblank=68/105=0.647619`。logic単独は2 VBlank以下だが、既存計測にはSuzy描画の独立下限がなく、未確定値をゼロ扱いしていない。

従って`phase3r_reachability=not_proven_pending_suzy_draw_bound`。Phase 3R本実装へは進まず、次は候補bpp変換・SCB構成のSuzy開始〜完了tick計測と2 VBlank収支表ゲート。証跡は`tick-calibration-v024.json`。release/cadence source・ROM・mapは前後不変。

v024完了時の回帰は`make clean && ./scripts/verify.sh`、`make smoke-host`、`make perf-host`、`make debug-contract`、`make static-layer-readback-gearlynx`、`make phase-2r-audio-diagnostics-gearlynx`、title/GAME OVER voice、対象`py_compile`、`git diff --check`を実行し、全て終了コード0。hostはgame625/sound351/IMA14949/sprite1647/smoke19、static stage 1/2/3、audio channel 0/1/2、title/GAME OVER voiceをPASS。perf-hostはlegacy median=`3184448us`、optimized median=`3352415us`。

## v023 bounded fixed-step catch-up 比較ROM（2026-08-13）

`make phase-2r-bounded-catchup-gearlynx`をPASSした。現行の`elapsed×4`/logic最大128/sound最大2048を、outer loopごとのlogic credit=`raw_elapsed*4`・最大12、sound credit=`raw_elapsed`・最大4へ変更し、上限超過creditを同一loop内でdiscard、次loopへ持ち越さない bounded fixed-step scheduler を実装した。`raw_elapsed=0/1`の待機意味、outer loop一回のinput poll、title/GAME OVER voice、audio applyの本番経路は維持した。

4敵NORMAL fresh/no-reinjectを各独立2 batch×10 interval、0敵profile/no-profile対照を各2 batch計測。各intervalのraw elapsed、実logic/sound、logic/sound discard、logic/sound clip count、Timer 2、公開display chain、全enemy/enemy-bullet slot差分を`bounded-catchup-v023.json`へ保存した。bounded counter式、discard/clip counter、fixture readback、`tgi_busy/tgi_sprite/tgi_updatedisplay`分類、公開symbol chainはPASS。fresh median/max=`38/39,38/39` VBlank、logic/soundは各intervalで`min(raw*4,12)`/`min(raw,4)`一致。no-reinject median/max=`36.5/39,36.5/39`、interval 1〜10で状態進化、changed enemy slot=`40`/batch、enemy-bullet slot=`12`/batch。

0敵同一公開chain profile/no-profile対照は`22/22`対`22/22` VBlank、差`0/0`、相対差`0%/0%`でPASS。判定は bounded scheduler による実行量増幅信号を状態コストから分離する比較として`state_cost_dominant`。bounded実装後も4敵の表示遅延は36〜39 VBlankで、3 VBlank契約は未達。追加最適化・Phase 3Rには進まない。

ROM/map保全: release Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰=`450` bytes、cadence=`109/37140/7890/308/1358`、MAIN余剰=`264` bytes。release/cadence ROM=`59903/60331` bytes。source変更前後の実行中不変をPASS。`GAME_VERSION_STRING="0.53.4"`。

実装差分は`src/main.c`/`src/game.c`/`include/game.h`/`include/cadence_probe.h`/`src/cadence_probe.s`、host scheduler tests、bounded verifier/Makeターゲット、証跡、台帳。discard/clipはprobe常駐領域を増やさず、公開raw elapsedと実logic/sound counterからverifierが算出・突合。未確認は実機音声の長時間聴感のみ（channel 0/1/2、title/GAME OVER voice verifierは完了コマンドセットで実行）。

完了時の回帰は`make clean && ./scripts/verify.sh`、`make test smoke-host debug-contract`、`make perf-host`、`make static-layer-readback-gearlynx`、`make phase-2r-audio-diagnostics-gearlynx`、title/GAME OVER voice verifier、対象`py_compile`、`git diff --check`を実行。全て終了コード0。perf-hostはoptimized median=`3189685us`、legacy median=`3104060us`、paired delta median=`33477us`。

## v022 catch-up 因果分離 verifier-only 診断（2026-08-12）

`make phase-2r-catchup-causality-gearlynx`をPASSした。新ターゲットは4敵NORMALのfresh（各interval再注入）とno-reinject（batch開始前1回のみ注入）を同一公開symbol chainで各2 batch×10 interval計測し、0敵NORMAL profile/no-profile陰性対照も各2 batchで実行した。ROM動作コード、scheduler、clip値、速度セマンティクス、`src/cadence_probe.s`は変更していない。

各intervalのraw elapsed VBlank、実logic/sound counter delta、現行式`min(raw_elapsed*4,128)`/`min(raw_elapsed,2048)`、logic/sound clip到達、clip廃棄量、Timer 2、公開display chain、全enemy/enemy-bullet slot差分を保存した。全fresh/no-reinject/対照のcounter式一致、fixture readback、`tgi_busy/tgi_sprite/tgi_updatedisplay`分類、公開symbol chainはPASS。freshは両batchともraw=`[11,73,148,153,154,153,154,153,154,154]`、median/max=`153/154` VBlank、logic=`[44,128,128,128,128,128,128,128,128,128]`、soundはrawと同値。logic clipは各batch9 interval、最大廃棄488 updates。

no-reinjectは両batchともraw=`[12,80,98,132,134,0,27,31,31,31]`、median/max=`31/134` VBlank、logic=`[48,128,128,128,128,0,108,124,124,124]`、soundはrawと同値。状態進化は両batchでinterval 1〜3、変更enemy slot=`12`、enemy-bullet slot=`3`。0敵陰性対照はprofile=`115.5/115.5`、no-profile=`115/115`、絶対差=`0.5/0.5` VBlank、相対差=`0.4348%/0.4348%`でPASS。

判定は **`mixed_or_inconclusive`**。freshのlogic clip到達・実行量増加とraw elapsedの正相関（raw↔logic=`0.6604`、raw↔sound=`1.0`）は`catchup_amplification_supported`側の信号を示す一方、no-reinjectの敵/敵弾状態進化と31 VBlank級への減衰も同時に観測され、catch-up量とstate costを本計測だけでは一意分離できない。したがってbounded fixed-step catch-up、scheduler修理、閾値緩和、Phase 3Rには進まない。

保全値はrelease/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`/`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`で診断前後不変。証跡は`catchup-causality-v022.json`。

## v021 4敵no-reinject chain verifier-only計測（2026-08-12）

`make phase-2r-display-profile-no-reinject-gearlynx`をPASSした。v019の4敵NORMAL fresh fixture（各interval再注入）とは別に、v021専用`--no-reinject`経路で独立2 batchを実行し、各batch開始前のfixture注入を1回だけ行い、10 interval中の`inject_state`呼出を0回にした。対象は4敵NORMALのみで、release/cadence ROMの動作コード、scheduler、閾値、Phase 3Rは変更していない。

4敵no-reinjectのmedian/maxは両batchとも`31/134` VBlank。interval 1〜3で敵slotのactive/type/x/yまたは敵弾のactive/x/yが変化し、各batchの状態進化はPASS（変更enemy slot 12、enemy bullet slot 3）。各公開境界で8敵slot（active/type/x/y）と16敵弾slot（active数・active座標）をreadbackし、fixture/readback整合性、`tgi_busy/tgi_sprite/tgi_updatedisplay`分類をPASSした。medianはv019 fresh比較値`153/154`から、既存free-run比較値`32/30`の中央値31±5 VBlank内へ減衰したため、判定は`state_dependent_model_confirmed`。

0敵profile/no-profile陰性対照も従来条件で再実行し、profile=`115.5/115.5`、no-profile=`115/115`、絶対差=`0.5/0.5` VBlank、相対差=`0.4348%/0.4348%`でPASS。MCP応答停止、fixture readback不整合、対照不成立はなし。証跡は`display-profile-v021.json`で、全raw interval、状態差分、注入回数、再現コマンド、ROM SHA/map Segment/MAIN余剰を保存した。

保全値はrelease/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`/`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`で前後不変。v021の設計差分はverifierと診断Makeターゲット、証跡、README/ISSUESの追加のみ。修理・最適化・閾値変更・ROM内profiler・Phase 3Rは未着手でBLOCKEDを維持する。

## v019 公開symbol表示境界verifier完遂（2026-08-12）

`make phase-2r-display-profile-gearlynx`をPASSした。v018の全公開breakpoint同時arm・再arm手順を廃止し、公開symbolを1件ずつ`set -> hit -> snapshot -> remove`する同一frame直列chainへ変更した。必要な`tgi_ioctl`だけはbreakpoint除去後に`step_out`し、`debug_get_status.paused`を確認してから次の単独breakpointをarmする。計測chainは`_game_timing_consume_vblanks -> tgi_busy -> _static_layer_draw -> tgi_sprite -> _game_display_request -> tgi_updatedisplay -> 次consume`で、内部関数address推測はない。

3 fixture×2 batch×各10 intervalを完走し、各intervalでlive fixture、elapsed VBlank、logic/sound counter、Timer 2、公開境界到達tick、`tgi_ioctl` ABI分類を保存した。0敵NORMALのmedian/maxは両batch `115.5/116`、4敵NORMALは`153/154`、4敵+BOSS BOSSは`107.5/108` VBlank。各intervalの`tgi_busy/tgi_sprite/tgi_updatedisplay`は全fixtureとも`1/1/1`で、4敵-0敵の実frame中央値差`+37.5 VBlank`はioctl呼出回数増加では説明されない。同じ差の公開境界到達はstatic/tgi_busyが`+5,275,566` CPU ticks、tgi_spriteが`+5,268,782.5`、display requestが`+6,983,383.5`、updatedisplayが`+6,983,395.5`遅い。これは表示境界への到達関係の記録であり、最適化箇所の推定には使わない。

0敵profile/no-profile陰性対照はprofile=`115.5/115.5`、no-profile=`115/115`、絶対差=`0.5/0.5` VBlank、相対差=`0.4348%/0.4348%`でPASS。公開symbol/ABI/fixture/ROM-map不変もPASS。release/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312...`/`8d40092e...`を維持。証跡は`display-profile-v019.json`。修理・閾値変更・ROM内profiler・Phase 3Rは未着手でBLOCKEDを維持。

## v018 公開symbol限定の表示境界診断（2026-08-12）

`scripts/verify-display-profile-gearlynx.py`と`make phase-2r-display-profile-gearlynx`を追加した。cadence `.lbl`から`_game_timing_consume_vblanks=0x7F5A`、`_game_update_logic=0x1D09`、`_game_sound_tick=0x20AA`、`_static_layer_draw=0x7355`、`_tgi_ioctl=0x8E13`を解決し、内部関数addressは推測しない。

`tgi_ioctl` ABIはcc65 `tgi_ioctl.s`／`popa.s`／Lynx driver sourceと既存v009 O2証跡で確認した。入口のA/Xはdata pointer、codeはzero-page `sp`が指すC stack byteであり、code 0=`tgi_sprite`、code 4/data 0=`tgi_busy`、code 4/data 1=`tgi_updatedisplay`に分類する。

実測はGearlynxの複数公開breakpoint再開後にMCPが`paused`状態を返さず応答待ちとなり、fixture 10 interval×2 batch×3件を完走できなかった。時間・件数・fixture証跡は受入値として採用せず、修理・閾値変更・Phase 3RはBLOCKED。ROM/mapは不変。release Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰`450`、cadence=`109/37140/7890/308/1358`、MAIN余剰`264`。

## v016 catch-up logic単価・内部経路bisect診断（2026-08-12）

`make phase-2r-logic-profile-gearlynx`で、既存cadence ROMの`_game_update_logic`入口（cadence label=`0x1D09`）を対象に、0敵NORMAL、4敵NORMAL、4敵+BOSS BOSSを各2 batch×10 logic updateで計測した。各hitでTimer 2 current、`_cadence_probe_logic_update_count`、VBlank probe、live GameState/enemy readbackを保存し、breakpointはhitごとにremoveして次のhitだけ再設定した。証跡は`logic-profile-v016.json`。

Timer 2はbackup周期のup-counter差分（mod `backup+1`）で、logic 1回の中央値は0敵NORMAL=`18`、4敵NORMAL=`86`、4敵+BOSS BOSS=`59` ticks。全fixtureで2 batchとも10 hit、probe logic deltaは全pair `1`、live fixtureは全hit valid。経路はソースdispatch（`src/game.c:1585-1594`）に基づき、NORMAL=`update_normal` 100%、BOSS=`update_boss` 100%へ帰属した。`update_normal`/`update_boss`の安全なlabelはmapに存在しないため、内部アドレス推測breakpointは置いていない。

v015と同じ0敵 cadence陰性対照はprofile median=`115.5/116.0`、no-profile median=`115/115` VBlank、絶対差=`0.5/1.0`、相対差=`0.4348%/0.8696%`でPASS。ROM/map前後不変をassertし、release SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`、cadence SHA=`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`を確認。Segmentは通常 CODE/RODATA/DATA/BSS=`36714/7888/308/1264`、MAIN余剰`450` bytes、cadence=`37140/7890/308/1358`、MAIN余剰`264` bytes。

判定は**診断PASS・修理/最適化ゲートBLOCKED**。A支配の内訳をlogic入口単価とNORMAL/BOSS dispatchへ帰属したが、catch-up上限、scheduler、ゲーム速度セマンティクス、3 VBlank閾値、Phase 3Rは変更していない。`docs/plan/2026-08-12-suzy-sprite-migration-v2.md`も未変更。

## v015 Phase 2R-2 section-profile診断（2026-08-12）

`make phase-2r-section-profile-gearlynx`で、既存cadence probeだけを読むverifier-only診断を追加した。0敵NORMAL、4敵NORMAL、4敵+BOSS BOSSを各10 frame・独立2 batchで、`_game_sound_tick`（A）、`_game_display_sync_complete`（B）、`_game_display_request`（C）の各入口へ一回だけbreakpointを設定し、hit直後にremoveして、logic/sound/elapsed VBlank/Timer 2 currentとlive fixture stateを各境界で保存する。証跡は`section-profile-v015.json`。

同一0敵fixtureのprofile breakpointあり/なしを比較し、乖離時は`debugger_timing_contamination`でFAIL扱いにする。注入なしのcontroller macroによるTITLE→STAGE_INTRO→NORMAL free-runも陽性対照として記録し、ROM・map Segment・MAIN余剰の診断前後不変をassertする。sectionの60%以上判定は帰属記録専用で、修理・閾値変更・Phase 3R・ROM内プロファイラ追加は行わない。

最終実測は全6 batchでsection A=100%、B/C=0%。0敵NORMALのprofile/no-profile medianは`115.5/116.0`対`115/115` VBlank（差`0.5/1.0`）で汚染なし。従ってv2の「hsize/vsizeが100 VBlank悪化の主因」は撤回候補として`ISSUES.md`と証跡JSONへ記録し、v2設計書は変更していない。

## v013 静的SCB penpalニブル・pixel verifier・channel 1 verifier修正（2026-08-12）

`src/static_layer.c`のSuzy palette nibble割当をpixel 1=`penpal[0]`下位、2bpp pixel 2=`penpal[1]`上位へ修正し、`scripts/verify-static-layer-readback-gearlynx.py`の独立rendererを同じlookupへ整合した。cc65/sp65の終端重複byte境界も再現し、stage 1/2/3で期待pixelと両physical framebuffer pageが一致した。SCB chainは`21/9/9`件、期待nonzeroは`851/2636/1869`、mismatchは全stage 0。

証跡: `phase-2r-v013.json`、frame PNG `stage{1,2,3}-{screen,vidbas,dispadr}.png`。O5回帰は`phase-2r-o5-v013.json`（Run A/C1 PASS、Run B no-write mismatch、`cls_type_control_difference_separated`）。release SHAは`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`、versionは`0.53.3`。

channel 1 verifierはrelease mapの`_sound_backend_apply_all`入口`0x05A1`でSFXを注入し、次の`_game_display_sync_complete`後にMIKEYを観測する順序へ修正。`channel-{0,1,2}-diagnostic-v013.json`は全て`exit_code=0`、channel 1は5 note changes、gain`22→16,28→21`。sound source/BGM/SFX本体、Timer/IRQ、voice、SCB typeは変更していない。

全体回帰では`make clean && ./scripts/verify.sh`、host smoke/perf/debug contract、O5、静的readback、audio diagnostics、title/GAME OVER voiceがPASS。`make frame-cadence-gearlynx`は終了コード1で、0敵NORMALのmedian/max `115/117` VBlank（2 run）など既存の3 VBlank契約g未達を再確認。性能最適化は追加していない。

## v012 O5 Run B差分bisect・channel 1非侵襲診断（2026-08-12）

`make phase-2r-o5-gearlynx`でv011 Run A/Bを再現後、Run Bが無変化だったため差分追試C1を別Gearlynxプロセスで実施した。証跡は`phase-2r-o5-v012.json`、raw CPU readbackは`phase-2r-o5-run-{a,b,c1}-{c038,e018}.bin`。

- cc65 driverの`cls_sprite`（`.cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s:407-421`）とRun Bの23Bを証跡へ保存。共通は`sprctl1=0x10`、`sprcoll=0x20`、packed data `03 84 00 00`。主差分は`sprctl0=0x01 TYPE_BACKNONCOLL`対`0x05 TYPE_NONCOLL`、next、data pointer、座標、hsize/vsize、palette。
- C1はRun Bから`sprctl0`だけを`0x05→0x01`へ置換。`penpal[0]=0`、chain、data、座標、等倍scaleは維持。`VIDBAS+30*80+10/20`で`0xAA→0x0A/0x0A`、Run Aは`0xFA/0xCA`、Run Bは`0xAA/0xAA`不変。
- 判定: **zero-pen no-writeはchain/dataではなく`TYPE_NONCOLL`対`TYPE_BACKNONCOLL`のcontrol/type差分で分離**。C2/C3は最大3追試の上限内で未実施。release SHAは`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`不変。
- channel 1は`scripts/verify-audio-gearlynx.py --diagnostic-output`で、注入直後`output_sfx=[1,15,28,3]`、次の各同期境界直前`sfx_id=0/output_sfx=[0,0,0,0]`、MIKEY disabledを記録。現行Verifierは`_game_display_sync_complete`停止後にSFXを再注入するため、適用境界の観測対象が既に消費済み。source変更なしのVerifierタイミング問題として切り分け、回避的PASS化・閾値緩和はしていない。
- channel 0（8秒）/2（20秒）はPASS、channel 1（8秒）は同一経路2回FAIL（0 pitch change、gain pairなし）。機械可読証跡は`channel-{0,1,2}-diagnostic-v012.json`。

## v011 Phase 2R-2 Gate A O5 minimal chain Run A/B（2026-08-12）

`make phase-2r-o5-gearlynx`で、release ROMへデバッガ注入だけを行うO5最小chain Run A/B診断を実施する。証跡は`phase-2r-o5-v011.json`、raw CPU readbackは`phase-2r-o5-run-a-c038.bin`、`phase-2r-o5-run-a-e018.bin`、`phase-2r-o5-run-b-c038.bin`、`phase-2r-o5-run-b-e018.bin`。

- release ROM SHA-256は`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`をassertする。release source/ROM動作コード、static layer、背景データ、BSS、C stack、versionは変更しない。
- O5は`_tgi_ioctl`入口でscratch先頭54Bを`SCB_REHV_PAL` 23B×2 + data 4B×2へ注入し、両物理page `$C038`/`$E018`各8160Bを`0xAA`で埋める。Run A/Bは別Gearlynxプロセスで実行する。
- Run Aは`penpal[0]={0x0F,0x0C}`、Run Bはrelease同等`{00,0F,0F,03,00,00,00,00}`。return時`VIDBAS`を描画pageとして選び、`(20,30)`/`(40,30)`の期待byteをRun A=`0xFA/0xCA`、Run B=`0x0A/0x0A`で検証する。
- 実測はRun Aが`0xAA→0xFA/0xCA`でPASS、Run Bは期待`0x0A/0x0A`ではなく`0xAA/0xAA`不変（target page全8160B sentinel）となった。Run Aでchain traversal/data/座標/非zero `penpal[0]`を確認し、Run Bでは`penpal[0]=0`時のzero pixel no-writeを観測したが、penpal誤り単独の確定・static generated asset不良との切り分けは未完。
- 全変化byteをJSONへ前後値付きで保存し、return時`SCBNEXT`/`SPRGO`/`SPRSYS`/`VIDBAS`/`DISPADR`を同一フローで記録する。brief指定のcls差分bisect（最大3追試）は未実施。O5判定・未解決事項はJSONと`ISSUES.md`へ記録する。

## v009 Phase 2R-2 Gate A O2/O3/O4（2026-08-12）

`make phase-2r-gate-a-gearlynx`で診断完遂。証跡は`phase-2r-gate-a-v009.json`、raw CPU readbackは`phase-2r-v009-o3-*.bin`/`phase-2r-v009-o4-*.bin`。

- O2: 実`_tgi_ioctl`入口`0x8C70`から`debug_step_out`でreturn（`0x73EE`）まで追跡。entry CPUのfastcall候補`AX=0xB36D`がscratch/SCB head `0xB36D`と一致し、chain 21件・終端成立。`SCBNEXT=$FC10`、`SPRGO=$FC91`、`SPRSYS=$FC92`、`VIDBAS=$FC08`、`DISPADR=$FD94`はentry/return後ともreadback取得可能。return後実値は`SCBNEXT=0x0000`、`SPRGO=0x00`、`SPRSYS=0x00`、`VIDBAS=0xE018`、`DISPADR=0xC038`。
- O3: O2前に`$C038`/`$E018`を各8160 bytes `0xAA`で埋め、CPU `read_memory`で同一アドレスを再読出し。return直後・`tgi_busy`後とも`$E018`は全8160 bytesがclear色`0`へ変化したが、期待static 243 pixelは0、`$C038`は8160 bytes全てsentinel不変。Suzyのclear実行は観測でき、static非clear描画は未観測。
- O4: stage 1 / `GAME_PHASE_STAGE_INTRO` / player rect `(80,60,8,6)` / environment inactiveで旧`_tgi_bar=0x8962`入口を捕捉。`game_display_request=0x0298`時点のraw readbackで`$C038`に8160 bytes変化、player ROIのsentinel差分625 pixel・背景色以外94 pixelを確認。旧TGI陽性対照PASS、Gearlynx raw-memory/physical-page観測を主因から除外。
- 判定: **Gate A受入未完**。O3は「clearのみ・static非描画」で、generated packed dataまたはSCB chain continuation/format候補まで分離。非clear asset解釈とchain traversalの一意分離は未完。v008 full 0敵NORMAL cadenceも`116/117`,`115/117` VBlankで3 VBlank契約未達。O5最小chain/Fable5再相談が次の一手。
- v008 cadence整合性: `phase-2r-v008.json:runs[].full_0_enemy_raw` と `cadence-zero-v008.json:scenarios[0].phase_runs[0].contract_g.runs[].raw_interval_vblank_counts`は各75 sampleで完全一致。median/max報告値も`116/117`,`115/117`と一致。variant推定fieldはsummaryに使用していない。

## v008 Phase 2R-2 cadence cause isolation（2026-08-12）

`src/cadence_probe.s`へ実ゲーム状態の75-sample fixture ringを追加し、各sampleを`phase[2:0] | boss_active[3] | normal_enemy_count[7:4]`へpackした。0敵 NORMALを独立2 batchで検証し、両batchとも75/75が`phase=1,boss_active=0,normal_enemy_count=0`、invalid 0。fixture汚染を防ぐため、voice scratchのstatic layer領域539 bytesを避けたオフセットへ配置した。

V-A（static Suzy chain/display）、V-B（旧player TGI+display）、V-C（display sync only）のcadence-only variantを追加し、0敵 NORMALで計測。V-A中央値/最大値`111/114`,`111/113`、V-B/V-C結果と全variantのfixture-validityを`cadence-v-{a,b,c}.json`へ保存し、`phase-2r-v008.json`でA+B-C推定を比較する。推定値はfull測定中央値と一致せず、最大値に非加算的な外れ（推定183/179 VBlank）が出るため、単純な描画要素加算は原因モデルとして不成立。

full 0敵 NORMALは中央値/最大値`116/117`,`115/117` VBlankで、3 VBlank契約g未達。従って2R-2受入・Phase 3着手条件は未達のまま。release ROM SHA-256は`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`から不変。cadence mapはCODE `0x911B`、BSS `0x054E`、MAIN spare `257` bytesで基準ガードを維持。

Gate AのSCB構造は21/9/9 chain、next/termination、通常`hsize/vsize=0x0100`、clear`0xA000/0x6600`、penpal 8要素をPASS。両framebufferは一致するが、期待非zero 243/1989/1453に対し実測nonzero 0。原因はSCB chain生成不足ではなく、`_tgi_ioctl`→`ControlDrawSprite`のSuzy投入後、またはdraw/view page handoff境界に限定。`SPRGO=$FC91`、`SPRSYS=$FC92`、`VIDBAS=$FC08`、`SCBNEXT=$FC10`、`DISPADR=$FD94`の実行境界観測を次の分離点とする。

O1 free-run title captureも実行。breakpointなしで3秒進行したrelease ROMのPNGは背景色のみ（`title-free-run.png`, SHA-256 `ed46245c0780ad08d2b419e24a26be3f25596bc7fd993a633ddcbd159e5c2acb`）。したがってpixel readback FAILはcapture直前の一時停止だけでは説明できず、titleのclear/text SCB経路でも再現する。

## v006 Phase 2R-2 readback（2026-08-12）

`make static-layer-readback-gearlynx` の実測証跡は `phase-2r-v006.json`。実 `_tgi_ioctl` 直前でSCB chainを読み、独立レンダラで期待画素を生成し、Gearlynx MCPの `get_frame_buffer(vidbas/dispadr)` と `get_screenshot` を比較した。stage 1/2/3のSCB件数はそれぞれ21/9/9、chain終端・next連結、通常SCB `hsize/vsize=0x0100`、clear `0xA000/0x6600`、8要素penpalをPASS。動的対象はx/y=250、enemy/object inactiveのfixture。

pixel/buffer readbackは3 stageともFAIL。両bufferは一致するが背景色のみで、期待非ゼロ画素243/1989/1453に対し実測非ゼロ画素0。stage別PNGとSHA-256をJSONへ保存。SCB構造の未達ではなく、Suzy投入後の実描画またはGearlynx buffer handoffで原因分離が必要。

cadenceは既存契約gを再計測し、0敵 NORMAL `103.0/103.5`, 4敵 `31/29`, 8敵 `42/42`, boss+4 NORMAL `38/38`, boss+4 BOSS `123/124` VBlank（median/max、2 run）で全FAIL。閾値緩和・Phase 3着手はしていない。

v005で2R-0/2R-1の受入不足を補完。`STATIC_LAYER_DEBUG_ASSERT`付きdebug objectを生成し、共有scratch先頭539 bytesのvoice所有権契約違反がcc65の`__afailed`へfail-fastすること、release objectにdebug参照が残らないことを確認した。詳細は`phase-2r-v005.json`。

Gearlynx直列回帰はtitle/GAME OVER voice、MIKEY channel 0（8秒）、channel 1（8秒）、channel 2（20秒）を全PASS。並列実行は同一デバッグポートの競合を起こすため採用していない。

v004の2R-0/2R-1統合結果は`phase-2r-v004.json`に保存。基準C stack予約を維持したまま通常/cadenceのリンクを回復し、MAIN spare 444/406 bytesを確保した。Gearlynx契約gは0/4/8/boss fixtureで継続FAIL。

v003の基準C stack予約測定。受入完了ではなく、RAM/設計ブロッカーとして停止した証跡。

- `ram-blocker-v003.json`: 基準CFG、通常/cadenceのmap実測、ld65のoverflow量、未生成label、128 bytes guard未測定理由を保存。
- 通常CFGは`__STACKSIZE__=$0780`（1920 bytes）、cadence CFGは`$0630`（1584 bytes）。v002で残っていた縮小予約を復元した。
- 通常ROMはBSS overflow 1186 bytes、cadence ROMは1224 bytes。リンク不能のためLNX、SHA-256、stack low-water、Gearlynx、pixel、cadence、音声回帰は測定していない。
- v003の停止条件に従い、音声圧縮・BSS削減・stack縮小・別予約領域流用は行っていない。
