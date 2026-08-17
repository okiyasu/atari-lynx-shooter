# ISSUES

最終更新: 2026-08-17(APS-053 v030: TITLE/GAME OVERテキストの文字間隔(カーニング)修正・T0-3診断アセット削除・v029のT0(死にモジュール除外)をまとめてコミット。version=0.53.9。)

### APS-053 v030: 文字間隔(カーニング)修正・T0-3診断アセット削除（2026-08-17）

- 状態: **実装・host/ROM/Gearlynx readback・全39グリフ視覚証跡PASS**。ブリーフ(`.briefs/APS-053/v030.md`)通り、カーニング修正・T0-3・バージョン更新を実施し、v029で未コミットだったT0(死にモジュール除外)と合わせて1コミットにまとめた。
- 根本原因: v028で5列×7行フルグリフ化した際、文字間に透明スペーサー列を挟む処理が`text_line_data()`(生成器)/`build_text_line()`(ランタイム)のどちらにも無く、隣接文字が密着していた(v025以前の4bit圧縮版では`column != 3`の副作用で偶然隙間ができていたが、v028でその副作用も失われていた)。
- 実装: `scripts/generate-static-layer.py`の`text_line_data()`と`src/static_layer.c`の`build_text_line()`に、`suffix_glyphs`処理と同じ「1文字描画後に`pixel += 1`」を追加し、グリフ5bit+スペーサー1bit=6bit/文字に変更。`pixel_bytes`計算式を`length * 5`→`length * (STATIC_LAYER_FONT_WIDTH + 1)`(Python側は`length * 6`)へ更新。両ファイルは同一ロジックを維持。付随して`TEXT_DATA_SIZE`(`static_layer.c`)を`99`→`113`(20文字上限×6bit基準)へ再計算。
- T0-3: `src/static_layer_diagnostic_data.c`(L/R BIT TEST literal、約64B)を削除し、`Makefile`の`ROM_OBJECTS`・`build/static_layer_diagnostic_data.o`ビルドルールを除去。`src/static_layer.c`から`"A V 0 5 6"`動的診断表示、`static_layer_title_text(id=5)`呼び出し、`title_text_data()`の`case 5u`分岐、ヘッダの`#ifndef CADENCE_PROBE`ガード付きexternを削除。ユーザーが実機で文字化け解消を確認済みであることを前提に着手(ブリーフ記載の前提条件)。
- 検証スクリプト側の追随: `scripts/verify-title-game-over-readback-gearlynx.py`の独立5x7 renderer(`draw_text()`)を6px/文字advanceへ更新、`TEXT_DATA_MAX_SIZE`を99→113へ更新、`title_expected()`とevidence中の`title_positions`からL/R BIT TEST・A V 0 5 6の2エントリを削除、`load_assets()`から`static_layer_diagnostic_data.c`参照を除去。`scripts/verify-aps053-diagnostic-rom.py`は診断ワイヤリングの存在を要求するアサーションを「存在しないこと」を要求するアサーションへ反転し、`pack_literal()`を同じ6bit化に追随、`FIXED_TEXTS`から`L/R BIT TEST`を除去、`title_diagnostic`/`font_rows_independent`等の診断専用evidenceフィールドを削除(ブリーフのファイル許可リストに本スクリプトが載っていたが「削除」注記が無く、診断削除後も本スクリプトを壊れたまま残すのは非日ため、診断アサーションのみ反転・削除する対応とした。設計判断ではなくT0-3の直接的な帰結と判断)。
- 視覚証跡(全39グリフ=A-Z 26字+0-9 10字+`/`,`:`,`.` 3記号): カーニング修正の目視確認のため、`static_layer.c`のTITLE描画パスへ一時的に`#ifdef APS053_KERNING_CAPTURE`ガード付きの2行(`"ABCDEFGHIJKLMNOPQRST"`/`"UVWXYZ0123456789/:."`)を追加し、`-DAPS053_KERNING_CAPTURE`付きでビルドしたROMをGearlynxで実レンダリング・スクリーンショット取得後、目視で全グリフが隣接せず等間隔に表示されることを確認してから、当該一時コードを完全に削除して最終ROMを再ビルドした(最終差分に痕跡なし、Makefileにも未登録)。証跡: `evidence/APS-053/kerning-39-glyph-v030.png`。
- 実プレイ証跡: `evidence/APS-053/title-screen.png`(`ASTEROID PATROL`/`A/B TO START`/`ARROWS: MOVE`/`A/B: FIRE`/`VOICEVOX:Nemo`/`V0.53.9`が診断表示なしで正しい間隔・文字形状で表示、目視確認済み)、`evidence/APS-053/game-over-voice-screen.png`、`evidence/APS-053/game-over-complete-screen.png`。
- artifact: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`58533` bytes、SHA-256=`ebddd18877207b9773ea59cede2143fa4bbfc8f07f47bef3ca046a57a5892d1b`、画面表示version=`V0.53.9`。LNX=`magic=LYNX version=1 bank0_page=1024 bank1_page=0`。
- 検証: `make clean && ./scripts/verify.sh`(0; stage155/game625/sound351/IMA14949/sprite1647、cc65 strict、lint、LNX、voice cart)、`./scripts/verify-title-game-over-readback-gearlynx.py --rom dist/asteroid-patrol.lnx --symbols build/asteroid-patrol.lbl --output evidence/APS-053/title-game-over-v027.json`(0; TITLE/GAME OVER voice/complete全PASS、pixel_mismatch=0、新golden)、`make static-layer-readback-gearlynx`(0; stage1/2/3 page0/page1 PASS)、`python3 scripts/verify-aps053-diagnostic-rom.py --rom dist/asteroid-patrol.lnx --output evidence/APS-053/diagnostic-rom-v030.json`(0; 固定5文言・診断非配線を確認)。コミット・push・stash・reset・checkoutなし(pushは明示承認待ち)。
- 設計差分: ブリーフの「全39グリフの視覚証跡で確認してからgolden期待値を再構築」の順序を、一時デバッグ計装(コミット対象外)で先に視覚確認し、golden側のコード変更(readbackスクリプト)は視覚確認と同時並行で実施した後、最終ROMで回帰PASSを確認する順に実施(実質的な確認順序は維持、golden実装自体は視覚確認前に完了していた点が差分)。`scripts/verify-aps053-diagnostic-rom.py`の扱い(前項参照)はブリーフに明記が無かったための実装判断。

### APS-053 v029: RAM会計T0 — 死にモジュール(ima_adpcm.o/pcm_stream.o)リンク除外（2026-08-17）

- 状態: **実装・両map実測・host/ROM/Gearlynx音声readback全PASS**。ブリーフ(`.briefs/APS-053/v029.md`)通りT0-1/T0-2のみ実施。T0-3(診断アセット削除)、Phase 3R本体は未着手。
- 実装: `Makefile`の`COMMON_ROM_OBJECTS`から`build/ima_adpcm.o`(1,090B)・`build/pcm_stream.o`(328B、計1,418B)をリンク対象から除外。`src/ima_adpcm.c`/`src/pcm_stream.c`本体・`tests/test_ima_adpcm.c`等ホストテストは無改変(host testは引き続き独立にビルド・実行され`ima adpcm tests passed: 14949`でPASS)。`include/version.h`を`0.53.7`→`0.53.8`へ更新。
- map実測(除外後): `build/asteroid-patrol.map`・`build/asteroid-patrol-cadence.map`ともに`ima_adpcm`/`pcm_stream`文字列の出現ゼロ(grep -c で確認)。`pcm_stream_irq`が担っていたinterruptorも消滅(condesセクションに`_pcm_stream_irq`等の残存なし)。
- MAIN余剰実測(mapのSegment list、STARTUP+LOWCODE+ONCE+CODE+RODATA+DATA+BSS合計、MAIN上限46,776B=`$0200-$B8B7`): release=`45,024B`使用・余剰`+1,752B`(セグメント`6D/10/1B/8A58/1ED3/134/4E9`)、cadence=`45,348B`使用・余剰`+1,428B`(セグメント`6D/10/1B/8B87/1E8B/134/546`)。T0以前は両ROMとも超過(release約1,186B超過・cadence約1,224B超過、`docs/plan/2026-08-17-ram-reclamation.md`§4記載の見積もり)だったのが、この2ファイル除外だけで両ROMとも黒字に転換した。
- 音声再生回帰(Gearlynx実機ROM、`interruptor`テーブル変化の副作用有無を機械的に確認): `scripts/verify-title-voice-gearlynx.py`(mode=title、mode=game-over)を最終ROMに対して実行し両方PASS。title: DAC_writes=17413(prefix 3+本編17408)、Timer3 IRQ=17408、全17408サンプルexact一致、channel D音声変化・停止・Stage1遷移を確認。game-over: DAC_writes=11696(prefix 3+本編11691)、Timer3 IRQ=11691、全11691サンプルexact一致、channel D音声変化・停止・GAME OVERゲート解放を確認。どちらもUnderrunなし(`remaining=0 active=0 underrun=0`)。
- artifact: `dist/asteroid-patrol.lnx`、size=`58608` bytes、SHA-256=`44b0da55a270d46419c63c5727a98180a9bb4b73a82fb4b608f0fcfcb0ff7611`。`dist/asteroid-patrol-cadence.lnx`、size=`58839` bytes、SHA-256=`d0f1baf62faa736503d0023bbc383fdde14ca610d32c60955ecfed082e322d5b`。両LNXとも`magic=LYNX version=1 bank0_page=1024 bank1_page=0`。
- 検証: `make clean && ./scripts/verify.sh`(0; stage155/game625/sound351/IMA14949/sprite1647、cc65 strict、lint、LNX、voice cart)、cadence ROM個別ビルド(`make dist/asteroid-patrol-cadence.lnx`、0)、`./scripts/verify-title-voice-gearlynx.py`(mode=title/game-over、各0)。コミット・push・stash・reset・checkoutなし。
- 設計差分: なし。ブリーフ・設計書(`docs/plan/2026-08-17-ram-reclamation.md`§4)通りT0のみ実施し、T0-3・Phase 3R本体には触れていない。

### APS-053 v028: 文字化け根本原因修正・5x7フルフォント化・golden再構築（2026-08-17）

- 状態: **実装・host/ROM/Gearlynx readback・全39グリフ視覚証跡PASS**。v025〜v027はcompact化(`(value >> 1) & 0x0f`)とcolumn!=3スキップにより、5列×7行フォントのうち実際には左3列×上5行しか描画していなかった(2文字目以降の右2列と下2行が構造的に欠落)。手計算でA/E/P/B/D/O/I/T等の大半が酷似したパターンに潰れて判読不能になることを確認し、実機報告と一致。さらにGearlynx readbackの期待値(`draw_text()`)自体がこの崩れた圧縮ロジックを再実装していたため、pixel mismatch=0のPASSは崩れた表示同士の自己言及的な一致に過ぎず、文字として正しいかどうかは一度も検証されていなかった。
- 実装: `scripts/generate-static-layer.py`(`text_line_data()`)と`src/static_layer.c`(`build_text_line()`)から圧縮(`>>1 & 0x0f`)と`column != 3`スキップを撤廃し、`font_glyphs`の5bit値・7行をそのまま使う描画へ変更(`bits & (16 >> column)`、column 0-4全走査)。`STATIC_LAYER_FONT_WIDTH`を4→5、`STATIC_LAYER_FONT_HEIGHT`を5→7、`static_layer_font_bits`を39glyph×5行(195B)→39glyph×7行(273B)へ拡張。
- ROM予算対応: 上記拡張を素直に固定20文字幅で実装すると通常ROMのMAIN領域が72byte超過してリンク失敗した。Suzy literal 1bppの行はpen 0(透明)の末尾列を描画してもしなくても見た目が変わらないため(`TYPE_NONCOLL`)、各行のpixelバイト数を固定20文字分ではなく**実際の文字列長**に応じて可変にする設計へ変更(生成器・ランタイム両方、両者は同一ロジックを維持)。6つの固定TITLE文言の合計データは、固定20文字幅のまま単純に7行化すると336B(旧・欠陥版)→594Bへ膨張してMAIN超過の直接原因になっていたが、可変幅化により336→391Bに縮小、`font_bits`拡張+78Bと合わせてMAIN領域内に収まった。ヘッダbyte(=1+データbyte数、Suzy literal 1bppの行総byte数)は各行で再計算(`pixel_bytes+1`)。空白埋めロジック(`for (; c < 20u; ++c) pixel = ...`)は不要になったため削除。
- golden側の欠陥修正: `scripts/verify-title-game-over-readback-gearlynx.py`の`draw_text()`(独立5x7 renderer)が同じcompact圧縮ロジックを再実装していたため、`bits & (16 >> column)`・全7行・per-glyph advance5へ修正。`static_layer_text_*_data`アセットの読み出しをmax固定width(80/100)決め打ちから、行headerのbyte数から実際の幅を導出する`decode_literal_auto_width()`へ変更(可変長行に対応)。`scripts/verify-aps053-diagnostic-rom.py`の`pack_literal()`(生成data再現の独立検証)も同一の可変長ロジックへ同期。
- 隠れていた第二のバグ(readback truncation): 上記修正後もGAME OVER画面の"A/B TO TITLE"でreadback回帰が新規に落ちた。原因は`verify-title-game-over-readback-gearlynx.py`の`capture_submissions()`がscratchメモリを`SCRATCH_SCBS + 56`byte(旧`TEXT_DATA_SIZE=56`決め打ち)しか読んでおらず、新フォントで64byte必要な行データの末尾(最終行の一部)が切り捨てられていた。読み取り長を新しい最大値`TEXT_DATA_MAX_SIZE=99`(`TEXT_DATA_SIZE`と同期)へ修正。
- ROM予算実測: 修正後の通常ROM Segment CODE/RODATA/DATA/BSS=`0x8FFA/0x1F97/0x134/0x4F1` bytes、MAIN領域(`0xBE38-__STACKSIZE__(0x0780)`)内スペア=`106B`(v025時点の同ROM余剰450Bから縮小、cadence variant同様の圧迫傾向)。Phase 3R着手前ゲート・scheduler・Timer/IRQ・音声・ゲームロジック・SCB構造・`build_hud`(別の3列HUDフォント、対象外)は変更なし。
- 視覚証跡(新規、全39グリフ=A-Z 26字+0-9 10字+`/`,`:`,`.` 3記号): TITLE画面の診断行(`static_layer.c`内`#ifndef CADENCE_PROBE`ブロック)を一時的に2行のフルグリフ文字列("ABCDEFGHIJKLMNOPQRST"/"UVWXYZ0123456789/:.")へ差し替えてROMを再ビルドし、`scripts/capture-title-screenshot.py`でGearlynx実レンダリングをキャプチャ、目視で全グリフが判読可能な正しい文字形状であることを確認した後、診断行を元の内容(`L/R BIT TEST`/`A V 0 5 6`)へ戻して最終ROMを再ビルドした(最終差分に痕跡は残らない)。証跡: `evidence/APS-053/full-font-glyphs-v028.png`(生スクリーンショット)、`evidence/APS-053/full-font-glyphs-v028-zoom.png`(8倍nearest-neighborアップスケール、判読確認用)。
- 実プレイ証跡: `evidence/APS-053/title-screen.png`、`evidence/APS-053/game-over-{voice,complete}-screen.png`(全て最終ROMでの`title-game-over-readback-gearlynx`実行時に取得)。TITLE画面の`ASTEROID PATROL`/`L/R BIT TEST`/`A V 0 5 6`/`A/B TO START`/`ARROWS: MOVE`/`A/B: FIRE`/`VOICEVOX:Nemo`/`V0.53.7`、GAME OVER画面の`GAME OVER`/`A/B TO TITLE`/`VOICE...`が全て正しい文字形状で表示されることを目視確認。
- artifact: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`60246` bytes、SHA-256=`74c616573e441f055f4b52d652348855a93ce72716332ba9df26039ec1730092`、画面表示version=`V0.53.7`。LNX=`magic=LYNX version=1 bank0_page=1024 bank1_page=0`。
- 検証: `make clean && ./scripts/verify.sh`(0; stage155/game625/sound351/IMA14949/sprite1647、cc65 strict、lint、LNX、voice cart)、`./scripts/verify-title-game-over-readback-gearlynx.py --rom dist/asteroid-patrol.lnx --symbols build/asteroid-patrol.lbl --output evidence/APS-053/title-game-over-v028.json`(0; TITLE/GAME OVER voice/complete全PASS、新golden)、`python3 scripts/verify-aps053-diagnostic-rom.py --rom dist/asteroid-patrol.lnx --output evidence/APS-053/diagnostic-rom-v028.json`(0; 固定6文言・動的mask整合PASS)、対象`py_compile`(0)、`git diff --check`(0)。実機LCD/writer転送は未確認(Gearlynxのみ)。コミット・push・stash・reset・checkoutなし。
- 設計差分: ブリーフ(`.briefs/APS-053/v028.md`)は「固定20文字幅を前提とした再設計」を示唆していたが、そのまま実装するとMAIN領域を72byte超過しリンクに失敗したため、文字列長に応じた可変幅行へ設計変更した(視覚的には無関係、pen 0透明列を省略するだけ)。ブリーフの「両者は必ず同一ロジックを維持すること」は生成器・ランタイム双方で可変幅ロジックとして維持している。「全26文字の視覚証跡」は文字通りのアルファベット26字に加え、`font_glyphs`が実際に持つ数字10字・記号3種を含む全39グリフで実施した(取りこぼしを避けるため)。

### APS-053 v027: 実機Suzy文字化け診断ROM（2026-08-13）

- 状態: **通常ROM生成・独立byte検査・Gearlynx TITLE/GAME OVER/static readback PASS。実機v027投入待ち**。ユーザーがv025 exact SHA `40346dd9a9280b0d55ad25ba9bea4aaa296c3cd3ee386fb69bb702865904a15a`を再転送しても文字化けを再現したため、v025事象を旧ROM転送だけで説明する仮説は除外。
- 実装: `include/version.h`を`0.53.6`へ更新。`scripts/generate-static-layer.py`から固定literal asset `L/R BIT TEST`を生成し、TITLEの既存文字間へ配置。`src/static_layer.c`内で固定`static_layer_title_text(id=5)`と動的`static_layer_text("A V 0 5 6")`を同時queue。後続version描画によるHUD scratch上書きを、TITLEの未使用SCB slotへ2枚目の56B literal bufferを置く方式で解消。診断asset/codeを通常ROM専用objectへ分離し、cadence ROMの既存MAIN余剰264Bを維持。scheduler、Timer/IRQ、audio/voice/cart、背景/可動object、Phase 3R、CFG/stackは変更なし。
- バイト根拠: cc65 2.19一次ソースで`SCB_REHV_PAL=23` bytes、`SPRCTL1 LITERAL=0x80/PACKED=0x00`、literal/packedの行count+1、high-nibble-first、行終端、末尾duplicate、`penpal[value >> 1]`のlow/high nibbleを確認。v027の独立検査は固定6文言、動的mask `8u >> column`、version payload一意性、固定/動的診断配線を確認。Gearlynxの一致だけを実機正しさの根拠にはしない。
- artifact: 通常ROM `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`60092` bytes、SHA-256=`3e3c539a5419022a7b6bbf37bf9f5f9de5dd3768a74619985a7f3db8fb5d3dfb`、表示=`V0.53.6`、LNX=`magic=LYNX version=1 bank0_page=1024 bank1_page=0`、payload=`60028` bytes、version absolute offset=`37580 (0x92CC)`。cadence ROMはsize=`60331`、SHA-256=`1b812b794b8541b803397b0efe1da50327efbecf88a4605ba5528dc0a14c935d`、Segment STARTUP/CODE/RODATA/DATA/BSS=`109/37140/7890/308/1358`、MAIN余剰=`264B`。
- 診断表示: 固定`L/R BIT TEST`=`(58,28)`、動的`A V 0 5 6`=`(62,34)`。L/R端線、A/V/0/5/6の非対称輪郭により、左右反転・左右端1pixel欠落・行崩れ・全面欠落を分類。期待TITLE nonzero=`607`、TITLE SCB=`10`。GAME OVER voice/complete submissions=`[21,1,1,1]`。
- 検証: `make clean && ./scripts/verify.sh`（PASS; stage155/game625/sound351/IMA14949/sprite1647、通常LNX60092）、`make aps053-diagnostic-rom-gearlynx`（PASS; diagnostic/title-game-over/static layer、stage1/2/3）、`make dist/asteroid-patrol-cadence.lnx`（PASS; cadence余剰264B）、`python3 -m py_compile scripts/generate-static-layer.py scripts/verify-aps053-diagnostic-rom.py scripts/verify-title-game-over-readback-gearlynx.py scripts/verify-static-layer-readback-gearlynx.py`（PASS）、`git diff --check`（PASS）。commit/push/stash/reset/checkoutなし。
- 原因分類: `confirmed`=v025 exact SHAの実機再現、v027 source/ROM固定data・動的data・LNX payload整合。`ruled_out`=v025事象を旧ROM転送だけで説明する単独仮説。`likely`=実機Suzyまたはwriter経路に依存する差異（field未特定）。`not determinable locally`=実機Suzyのliteral 1bpp/SCB解釈、実機LCD表示、v027投入ファイルのSHA・writer転送ログ。実機確認はSHA一致→`V0.53.6`→診断文字形状の順序で行う。

### APS-053 v026: 実機投入識別・Suzy差異切り分け（2026-08-13）

- 状態: **診断ROM・host/strict ROM/LNX/Gearlynx readback PASS、実機差異は物理投入未確認で停止**。v025はcompact glyph mask修正後も`GAME_VERSION_STRING`を`0.53.4`のままにしており、旧ROMと修正版を画面上で一意識別できなかった。必要最小の診断変更として`include/version.h`を`0.53.5`へ更新し、通常ROMだけを再生成。ゲームロジック、scheduler、Timer/IRQ、audio/voice、Phase 3R、背景/可動object、SCB構造は変更なし。
- artifact: `/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx`、size=`59903` bytes、SHA-256=`333fdfbec6f28b3d898d2646f8f1ba8eefd20aee519f9b210c1dbca3d60c5ba9`、画面期待version=`V0.53.5`。LNX=`magic=LYNX version=1 bank0_page=1024 bank1_page=0`、header後payload=`59839` bytes、version payload offset=`0x9251`/絶対`37457`に`0.53.5`が1箇所。生成UTC/source・generator・static data hashは`evidence/APS-053/diagnostic-rom-v026.json`。
- source根拠: ローカルcc65 2.19一次ソース`.cache/cc65-2.19/source/include/_suzy.h`で`SCB_REHV_PAL=23` bytes、`.cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s`で`tgi_sprite -> tgi_ioctl(0)`、`SCBNEXT`/`VIDBAS`/`SPRGO`、double-buffer page、`.cache/cc65-2.19/source/src/sp65/lynxsprite.c`で`literal=1`/`packed=0`、count+1、high-nibble-first、行終端、末尾重複byte workaroundを確認。penpalは`value >> 1`のbyte、odd=low nibble/even=high nibble。Gearlynxだけの一致は自己同型検証を含むため、実機Suzy差異の否定根拠には不採用。
- 原因分類: `confirmed`=v025まで旧ROM判別不能、現行LNX/version/payload、固定5文言の生成dataと動的文字mask`8 >> column`の整合。`likely`=実機へ旧ROMまたは別ファイルを転送した可能性（投入ファイルSHA未取得のため未確定）。`not determinable locally`=物理writer転送結果、実機LCD version、実機SuzyのSCB/1bpp/penpal挙動。リポジトリ内に転送ツール・手順・転送ログなし。
- 実機確認手順: writerへ渡すファイルSHAが`333fdf...c5ba9`と一致、reset/reload後TITLEが`V0.53.5`、writer名・転送ログ・投入pathを保存。SHA/version不一致のままハード差調査へ進まない。
- 診断: 新規`scripts/verify-aps053-diagnostic-rom.py`、Makeターゲット`aps053-diagnostic-rom-gearlynx`。独立compact-5x7 rendererで固定TITLE 5文言と動的maskを静的検査し、LNX header/version payloadを検査。`title-game-over-v026.json`はTITLE/GAME OVER voice/complete全PASS、`phase-2r-v026.json`はstatic layer stage1/2/3全PASS。
- 検証: `make verify`終了コード0（stage155/game625/sound351/IMA14949/sprite1647、cc65 strict、lint、LNX、voice cart）、`make aps053-diagnostic-rom-gearlynx`終了コード0（diagnostic ROM、TITLE/GAME OVER、static layer readback）、`python3 -m py_compile scripts/verify-aps053-diagnostic-rom.py scripts/verify-title-game-over-readback-gearlynx.py scripts/verify-static-layer-readback-gearlynx.py`終了コード0、`git diff --check`終了コード0。commit/push/stash/reset/checkoutなし。

### APS-053 v025: TITLE/GAME OVER Suzy文字文字化け修正（2026-08-13）

- 状態: **実装・host/ROM/Gearlynx framebuffer readback・実プレイ画面証跡PASS**。原因はcompact font row（`(value >> 1) & 0x0f`）に対してmask `4 >> column`を使っていたこと。`scripts/generate-static-layer.py:text_line_data()`と`src/static_layer.c:build_text_line()`を`8 >> column`へ修正し、固定TITLE assetsと動的ASCII文字（version/GAME OVER/VOICE.../A/B TO TITLE）の左右端を含むglyph列を同一表現へ統一。HUDの旧3bit glyph mask、ゲーム挙動、scheduler、Timer/IRQ、背景/SCB方式、voice再生は変更なし。
- 証跡: 新規`make title-game-over-readback-gearlynx` / `scripts/verify-title-game-over-readback-gearlynx.py`。独立compact-5x7 rendererでTITLEの`ASTEROID PATROL`、`A/B TO START`、`ARROWS: MOVE`、`A/B: FIRE`、`VOICEVOX:Nemo`、versionを期待画素化。GAME OVERは`VOICE...` fixtureとvoice complete後`A/B TO TITLE` fixtureを連続検証。TITLE SCB=`8`、GAME OVER各state submissions=`[21,1,1,1]`、全sceneでvidbas/dispadr/screenshot pixel mismatch=`0`、両physical page一致。JSON=`evidence/APS-053/title-game-over-v025.json`、PNG=`evidence/APS-053/title-{vidbas,dispadr,screen}.png` / `game-over-{voice,complete}-{vidbas,dispadr,screen}.png`。
- ROM/RAM: `GAME_VERSION_STRING=0.53.4`。通常LNX=`59903` bytes、SHA-256=`40346dd9a9280b0d55ad25ba9bea4aaa296c3cd3ee386fb69bb702865904a15a`、Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰=`450B`。cadence LNX=`60331` bytes、SHA-256=`006ca98e09b3a5e50665a9955a4a486bad20d36040eefda55fbe309d4cb57517`、Segment=`109/37140/7890/308/1358`、MAIN余剰=`264B`。版数は上げていない。
- 検証: `make clean && ./scripts/verify.sh`（0; stage155/game625/sound351/IMA14949/sprite1647）、`make title-game-over-readback-gearlynx`（0）、`make static-layer-readback-gearlynx`（0; stage1/2/3 PASS）、`make smoke-host`（0; 19）、`make perf-host`（0）、`make debug-contract`（0）、`make phase-2r-audio-diagnostics-gearlynx`（0; channel0/1/2 PASS）、`python3 scripts/verify-title-voice-gearlynx.py --mode title` / `--mode game-over`（0）、対象`py_compile`（0）、`git diff --check`（0）。実機LCD/speaker、長時間playthrough未確認。コミット・push・stash・reset・checkoutなし。

### APS-053 v024: Phase 3R到達可能性 Timer2 tick→VBlank 校正（2026-08-13）

- 状態: **verifier-only校正PASS、Phase 3R本実装は未着手**。`scripts/calibrate-cadence-ticks-gearlynx.py`をAPS-049の旧`total_ticks`実験からv024専用校正器へ更新し、`phase-3r-tick-calibration-gearlynx`をMakefileへ追加。ROM動作コード、scheduler、Timer/IRQ、GAME_VERSION_STRING、Suzy/SCB、背景、C stackは変更なし。
- 方法/実測: GearlynxのTimer 2 IRQ=`irq=2`（`TIMER2_INTERRUPT`=`VBL_INTERRUPT`）を各独立2 batch×18 hitで取得。各隣接hitのVBlank差分=`1`、0差分=`0`、Timer2 backup/currentは全34区間で`0x68/0x68`、backup周期=`105` tick、wrap/不安定値なし。CPU `total_ticks`中央値=`184668/184680`、CV=`0.000753/0.000777`、debugger汚染判定PASS。
- 理論下限: v016証跡の0敵=`18`、4敵=`86` Timer2 up-counter tickから純増=`68` tickを固定。`timer2_ticks_per_vblank=105`、`logic_min_vblank=68/105=0.647619`でlogic単独は2 VBlank以下。ただしSuzy描画下限は既存公開境界計測から独立に証明できず、ゼロ扱いしていない。判定=`not_proven_pending_suzy_draw_bound`。次ゲートはPhase 3R本実装ではなく、bpp変換・SCB構成別のSuzy最小描画計測と収支表。
- 証跡/保全: `evidence/APS-053/tick-calibration-v024.json`。release/cadence Segment=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264`、ROM=`59903/60331` bytes、ROM/map前後不変。コミット・push・stash・reset・checkoutなし。
- 検証: `make phase-3r-tick-calibration-gearlynx`（0、LNX header、校正PASS）、`make clean && ./scripts/verify.sh`（0、game625/sound351/IMA14949/sprite1647、LNX 59903 bytes）、`make smoke-host`（0、19）、`make perf-host`（0、legacy median=`3184448us` / optimized median=`3352415us`）、`make debug-contract`（0）、`make static-layer-readback-gearlynx`（0、stage 1/2/3 PASS）、`make phase-2r-audio-diagnostics-gearlynx`（0、channel 0/1/2 PASS）、title/GAME OVER voice（0/0）、`python3 -m py_compile scripts/calibrate-cadence-ticks-gearlynx.py`（0）、`git diff --check`（0）。

### APS-053 v023: bounded fixed-step catch-up 比較ROM（2026-08-13）

- 状態: **実装・host回帰・Gearlynx比較PASS、3 VBlank契約未達のため追加最適化/Phase 3Rは停止**。logic credit=`raw_elapsed*4`を最大12、sound credit=`raw_elapsed`を最大4へbounded化し、超過分を同一outer loopで明示discard。raw elapsed取得、Timer/IRQ、入力poll一回、voice完了時baseline reset、audio apply、背景/Suzy/collision、Phase 3Rは変更なし。
- 証跡: `evidence/APS-053/bounded-catchup-v023.json`。4敵NORMAL fresh/no-reinjectを各独立2 batch×10 interval、0敵profile/no-profileを各2 batch実行。fresh median/max=`38/39,38/39` VBlank、no-reinject=`36.5/39,36.5/39`。fresh/no-reinject各intervalで実logic=`min(raw*4,12)`、sound=`min(raw,4)`、logic/sound discard、clip countが期待式と一致。状態進化はno-reinject全interval、changed enemy slot=`40`/batch、enemy-bullet=`12`/batch。0敵対照`22/22`対`22/22`、差0、相対0%。判定=`state_cost_dominant`。bounded化しても4敵表示は36〜39 VBlankで、3 VBlank契約gは未達。
- ABI/容量: release Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰=`450`。cadence=`109/37140/7890/308/1358`、MAIN余剰=`264`。ROM=`59903/60331` bytes。discard/clipはprobe常駐領域を増やさず、公開raw elapsed・実logic/sound counterからverifier算出。version=`0.53.4`。
- 検証: `make clean && ./scripts/verify.sh`、`make test smoke-host debug-contract`、`make perf-host`、`make static-layer-readback-gearlynx`、`make phase-2r-audio-diagnostics-gearlynx`、title/GAME OVER voice verifier、`make phase-2r-bounded-catchup-gearlynx`（各0、bounded evidence PASS、LNX release/cadence=`59903/60331`）、`python3 -m py_compile scripts/verify-display-profile-gearlynx.py`、`git diff --check`を実施。host game625/sound351/IMA14949/sprite1647/smoke19、stage readback 1/2/3 PASS、audio channel 0/1/2 PASS、title/GAME OVER voice PASS。perf-hostは終了コード0（optimized median 3189685us / legacy median 3104060us、paired delta median 33477us）。
- 設計差分/リスク: v022の現行clip式からbounded cap/discardへ変更。bounded schedulerは実装済みだが、4敵3 VBlank契約を達成しない。MAIN余剰264Bを維持するため、discard/clipの数値はROM内累積probeではなくverifierで厳密算出。hostではouter loop一回のFIRE入力をbounded logic 12回へ渡しても一発のみを確認。コミット・push・stash・reset・checkoutなし。

### APS-053 v022: catch-up因果分離 verifier-only 診断（2026-08-12）

- 状態: **verifier-only診断PASS、`mixed_or_inconclusive`、修理/最適化ゲートBLOCKED**。`scripts/verify-display-profile-gearlynx.py`へ`--catchup-causality`とcatch-up計算・相関分析を追加し、`phase-2r-catchup-causality-gearlynx`をMakefileへ追加。変更はverifier、診断ターゲット、evidence/README/ISSUESのみ。release/cadence ROMのC/asm、scheduler、速度セマンティクス、clip値、Phase 3R、コミット・push・stash・reset・checkoutは変更なし。
- 方法: 4敵NORMAL fresh（各interval再注入）/no-reinject（batch開始前1回のみ注入）を各独立2 batch×10 interval、同一公開symbol chainで計測。各intervalのraw elapsed VBlank、実logic/sound delta、現行clip式、logic/sound clip到達・廃棄量、Timer 2、公開display chain、全8 enemy slotのactive/type/x/y、全16 enemy-bullet slotのactive/x/y差分を保存。0敵profile/no-profile陰性対照も各2 batchで実行。
- 実測: fresh両batch raw=`11,73,148,153,154,153,154,153,154,154`、median/max=`153/154` VBlank、logic=`44,128,128,128,128,128,128,128,128,128`、soundはraw同値、logic clip 9/10 interval、最大廃棄488。no-reinject両batch raw=`12,80,98,132,134,0,27,31,31,31`、median/max=`31/134`、logic=`48,128,128,128,128,0,108,124,124,124`、soundはraw同値。no-reinject状態進化はinterval 1〜3、変更enemy slot=`12`、enemy-bullet slot=`3`。
- 因果判定: freshのclip到達・実行量増加とraw elapsedの相関（raw↔logic=`0.6604`、raw↔sound=`1.0`）はcatch-up増幅側を支持するが、状態進化と31 VBlank級への減衰も同時に存在。`catchup_amplification_supported`と`state_cost_dominant`を一意に分離できず、`mixed_or_inconclusive`とした。bounded fixed-step catch-up、scheduler修理、閾値緩和、Phase 3Rは未着手。
- 陰性対照: profile=`115.5/115.5`、no-profile=`115/115`、絶対差=`0.5/0.5` VBlank、相対差=`0.4348%`、fixture/readback、counter式、公開chain、MCP応答停止なし。証跡は`evidence/APS-053/catchup-causality-v022.json`。
- ABI/保全: cadence公開symbolは`consume=0x7F5A`、`logic=0x1D09`、`sound=0x20AA`、`static_layer=0x7355`、`tgi_ioctl=0x8E13`、`display_request=0x0298`。release/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`/`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`、source tree hash set前後不変。
- 検証: `make phase-2r-catchup-causality-gearlynx`（0、fresh/no-reinject/0敵対照・v022 evidence PASS）、`make clean && ./scripts/verify.sh`（0、stage155/game617/sound351/IMA14949/sprite1647、LNX 59903 bytes）、`make smoke-host`（0、19）、`make perf-host`（0、optimized median 3576455us / legacy median 3841766us）、`make debug-contract`（0）、`make static-layer-readback-gearlynx`（0、stage 1/2/3 PASS）、`python3 -m py_compile scripts/verify-display-profile-gearlynx.py`（0）、helper smoke（0）、`git diff --check`（0）。

### APS-053 v021: 4敵no-reinject chain verifier-only計測（2026-08-12）

- 状態: **verifier-only診断PASS、`state_dependent_model_confirmed`、修理/最適化ゲートBLOCKED**。`scripts/verify-display-profile-gearlynx.py`へ`--no-reinject`と敵/敵弾slot readbackを追加し、`phase-2r-display-profile-no-reinject-gearlynx`をMakefileへ追加。変更はverifier、診断ターゲット、evidence/README/ISSUESのみ。release/cadence ROMのC/asm、`src/`、`include/`、`cfg/`、scheduler、閾値、Phase 3R、コミット・push・stash・reset・checkoutは変更なし。
- 方法: 4敵NORMALだけを独立2 batchで各10 interval計測。各batch開始前の既存fixture注入は1回、10 interval中の再注入は0回。各公開境界で8 enemy slotの`active/type/x/y`、16 enemy-bullet slotのactive数とactive slotの`x/y`、elapsed VBlank、logic/sound counter、Timer 2、公開symbol境界、ABI分類を保存。
- 実測: no-reinject median/maxは両batch`31/134` VBlank。interval 1〜3で状態変化を検出し、各batchのchanged enemy slot=`12`、changed enemy bullet slot=`3`、fixture/readback整合性と公開境界chainはPASS。v019 fresh比較値`153/154`から、既存free-run比較値`32/30`の中央値31±5 VBlank内へ減衰。判定=`state_dependent_model_confirmed`。
- 陰性対照: 0敵profile/no-profileを従来条件で再実行し、profile=`115.5/115.5`、no-profile=`115/115`、絶対中央値差=`0.5/0.5` VBlank、相対差=`0.4348%/0.4348%`、`debugger_timing_contamination=false`。MCP応答停止、fixture readback不整合、対照不成立なし。
- ABI/保全: cadence公開symbolは`consume=0x7F5A`、`logic=0x1D09`、`sound=0x20AA`、`static_layer=0x7355`、`tgi_ioctl=0x8E13`、`display_request=0x0298`。release/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`/`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`前後不変。証跡は`evidence/APS-053/display-profile-v021.json`。
- 設計差分: v019 fresh状態とv013既存free-run状態の矛盾を、同一4敵fixtureの再注入有無とslot状態進化で分離。ROM内profiler、修理、閾値緩和、Phase 3Rへ進まない。詳細は`evidence/APS-053/README.md`。
- 検証: `make phase-2r-display-profile-no-reinject-gearlynx`（0、v021 evidence PASS）、`make clean && ./scripts/verify.sh`（0、stage155/game617/sound351/IMA14949/sprite1647、LNX 59903 bytes）、`make smoke-host`（0、19）、`make perf-host`（0、sync299.62Hz、optimized median 3235892us / legacy median 3097497us）、`make debug-contract`（0）、`make static-layer-readback-gearlynx`（0、stage 1/2/3 PASS）、`python3 -m py_compile scripts/verify-display-profile-gearlynx.py`（0）、`git diff --check`（0）、v021 evidence assertions（0）。

### APS-053 v019: 公開symbol表示境界verifier完遂（2026-08-12）

- 状態: **verifier-only診断PASS、修理/最適化ゲートBLOCKED**。`scripts/verify-display-profile-gearlynx.py`をv019へ更新し、Makeターゲット出力を`evidence/APS-053/display-profile-v019.json`へ変更。release/cadence ROMのC/asm、`src/`、`include/`、`cfg/`、背景データ、ROM内profiler、scheduler、閾値、Phase 3Rは変更していない。コミット・push・stash・reset・checkoutなし。
- 安全手順: v018の複数公開breakpoint同時arm/re-armを廃止。公開symbolを常に1件だけ`set -> hit -> snapshot -> remove`し、必要な`tgi_ioctl`だけbreakpoint除去後の`step_out`完了を`paused`で確認する同一frame直列chainへ変更。chainは`consume -> tgi_busy -> static_layer_draw -> tgi_sprite -> game_display_request -> tgi_updatedisplay -> 次consume`。内部関数address推測なし。
- 実測: 0敵NORMAL、4敵NORMAL、4敵+BOSS BOSSを各10 interval×独立2 batch完走。median/maxは0敵=`115.5/116,115.5/116`、4敵=`153/154,153/154`、BOSS=`107.5/108,107.5/108` VBlank。全60 interval（consume endpoint 120件）のlive fixture/ABI分類/境界chainがvalid。各intervalの`tgi_busy/tgi_sprite/tgi_updatedisplay`は全fixtureとも`1/1/1`。
- 0敵/4敵関係: 4敵-0敵の実frame中央値差は`+37.5 VBlank`。同じ差のconsume起点公開境界到達は`tgi_busy/static_layer=+5,275,566`、`tgi_sprite=+5,268,782.5`、`display_request=+6,983,383.5`、`tgi_updatedisplay=+6,983,395.5` CPU ticks。ioctl呼出回数は同一のため、回数増加では実frame差を説明しない。到達関係の記録のみで最適化箇所は推定しない。
- 陰性対照: 0敵profile/no-profile median=`115.5/115.5`対`115/115`、絶対差=`0.5/0.5`、相対差=`0.4348%/0.4348%`で`debugger_timing_contamination=false`。
- ABI/保全: cadence公開symbolは`consume=0x7F5A`、`logic=0x1D09`、`sound=0x20AA`、`static_layer=0x7355`、`tgi_ioctl=0x8E13`、`display_request=0x0298`。release/cadence Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、`109/37140/7890/308/1358`、MAIN余剰=`450/264` bytes、ROM SHA=`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`/`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`不変。
- 設計差分: v2のhsize/vsize主因撤回候補、ROM内profilerはユーザー承認必須、修理ゲートBLOCKEDを維持。v2設計書本文は変更していない。
- 検証: `make phase-2r-display-profile-gearlynx`（0、v019 evidence PASS）、`make clean && ./scripts/verify.sh`（0、stage155/game617/sound351/IMA14949/sprite1647、LNX 59903 bytes）、`make smoke-host`（0、19）、`make perf-host`（0、sync299.07Hz、optimized median 3773260us / legacy median 4189255us）、`make debug-contract`（0）、`make static-layer-readback-gearlynx`（0、stage 1/2/3 PASS）、`python3 -m py_compile scripts/verify-display-profile-gearlynx.py`（0）、`git diff --check`（0）。

### APS-053 v018: 公開symbol限定の表示境界診断（2026-08-12）

- 状態: **verifier-only実装、Gearlynx実測BLOCKED**。`scripts/verify-display-profile-gearlynx.py`と診断専用Makeターゲット`phase-2r-display-profile-gearlynx`を追加。release/cadence ROMのC/asm、`src/`、`include/`、`cfg/`、ROM内プロファイラ、Phase 3Rは変更していない。コミット・push・stash・reset・checkoutなし。
- 公開symbol解決: `_game_timing_consume_vblanks=0x7F5A`、`_game_update_logic=0x1D09`、`_game_sound_tick=0x20AA`、`_static_layer_draw=0x7355`、`_tgi_ioctl=0x8E13`をcadence `.lbl`から解決。内部関数address推測なし。
- ABI根拠: cc65 `tgi_ioctl.s`の`A/X→ptr1`、`jsr popa`、runtime `popa.s`の`lda (sp)`を確認。`_tgi_ioctl`入口ではdata pointer=`A|X<<8`、codeはzero-page `sp`の値が指すC stack byteとして分類する実装。code 0=`tgi_sprite`、code 4/data 0=`tgi_busy`、code 4/data 1=`tgi_updatedisplay`。既存`phase-2r-gate-a-v009.json`のAX/SCB head一致を補助根拠に使用。
- 実測分岐: 公開boundaryを複数breakpointで再開する試行は、初期イベント捕捉後にGearlynxが`paused=true, at_breakpoint=false`またはMCP応答待ちとなり、10 interval×2 batch×3 fixtureの完走不能。時間計測結果・tgi件数・fixture結果を受入証跡として採用していない。閾値緩和、修理、Phase 3Rへ進まない。
- map保全値: release Segment STARTUP/CODE/RODATA/DATA/BSS=`109/36714/7888/308/1264`、MAIN余剰=`450` bytes。cadence=`109/37140/7890/308/1358`、MAIN余剰=`264` bytes。通常/cadence LNX headerは`59903/60331` bytesで既存値不変。
- 検証: `python3 -m py_compile scripts/verify-display-profile-gearlynx.py`成功、`git diff --check`成功、`make phase-2r-display-profile-gearlynx`はGearlynx MCP境界待ちで手動中断（診断結果FAIL扱い、受入PASSではない）。
- 設計差分: v2本文は変更なし。hsize/vsize主因撤回候補、ROM内プロファイラはユーザー承認必須、修理ゲートBLOCKEDを維持。次の一手はMCPが複数公開breakpointのstep-out後も再開状態を返す手順の再設計、またはユーザー承認後のcadence限定ROM内プロファイラ検討。

### APS-053 v016: Phase 2R-2 catch-up logic単価・内部経路bisect診断（2026-08-12）

- 状態: **verifier-only診断PASS、修理/最適化ゲートBLOCKED**。`scripts/verify-logic-profile-gearlynx.py`と診断専用Makeターゲット`phase-2r-logic-profile-gearlynx`、`evidence/APS-053/logic-profile-v016.json`、README/台帳のみ追加/更新。release/cadence ROMのC/asm、`src/`、`include/`、cfg、背景データ、Timer/IRQ、C stack、scheduler上限、Phase 3Rは変更していない。コミット・push・stash・reset・checkoutなし。
- 方法: `_game_update_logic`入口の連続10 hitを各fixture・各2独立batchで取得。各hitでTimer 2 current、probe logic counter/VBlank counter/elapsed counter、live GameState/enemy readbackを保存し、breakpointを`set→hit→snapshot→remove→step_out→次hit再設定`で運用。最終callback後のprobe logic countは全batch 10。
- 単価: Timer 2 backup周期up-counter差分（mod `backup+1`）の中央値は0敵NORMAL `18` ticks、4敵NORMAL `86` ticks、4敵+BOSS BOSS `59` ticks。各fixtureのlive stateは20/20 hit valid、logic counter deltaは全pair `1`。VBlank counterはdisplay hook resetを検出して境界差分を無効化し、raw/reset情報は証跡へ保持。単価差は記録のみで、コード修理・上限変更・閾値変更へ進まない。
- 経路: map/labelで安全に解決できた公開境界はcadence `_game_update_logic=0x1D09`、`_game_sound_tick=0x20AA`。staticな`update_normal`/`update_boss`はlabel未出力のため内部アドレスを推測せず、`src/game.c:1585-1594`のlive phase dispatchでNORMAL=`update_normal` 100%、BOSS=`update_boss` 100%へ帰属。内部関数entry/returnの独立測定は未実施。
- 陰性対照: v015同様の0敵 cadence profile/no-profileを再実施。profile median=`115.5/116.0`、no-profile median=`115/115` VBlank、絶対差=`0.5/1.0`、相対差=`0.4348%/0.8696%`、`debugger_timing_contamination=false`。診断前後のROM/map SHA・Segment・MAIN余剰不変をassert。
- 保全値: release ROM `59903` bytes / SHA`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`、cadence ROM `60331` bytes / SHA`8d40092eb11e6f43b16a404dc7795644896305f59dd4133bbd0aa812bb646cab`。通常 Segment CODE/RODATA/DATA/BSS=`36714/7888/308/1264`、MAIN spare=`450` bytes。cadence=`37140/7890/308/1358`、MAIN spare=`264` bytes。map SHAは通常`d8bb6ef95cae7675ef2c117da19e439485fe893dbe6af0173ea7f18004bbde24`、cadence`3bc8cba2000797c72da9155b5ddb35ab2b39f748f135e798e63c591d9f961136`。
- 設計差分: v2のhsize/vsize主因撤回候補を維持。logic単価・経路帰属を追加しただけで、v2設計書は変更していない。A支配の事実は記録したが、section A内のcatch-up上限/scheduler/ゲーム速度のどれを修理すべきかは未分離のため停止。Phase 3Rは未着手。
- 検証: `make phase-2r-logic-profile-gearlynx`（0、LNX header、v016 evidence PASS）、短縮Gearlynx smoke（0、2 hit/probe count 2）、`python3 -m py_compile scripts/verify-logic-profile-gearlynx.py`（0）。全体回帰は次段で実施予定。

### APS-053 v015: Phase 2R-2 section-profile診断（2026-08-12）

- 状態: **verifier-only実装**。`scripts/verify-section-profile-gearlynx.py`と診断専用Makeターゲット`phase-2r-section-profile-gearlynx`を追加。release/cadence ROMの動作コード、`src/`、`include/`、背景データ、Timer/IRQ、C stack、Phase 3Rは変更しない。
- 方法: 0敵NORMAL、4敵NORMAL、4敵+BOSS BOSSを各10 frame・独立2 batchで計測し、A=`_game_sound_tick`初回hit、B=`_game_display_sync_complete`、C=`_game_display_request`の各境界で一回だけbreakpointを設定→hit→remove。各境界のprobe cumulative counter、live fixture readback、可能なTimer 2 current、section/frame差分を`evidence/APS-053/section-profile-v015.json`へ保存する。
- 対照: 同一0敵でprofile breakpointあり/なしのcadence median比較を実施し、乖離時は`debugger_timing_contamination`としてFAIL扱い。注入なしcontroller macroによるTITLE→STAGE_INTRO→NORMAL free-runを陽性対照とし、未到達を成功扱いしない。
- 判定: sectionの60%以上は帰属記録のみ。根拠なしの最適化、閾値緩和、Phase 3R着手なし。ROM SHA、map Segment list、MAIN余剰の前後不変をassertする。
- 設計差分: v2の「hsize/vsizeが100 VBlank悪化の主因」は、3 fixture×2 batchの全section集計でA=100%、B/C=0%となったため撤回候補。v2設計書自体は書き換えていない。

### APS-053 v013: 静的SCB penpalニブル修正・pixel verifier整合・channel 1 verifier修理（2026-08-12）

- 状態: **実装・対象回帰完遂**。`src/static_layer.c`のSuzy nibble割当、独立pixel renderer、channel 1 verifierの注入→sound apply→MIKEY観測順を修正。SCB type、背景データ、sound本体、Timer/IRQ、voice、可動object/collision/logic/inputは変更していない。コミット・push・stash・reset・checkoutなし。
- 静的SCB: pixel 1を`penpal[0]`下位、2bpp pixel 2を`penpal[1]`上位へ修正。pixel 0の`TYPE_NONCOLL`透明は維持。`make static-layer-readback-gearlynx`でstage 1/2/3のSCB chain `21/9/9`、両物理page一致、pixel照合をPASS。期待nonzero `851/2636/1869`、証跡`evidence/APS-053/phase-2r-v013.json`。
- packed renderer: cc65/sp65の終端重複byte境界を、valid packetとduplicate-byte内のtruncated literalを分離して再現。座標ハードコードや期待画像の上書きなし。stage 1/2/3 framebuffer mismatch `0`。
- channel 1: sound apply入口`0x05A1`（release mapの`_sound_backend_apply_all`）でSFXを注入し、次の`_game_display_sync_complete`後にMIKEYを観測。`channel-1-diagnostic-v013.json`は`exit_code=0`、5 note changes、gain`22→16,28→21`、channel 0/2も`exit_code=0`。release source/BGM/SFX dataは変更していない。
- O5回帰: `phase-2r-o5-v013.json`でRun A/B/C1を再実施。Run A/C1 PASS、Run B no-write mismatchを保持し、classification=`cls_type_control_difference_separated`。release ROM SHA`0c200312f9426b0cd8039ca3a374e8e782f9573b30bc19b0fb5d5c8b73dcafeb`、version`0.53.3`。
- 検証: `make clean && ./scripts/verify.sh`（0、stage155/game617/sound351/IMA14949/sprite1647、LNX 59903 bytes）、`make smoke-host`（0、19）、`make perf-host`（0、optimized median 3124603us / legacy median 3134322us）、`make debug-contract`（0）、`make static-layer-readback-gearlynx`（0）、`make phase-2r-o5-gearlynx`（0、A PASS/B MISMATCH/C1 PASS）、`make phase-2r-audio-diagnostics-gearlynx`（0、channel 0/1/2全PASS）、title/GAME OVER voice（0/0）、対象`py_compile`、`git diff --check`を実施。`make frame-cadence-gearlynx`は終了コード1。実測run medians/maximaは0敵`115/117,115/117`、4敵`32/32,30/30`、8敵`43/43,43/43`、4敵+boss NORMAL`38/39,38/39`、4敵+boss BOSS`120/124,120/124`で、既存の3 VBlank契約g未達。静的SCB/音声Verifier修正とは独立した既知の性能ブロッカーとして保持。

## 課題台帳

### APS-053: Phase 2R-2 Gate A O5 Run B差分bisect・channel 1非侵襲診断（2026-08-12）

- 状態: **O5のzero-pen no-write原因をcontrol/type差分まで分離。channel 1はVerifierタイミング問題として切り分け、release修正は保留**。変更はO5診断スクリプト、音声Verifier診断ログ出力、Makeターゲット、証跡、README/台帳のみ。release source/ROM動作コード、static layer、生成器、readback renderer、BSS、C stack、背景データ、versionは変更していない。コミット・push・stash・reset・checkoutなし。
- O5比較: cc65 `cls_sprite` source `.cache/cc65-2.19/source/libsrc/lynx/tgi/lynx-160-102-16.s:407-421`を23B証跡表現へ保存。Run Bとの共通項は`sprctl1=0x10`、`sprcoll=0x20`、packed data`03 84 00 00`。差分候補は`sprctl0/type`、SCB1 `next`、data pointer、座標、hsize/vsize、palette。
- C1: Run Bから`sprctl0`のみ`0x05 TYPE_NONCOLL→0x01 TYPE_BACKNONCOLL`へ変更し、`penpal[0]=0`・chain・data・座標・scaleを維持。Run Aは`VIDBAS+30*80+10/20`で`0xFA/0xCA`、Run Bは`0xAA/0xAA`不変、C1は`0x0A/0x0A`。C1一走行で原因を分離したためC2/C3は未実施（追試上限3以内）。証跡`evidence/APS-053/phase-2r-o5-v012.json`、raw`phase-2r-o5-run-{a,b,c1}-{c038,e018}.bin`。
- 実測判定: **chain traversal・packed data・penpal[0]=0単独ではなく、`TYPE_NONCOLL` control/typeがzero pixel writeを抑止する差分**。penpal修正・性能最適化・Phase 3Rは未着手。3 VBlank契約g未達も維持。
- channel 1: `--diagnostic-output evidence/APS-053/channel-1-diagnostic-v012.json`で、注入直後は`output_sfx=[1,15,28,3]`/`sfx_id=1`、各次同期境界直前は`sfx_id=0`/`output_sfx=[0,0,0,0]`/logical volume`0`/MIKEY disabledを記録。Verifierは`_game_display_sync_complete`停止後にSFXを再注入し、その同じ境界を観測するため、低FPS区間のsound tickで短い4-step SFXが次回適用前に消費される。source回帰ではなくVerifierの注入・観測順序問題と判定。回避的PASS化・閾値緩和なし。
- 音声回帰: channel 1は既存コマンドを同一条件で2回実行し、各`0 note change`・gain pairなし・終了コード1。channel 0（8秒）は2 pitch、gain`11→8,13→9`で終了コード0、channel 2（20秒）は2 pitch、gain`1→1,15→11`で終了コード0。title/GAME OVER voiceは終了コード0。
- 保全: release normal SHA`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`、normal map MAIN spare`443`、BSS`0x04F0`を確認。cadence map/ROMは`make phase-2r-o5-gearlynx`再実行時に同様のguardを記録する。通常/cadenceとも各MAIN spare≥256 bytes、BSS非増加、release SHA不変を診断スクリプトでassertする。
- 検証: `make clean && ./scripts/verify.sh`（終了コード0、stage155/game617/sound351/IMA14949/sprite1647、strict cc65/LNX）、`make smoke-host`（19、0）、`make perf-host`（0、sync299.33Hz）、`make debug-contract`（0）、O5 v012（A PASS/B mismatch/C1 PASS）、audio channel0/1/2直列（0/1/0）、title/GAME OVER voice（0/0）、対象`py_compile`、`git diff --check`を実施。channel 1は原因切り分けのため失敗を保持。

### APS-053: Phase 2 静的背景・HUD・clearのSuzy SCB化

#### APS-053 v011 Phase 2R-2 Gate A O5最小chain Run A/B（2026-08-12）

- 状態: **O5最小chain Run A/B診断完遂、Gate A受入判定は診断結果に従う**。追加は診断スクリプト、Makeターゲット、計測証跡、台帳/READMEのみ。release source/ROM動作コード、static layer、生成器、readback renderer、BSS、C stack、背景データ、versionは変更していない。コミット・push・stash・reset・checkoutなし。
- 方法: `make phase-2r-o5-gearlynx`で通常/cadence mapとLNX headerを検査後、release ROMの安定TITLE→`_game_display_sync_complete`停止→`GAME_PHASE_STAGE_INTRO`・player `(250,250)`・敵inactiveを注入。実`_tgi_ioctl`入口でentry CPU/SCB headを確認し、両物理page `$C038`/`$E018`各8160Bを`0xAA`へ充填、scratch先頭へ54Bの`SCB_REHV_PAL` 2-chain + 4B data×2を書込み、readback一致後にrelease TGIへreturnさせた。Run A/Bは別Gearlynxプロセス。
- chain: SCB1/2は`sprctl0=0x05`（1bpp/TYPE_NONCOLL）、`sprctl1=0x10`（PACKED/REHV）、`sprcoll=0x20`、`hsize/vsize=0x0100`、座標`(20,30)`/`(40,30)`、dataは各`03 84 00 00`。Run Aは`penpal[0]=0x0F/0x0C`、Run Bはrelease同等`00 0F 0F 03 00 00 00 00`。
- 証跡: `evidence/APS-053/phase-2r-o5-v011.json`へentry/return CPU、entry fastcall候補とSCB head一致、注入54B readback、return時`SCBNEXT`/`SPRGO`/`SPRSYS`/`VIDBAS`/`DISPADR`、両pageのraw SHA-256・全変化byteの前後値を保存。rawは`phase-2r-o5-run-a-c038.bin`/`e018.bin`、Run B同名系。
- 実測判定: **Run AはPASS**。return時`VIDBAS=0xE018`、`DISPADR=0xC038`、`SCBNEXT=0`、`SPRGO=0`、`SPRSYS=0`。`0xE982`（`(20,30)`）が`0xAA→0xFA`、`0xE98C`（`(40,30)`）が`0xAA→0xCA`となり、両SCBのchain traversal、1bpp data`03 84 00 00`、座標/上位nibble、非zero `penpal[0]`の描画を確認。**Run Bは期待`0x0A/0x0A`に対し両byte不変`0xAA/0xAA`**。entry pointer/readbackはPASSで、Run Bのtarget pageは全8160B sentinel不変。したがってO5は「chainが第1だけ」ではなく、`penpal[0]=0`時にzero pixelが書込まれない挙動を観測した。`penpal[0]`誤り単独の確定、およびstatic generated asset不良との切り分けは未完。次候補はbrief指定のcls差分bisect（最大3追試）だが、本ターンではRun A/B以外を実施していない。O5単独で3 VBlank契約g未達を解消したとは扱わず、Phase 3R・性能最適化・penpal修正の先行実装へ進まない。
- map/保全: 通常/cadenceの全Segment（STARTUP/CODE/RODATA/DATA/BSS）、MAIN spare、BSS非増加、release SHAを証跡へ記録。通常/cadence MAIN spare各256B以上、release SHA`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`不変をassertする。
- 検証: `make clean && ./scripts/verify.sh`（stage155/game617/sound351/IMA14949/sprite1647、strict cc65/LNX、終了コード0）、`make smoke-host`（19）、`make perf-host`（終了コード0、sync 75/300/75、299.07Hz）、`make debug-contract`、O5 target再実行、対象py_compile、`git diff --check`を実施。title/GAME OVER voiceはPASS、audio channel 0（8秒）/channel 2（20秒）はPASS。既存`verify-audio-gearlynx.py --seconds 8 --channel 1`は同一コマンド2回とも`0 note change`・gain pairなしで終了コード1（SFX verifier/実行経路の未解決FAIL）。

#### APS-053 v009 Phase 2R-2 Gate A O2/O3/O4（2026-08-12）

- 状態: **O2/O3/O4診断完遂、Gate A受入未完**。release source/ROM動作コード、static layer、可動object、collision、logic/input/sound/Timer/IRQ/voice/cart/C stack予約、背景データは変更していない。診断スクリプト・Makeターゲット・計測証跡・台帳のみ追加/更新。
- O2: 実`_tgi_ioctl`入口`0x8C70`から`debug_step_out`でreturn`0x73EE`まで追跡。entry CPU fastcall候補`AX=0xB36D`が`title_voice_scratch_buffer`/SCB head`0xB36D`と一致。SCB chain 21件・終端成立。`SCBNEXT=$FC10`、`SPRGO=$FC91`、`SPRSYS=$FC92`、`VIDBAS=$FC08`、`DISPADR=$FD94`をentry/return後に同一フローでreadback可能。return後実値`SCBNEXT=0x0000`、`SPRGO=0x00`、`SPRSYS=0x00`、`VIDBAS=0xE018`、`DISPADR=0xC038`。証跡は`evidence/APS-053/phase-2r-gate-a-v009.json`。
- O3: O2前に物理`$C038`/`$E018`各8160 bytesを`0xAA` sentinel化し、MCP screenshot/framebuffer APIを使わずCPU `read_memory`で再読出し。`$E018`は`_tgi_ioctl` return直後・production `tgi_busy`後とも全8160 bytesがclear色`0`へ変化、期待static 243 pixelは0。`$C038`は8160 bytes全てsentinel不変。Suzy clear実行は観測できたがstatic non-clear描画は未観測。
- O4: stage 1 / `GAME_PHASE_STAGE_INTRO` / player rect`(80,60,8,6)` / environment inactiveで旧`_tgi_bar=0x8962`を捕捉。`game_display_request=0x0298`時点のraw readbackで`$C038`に8160 bytes変化、player ROIのsentinel差分625 pixel・背景色以外94 pixel。旧TGI陽性対照PASS、Gearlynx debugger/raw physical-page観測問題を主因から除外。
- 原因分類: **O3 clear-only/static-nonrender**。generated packed dataまたはSCB chain continuation/format候補まで分離。O2のchain head/termination/readbackとO4陽性対照は成立するが、非clear asset解釈とchain traversalの一意分離は未完。推測で原因確定せず、O5最小chain/Fable5再相談が必要。
- v008 cadence整合性: `phase-2r-v008.json:runs[].full_0_enemy_raw` と`cadence-zero-v008.json:scenarios[0].phase_runs[0].contract_g.runs[].raw_interval_vblank_counts`は各75 sampleで完全一致。reported median/maxも`116/117`,`115/117`と一致。variant推定fieldはcadence summaryに使用していない。
- 検証: `make clean && ./scripts/verify.sh`（stage155/game617/sound351/IMA14949/sprite1647、strict cc65/LNX、終了コード0）、`make smoke-host`（19）、`make perf-host`（終了コード0）、`make debug-contract`（終了コード0）、`make phase-2r-gate-a-gearlynx`（LNX/O2/O3/O4/v008 cadence consistency、終了コード0）、title/GAME OVER voice、channel 0/1/2 audio、関連`py_compile`、`git diff --check`を実施。`make static-layer-readback-gearlynx`は既存stage1/2/3 pixel FAIL（期待243/1989/1453、実測0）で終了コード2。`make frame-cadence-gearlynx`は0敵`116/117`,`115/117`、4敵`32/32`,`30/30`、8敵`43/43`,`43/43`まで計測後、boss batch completion MCPが約10分応答せず手動中断（make終了2）。`--only-zero`短縮再計測も同じcompletion waitで中断し、新規cadence証跡は未生成。release SHA`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`不変、通常map MAIN spare`443` bytes、BSS→stack residual`443` bytes、BSS`1264` bytes。

#### APS-053 v008 Phase 2R-2原因分離（2026-08-12）

- 状態: **fixture妥当性検証と描画要素分離を完了、受入未完**。実ゲーム状態の75-sample ringを導入し、0敵 NORMALの2 batch×75を全sample validで確認。phase 3 bits / boss active / normal enemy countのpack値が全て契約どおりで、fixture injection意図ではなく実`GameState` readbackを記録する。
- cadence variant: V-A=static Suzy chain/display、V-B=旧player TGI+display、V-C=display sync only。0敵 NORMALを各2 batchで計測し、V-A中央値/最大値`111/114`,`111/113` VBlank。`phase-2r-v008.json`のA+B-C推定はfull中央値と一致せず、推定最大値183/179の非加算外れを示した。描画コストを単純加算する原因仮説は棄却。
- full cadence: 0敵 NORMAL中央値/最大値`116/117`,`115/117` VBlank。3 VBlank契約g未達のため受入・Phase 3着手は停止。cadence mapはCODE`0x911B`、BSS`0x054E`、MAIN spare`257` bytes。通常release ROM SHA-256は`19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`で不変。
- drawing cause: real `_tgi_ioctl`直前のSCB chainは21/9/9、next/termination、通常`hsize/vsize=0x0100`、clear`0xA000/0x6600`、penpal 8要素がPASS。両bufferは一致するが期待nonzero 243/1989/1453に対し実測0。SCB構造・fixture破損ではなく、Suzy `SPRGO=$FC91`/`SPRSYS=$FC92`後の描画完了または`VIDBAS=$FC08`/`DISPADR=$FD94` handoff境界が未分離。証跡は`evidence/APS-053/phase-2r-v008.json`、`cadence-v-{a,b,c}.json`。
- O1 free-run title: `scripts/capture-title-screenshot.py`でrelease ROMをbreakpointなし・3秒実行してもPNGは背景色のみ。`evidence/APS-053/title-free-run.png` SHA-256=`ed46245c0780ad08d2b419e24a26be3f25596bc7fd993a633ddcbd159e5c2acb`。一時停止直後のcaptureだけが原因ではないことを確認。
- 次: Gate Aのレジスタ実行境界観測（`SCBNEXT=$FC10`、`SPRGO`/`SPRSYS`、`VIDBAS`、`DISPADR`）とO1 free-run title screenshotを追加し、Suzy未実行とcapture page誤りを分離。3 VBlank未達が解消するまで閾値緩和・Phase 3着手なし。

#### APS-053 v004 統合結果（2026-08-12）

- 状態: **2R-0/2R-1実装、基準CFGでリンク回復。受入未完**。通常/cadenceのMAIN余裕を確保したが、Gearlynx契約gは依然FAIL、Atari Lynx実機・pixel readback・buffer readback未確認。
- 2R-0: `src/static_layer.c`の通常SCBは`hsize/vsize=0x0100`へ統一し、clearのみ`160x102`の`0xA000/0x6600`へ復元。全SCBの`penpal[0..7]`を`memset`で初期化後、使用色/詳細色を設定。`title_voice_is_playing()`ガードをstatic background/text/creditへ追加し、`title_voice_scratch_buffer`先頭539 bytesをvoice再生中に描画しない契約を明文化。
- 2R-1: `COMPACT_ROM_CFLAGS`（main/static layerのみ`-O`）を導入。背景は生成packed data＋再利用SCB chain、HUDはliteral sprite、固定文言は生成literal data、動的文言は4x5 compact glyphへ縮小。`src/main.c`から`tgi_outtextxy`を全削除（`rg` 0件）。TGI vector fontの呼び出しは削除したが、標準driver由来のfont関連kernel BSSはmap上に残る。
- RAM/map実測（基準`__STACKSIZE__`維持）: 通常`CODE=0x8F71 (36721)`、`RODATA=0x1ED0 (7888)`、`DATA=0x0134 (308)`、`BSS=0x4F0 (1264)`、BSS end `0xB6FC`、MAIN upper `0xB8B8`、spare `0x1BC (444)`。cadence`CODE=0x90C3 (37059)`、`RODATA=0x1ED2 (7890)`、`DATA=0x0134 (308)`、`BSS=0x512 (1298)`、BSS end `0xB872`、MAIN upper `0xBA08`、spare `0x196 (406)`。v003 overflow（通常1186/cadence1224）を解消し、両方256 bytes以上を確保。
- ROM: 通常LNX 59,910 bytes、SHA-256 `19bffae3019e1fe64c5578e8c581a3201c93ad0fdafa9ea2735da056f9d94f0c`。cadence LNX 60,250 bytes、SHA-256 `ad3a39dc3acbe705b3cf1cff2dd70b5f0e250b5fc0875847c0657f8947af7f85`。version `0.53.2`。
- PASS: `make clean && ./scripts/verify.sh`（stage155/game617/sound351/IMA14949/sprite1647、strict cc65、voice/cart/LNX）、`make smoke-host`（19）、`make perf-host`、Python `py_compile`（static-layer/frame/audio/title/visual verifier）、`git diff --check`。
- cadence: `make frame-cadence-gearlynx`でTITLE校正PASS（median`3.0/3.0`、raw`3/4`周期）後、契約gはFAIL。実測run median/maxは0敵`103.0/103.5`, `115/115`、4敵`31.0/29.0`, `31/29`、8敵`41.5/41.5`, `42/42`、boss+4 NORMAL`37.0/37.0`, `38/38`、boss+4 BOSS`119.5/120.5`, `123/124` VBlank。
- 設計差分/リスク: 固定文言をliteral asset化し、voice credit suffixもSCB化。4x5 compact fontは旧TGI vector fontと字形・大文字小文字の見た目が一致しない可能性あり。Gearlynxの契約g/pixel/readback、実機の判読性・IRQ余裕・長時間再生は未確認。`evidence/APS-052/logic-catchup-gearlynx.json`は今回のcadence計測結果で更新済み。

#### APS-053 v006 Phase 2R-2実SCB/cadence/pixel/buffer readback（2026-08-12）

- 状態: **2R-2検証実施、受入未完**。`scripts/verify-static-layer-readback-gearlynx.py` と `make static-layer-readback-gearlynx` を追加。release sourceの動作コード、stack reservation、背景データは変更していない。
- SCB readback: 実 `_tgi_ioctl` 直前でstage 1/2/3を取得。chain件数は21/9/9。全chainの`next`終端・連結、通常`hsize/vsize=0x0100`、clear`0xA000/0x6600`、penpal 8要素をPASS。fixtureはplayer x/y=250、enemy/object inactive。
- Pixel/buffer readback: `get_frame_buffer(vidbas/dispadr)` と `get_screenshot` を両buffer・全stageで保存。各stageとも`vidbas == dispadr`だが背景色のみ（期待非ゼロ画素243/1989/1453、実測0）。SCB構造の不一致ではなく、Suzy投入後の実描画またはGearlynx buffer handoffの未分離原因として記録。証跡は`evidence/APS-053/phase-2r-v006.json`とstage別PNG。
- Cadence: 既存契約gを独立2 runで再計測。0敵 NORMAL `103.0/103.5`、4敵 `31/29`、8敵 `42/42`、boss+4 NORMAL `38/38`、boss+4 BOSS `123/124` VBlank（median/max）。全ケース3 VBlank以下未達、閾値緩和なし。
- 未達時の原因分離: static SCB chain readback PASS、framebuffer pixel readback FAIL、cadence FAILを別判定。背景全再描画の最適化、SCB構造変更、Phase 3は未着手。次はGearlynxのSuzy実行完了／DISPADR handoff境界を追加観測し、pixel mismatchが実描画未実行かcapture page誤りかを分離する。

#### APS-053 v005 2R-0/2R-1受入補完（2026-08-12）

- 状態: **2R-0/2R-1受入完了**（Dev、commit/push/stash/reset/checkoutなし）。既存release guardを維持したまま、`STATIC_LAYER_DEBUG_ASSERT`を追加。`static_layer_draw`、title text、通常text、text flush、credit suffixの各APIがvoice再生中に呼ばれるとdebug buildではcc65 `assert` の`__afailed`へfail-fastし、release objectには同参照を残さない。
- 契約: static layerは`title_voice_scratch_buffer`先頭539 bytesをSCB/HUDに使用。voice再生中はvoiceが全scratchを所有し、static layerとは非同時利用。宣言を`include/static_layer.h`と`include/title_voice.h`へ同期。
- Debug検証: `make debug-contract` PASS。`build/static_layer-debug.o`のimportに`__afailed`、通常`build/static_layer.o`には`__afailed`なし。意図的違反のfail-fast経路をdebug objectで確認。
- Gearlynx: `python3 scripts/verify-title-voice-gearlynx.py --mode title` PASS（channel D varied、17408 exact DAC writes、underrun=0、38 tick wait）。`--mode game-over` PASS（11691 exact DAC writes、underrun=0、input gate release）。`verify-audio-gearlynx.py`はchannel 0/1/2を各指定秒数でPASS（pitch change、75% gain: 0=`11→8,13→9`、1=`28→21`、2=`1→1,15→11`）。
- 証跡: `evidence/APS-053/phase-2r-v005.json`。Gearlynxスクリプトは同一debug portを使用するため直列実行。

- 状態: **実装済み・受入未完**（Dev、2026-08-12。commit/push/stash/reset/checkoutなし）。`tgi_clear`、space/sky/caveの静的背景、HUD clear/glyphを再利用SCB chain経由のSuzy描画へ置換。自機・敵・boss・弾・item・explosionの既存TGI run描画、collision、logic/input/sound/IRQ、TGI double-buffer同期は変更なし。
- 実装: `src/static_layer.c`でclear・背景・HUDを最大21個の`SCB_REHV_PAL` chainへ構築し、1回の`tgi_sprite()`で裏bufferへ投入。SCBは`TYPE_NONCOLL`/`NO_COLLIDE`、背景は生成済みpacked 1/2bpp、HUDは80x5の1bpp literal sprite。SCB/HUD領域は既存`title_voice_scratch_buffer`を共有し、`scripts/generate-static-layer.py`がpixel正本から`include/static_layer_data.h`/`src/static_layer_data.c`を生成。
- ROM/map実測: 通常LNX 61,533 bytes、SHA-256 `5e75fe9aa77be211334dcc491c6ddb49b7e8a5f809e0ad79725683251be08473`、CODE `0x978C`、RODATA `0x1D0C`、BSS `0xB864..0xBD59` (1,270 bytes)、C stack開始 `0xBE54`、BSS→stack残余250 bytes、stack reservation `0x1E4` (484 bytes)。cadence LNX 61,873 bytes、SHA-256 `ac1af073c4878d13792538cf3d97c7c504eb7b4b4b6eace76c77596c8713ccdb`、CODE `0x98DE`、RODATA `0x1D0E`、BSS `0xB9B8..0xBECF` (1,304 bytes)、C stack開始 `0xBFA0`、BSS→stack残余208 bytes、stack reservation `0x98` (152 bytes)。両LNX header検査PASS、BSS/stack非重複。実測stack未使用は0敵/4敵で61 bytes、8敵/BOSSで0 bytesとなり、要求128 bytes guardは未達。CFGのstack reservation変更はv001からの既存差分を維持し、v002では変更なし。
- PASS: `make verify`（stage 155 / game 617 / sound 351 / IMA 14,949 / sprite 1,647、cc65 strict、lint、通常ROM）、`make smoke-host`（19）、`make perf-host`、`python3 -m py_compile scripts/generate-static-layer.py scripts/verify-stage-visuals-gearlynx.py scripts/verify-frame-pacing-gearlynx.py`、`git diff --check`。
- 未達: `scripts/verify-stage-visuals-gearlynx.py`は`stage 1 player collision/visibility mismatch: rect=(10,48,8,6) dying=1 invincibility=0`でFAIL。最終`make frame-cadence-gearlynx`は全5ケースを計測したがFAIL（0敵 NORMAL raw中央値 `101.0/100.5`、4敵 `25.0/23.0`、8敵 `35.0/35.0`、BOSS+4 NORMAL `31.0/31.0`、BOSS+4 BOSS `117.5/117.0` VBlank、全ケース3以下未達）。APS-053向け全3 stage NORMAL/CAST/BOSS pixel証跡、Suzy/TGI buffer readback証跡は未生成。
- 設計差分/次: starを1x1点SCBへ分解し、HUDをliteral 80x5 spriteへ統合したが、0敵 cadence は約100 VBlankで改善せず。pixel verifier同期条件、cadence根因、buffer readback証跡、実機長時間IRQは未解決。`evidence/APS-052/logic-catchup-gearlynx.json`は最終全5ケース計測結果へ更新済みだが、契約g `all_contract_g_within_budget=false`。

#### APS-053 v003 是正結果（2026-08-12）

- 状態: **基準RAM/設計ブロッカーで停止**。`cfg/lynx-voice.cfg`を`__STACKSIZE__=$0780`、`cfg/lynx-voice-cadence.cfg`を`$0630`へ復元し、縮小予約を成功条件として扱わない。
- 通常ROM: `make clean && make verify`で`ld65: Segment 'BSS' overflows memory area 'MAIN' by 1186 bytes`。`build/asteroid-patrol.map`の`CODE=0x978C`、`RODATA=0x1D0C`、`DATA=0x0134`、`BSS=0xB864..0xBD59 (0x4F6/1270 bytes)`、基準MAIN終端`0xB8B8`。リンクに必要な削減量は`0x4A2/1186 bytes`。
- cadence ROM: `make dist/asteroid-patrol-cadence.lnx`で`ld65: Segment 'BSS' overflows memory area 'MAIN' by 1224 bytes`。`build/asteroid-patrol-cadence.map`の`CODE=0x98DE`、`RODATA=0x1D0E`、`DATA=0x0134`、`BSS=0xB9B8..0xBECF (0x518/1304 bytes)`、基準MAIN終端`0xBA08`。リンクに必要な削減量は`0x4C8/1224 bytes`。
- C stack guard: 128 bytes以上の実測はリンク失敗のため未測定。`.lbl`は生成されず、BSS/stack実行時guard、ROM SHA/LNX、Gearlynx、pixel、cadence、音声回帰は実行不能。詳細な機械可読証跡は`evidence/APS-053/ram-blocker-v003.json`。
- 制約遵守: 音声圧縮、BSS削減、stack予約縮小、別予約領域流用を実装していない。既存partial実装のSCB受入不合格（0敵cadence、pixel、buffer readback）も未解消。次はRAM/設計方針（少なくとも通常1186 bytes・cadence1224 bytesの削減元、またはPhase 2 rollback/再設計）の明示判断が必要。

### APS-052: Phase 1 Timer 2基準logic catch-up

- 状態: **Phase 1完了・実sound tick/stack/低FPS音声回帰PASS**（Dev、2026-08-11。commit/push/stash/reset/checkoutなし）。描画cadence契約gは現行の未最適化描画経路が原因で期待どおりFAIL、Phase 2（描画最適化）は未着手。
- `src/game_timing.s`を追加。Timer 2 VBlankを32-bit monotonic counterへ加算し、`SEI`付きatomic consumeで16-bit elapsedをdraw開始前に返却。title/GAME OVERのblocking voice pump完了後はbaseline resetで蓄積VBlankを破棄。logicは最大128 updates/draw、soundは最大2048 ticks/draw、`sound_backend_apply_all()`はdrawごと1回。
- `game_logic_updates_for_draw_frame()`はproductionの`4/1`分母に合わせたcc65縮小経路とhostのremainder境界テストを保持。main loopはdrawごとinput poll/sound applyを1回、同一inputでcatch-up logicを反復。
- APS-052 cadence probeは実`game_update_logic()`戻り後のlogic counter、production consume elapsed、実`game_sound_tick()`戻り後のsound counter、stack low-waterを記録。sound counterはZP `$0023..$0026`へ置き、BSSを増やさない。debugger再開直後の6 display requestはwarm-upとして別記録。raw display合計とproduction elapsedの終端request差分を混同せずevidenceへ保存。
- sound上限を`GAME_SOUND_TICKS_MAX=2048`へ拡張。正本証跡`evidence/APS-052/logic-catchup-gearlynx.json`で、4敵NORMALはproduction `394/361` VBlank・actual sound `394/361`・discard `0/0`・clip `false/false`、8敵NORMALは`534/533`・`534/533`・`0/0`・`false/false`、boss+4はNORMAL `476/476`・`476/476`、BOSS `1797/1798`・`1797/1798`で全て音声実時間追従PASS。0敵の`1356/1354`もactualとproductionの一致を記録。4敵logic ratioは`1.0`/`1.0`、clip `0`/`0`。
- stack high-water guard: 通常CFG C stack `$B8B8..$C038`、cadence CFG C stack `$BA08..$C038`。4/8/boss+4計測時の最深`cc65 sp=0xBF00`、cadence stack used 312 bytes、未使用1272 bytes（要求128 bytes以上）でPASS。title/GAME OVER voiceでも同じstack guard回帰を維持。
- ROM: `GAME_VERSION_STRING=0.52.4`。通常`dist/asteroid-patrol.lnx` 60,295 bytes、SHA-256 `77968e51735bbe523d02462b9c2d5af1515e4ec18afaf7e38501eba7f5a569b4`。cadence `dist/asteroid-patrol-cadence.lnx` 60,635 bytes、SHA-256 `22492b25a89f0a540d58a95e18f9e272818acfd969b37f6c8bdb0013c56c72cd`。通常BSS `$B38E..$B88E` (1,269 bytes)、C stack開始`$B8B8`、残余53 bytes。cadence BSS `$B4E2..$B9F8` (1,303 bytes)、C stack開始`$BA08`、残余15 bytes、interval `$B8E7..$B8F6`、ZP sound counter `$0023..$0026`。両LNX header検査成功。
- 音声: title/GAME OVERのTimer3/DAC exact sample、underrun=0、38 tick wait、BGM/gate遷移、assembly decodeをPASS。MIKEY channel 0/2は複数pitchとgain `5→3`,`16→12`,`3→2`,`15→11`、channel 1は短いSFXの1 pitch changeとgain `28→21`をPASS。
- 検証: `make clean && ./scripts/verify.sh`、host回帰（game 617 / sound 351 / IMA 14,949 / sprite 1,647）、`python3 -m py_compile scripts/verify-frame-pacing-gearlynx.py`、`git diff --check`を実行済み。`make frame-cadence-gearlynx`は両ROM LNX検査、TITLE校正、4/8/boss+4の実sound tick/logic/stack証跡を生成後、描画契約gの期待FAIL終了コード2（4敵logic・4/8/boss+4 sound条件PASS）。

#### APS-052設計差分・未確認

- 設計差分: `GAME_SOUND_TICKS_MAX`を24から2048へ拡張し、production elapsedに対する実sound tick戻り後counterをZPへ追加。scheduler予定budget counterは削除し、実logic counterをlogic比率の唯一の実行証跡へ統一。計測ROMは実更新経路を使用。debugger再開遷移の6 requestだけをwarm-upとして別記録。区間数はAPS-052検収の実行可能性に合わせ16へ短縮（APS-051既存75区間証跡は変更なし）。remainderは本番分母が1のためsigned char引数で保持し、cc65では同値の小型経路を使用。
- 未確認: Atari Lynx実機での4/8敵時の速度・体感、低FPS時のSFX/BGM進行の実機差、長時間（16-bit API elapsedの65,536 VBlank超）動作、実機IRQマージン。Gearlynxでは未最適化描画cadence契約g FAIL継続。

### APS-051: 実時間cadence計測の是正（段階1）

- 状態: **段階1完了・段階2待ち**（Dev、2026-08-11、v003計測経路。commit/push/stash/reset/checkoutなし）。
- 通常ROM`dist/asteroid-patrol.lnx`から`cadence_probe.o`、`main-cadence.o`、probe header/hookを除外。`make verify`/`make rom`は通常ROMのみを生成し、`make frame-cadence-gearlynx`だけが`dist/asteroid-patrol-cadence.lnx`を専用cfg・label・map付きで生成して計測する。
- cadence interval 75 bytesは`src/cadence_probe.s`の計測ROM専用BSSへ正規確保。計測ROM map実測: BSS `$B319..$B857` (1,343 bytes)、C stack開始`$B878`、残余32 bytes、interval `$B76B..$B7B5` (75 bytes)でBSS/MAIN内かつstack非重複を機械検査。通常ROMはBSS `$B2A5..$B791` (1,261 bytes)、C stack開始`$B838`、残余166 bytes、probe symbol/moduleなし。
- 通常ROMと計測ROMは、共通GameState BSS相対配置（`_game`/`_game_enemies`）および生成stage/sprite/voice assetのSHA-256を検証。計測ROMのBSS拡張・code追加による絶対アドレス移動は、probe専用ROM内に限定。
- Timer 2 VBLANK基準は`184,482 ticks = 13,333.333333333334us`、契約g上限は`1.05 VBlank`。debug_step_frame、requestごとのpause/resume、ホストwall-clockは契約g判定に不使用。各batchは76 display request間を連続実行し、完了write breakpointを1回だけ使用。
- TITLE校正ゲートは独立2 batchともPASS。両runのraw 75 samplesが全て`3 VBlank`、中央値/最大値`3`、既存基準`553,362 / 184,482 = 2.999544671`との差`+0.000455329`。
- cadence契約gは全fixtureで意図どおりFAIL（`make frame-cadence-gearlynx`終了コード1）。各fixtureは独立2 batch、raw sample・run別中央値/最大値を`evidence/APS-051/frame-cadence-gearlynx.json`へ保存。
  - `0 normal`: median `15/14 VBlank`、max `15/16 VBlank`、各75/75超過
  - `4 normal`: median `24/23 VBlank`、max `28/135 VBlank`、各75/75超過
  - `8 normal`: median `33/33 VBlank`、max `145/145 VBlank`、各75/75超過
  - `boss+4 normal / NORMAL`: median `29/29 VBlank`、max `142/142 VBlank`、各75/75超過
  - `boss+4 normal / BOSS`: median `35/35 VBlank`、max `36/36 VBlank`、各75/75超過
- 通常ROM: `GAME_VERSION_STRING=0.51.2`、LNX `60,062 bytes`、SHA-256 `710bd88fd025eab61821ece965d46198d21b56e6da7ca21bdb967ad86e9ad256`。計測ROM: LNX `60,178 bytes`、SHA-256 `0ce571704f96c64f82a72078aa380a936d1aa18f672bda18d62ed7a7df49ebf6`。両LNX header検査成功。
- 検証: `make clean && ./scripts/verify.sh`（game 611 / sound 351 / IMA 14,949 / sprite 1,647、cc65 strict、lint、通常ROM LNX）成功、`make smoke-host`（19）成功、`make perf-host`成功。`make frame-cadence-gearlynx`は両ROM LNX検査PASS後、期待されたcadence FAILで終了コード1。`python3 -m py_compile scripts/verify-frame-pacing-gearlynx.py`、`python3 -m json.tool evidence/APS-051/frame-cadence-gearlynx.json`、map分離/BSS検査、`git diff --check`成功。
- 旧v001のbreakpoint介入値`14x`〜`145x`、v002のprobe混入通常ROM結果、およびそこから導いた「現行ROMの確定性能値」は正本から撤回。v002結果はprobe混入ROMの暫定結果としてのみ履歴扱いし、正本は分離済みcadence ROMと通常ROM双方のpath/size/SHA。
- host `tests/perf_bench.c`は実TGI/Suzy描画をリンクしないため、出力を描画性能やLynx実機速度の根拠にしない。段階2はSuzyハードスプライト（SCB直接）等で敵描画・背景全再描画を削減し、修理済み契約gでGearlynxの敵4/8体を独立2 batch再測定する。Atari Lynx実機でも敵4/8体の速度実測・体感確認を行い、cadence自動テスト単独PASSでは受入しない。

### APS-050: APS-047受入修正完了(APS-049未確定項目の解消)

- 状態: **v005完了**（Dev、2026-08-11。commit/push/stash/reset/checkoutなし）。APS-049で採用した`boss 2x`を廃止し、3ボスを**全員1x固定＋anchor=collision中心との整列**へ戻して、全停止位置におけるvisual端点クリップを排除。`scripts/generate-stage-data.py`の`SPRITE_CONTRACTS`(boss3種全て`scale=1`)と`src/main.c`の`draw_sprite()`を1x前提へ整理、`tests/test_stage_data.py`のsprite goldenを`tests/golden/sprite-data-v050.json`へ更新。`Makefile`/`include/version.h`(`0.50.0`)/`docs/plan/design.md`/`ISSUES.md`を同期。
- 完了条件: v001選択肢(b)（全3ボス1x）反映、`scripts/verify-stage-visuals-gearlynx.py`に`sprite_render_clip_counts`/`assert_sprite_not_clipped`を通し、全bossの`clipped_columns/rows`が0をPASS。
- 実測結果: `make clean && ./scripts/verify.sh`、`make smoke-host`、`make perf-host`、`python3 scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-050` をPASS。headless boss個別capture(13種)はいずれも`boss_clipped_columns=0`。
  - 注意: GUI実行は、同一環境実行時に`real TITLE input did not reach Stage 1 NORMAL`または`GUI/headless PNG mismatch`を2回観測しPASSに至っていない（非決定的）。headless回帰はPASS。
- ROM/RAM: `dist/asteroid-patrol.lnx` 60,062 bytes。`GAME_VERSION_STRING=0.50.0`（詳細はevidence/APS-050）。

### APS-049: APS-047受入不合格の根本修正(cadence実時間検証・sprite単一ソース化・契約テストa-g)

- 状態: **v003で残作業をほぼ完了したが、boss 2x採用に伴う画面端クリッピングの新規発見によりユーザー判断待ちで停止**（Dev、2026-08-10。commit/push/stash/reset/checkoutなし）。B(sprite単一ソース化)・契約a〜eはv001から維持。契約g(低頻度方式)は`verify-frame-pacing-gearlynx.py`本体へ正式統合済み(プロトタイプ`verify-frame-pacing-lowfreq-gearlynx.py`は一本化により削除)。boss 2xを実際に有効化した状態での契約g再測定はPASS(boss+4normal 37.683us/13,333us予算、0.28%)。契約f(capture pixel、preview起点)を新規実装しGearlynx証跡13種一式を保存、その過程で**coral_bastion/violet_geodeのboss停止位置(stop_x)で visual右端が画面外へ3pxクリップされる**ことを発見(amber_carrierは0px、詳細は下記A節参照)。これはv001/v002の契約gが検証していなかった別種の不具合で、採用可否の最終判断にはユーザー確認が必要。
- brief: `.briefs/APS-049/v001.md`, `.briefs/APS-049/v002.md`, `.briefs/APS-049/v003.md`。前版レビュー: `.briefs/APS-048/review-v001.md`(Fable5独立レビュー)。

#### B. sprite単一ソース化(完了)

- `assets/stages/stages.json`の`sprites`節からvisual grid(手書きgrid)を撤去し、`{id, kind, width, height}`(width/heightはcollision寸法)のみに変更。visual正本は`assets/previews/aps044-player-preview.json`(A案delta-wing採用)と`aps044-enemy-preview.json`の16x16 gridに一本化。
- `scripts/generate-stage-data.py`を全面改修: `load_previews()`でpreview 2ファイルをロードしframe 0として採用(逐語一致、変換・再authoringなし)。`SPRITE_ROLES["player"]`に`C`(A案engine flare role、`$FD5`)を追加。旧`SPRITE_FRAME_RUN_COUNTS`/`SPRITE_MIN_COLORED_CELLS`/`SPRITE_TOTAL_AUTHORED_RUNS`/`SPRITE_DESIGN_FEATURES`のハードコード定数は撤廃し、preview golden(SHA-256)+cell単位逐語一致検証へ置換。
- anchor: `(dx,dy) = collision中心 - visual bbox中心`をgeneratorが決定論的に算出(`sprite_anchor()`)し、1 byteへpack(`(dx+8)<<4 | (dy+8)`、範囲-8..7、分岐なしdecodeでCODEサイズを節約)。`GameSpriteDefinition`へ追加。
- frame 1: previewJSONに新設した`anim_delta`(cell単位の追加・再着色リスト、消灯なし)をoverlayとして適用。RAM予算のため最終的に**1 spriteあたり1 cell**まで切り詰めた(ブリーフの目安は2〜6 cell)。`draw_sprite()`はframe 0を描画後、`animation_frame!=0`ならframe 1(delta)を追加描画する2段階方式。
- run encoding: 3 bytes/run(y5/x0 5/len5/color8bit)から**2 bytes/run**(`y:4bit|x0:4bit`, `len:4bit|color:4bit`)へ圧縮。全sprite canvasが16x16に統一されたため4bitずつで収まる。`GameSpriteDefinition`も`{anchor(1B), frame0_offset(2B), frame0_count(1B), frame1_count(1B)}`(frame1はframe0直後に連続配置しoffsetを持たない)へ圧縮。
- **boss visual scaleはv003で2x採用**(`draw_boss()`側`draw_sprite_run_scaled`visitorでRODATA増加ゼロ)。契約gの実測合格(下記A節)を条件に2xへ切り替え済み。ただし2x採用に伴い**coral_bastion/violet_geodeのstop_x停止位置でvisual右端が画面外へ3pxクリップされる**新規事象を発見(下記A節参照、ユーザー判断待ち)。
- RAM実績: 変更前(APS-047時点)は3 bytes/run・274 runsでBSS残余698 bytes(baseline)。今回の16x16統一・preview逐語一致化で frame0 run数は480(旧274から+206、`player=44, scout=29, saucer=21, dropper=33, fighter=27, bomber=37, supply=30, cave_bat=35, rock_worm=30, mining_drone=34, coral_bastion=69, amber_carrier=40, violet_geode=51`)。2 bytes/run化・構造体圧縮・delta 1cell化まで行った結果、boss 1x固定時点では残余389 bytes。**boss 2x visitor(SpriteDrawOrigin構造体・スケール処理のローカル変数)を有効化した最終ビルドではBSS残余150 bytes**(cc65 C89はローカル変数を静的領域に置くため、コード追加分だけBSSが増えた。`__BSS_RUN__+__BSS_SIZE__`〜`__MAIN_START__+__MAIN_SIZE__`間の`build/asteroid-patrol.map`実測。受入条件の`≥11 bytes`はクリア)。`make verify`成功、`dist/asteroid-patrol.lnx`(60,078 bytes)生成確認済み。

#### 契約テストa〜e(実装済み・host/静的検証で緑)

- a(正本固定): `tests/golden/sprite-data-v049.json`にpreview(player variant a + enemy 12体)+ stages.json sprites(collision契約)を合わせたJSON snapshotのSHA-256を固定。`tests/test_stage_data.py`にgrid改変検知テストを追加。
- b(正本→runtime grid逐語一致): `tests/test_stage_data.py`に、`sprite_runs()`で生成したrunをgridへ再構成しpreview gridと一致することを13種全部で検証する処理を追加(`grid_from_runs`)。frame1もdelta適用結果と一致することを検証。features座標のrole(非透明)一致も検証。
- c(grid→packed run round-trip): `tests/test_sprite_data.c`を2 bytes/run decodingへ全面書き換え、`game_sprite_visit_runs`のtranslateされた座標がdecodeした値と一致することを検証(round-trip)。
- d(mapping): `game_enemy_sprite_ids`/`game_boss_sprite_ids`検証は既存のまま維持。
- e(ROM bytes): 新規`scripts/verify-sprite-rom-bytes.py`を追加。generatorの`pack_sprite_run`/`pack_sprite_anchor`と同じロジックでrun+definitionバイト列を再構築しSHA-256固定、`dist/asteroid-patrol.lnx`内にそのバイト列が連続して存在することをオフセット検索で確認、ROM全体のSHA-256も記録。v003最終ビルドでの実行結果: `PASS: sprite run/definition bytes (sha256=4343744b...) present at ROM offset 43155; ROM sha256=36382798...`(boss 2x採用でCODEサイズが変わりオフセット/ROM全体SHA-256はv002時点の値から変化、run/definitionバイト列自体のSHA-256は不変)。evidence: `evidence/APS-049/sprite-rom-bytes.json`。実行属性(+x)が欠けていたため`chmod +x`で修正(他script同様755に統一)。
- f(capture pixel、v003で新規実装): `scripts/verify-stage-visuals-gearlynx.py`を全面書き換え。旧版は`stages.json`の`sprites[].frames`(APS-047時代の簡略grid)を期待値源にしていたため、B節でgridを撤去した現行`stages.json`とはもう整合しない状態だった(そのままでは`KeyError`で実行不能)。新版は`assets/previews/*.json`のframe0 grid+`anim_delta`適用後のframe1を期待値源とし、`generate-stage-data.py`の`sprite_anchor()`/`SPRITE_CONTRACTS`をimportしてanchor・scaleを再現、main.cの`draw_sprite_run_scaled`と同じ「gridセル→scale×scaleブロック」変換でGearlynx実機capture(headless/GUI双方)のpixelと突き合わせる。ROM run/definitionバイト一致は契約eの責務のため重複実装しない。全13種PASS(詳細は下記A節参照、boss右端クリップはpixel照合上「画面外は未描画」としてスキップする実装 — `draw_clipped_hline`のx軸クランプ/y軸dropと同一挙動)。evidence: `evidence/APS-049/runtime-sprite-gearlynx.json`(headless)・`evidence/APS-049/gui/runtime-sprite-gearlynx-gui.json`(GUI、headlessとSHA-256完全一致を確認)。

#### A. cadence実時間検証・boss 2x採用(v003: 低頻度方式を正式統合・実測ゲートPASS、ただし画面端クリッピングを新規発見)

- v001セッションで`scripts/verify-frame-pacing-gearlynx.py`にtotal_ticksベースの契約g(1 draw frame実時間)を追加したところ、0 normal/0 bossで74/74フレーム全部が13.3ms予算超過(最大55,738.865us)しFAILしていた件、v002で手法切り分けを実施し**旧計測手法(高頻度breakpoint往復)側のアーティファクトと確定した**。
- **キャリブレーション(`scripts/calibrate-cadence-ticks-gearlynx.py`、新規)**: 現ビルドの未使用BSS残余(`.map`から動的算出、今回は`$B6B3`〜`$B837`の389 bytes)へ既知cycle数のNOP直線列(2 cycles/NOP、分岐なし)を書き込み、IRQを無効化した状態でPCを直接そこへ書き込んで実行し、`total_ticks`の(1)線形性・再現性、(2)MCP往復頻度への感度を検証。結果: n=50/100/200/388全てでticks/nop比が9.06付近で安定(線形)、同一Nの3回反復で完全一致(決定論的)、**単発continue(1往復) vs 分割continue(388往復、最大1552往復まで反復)で結果が完全一致(inflation比1.000)**。すなわちtotal_ticksそのものはMCP往復回数・経過real時間に一切影響されない、信頼できるCPUサイクル比例カウンタであることを確認(evidence: `evidence/APS-049/cadence-tick-calibration.json`)。※Timer2 VBLANK IRQとdisplay_requestの周期比較(1:3、想定と不一致)も同ファイルに記録したが解釈が未確定のため合否判定には使っていない。
- **APS-051で撤回**: 上記の低頻度再測定と「敵ゼロでも実性能バグなし」という結論は、要求フレーム数の実行を保証しないbulk frame-stepに依存していたため、契約gの根拠として無効化。APS-051の連続display request間隔測定で、現行未最適化ROMが全fixtureで1.05 VBlank契約にFAILすることを再確認した。APS-049の履歴証跡は改変せず、正しい現行判定は`evidence/APS-051/frame-cadence-gearlynx.json`を参照する。
- **boss 2x実測ゲート(v003)**: boss 2x描画を実際に有効化した状態(`src/main.c`の`draw_sprite`が`GAME_SPRITE_CORAL_BASTION`〜`GAME_SPRITE_VIOLET_GEODE`で`scale=2`を適用)で`make verify`によるclean ROM再生成後、低頻度方式で0/4/8 normal・boss+4normalを再測定。**全fixture PASS**、最重量ケース(boss+4normal, phase=boss)でも37.683us/13,333.333us予算(0.28%)と潤沢な余裕。evidence: `evidence/APS-049/frame-cadence-gearlynx.json`。この実測を根拠にboss 2xを採用しコード化した(`src/main.c`・`scripts/generate-stage-data.py`のコメントも実測値を明記するよう更新)。
- **新規発見: boss 2x採用時の画面端クリッピング(v003、未解決・ユーザー判断待ち)**: 契約f実装中に、2xスケール後のboss visual(32x32)がboss停止位置(`bosses[].stop_x`)+anchorで配置されると、**coral_bastion(stage1)とviolet_geode(stage3)で右端3列が画面幅160pxを超えクリップされる**ことが判明(`amber_carrier`(stage2)は160pxちょうどに収まりクリップ0)。実測: `stop_x=132, anchor_dx=-1` → 描画原点131、幅32 → 右端163(160を3超過)。`draw_clipped_hline()`は超過分を静かに切り捨てる仕様(x1を159へクランプ)ため、クラッシュや検証エラーにはならず**視覚的にボスの右側約1割が見えないまま**になる。1xスケール時は同じ停止位置でも右端154(クリップなし)だったため、**2x採用によって新たに生じた事象**であり、契約g(タイミングのみ検証)では検出できない種類の不具合。v001/v002の採用判定基準(13.3ms予算)はクリアしているが、この画面端クリッピングは基準に含まれていなかった新事実のため、Devの判断だけで採用/フォールバックを決めず、ここで止めてユーザー判断を仰ぐ(詳細は下記「次にすべきこと」)。evidence: `evidence/APS-049/coral-bastion.png`・`evidence/APS-049/violet-geode.png`(右端が黒塗りで欠けた状態のnative capture)、`evidence/APS-049/runtime-sprite-gearlynx.json`の`individual_sprite_sha256.coral_bastion/violet_geode.clipped_columns=3`。

- ROM/RAM(v003最終ビルド): `GAME_VERSION_STRING=0.49.0`。`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx` 60,078 bytes、SHA-256 `36382798f4c289e76e42f1ed3bd4e53927a6da64946491a2277fa361ef225992`。BSS残余150 bytes(`build/asteroid-patrol.map`実測、受入条件`≥11 bytes`クリア)。`make clean && make verify`(host test 611+351+14949+1647 checks・lint・rom・inspect)、`make smoke-host`(19 checks)、`make perf-host`、`python3 -m py_compile`、`git diff --check`全成功。

#### 残作業

- **boss 2x採用可否の最終判断**(下記「次にすべきこと」参照、ブロッキング)。
- `README.md`/`docs/plan/design.md`へのAPS-049反映(未着手、`ISSUES.md`のみ先行記録)。boss 2x採用可否のユーザー判断確定後にまとめて反映する。

#### 次にすべきこと(ユーザー判断が必要な事項)

1. **boss 2x採用可否の最終判断**: 契約g(タイミング)はPASSしたが、上記の画面端クリッピング(coral_bastion/violet_geode右端3px)をどう扱うか判断をお願いしたい。選択肢:
   - (a) 3px程度は許容範囲としてboss 2xをそのまま採用する(現在のコード状態)。
   - (b) v001記載のfallbackどおり**全boss**を1x等倍+collision中心整列に戻す(クリップなし、ただし迫力は元のAPS-047水準に戻る)。
   - (c) クリップする2種(coral_bastion/violet_geode)だけ1xへ個別fallbackし、amber_carrierのみ2x採用する(見た目の統一感は失われるが実装は比較的小さい)。
   - (d) stop_x自体を左へ調整してクリップを解消する(ただしstop_xはboss script/難度に関わるゲームルールで、v001の「触ってはいけない範囲」に該当するため、変更するならユーザーの明示承認が必要)。
2. 上記が確定次第、必要な追加実装(fallback適用・再ビルド・再テスト)とISSUES.md/README.md/docs/plan/design.mdへの反映を行う。

### APS-047: 重み付き容量・75 Hz cadence不具合・runtime sprite実証

- 状態: 実装・host/ROM/Gearlynx cadence/visual headless/GUI・title/GAME OVER/A/C/B回帰・証跡完了（Dev、2026-08-10。Atari Lynx実機・コミット・pushなし）。
- 重み付き容量: 公開定数normal=1、boss=4、limit=8。通常敵は`active && x<160`、bossはactiveだけを算入し、4 normal+boss=8と8 normalを受理、5 normal+boss=9、8 normal+boss=12、9 normalを拒否。player、弾、environment、画面外pre-spawnは非算入。JSON/generator/generated header/runtime/host/Gearlynxを同じ式へ統一し、既存Stageの4枠・難度・spawn/respawn/boss scriptは不変。
- cadence: APS-046の製品frame終端busy-waitを撤去。前回VBLANK swap pending中にinput 1→logic 4→sound 1を処理し、back buffer再利用直前のみprevious display completionを同期してdraw 1→display request 1。`tgi_setframerate(75u)`だけをhardware presentation源とし、delay・skip・敵数別更新数なし。Gearlynx headless/GUIで0/4/8 normalと4 normal+bossを各75 draw、coexist fixtureのBOSSを追加75 draw測定し、各runのinput/logic/sound/sync/request=75/300/75/75/75、player +8、bullet +16、normal -4、boss +2、boss attack timer +4を直接breakpoint/readbackで確認。MCP wall-clockはadvisory。
- runtime sprite: 全13種26 frameをAPS-044 previewの部位/配色に基づき既存canvasへ手作業再authoring。playerのnose/canopy/delta wing/keel/notch/engine flareと敵/boss固有部位を固定し、旧stripe/mapping swap mutationを拒否。274/524 runsを3 bytes/runへpackし、共通`game_sprite_visit_runs()`をhostと製品rendererで共有。最終ROMのrun 822 bytes、definition 104 bytes、enemy mapping 1..9、boss mapping 255/10/11/12をJSON canonicalと照合。GearlynxではTITLE実入力→Stage 1 NORMALの実プレイ、Stage 1〜3 NORMAL/CAST/BOSS、全13個別spriteをGameState/palette/framebuffer pixelと照合し、headless/GUI対応PNG byte一致。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 51、game 611、sound 351、IMA 14,949、sprite 1,055、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain/cart/LNX成功。ASan/UBSan付きgame 611/sound 351/IMA 14,949/sprite 1,055/smoke 19、`make smoke-host` 19、`make perf-host`、5 Python verifierの`py_compile`、`git diff --check`成功。perf syncは75 draw/300 logic/75 sound、298.77 Hz、game speed x1.00。
- audio回帰: title 17,408、GAME OVER 11,691のTimer 3 IRQ/DAC sample完全一致、underrun 0、title 38→0 waitと両入力gate成功。A/C/Bは8/20/8秒で6/3/6 pitch変化、全logical volume→75% MIKEY gain一致。audio/voice asset、Timer、開始後38 tick、cart payload不変。
- ROM/RAM: `GAME_VERSION_STRING=0.47.0`。`/Users/mammycloud-m4/Documents/develop-m4/atari-lynx-shooter/dist/asteroid-patrol.lnx` 59,530 bytes、SHA-256 `06266e561dbd896a6c8db749d6d06a552e374b078d4fe56fc9b39812eaea712b`。CODE `0x94D4`、RODATA `0x17F1`、DATA `0x134`、BSS `0xB091..0xB57D`=`0x4ED`、MAIN最終used `0xB57E`、C stack開始`0xB838`、残余698 bytes。APS-046比BSS不変、MAIN -2 bytes、stack +2 bytes。sprite RODATA `0x3AB`、run 274。title/game-over cart payload hash不変。
- 差分/未確認: ブリーフ差分なし。collision、anchor、2 frame、palette role、移動、ゲームルール、stage、boss、音声、dynamic allocation不変。Atari Lynx実機の75 Hz持続、8 weighted時cycle margin、LCD判読性/残像、Lynx I/II差、実機speaker音量/音質、IRQ margin、長時間playthrough未確認。commit/push/stash/reset/checkout、BIOS・外部ROM/素材操作なし。詳細は`evidence/APS-047/README.md`。

### APS-046: 8体基準75 Hz frame pacing・同時combatant上限8

- 状態: 実装・host/ROM/Gearlynx pacing・visual headless/GUI各連続2回・title/GAME OVER/A/C/B回帰・証跡完了（Dev、2026-08-10。Atari Lynx実機・コミット・pushなし）。
- capacity/count: `GAME_MAX_ENEMIES=8`をtrue runtime capacity、`GAME_STAGE_ACTIVE_ENEMIES=4`を既存Stageの初期/respawn数と分離。NORMALは`active && x<160`の通常敵、BOSSはactive bossをcombatantとして数え、通常敵+bossを常に8以下へ制限。host/Gearlynx注入は0/1/4/8、7+bossを受理し、8+boss=9を拒否。player、弾、環境物、画面外pre-spawnは非算入。追加4枠の撃破時はscore/drop後にinactive化し、既存4枠の決定的respawn/移動/攻撃/drop/scoreは維持。
- stage contract: `assets/stages/stages.json`へ`combatant_limit=8`と各Stageの`boss_coexists_with_normal_enemies=false`を固定。generatorは上限8、既存formation 4枠、boss非共存を検証し、limit 9/boss共存/9 active slot mutationを全拒否。生成headerへ`GAME_STAGE_COMBATANT_LIMIT=8u`を出力し、stage behavior golden v034は不変。
- pacing: 初期化の`tgi_setframerate(75u)`を唯一のtiming sourceとして維持し、明示`GAME_FRAME_END_WAIT(tgi_busy())`をdraw/voice処理後のframe終端へ配置。0〜8体の余剰時間はhardware waitへ吸収し、overrun時はwaitが即完了するだけでlogic/input/soundをskipしない。host instrumentationは0/4/8体のwait到達、underbudget wait、overrun即完了、75 draw/300 logic/75 soundを検査。
- Gearlynx pacing: 0/4/8 injected activeを各75 hardware frame、`tgi_busy()`完了直後の`_game_frame_end_complete` breakpointで連続確認し、活動数readbackは各々0/4/8で固定。Timer 0はenabled/reload・1 MHz、Timer 2 VBLANKはenabled/reload/linked/interrupt、9体注入は未書込で拒否。MCP debuggerのframeごとのread/write往復を含むwall値はmedian 210,860/250,288/295,043 usで12,000〜15,000 us窓外のためadvisoryに不採用し、ブリーフどおりhardware completionを合否正本とした。JSONは`evidence/APS-046/frame-pacing-gearlynx.json`。
- RAM packing: ROMでは8敵を独立静的`game_enemies[8]`へ置き、`GameState`はpointerを保持。固定寸法のenemy bullet/power/asteroid/rockを`GamePosition`へpackingし、enemyのstage dataから導出可能なfire interval/drop flagを除去。動的確保・bullet/weapon capacity削減なし。hostは互換的な分割inline backingと`game_enemy_at()`を使い全8枠をinstrument可能。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 44、game 609、sound 351、IMA 14,949、sprite 770、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain/cart/LNX成功。ASan/UBSan付きgame 609/sound 351/IMA 14,949/sprite 770/smoke 19、`make smoke-host` 19、`make perf-host`、5 Python verifierの`py_compile`、`git diff --check`成功。perf syncは75 draw/300 logic/75 sound、299.64 Hz、game speed x1.00。
- Gearlynx visual/audio: Stage 1〜3 NORMAL/CAST/BOSSのheadless/GUIを各連続2回成功し、対応PNG byte一致、全13 sprite/full-screen hashはAPS-045と一致。title 17,408、GAME OVER 11,691のIRQ/DAC完全一致・underrun 0・gate成功。A/C/Bは8/20/8秒で6/3/6 pitch変化、全logical volume→75% MIKEY gain一致。証跡とhashは`evidence/APS-046/README.md`。
- ROM/RAM: `GAME_VERSION_STRING=0.46.0`。`dist/asteroid-patrol.lnx` 59,532 bytes（APS-045比-685）、SHA-256 `6d5c2a5e67da94fa4eba9b2164a2859ceee7a33d212e6d0f9c19eec0bf91c721`。CODE `0x93A7`、RODATA `0x1923`、DATA `0x131`、BSS `0xB093..0xB57F`=`0x4ED`、MAIN最終used `0xB580`、C stack開始`0xB838`、残余696 bytes。全値がbaseline BSS `0x4ED`/MAIN `0xB82D`/残余11以上。sprite RODATA `0x4DD`、title/game-over asset hash、run 282は不変。
- 差分/未確認: ブリーフ差分なし。許可されたcapacity/pacing/state packing/stage契約/host・Gearlynx verifier/version/docs/evidenceだけを変更。Atari Lynx実機の13.333 ms持続、8体時frame overrun margin、LCD、Lynx I/II差、実機speaker音量/音質、IRQ cycle margin、長時間playthroughは未確認。commit/push/stash/reset/checkout、BIOS・外部ROM/素材操作なし。

### APS-045: APS-044 A案・敵9種・boss3種のruntime canvas反映

- 状態: 実装・host/ROM/Gearlynx visual headless/GUI各連続2回・title/GAME OVER/A/C/B回帰・証跡完了（Dev、2026-08-10。Atari Lynx実機・コミット・pushなし）。
- 正本/実装: `assets/previews/aps044-player-preview.json`のA案と`aps044-enemy-preview.json`の12体を概念・配色・部位分離の正本とし、縮小変換・外部素材・AI生成画像なしで`assets/stages/stages.json`の既存canvasへ手作業再authoring。playerはdelta wing/nose/canopy/keel/left engine、normalはsensor wedge、offset dome/rim、claw/pod、bank wing/nose、armored bay、cargo/lock、split wing、segmented drill、asymmetric chassis、bossはspires/turret/reactor、bridge/nacelle/engine、facet/nucleus/fissureを固定。各2frameで部位を1px移動または左右反転。
- canvas/collision/role不変: player `12x10 / 8x6`、通常敵9種`12x12 / 8x8`、boss `24x16 / 24x16`・`28x14 / 28x14`・`24x24 / 24x24`、左上anchor、既存role集合不変。AABB、移動、spawn、発射、難度、stage/boss config/script、state、runtime renderer、sound/voice/cart、`src/`、`include/game.h`はAPS-045で変更なし。
- cell/role: player 50/50 (`7=5/5 8=37/36 9=8/9`)、scout 49/49、saucer 51/51、dropper 50/50、fighter 48/48、bomber 64/64、supply 48/48、cave_bat 54/54、rock_worm 52/52、mining_drone 52/52、coral 149/149、amber 145/145、violet 148/146。全frame 3〜4 role、複数row span、切欠きまたは分割部位、上下/左右非対称、frame差を保持。詳細role cells/識別部位は`docs/plan/design.md` APS-045表。
- run/canonical: run列`7/7,10/10,9/9,12/12,9/9,10/10,10/10,9/9,8/8,8/8,15/15,14/14,20/20`、合計282を固定。`tests/golden/sprite-data-v045.json` snapshot SHA-256 `0656310e1b41f06c1b6a3ec22d1f07a98cf20bac4da2deed50030ec937963481`。generatorは全pixel goldenに加え、13 ID別のnose/canopy/engine/keel、sensor/wedge、dome/rim、claw/port、wing/nozzle、armor/bay、cargo/lock、split wing/eye、segment/drill、boss主要部位をframe別座標で検査し、feature shift negative mutationを拒否。Stage golden v034と旧v043 goldenは履歴として不変。
- 自動検証: 最終ツリーの`make clean && ./scripts/verify.sh`終了コード0。stage 40、game 583、sound 351、IMA 14,949、sprite 770、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain、3-entry cart、LNX成功。ASan/UBSan付きgame 583/sound 351/IMA 14,949/sprite 770/smoke 10、`make smoke-host` 10、`python3 -m py_compile scripts/generate-stage-data.py scripts/verify-stage-visuals-gearlynx.py`、`git diff --check`成功。
- 性能: `make perf-host`成功。75 draw/300 logic/75 soundのsync 298.82 Hz、game speed x1.00。500万draw paired medianはlegacy 1,557,021 us、optimized 1,547,751 us、delta 11,098 us。runtime描画/logicとrun総数282不変のため描画call予算55/27を維持。
- Gearlynx visual: headless/GUIを各連続2回成功。Stage 1〜3 NORMAL/CAST/BOSS、hardware palette、boss active、collision、全13 individual spriteのauthoring grid対全非空pixel照合を実施し、対応22 PNGのheadless/GUI byte一致を確認。初回GUIでvalid GameStateに対しstale front bufferを撮る同期不足を検出したため、verifierだけをpost-logic/pre-draw sound→next logicの完全handoff 2回へ修正し、最終4走で再確認。hash/制約は`evidence/APS-045/README.md`。
- Gearlynx音声: title 17,408 IRQ/DAC完全一致、underrun 0、停止zero、wait `38..0`の38 transition後Stage 1/channel A開始。GAME OVER 11,691 IRQ/DAC完全一致、underrun 0、A/C/B停止、release→press TITLE、held 8 poll安定。A/C/Bは8/20/8秒で6/3/6 pitch変化、logical volume→75% MIKEY gain全一致。
- ROM/RAM: baselineはLNX 60,217 bytes、sprite RODATA 1,245 bytes、282 runs、BSS 1,261 bytes、MAIN最終`0xB82D`、stack`0xB838`/残余11 bytes。最終`GAME_VERSION_STRING=0.45.0`、`dist/asteroid-patrol.lnx` 60,217 bytes（±0）、SHA-256 `c0fae56ce368e17a162695045f50a1f6415c59e2c2e4523ddcfa3ed3dc71cd39`。sprite RODATA `0x4DD`、BSS `0xB340..0xB82C`=`0x4ED`、MAIN/stack/残余、title cart offset 45,603/8,704/hash `99eb68...`、GAME OVER offset 54,307/5,846/hash `848691...`全てbaseline不変。
- 差分/未確認: ブリーフ差分なし。変更は許可範囲のsprite 13 frame pair、host contract/test/golden参照、visual verifier、version、README/design/ISSUES/evidence。Atari Lynx実機LCDの原寸判読性/残像、Lynx I/II差、実機speaker音量/音質、IRQ cycle margin、長時間playthrough未確認。commit/push/stash/reset/checkout、BIOS・外部ROM/素材操作なし。

### APS-044: ゲーム資産を変更しない自機16x16単体A/Bプレビュー

- v004状態/原因: v003のplayer generator所有範囲修正でsource SHA-256が変わる一方、sheet generatorが旧source SHA-256を固定検証していた相互依存を解消。player `--check`は共有directoryの他所有者3 sheetとsheet所有READMEを許容し、明示8 player PNGだけの存在・全pixel・SHA-256・独立再生成byte一致を検証する。sheet generator側の変更はplayer source固定値1箇所だけ。
- v004 source SHA-256: `scripts/generate-aps044-player-preview.py`=`6209bc1e86e725232613c8b2b6dcb905dc3b5390bc9a437ce40f1e106ecab45b`、`scripts/generate-aps044-character-sheets.py`=`6e7a4c0c0493d5ff6c86475dfbd3ed20f1ad82c4da84161ec5619d145fca40e4`。依存方向はsheet generator→player generatorの固定hash検証だけで、player側はsheet source/contentを参照しない。
- v004全11 PNG不変: `a-dark-8x.png`=`579e14a45713807261e025ae50b11e0008489a14fc61f0cd2a492aae68dcd9e1`、`a-dark.png`=`4dea3d93f42883368b6b1e28eaaba1e971906f2e0c669ccd0e4980c221b43926`、`a-transparent-8x.png`=`db9f98b72cb92c4622bcf9762d81d487001a84d6e8a9e40367b4d7720f37881d`、`a-transparent.png`=`429bd28826eab556f03f5e2e2263a1d3f1f89551169189f63d61ad35a86dbc01`、`b-dark-8x.png`=`6d31169b439aa5104655d72adf6608e3d9b39709e06c59ba0defb7f4d0daa613`、`b-dark.png`=`d37ca7ad659673ac0faa6469b9c58b28a5c4eceb050a21b8b4ab30db37ace7e5`、`b-transparent-8x.png`=`e06db89085ec0656ee065e1e98ae21ebbd4c6aca58f71fc8e1a9002830d7b078`、`b-transparent.png`=`89cd83951a3b9428db061a8a9ba740bcb401eec29c734219ccf040a5ff4a3523`、`normal-enemies-sheet.png`=`59ebddfaa534a8ea527d0f7a6864ac27da9f7d8758b40c648bf03ffc359dd01c`、`bosses-sheet.png`=`a5273b14231c43c3b0b239b256e2ec88c57c97b8116649dbfa341e3642fff66d`、`all-characters-sheet.png`=`c83f80e8b57052816ae7bb46a2a057b4eb9f81acc454845938798ff21326866b`。artifact名集合も8 player+3 sheetから不変。
- v002状態: 敵9種・boss3種の独立16x16 fixed-grid、label付き3 sheet、host validator、独立再生成byte一致、文書化完了（Dev、2026-08-10）。v001自機A/Bとゲーム資産は不変。人間の採用判断待ち。
- v002正本/生成: `assets/previews/aps044-enemy-preview.json`へ通常敵`scout,saucer,dropper,fighter,bomber,supply,cave_bat,rock_worm,mining_drone`とboss`coral_bastion,amber_carrier,violet_geode`を各16x16・単一frameで手作業固定。`scripts/generate-aps044-character-sheets.py`はPython標準libraryとlocked v001 generatorのPNG codec/raster helperだけを使い、`assets/stages/stages.json`を読まず、ゲームgrid・外部素材・生成画像を流用しない。
- v002 cells/role: scout 73=`A40/B30/C3`、saucer 65=`A28/B27/C10`、dropper 65=`A29/B33/C3`、fighter 68=`A39/B27/C2`、bomber 92=`A47/B41/C4`、supply 69=`A32/B34/C3`、cave_bat 53=`B23/D22/E8`、rock_worm 47=`B24/D11/E12`、mining_drone 66=`B30/D27/E9`、coral_bastion 135=`A75/B48/C8/F4`、amber_carrier 85=`A43/B36/C4/F2`、violet_geode 98=`B28/D46/E16/F8`。grid名は全て`aps044_<id>_preview`。
- v002 silhouette/部位/陰影: scout=sensor wedge/sensor/B shadow、saucer=offset dome/rim/下側shadow、dropper=claw/cargo pod/C投下口、fighter=bank wing/long nose/nozzle keel、bomber=armored pod/bomb bay/段差shadow、supply=cargo frame/C lock/asymmetric antenna、cave_bat=swept split wing/D membrane/E eye、rock_worm=segmented drill/B seam/E facet、mining_drone=asymmetric drill chassis/E core/右drill、coral_bastion=spires/turret/C reactor/F slit/下砲郭shadow、amber_carrier=bridge/nacelle/C engine/段差hull、violet_geode=offset facet/F nucleus/E fissure/B shadow。
- v002 sheet/位置: `normal-enemies-sheet.png`は432x456・3x3でrow-majorにscout/saucer/dropper、fighter/bomber/supply、cave_bat/rock_worm/mining_drone。`bosses-sheet.png`は432x152・横3体でcoral/amber/violet。`all-characters-sheet.png`は576x608・4x4でrow 0=`player_a,player_b,scout,saucer`、row 1=`dropper,fighter,bomber,supply`、row 2=`cave_bat,rock_worm,mining_drone,coral_bastion`、row 3=`amber_carrier,violet_geode`（残り2 cellは背景）。tile内spriteは128x128 (`x/y=8`)、labelはbitmap 3x5の2倍・`y=138..147`で非重複。
- v002 host検証: strict JSON、12 ID/順序/grid名/category/16x16、palette role 3〜4、同色run<12、bbox fill<=85%、row span>=3、taper/cutout、上下非対称、単一8-connected foreground、散点noise上限、全周2px outline禁止、ID別feature座標、grid一意性を検査。8 negative mutationを全拒否。sheetは全pixel、8x block、label bitmap/領域、3x3/3横/14体、寸法、SHA-256、独立temporary directory再生成byte一致を検査。正確な全metrics/配置/hashは`evidence/APS-044/README.md`。
- v002 sheet SHA-256: `normal-enemies-sheet.png`=`59ebddfaa534a8ea527d0f7a6864ac27da9f7d8758b40c648bf03ffc359dd01c`、`bosses-sheet.png`=`a5273b14231c43c3b0b239b256e2ec88c57c97b8116649dbfa341e3642fff66d`、`all-characters-sheet.png`=`c83f80e8b57052816ae7bb46a2a057b4eb9f81acc454845938798ff21326866b`。3枚を目視し、sprite/label分離と14体比較構成を確認。
- v002保全/未確認: locked v001 player JSON/generator/8 PNGを固定SHA-256と全pixelで再検証しbyte不変。`assets/stages/stages.json`、`src/`、`include/`、Makefile、tests/golden、ROM/LNX/versionはv002で変更なし。未確認は人間による原寸16x16判読性・採用判断、Atari Lynx実機LCD/残像、採用後12x10 runtime再設計・run予算・2frame化。commit/push/stash/reset/checkoutなし。
- 状態: preview正本・PNG 8枚・標準library generator/validator・再生成byte一致・文書化完了。A/B採用判断待ち（Dev、2026-08-10。ゲーム反映・ROM/LNX・Gearlynx・コミット・pushなし）。
- 分離: `assets/previews/aps044-player-preview.json`を新規の唯一のpreview正本とし、A=`delta-wing`、B=`twin-boom-heavy`を各16x16・右向き・単一frameで固定。`9=#334488`、`8=#FF6644`、`7=#99FFEE`、`C=#FFDD55`だけを使用。外部素材・生成画像・既存sprite流用なし。PNGは自機pixelと指定backgroundだけで、文字・枠・UI・ゲーム画面を含まない。
- A grid/評価: 94 cells（`9=32/8=54/7=6/C=2`）、bbox 16x11、fill 53.4%、44 run、row span 3/5/8/10/13、右端3列4/2/1。幅広delta主翼、1px nose、3x2 canopy、左端1x2 flare、keel/notchを分離。透明/暗色原寸で細い機首とcanopyを識別点とする。12x10直接縮約概算58〜62 cells/27〜31 runで、runtime player上限16へは採用後の再authoringが必要。既存fighterの単胴bank翼・`A/B/C`敵paletteに対し、player palette、幅広delta、下側keel、左engineで差別化。
- B grid/評価: 100 cells（`9=41/8=51/7=4/C=4`）、bbox 16x12、fill 52.1%、49 run、row span 1/3/6/7/9/10/11/12/14、右端3列5/2/1。上下非対称twin-boom、1px nose、2x2 canopy/flare、中央gap、下側垂直尾翼を分離。12x10直接縮約概算62〜66 cells/30〜35 runで同じく別authoringが必要。既存fighterにないtwin-boom・重装量感・2x2 engineで差別化。
- 生成物: `evidence/APS-044/`へ`a|b`×`transparent|dark`×`16x16|8x(128x128)`のPNG 8枚とhash/metric manifestを出力。darkはexact `#111122`、拡大は各source pixelを8x8 blockへ複製するnearest-neighbor。SHA-256は`a-dark-8x=579e14a4...`、`a-dark=4dea3d93...`、`a-transparent-8x=db9f98b7...`、`a-transparent=429bd288...`、`b-dark-8x=6d31169b...`、`b-dark=d37ca7ad...`、`b-transparent-8x=e06db890...`、`b-transparent=89cd8395...`（完全値はevidence README）。
- host検証: `scripts/generate-aps044-player-preview.py`がstrict JSON、16x16、固定palette/4 role、bbox/margin、8 hull run<=6、全role run<12、9の2px厚band禁止、fill<=85%、row span>=3、非primitive/上下非対称/単一8-connected silhouette、C flare、7 canopy、右端taper、9 nose、tail notch、上縁outline、5部位を検査。PNG encoder/decoderも標準libraryのみでRGBA/dimension/chunk CRC/filter/pixel/background/8x blockを検査し、独立temporary directoryの再生成8枚とbyte一致を確認。
- 自動検証: `python3 scripts/generate-aps044-player-preview.py`、同`--check`、`python3 -m py_compile scripts/generate-aps044-player-preview.py`成功。in-memory mutationによるcanvas/palette/hull run/nose role/canopy/background/scale/invalid cellのnegative 8件も全拒否。`python3 scripts/generate-stage-data.py validate --golden tests/golden/stage-data-v034.json --sprite-golden tests/golden/sprite-data-v043.json`成功。`git diff --check`成功。
- ゲーム資産不変: `assets/stages/stages.json`はSHA-256 `40f976cd6d691bf0eb40ff22f0fd99889c3948613d4152389c11ef17f9a45906`・mtime `2026-08-09T21:22:30+0900`、`include/version.h`はSHA-256 `4abc091559c43b8a7c7b4abe6c43647a6d0f6b4e85921fc2cb6d7b47ddb5dcb2`・mtime `2026-08-09T21:13:01+0900`のAPS-044着手前状態を維持。APS-044の変更はpreview JSON/script/evidenceと本項/designだけ。`src/`、`include/`、Makefile、tests/golden、Stage/formation/boss/environment/palette、runtime/collision/input/difficulty/sound/voice/cart/cfg、APS-041〜043 evidence/briefを変更していない。
- 設計差分/未確認: ブリーフ差分なし。16x16/128x128 PNGの機械的pixel判定まで完了。人間による16x16原寸の判読性、A/B選択、Atari Lynx実機LCD/残像、採用案の12x10再設計・run予算・2frame化は未確認かつゲーム反映前の別工程。`make`、ROM、LNX、Gearlynx、version更新を意図どおり実行せず、commit/push/stash/reset/checkoutなし。

### APS-043: 密度ある手作業1px dot art・全自動visual検証

- 状態: 実装・全自動検証・Gearlynx headless/GUI各連続2回・title/GAME OVER/A/C/B回帰完了（Dev、2026-08-09。Atari Lynx実機・コミット・pushなし）
- fixed dot art: `assets/stages/stages.json`を唯一の正本として全13種2frameを再設計。単色外周や空白依存を避け、各行の色遷移をB/A/B外殻、B/D/E鉱物節、B/D/E/F/E/D/B nucleus等へ手作業で割り当てた。visual/collisionはplayer 12x10/8x6、通常敵12x12/8x8、boss 24x16・28x14・24x24/同寸法、左上anchorのまま。AABB、移動、spawn、発射、難易度、drop、boss config/script、背景、敵弾、音声、runtime C/assembly/renderer/GameStateは不変。
- cell/構造: 各frameの着色cellはplayer 55/55、scout 49/49、saucer 50/50、dropper 50/50、fighter 50/50、bomber 64/68、supply 49/49、cave_bat 48/48、rock_worm 55/55、mining_drone 52/52、coral_bastion 134/134、amber_carrier 154/154、violet_geode 144/144。全frameが固定3〜4 roleでoutline/shadow、主面、highlight/発光部、2frame差を持つ。visual/collision、silhouette、左scroll識別意図は`docs/plan/design.md`のAPS-043表へ全種記録。
- run/容量: 26 frameのrun列`7/7,10/10,9/9,12/12,9/9,10/10,10/10,9/9,8/8,8/8,15/15,14/14,20/20`、合計282をAPS-042から厳密維持。authoring実値の通常画面worst-case 55、boss 27 draw call/draw、class上限16/18/28、総予算524も不変。`sprite_data.o` RODATA `0x4DD`（1,245 bytes）。
- canonical/host回帰: `tests/golden/sprite-data-v043.json`のsprites-only canonical SHA-256 `4f29fec62a49034d0003a1437d9bcdc6d76c9e19f01156b8622051f6a0d3dcc1`を固定。generator/C testは13 ID、visual/collision、exact run列/合計282、sprite別cell下限、3〜4 role、canvas内run、2frame差、dense offsetを検査し、低密度playerを拒否するnegative回帰を追加。Stage挙動golden `stage-data-v034.json`は不変。
- 自動検証: 最終ツリーで`make clean && ./scripts/verify.sh`終了コード0。stage 39、game 583、sound 351、IMA 14,949、sprite 770 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain strict verify、3-entry cart、LNX成功。ASan/UBSan付きgame 583/sound 351/IMA 14,949/sprite 770/smoke 10、`make smoke-host` 10、`python3 -m py_compile`（stage generator/visual/title verifier）、`git diff --check`成功。
- 性能: `make perf-host`成功。75 draw/300 logic/75 soundの`--sync`は298.80 Hz、game speed x1.00。500万draw比較はlegacy median 1,590,680 us、optimized median 1,574,649 us、paired delta median 23,485 us。runtime描画関数・logic/stateを変更せず、run総数282のためAPS-042描画負荷を維持。
- Gearlynx visual: `scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-043`と`--gui --output-dir evidence/APS-043/gui`を各連続2回成功。Stage 1〜3 NORMAL/CAST/BOSS、hardware palette、boss active、double-buffer同期、collision readbackを確認。全13 spriteをauthoring grid/hardware paletteと全非空pixel単位で照合し、個別13 PNGとfull-screen 9 PNGを各modeへ保存。GUI/headlessの対応22 PNGはbyte一致。全hashとrender injection制約は`evidence/APS-043/README.md`へ記録。
- Gearlynx音声回帰: titleはTimer 3 IRQ/DAC 17,408 sample完全一致、underrun 0、停止zero、`38..0`の38 transition後Stage 1/BGM開始。GAME OVERは11,691 sample完全一致、underrun 0、A/C/B停止、release→press TITLE復帰、held press 8 poll安定。channel A/C/Bは8/20/8秒で6/3/6 pitch変化、全てlogical volume→75% MIKEY gain一致。
- ROM/RAM: `GAME_VERSION_STRING=0.43.0`。LNX 60,217 bytes（APS-042比±0）、SHA-256 `4928ae53c81793b383a294e452d8cf126bb0e68810d3c8f1ebbabc5ead031f76`。CODE 38,484 bytes、RODATA 6,435 bytes、DATA 305 bytes、BSS `0xB340..0xB82C`（1,261 bytes）、MAIN最終使用`0xB82D`/上限`0xB837`、C stack開始`0xB838`、残余11 bytes。title cart offset 45,603/8,704 bytes/hash `99eb68...`、GAME OVER cart offset 54,307/5,846 bytes/hash `848691...`でpayload/hash不変。
- 差分/未確認: APS-043変更はsprite grid、host generator/test/golden、visual verifier/evidence、version、README/design/ISSUES、briefと、完了条件のv043 golden参照置換に必要なMakefile 1行に限定。APS-041のruntime/title待機成果とAPS-042のvisual/collision分離・検証器成果を保全し、`src/`・`include/game.h`への追加変更なし。Atari Lynx実機LCDの視認性・残像・Lynx I/II差、実機音量/clip/IRQ負荷/DAC音質、長時間反復は未確認。commit/push/stash/reset/checkout、BIOS・外部ROM・外部素材の取得/読取/生成なし。

### APS-042: 固定sprite高解像度化・全自動visual検証

- 状態: 実装・全自動検証・Gearlynx headless/GUI各連続2回・title/GAME OVER/A/C/B回帰完了（Dev、2026-08-09。Atari Lynx実機・コミット・pushなし）
- visual/collision分離: 固定horizontal-run RLEと`draw_sprite()`を変更せず、`assets/stages/stages.json`の自機visual canvasを8x6→12x10、通常敵9種を8x8→12x12へ拡大。既存`GameRect.x/y`をvisual左上anchorとして追加pixelを右/下へ描く。collisionは`GAME_PLAYER_WIDTH/HEIGHT=8x6`、`GAME_ENEMY_WIDTH/HEIGHT=8x8`、boss 24x16/28x14/24x24のまま。AABB、移動、spawn、発射、難易度、drop、boss config/script、renderer、GameState/MAIN runtimeは変更なし。
- 固定grid: player/scout/saucer/dropper/fighter/bomber/supply/cave_bat/rock_worm/mining_drone/coral_bastion/amber_carrier/violet_geodeの全13種2frameを、既存3〜4 palette roleだけで再設計。暗いoutline、主色、canopy/visor/claw/pod/cargo/wing/segment/drill/reactor/bridge/nucleusの機能点とframe差を固定。設計意図は`docs/plan/design.md`のAPS-042表へ全種記録。
- run/容量: 26 frameの実run数は`7/7, 10/10, 9/9, 12/12, 9/9, 10/10, 10/10, 9/9, 8/8, 8/8, 15/15, 14/14, 20/20`、合計282でAPS-040/041基準と同一。class上限16/18/28、総予算524をhost generator/headerへ固定。authoring実値の通常画面worst-caseは7+4*12=55、bossは7+20=27 draw call/draw（予算88/44内）。最初の484-run案はlink時MAINを797 bytes超過したためruntimeを削らずgridだけを簡略化し、最終`sprite_data.o` RODATAを`0x4DD`（1,245 bytes）へ戻した。
- canonical/host回帰: 旧`sprite-data-v040.json`を`tests/golden/sprite-data-v042.json`へ置換し、sprites配列だけのcanonical SHA-256 `521ab2b281f37d54e1b59ae551b4d02e92025fec0e986ec02eafdfc223864faf`を固定。generator/testは13 ID、visual canvas、別契約のcollision寸法、class run上限、total budget、固定role、canvas内run、2frame差、dense offsetを検査。Stage挙動golden `stage-data-v034.json`は不変。
- 自動検証: 最終ツリーで`make clean && ./scripts/verify.sh`終了コード0。stage 38、game 583、sound 351、IMA 14,949、sprite 744 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain strict verify、3-entry cart、LNX成功。ASan/UBSan付きgame 583/sound 351/IMA 14,949/sprite 744/smoke 10、`make smoke-host` 10、`python3 -m py_compile`（stage generator/visual/title verifier）、`git diff --check`成功。
- 性能: `make perf-host`成功。75 draw/300 logic/75 soundの`--sync`は299.08 Hz、game speed x1.00。500万draw比較はlegacy median 1,554,745 us、optimized median 1,558,587 us、paired delta median -2,776 us。runtime描画関数・logic・stateを変更せず、authoring run総数も282のためAPS-041 runtime負荷を維持。
- Gearlynx visual: `scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-042`と`--gui --output-dir evidence/APS-042/gui`を各連続2回成功。Stage 1〜3 NORMAL/CAST/BOSS、hardware palette、boss active、double-buffer同期、collision readbackを確認。全13 spriteをauthoring grid/hardware paletteと非空pixel単位で照合し、個別13 PNGとfull-screen 9 PNGを各modeへ保存。GUI/headlessの対応22 PNGはbyte一致。全hashとrender injectionの制約は`evidence/APS-042/README.md`へ記録。
- Gearlynx音声回帰: titleはTimer 3 IRQ/DAC 17,408 sample完全一致、underrun 0、停止zero、`38..0`の38 transition後Stage 1/BGM開始。GAME OVERは11,691 sample完全一致、underrun 0、A/C/B停止、release→press TITLE復帰、held press 8 poll安定。channel A/C/Bは8/20/8秒で7/3/6 pitch変化、全てlogical volume→75% MIKEY gain一致。
- ROM/RAM: `GAME_VERSION_STRING=0.42.0`。LNX 60,217 bytes（APS-041比±0）、SHA-256 `42bbf19423b3a9c261e1c1ce6cf49cab142ea53acd3a5683204da7435c26d57c`。CODE 38,484 bytes、RODATA 6,435 bytes、DATA 305 bytes、BSS `0xB340..0xB82C`（1,261 bytes）、MAIN上限`0xB837`、C stack開始`0xB838`、残余11 bytes、sprite RODATA 1,245 bytesでAPS-041不変。title cart offset 45,603/8,704 bytes/hash `99eb68...`、GAME OVER cart offset 54,307/5,846 bytes/hash `848691...`でpayload/hash不変。
- 差分/未確認: APS-042変更はsprite grid、host generator/test/golden、visual verifier/evidence、version、README/design/ISSUES、briefに限定。APS-041未コミットの`include/game.h`/`src/game.c`/`src/main.c`/title verifier/game/smoke回帰を保全し追加変更なし。Atari Lynx実機LCDの視認性・残像・Lynx I/II差、実機音量/clip/IRQ負荷/DAC音質、長時間反復は未確認。commit/push/stash/reset/checkout、BIOS・外部ROM・外部素材の取得/読取/生成なし。

### APS-041: title voice完了後75Hz基準38 tick静止待機

- 状態: 実装・全自動検証・Gearlynx headless連続2回/GUI 1回を含む統合回帰完了（Dev、2026-08-09。Atari Lynx実機・コミット・pushなし）
- 待機仕様: 公開定数`GAME_TITLE_POST_VOICE_WAIT_TICKS=38`。0.5秒は75 Hz基準37.5 tickのため短縮せず`ceil(0.5 * 75)=38`へ切上げ、実時間`38/75=0.506666...`秒。`game_title_voice_complete()`は即時`game_start()`せず、既存1-byte gateの`title_voice_pending=2`をpost-voice wait状態、`title_start_armed=38`を残tickとしてTITLE内待機へ一度だけ移す。voice開始失敗時もmainの既存complete呼出しから同じ経路へ入る。
- 75 Hz経路: 300 Hzの`game_update_logic()`はwait状態を含む全nonzero pendingで即returnし、FIRE/方向、player/enemy/bullet/score/Stage timerを更新しない。main loopが4 logic update後にouter draw frameごと1回だけ呼ぶ既存`game_sound_tick()`で残数を1減算。最初の37回はTITLE・`phase_timer=0`・BGM停止、38回目だけ`game_start()`を一度呼び、同じ75 Hz sound tickでStage 1 INTRO/BGMを開始する。新規GameState field、BSS、動的確保、浮動小数なし。
- 容量対応: 最初の独立draw-frame API/16-bit counter案はlink時MAINを122 bytes超過、既存sound tick/1-byte gate統合案も初版は29 bytes超過。最終版はwait invariantに基づく1-byte pre-decrementへ縮小しlink成功。要求動作と公開38 tick定数を維持し、GameStateレイアウト/既存Gearlynx offset不変。最終stack残余11 bytesのため、後続runtime追加はMAIN容量見直しが必要。
- host回帰: game 583 checks、smoke 10 checks。voice完了直後の38、4 logic update×37 draw frame後の1、38回目だけのINTRO/BGM開始、待機中FIRE/方向・player位置・4 enemy・両bullet群・score・Stage timer・BGM停止、重複complete無効、GAME OVER→TITLE→voice→38 tick再開始を検査。voice開始失敗と同義の直接complete経路も同じ状態機械を使用。既存boot TITLE、GAME OVER、ALL CLEAR gate回帰成功。
- 自動検証: 最終ツリーで`make clean && ./scripts/verify.sh`終了コード0。stage 36、game 583、sound 351、IMA 14,949、sprite 738 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain strict verify、3-entry cart、LNX成功。ASan/UBSan付きgame 583/sound 351/IMA 14,949/sprite 738/smoke 10、`make smoke-host` 10、`make perf-host`、`python3 -m py_compile scripts/verify-title-voice-gearlynx.py`、`git diff --check`成功。
- 性能: `make perf-host`内の`--sync`計測は75 draw/300 logic/75 sound、298.47 Hz、game speed x0.99。500万draw比較はlegacy median 1,560,468 us、optimized median 1,559,638 us、paired delta median 17,240 us。wait処理は既存75 Hz sound tickに限定し、通常300 Hz logic/BGM4倍/sound tick数を変更しない。
- Gearlynx title: headlessを連続2回、同一経路のGUIを1回成功。各回Timer 3 IRQ 17,408、gain後DAC全17,408 sample一致、underrun 0、停止zero、`title_start_armed` write breakpointで`38,37,...,1,0`の全39値/38 transition、全wait write時TITLE・pending=2・BGM停止を確認し、その後Stage 1/BGM開始。headlessのtrace/breakpointは実時間進行を遅延させるためwall-clockを合否に使わず、75 Hz outer tickにだけ存在するcounter write回数を実ROM上の正本とした。
- Gearlynx回帰: GAME OVERは11,691 IRQ/DAC完全一致、underrun 0、A/BGM停止、完了前gate、release→press TITLE復帰、held press 8 poll安定。channel Aは8秒で7 pitch変化、Cは20秒で3、Bは8秒で6、全て75% logical→MIKEY gain一致。
- ROM/RAM: `GAME_VERSION_STRING=0.41.0`。LNX 60,217 bytes（APS-040比+91）、SHA-256 `5a513dbfeb41434397996952e39fd321015b318a974a72f85fc9a0bab4c20840`。CODE 38,484 bytes、RODATA 6,435 bytes、DATA 305 bytes、BSS `0xB340..0xB82C`（1,261 bytes）、C stack開始`0xB838`、残余11 bytes。sprite RODATA `0x4DD` 1,245 bytes不変。title cart offset 45,603/8,704 bytes/hash `99eb68...`、GAME OVER cart offset 54,307/5,846 bytes/hash `848691...`でpayload/hash不変。
- 差分/未確認: 変更はtitle post-voice状態機械、host/Gearlynx回帰、version、README/design/ISSUES、発行済みbrief v001に限定。sprite/stage authoring、当たり判定・移動・難易度・enemy/boss/bullet/background、sound table/MML、voice asset/metadata/gain/stream assembly、Timer 3、queue/IRQ/DAC、cart/cfgは変更なし。Atari Lynx実機の0.506667秒体感、LCD、音量、clip、IRQ負荷、DAC音質、Lynx I/II差、長時間反復は未確認。コミット、push、stash、reset、checkout、BIOS・外部ROM・外部素材の取得/読取/生成なし。

### APS-040: 固定spriteデータによるキャラクター表示詳細化

- 状態: 実装・全自動検証・通常敵9種を含むGearlynx headless/GUI各連続2回検証完了（Dev、2026-08-09。Atari Lynx実機・コミット・pushなし）
- sprite grid: `assets/stages/stages.json`の全13 sprite・2 frameだけを固定authoring dataとして再設計。自機は右向き機首/canopy/engine flare、Stage 1/2通常敵はscout sensor、saucer rim/beacon、dropper claw/core、fighter bank、bomber pod/bay、supply container、Stage 3通常敵はbat wing stroke、worm節、mining drill/core、bossはcoral reactor/command slit、amber carrier bridge/nacelle、violet geode facet/nucleusをrole固定色と輪郭差で表現。sprite ID/順序/kind/寸法（8x6、8x8、24x16、28x14、24x24）、2 frame、collision rectangle、enemy/boss参照は不変。
- 容量制約: 全26 frameのhorizontal run数は`7/7, 10/10, 9/9, 12/12, 9/9, 10/10, 10/10, 9/9, 8/8, 8/8, 15/15, 14/14, 20/20`、合計282でAPS-039基準と同一。各frame 3〜4色・1〜20 run・rect内・frame差を維持し、`sprite_data.o` RODATA `0x4DD`（1,245 bytes）、runtime/RAM addressを増減させず詳細化。
- canonical回帰: `tests/golden/sprite-data-v040.json`を追加し、`sprites`配列だけのcanonical SHA-256 `307152b7af0c05722d48e6dac5f87045e46b2c1596df65e061894a7986fef5af`を固定。generator/MakefileがStage挙動golden `stage-data-v034.json`とsprite goldenを独立検証。sprite grid変更時のnegative回帰を追加。C89 host testは全26 frameの固定run数、dense offset、寸法、role、色数、20 run上限、frame差を検査し738 checks成功。JSON/hash/parserはROMへ非搭載。
- 自動検証: 最終ツリーで`make clean && ./scripts/verify.sh`終了コード0。stage 36、game 542、sound 351、IMA 14,949、sprite 738 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain strict verify、3-entry cart、LNX成功。ASan/UBSan付きgame 542/sound 351/IMA 14,949/sprite 738/smoke 8、`make smoke-host` 8、`make perf-host`成功（sync 75 draw/300 logic/75 sound、299.94 Hz、game speed x1.00）、`git diff --check`成功。
- Gearlynx visual: `python3 scripts/verify-stage-visuals-gearlynx.py --output-dir evidence/APS-040`を最終ROMで連続2回成功。各回Stage 1〜3 NORMAL/BOSSの6画面、生成palette、boss active、double-buffer同期を確認。`--gui --output-dir evidence/APS-040/gui`も成功し、GUI/headlessの対応6 PNGはSHA-256一致。証跡hashは`evidence/APS-040/README.md`に記録。
- APS-040 v002通常敵visual: `GameState`先頭のplayer 4 bytes、`GameEnemy` 14 bytes×4、`GameBullet` 5 bytes×12、`GameEnemyBullet` 7 bytes×16、`GamePowerItem` 6 bytes、`GameBoss.rect` 4 bytesを`include/game.h`から積算し、既存map検証器の`boss.active=242`と一致することで`enemies=4`/stride 14を検算。各Stage NORMALのsound tick entryで3敵をhost debugger injectionし、2回の同一drawでfront/back bufferを同期。Stage 1 SCOUT(0)/SAUCER(1)/DROPPER(2)、Stage 2 FIGHTER(3)/BOMBER(4)/SUPPLY(5)、Stage 3 CAVE_BAT(6)/ROCK_WORM(7)/MINING_DRONE(8)をそれぞれ`(40,24,8,8)/(80,47,8,8)/(120,70,8,8)`でactive/type/rect readback。第4slot inactive、player通常表示・非重複、player/enemy bullet・power item不在、stage palette一致を確認。
- APS-040 v002 framebuffer: Python標準libraryだけでGearlynx RGBA PNGを復号し、displayed animation frameの9 sprite全非空pixelをauthoring gridのrun/colorとhardware paletteから復元したRGBへ逐点照合。headlessとGUIを各連続2回成功し、追加`stage1/2/3-cast.png`を含む対応9 PNGのSHA-256一致を確認。CAST hashは`047680a1...`,`ed8fec7a...`,`1041b23d...`、全9 hashは`evidence/APS-040/README.md`へ記録。注入はrender証跡専用で、spawn/移動/攻撃/dropのゲームプレイ代替ではない。
- APS-040 v002全回帰: 最終ツリーで`make clean && ./scripts/verify.sh`終了コード0（stage 36/game 542/sound 351/IMA 14,949/sprite 738、strict C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、voice/gain/cart/LNX）。ASan/UBSan付きgame 542/sound 351/IMA 14,949/sprite 738/smoke 8、`make smoke-host` 8、`make perf-host`成功（sync 75 draw/300 logic/75 sound、298.85 Hz、game speed x1.00）、`python3 -m py_compile scripts/verify-stage-visuals-gearlynx.py`、`git diff --check`成功。Gearlynx title/GAME OVERは17,408/11,691全sample一致・underrun 0・遷移/gate成功、A/C/Bは8/20/8秒で6/3/5 pitch変化・75% gain一致。
- APS-040 v002不変確認: `GAME_VERSION_STRING=0.40.0`、LNX 60,126 bytes/SHA-256 `8706fa5f373ffbb7e9f608fb9e42fe0d149fe75cf20a7a93c30cc17c4bdfe1c3`、BSS `0xB2E5..0xB7D1` 1,261 bytes、C stack `0xB838`/残余102 bytes、sprite RODATA `0x4DD` 1,245 bytes、title cart 45,512/8,704 bytes/hash `99eb68...`、GAME OVER cart 54,216/5,846 bytes/hash `848691...`でv001最終値から不変。v002変更はhost visual verifier、追加6 PNG（headless/GUI各3）、evidence README、ISSUES、発行済みbrief v002のみ。runtime/sprite data/version/README本体/design/golden/tests/Makefile/sound/voice/cart/cfgは変更なし。実機LCD視認性・残像・Lynx I/II差は未確認。
- Gearlynx音声回帰: titleはTimer 3 IRQ/DAC 17,408 sample完全一致、underrun 0、停止zero、Stage 1 BGM開始。GAME OVERは11,691 sample完全一致、underrun 0、A/BGM停止、release→press TITLE復帰、held press 8 poll安定。channel Aは8秒で6 pitch変化、Cは20秒で3、Bは8秒で6、全て75% logical→MIKEY gain一致。
- ROM/RAM: `GAME_VERSION_STRING=0.40.0`。ROM生成前にversionを更新し、その後の最終ROMだけを検証。LNX 60,126 bytes（APS-039比±0）、SHA-256 `8706fa5f373ffbb7e9f608fb9e42fe0d149fe75cf20a7a93c30cc17c4bdfe1c3`。BSS `0xB2E5..0xB7D1`（1,261 bytes）、C stack開始`0xB838`、残余102 bytes、sprite RODATA `0x4DD`で全てAPS-039基準不変。title cart offset 45,512/8,704 bytes、GAME OVER offset 54,216/5,846 bytes、payload hash不変。
- 差分/未確認: 変更はsprite grid、sprite-only golden/host回帰、visual verifierのGUI option、version、README/design/ISSUES/evidenceに限定。Stage/formation/boss script/environment/palette、`src/`、GameState/AABB、描画/更新順、敵弾、移動、攻撃、drop、BGM/SFX/voice/Timer/cart semanticsは不変。Atari Lynx実機LCDの視認性、残像、Lynx I/II差、実機音量/clip/IRQ負荷/DAC音質、日本語聴感、長時間反復は未確認。BIOS・外部ROM・外部素材の取得/読取/生成、commit/push/stash/reset/checkoutなし。

### APS-039: BGM Gearlynx検証器のtitle voice状態同期

- 状態: 検証器修正・自動検証・Gearlynx統合再検証完了（Dev、2026-08-09。runtime/ROM変更、実機聴感、コミット、pushなし）
- 失敗条件/原因: APS-038統合ROMでtitle/GAME OVER voice検証は成功した一方、旧`scripts/verify-audio-gearlynx.py --channel 0 --seconds 8`はpitch変化0で失敗。旧scriptがTITLE描画後の`tap a`→固定`wait 30`→`tap a`とwall-clock sleepだけでStage 1開始を仮定し、75 Hz入力pollの間に瞬間tapが消えると`title_voice_pending`が立たずTITLEへ残留してBGMが開始されない検証器側の入力同期不備。game/runtimeのBGM回帰ではない。
- 修正: linker mapから既存`main_bss_game_address()`と`title_voice.o` BSSを解決し、`GameState`現行offsetでstage/phase/title_start_armed/title_voice_pending/SoundState.bgm_active、voice BSSでremaining/active/underrunを期限付き5 ms poll。`stage=1, phase=TITLE, armed=1, pending=0`後に持続`press a`を一度だけ送信し、`pending=1, voice active=1`を確認してrelease。`voice remaining=0, active=0, stage=1, phase!=TITLE, bgm_active=1`とA/C MIKEY activeを待ってからpitch/gain観測。B SFXは同じ同期後に`stage=1, phase=NORMAL`を待ってpause注入。瞬間tap、固定`wait 30`、タイトル描画後/開始後の固定sleepを合否条件から除去。
- timeout診断: TITLE armed、入力受理/voice開始、voice完了/Stage 1 BGM、NORMAL、A/C MIKEY activeを別deadlineとして識別。失敗時はstage/phase/armed/pending/bgm_active、voice remaining/active/underrun、対象channel enabledを短い一行へ出力し、title未受理・voice待ち・BGM未開始を分離可能。runtime、sound table/MML、voice asset/metadata/hash、Timer 3/cart、stage/sprite/versionは変更なし。
- Gearlynx BGM/SFX: 最終SHA-256 `43356c97f0fcfeb3e984f882186b868c79397ceee2064049d69256110810c966`の0.39.0 ROMでchannel A `--seconds 8`を連続2回成功（各6 pitch変化、logical→MIKEY `5→3, 8→6, 11→8, ... 17→12`）。channel C `--seconds 20`は3 pitch変化、`1→1, 2→1, 3→2, ... 16→12`。channel B既定8秒はStage 1 NORMAL同期後のshot state注入から6 pitch変化、`13→9, ... 31→23`とtraceを確認。全channelで75%式一致、gain mismatch 0。
- Gearlynx voice回帰: titleはTimer 3 IRQ 17,408、gain後DAC全17,408 sample一致、underrun 0、停止zero、channel A BGM開始。GAME OVERはIRQ 11,691、DAC全11,691一致、underrun 0、A/BGM停止、release→press TITLE復帰、held press 8 poll安定。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 542、sound 351、IMA 14,949、sprite 712、strict C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、voice/gain strict verify、3-entry cart、LNX成功。`make smoke-host` 8、`make perf-host`成功（sync 75 draw/300 logic/75 sound、299.28 Hz、game speed x1.00）、`python3 -m py_compile scripts/verify-audio-gearlynx.py`、`git diff --check`成功。
- ROM/RAM: `GAME_VERSION_STRING=0.39.0`不変、LNX 60,126 bytes、SHA-256 `43356c97f0fcfeb3e984f882186b868c79397ceee2064049d69256110810c966`不変。BSS `0xB2E5..0xB7D1`（1,261 bytes）、C stack開始`0xB838`、残余102 bytes。title cart offset 45,512/8,704 bytes、GAME OVER offset 54,216/5,846 bytesで両payload/hash一致。
- 差分/未確認: ブリーフどおり検証器と台帳だけを変更。README/designの現行仕様と矛盾なしのため変更なし。Atari Lynx実機の音量、clip、IRQ負荷、DAC音質、日本語聴感、Lynx I/II差、長時間反復は未確認。コミット、push、stash、reset、checkout、BIOS・外部ROM・外部素材の取得/読取/生成なし。

### APS-038: title/GAME OVER共有voice center-preserving +25% saturating gain

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-09。実機聴感・コミット・pushなし）
- hardware判定: Lynx Sound Overviewのdirect DAC記述、cc65 V2.19 `AUD3VOL=$FD38`/`AUD3OUT=$FD3A`、Gearlynx main `f0be31d2c33da1e9b5d4cb1fe93c34b6dc34af70`のvolume/output独立registerとoutput直接mixを照合。`AUD3VOL`はpolynomial bitの通常/integrate出力用で、停止したaudio timer下のCPU `AUD3OUT`直書きを後段増幅しないため不採用。PCM側gainを採用。
- gain: 復号済みsigned DAC byteをunsigned centerへ移した`u = byte XOR 0x80`に対し、中心からの絶対振幅を`floor(abs(u - 128) * 5 / 4)`（絶対値を0方向へ丸め）、符号復元後`-128..127`へsaturateしsigned byteへ戻す。256-byte `voice_gain_table`を生成し、共有`decode_complete`でtitle/GAME OVERへ一度だけ一定時間lookup。zero/silence `0x00`、clamp前の正負対称性、Timer 3 `backup=0x7D control=0xD8`、queue/IRQ、state/input gate、BGM/SFX 75% hardware gainを保全。
- generator/C89回帰: `scripts/generate-title-voice-gain.py`でassembly include生成・strict一致・全asset解析を追加。C89 host referenceと全256 table entry、全256 runtime mapping、center、`u'=0/255`相当のsigned `0x80/0x7F` clamp、正負1〜102対称を検査。両ADPCMの全29,099 sampleをdecodeし、gain mapping、center、clamp、silent tailを検査。IMAテストは14,949 checks成功。host helperはcc65 ROMで未使用のため`__CC65__`時に除外し、ROM runtimeはassembly tableだけとした。中間linkのMAIN 51 bytes超過を解消し、最終残余102 bytes。
- asset解析: titleは17,408 samples/8,704 bytes/SHA-256 `99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2`、signed DAC `-28..33`/peak 33 → `-35..41`/peak 41、center 3,583→3,583、clamp 0（0.000000%）、silent tail 815。GAME OVERは11,691 samples/5,846 bytes/SHA-256 `848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f`、`-20..24`/peak 24 → `-25..30`/peak 30、center 2,778→2,778、clamp 0（0.000000%）、silent tail 826。payload/hash/header/cart entry不変。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 542、sound 351、IMA 14,949、sprite 712 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice/gain table strict verify、3-entry cart、LNX成功。`make smoke-host` 8、`make perf-host`成功（sync 75 draw/300 logic/75 sound、299.19 Hz、game speed x1.00）、`git diff --check`成功。
- Gearlynx: 1.2.21でtitle/GAME OVERを各2回連続PASS。titleは各回Timer 3 IRQ 17,408、gain後全17,408 DAC sequenceがhost referenceと一致、underrun 0、silent tail/停止zero、完了後channel A BGM開始。GAME OVERは各回IRQ 11,691、gain後全11,691 DAC一致、underrun 0、A/C/B停止、complete前gate、release→press後TITLE復帰、押下保持8 poll安定。両voiceで126 us/7,936.508 Hz、reference clamp 0を確認。
- ROM/RAM: `GAME_VERSION_STRING=0.39.0`、LNX 60,126 bytes、SHA-256 `43356c97f0fcfeb3e984f882186b868c79397ceee2064049d69256110810c966`。CODE 38,393 bytes、RODATA 6,435 bytes、DATA 305 bytes、BSS `0xB2E5..0xB7D1`（1,261 bytes）、C stack開始`0xB838`、残余102 bytes。title cart offset 45,512、GAME OVER cart offset 54,216で両payload一致。
- 差分/未確認: ブリーフ許可どおりvolume register案を退けPCM tableを採用。soft kneeは不要（両assetのclamp 0）で、要求どおり+25% hard saturationを維持。ADPCM/metadata/VOICEVOX/speech rate、Timer 0/2/3設定値、cart layout semantics、game state transition、BGM/SFX table/gainへ変更なし。Atari Lynx実機の音量、clip、IRQ負荷、DAC音質、日本語聴感、Lynx I/II差、長時間反復は未確認。コミット、push、stash、reset、checkout、BIOS取得なし。

### APS-037: VOICEVOX Nemo音声差替え・公開可能ライセンス構成

- 状態: 実装・自動検証・Gearlynx機械検証完了、raw hash再生成不整合是正済み（Dev、2026-08-09。実機聴感・コミット・pushなし）
- 生成元: 公式VOICEVOX editor 0.25.2 arm64 DMG（2,017,545,955 bytes、SHA-256 `4d532a84470c6d0cf713d2c5c6e6e5f8d2c36b18821055fd2c73386fcdfd6b91`、取得2026-08-09T10:28:51+09:00）と公式Nemo Engine 0.24.0 arm64 VVPP（134,610,531 bytes、SHA-256 `d67cbe5c8e23c0ee41a398e12e20b98de039a0eada944a3938bc6c3e39fc8f4f`、取得2026-08-09T10:31:21+09:00）をrepo外へ導入。配布API digestと取得物を照合し、arm64 native/Rosetta不使用。localhost `127.0.0.1:50121`以外のAPI、外部送信、Personal Voice、第三者音声素材なし。
- voice/asset: VOICEVOX Nemo男性2（engine `男声2`、UUID `7ecc7a17-1465-4b22-a3b5-842a110ff55e`、style `ノーマル` ID 10000）、speed 0.9/pitch -0.08/intonation 0.9/volume 1.0。titleは17,408 samples/8,704 bytes/SHA-256 `99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2`、GAME OVERは11,691 samples/5,846 bytes/SHA-256 `848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f`。engine既定0.1秒post-phonemeを800 exact-zero sampleへ決定的正規化。
- generator/verify: `scripts/generate-title-voice.py`をlocalhost限定VOICEVOX API生成へ置換。engine/editor/installer version・speaker UUID/name・style ID/name・8 kHz mono signed 16-bit WAV・sample count・固定query/ADPCM hash・metadata/header・固定クレジット・ライセンス記録をstrict検証。再生成実測でtitleのraw WAV/正規化PCM hashが初回値から変化してもADPCM `99eb68...`・17,408 samplesが一致したため、raw hashは各生成runのprovenanceとしてlowercase SHA-256形式だけを検査し、cross-run完全一致を要求しない。metadataの`hash_policy`に境界を明記し、異なるPCM hashが同一ADPCM/sample count/headerへ量子化されるhost回帰を追加。旧生成依存、旧license note、旧provider表記・成果物を現行文書/metadataから除去。
- v002再生成: Nemo 0.24.0 arm64実起動下でtitle→GAME OVERの順に再生成し、title raw WAV `a92b34da96447a8b76bfa9a6f945343fb6fefff80e27cae0c81d3d6f569ef84f` / normalized PCM `58a6265bf42b93603eb90e898dcba94eec6bea698a03623fdfa307a41cdb228d`、GAME OVER raw WAV `55f0c015fd0e5f18fb85b64920dbb9f300edb7e854d3dbaedd862e5c73d27c20` / normalized PCM `37ef9d6ee33c633c1162bfc51f2f4a0bb0a9df62ad8d24b859291c3878a0df9c`をrun provenanceとして記録。固定query hash、両sample count、両最終ADPCM/hash、header/cart payload一致。ROM/runtime/state machine変更なし。
- license/UI: 2026-08-09確認のVOICEVOX Nemo規約とソフトウェア規約に基づき、商用・非商用利用条件、禁止事項、一次資料URLを`assets/voice/LICENSE.md`へ固定。恒久クレジット`VOICEVOX:Nemo（男性2）`をREADME/metadataとタイトル画面y=82..88へ表示し、操作行・version y=90との非重複を確認。
- runtime/cart: 既存3 entry、Timer 3 `backup=0x7D control=0xD8`（126 us、7,936.508 Hz）、channel D、75% gain非適用、5 buffer/3段queue/専用IRQ、title完了遷移、GAME OVER release→press gateを維持。title実効2.193408秒、GAME OVER実効1.473066秒。entry 1はblock 44/offset 197/cart offset 45,253/length 8,704、entry 2はblock 52/offset 709/cart offset 53,957/length 5,846でROM payload一致。
- 自動検証: v002で`make voice-generate`→`make voice-generate-game-over`→`make voice-check`、続けて`make clean && ./scripts/verify.sh`終了コード0。raw hash形式/hash policy/異なるPCM→同一ADPCM境界、stage 35、game 542、sound 351、IMA 14,574、sprite 712 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、両voice strict verify、3-entry cart、LNX成功。ASan/UBSan付きgame 542/sound 351/IMA 14,574/sprite 712/smoke 8、`make smoke-host` 8、`make perf-host`成功。
- Gearlynx: 1.2.21でtitleとGAME OVERを各2回連続成功。titleは各回17,408 IRQと全17,408 DAC sample一致、underrun 0、完了後channel A BGM開始。GAME OVERは各回11,691 IRQと全11,691 DAC sample一致、underrun 0、A/C/B停止、完了前gate、release→press後TITLE復帰、押下保持8 poll安定を確認。
- ROM/RAM: `GAME_VERSION_STRING=0.38.0`、LNX 59,867 bytes、SHA-256 `e5b619b56eadb1fff3fe8655db1f9314b64b2e6bc06ea25d06bb07ae6a109d32`。CODE 38,390 bytes、RODATA 6,179 bytes、DATA 305 bytes、BSS `0xB1E2..0xB6CE`（1,261 bytes）、C stack開始`0xB838`、残余361 bytes。
- 差分/未確認: Runtime/audio topology/state gateはブリーフどおり不変。日本語suffixだけTGI標準font非対応のため共有5x7 mask rendererを使用。Atari Lynx実機のIRQ負荷、DAC音質・日本語聴感・音量バランス、Lynx I/II差、長時間反復は未確認。規約変更後の新規公開時は一次資料を再確認する。コミット、push、stash、reset、checkout、BIOS取得なし。

### APS-036: 出力ゲイン75%・GAME OVER音声

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-09。実機聴感・コミット・pushなし）
- 目的: 論理BGMおよび全7 SFXのMIKEY出力だけを既存値の3/4（切捨て、非zeroは最低1）へ下げ、channel Dのタイトル音声はgain/data/rateを不変にする。当時のローカル音声パイプラインで「お前は弱かった」を8 kHz mono IMA ADPCM化し、最終爆発SFX完了後のGAME OVER画面で一度だけ再生する。旧生成物はAPS-037で削除・差替え済み。
- 保全条件: music/SFX table値・duration/priority/envelope意味、タイトル音声asset/再生rate、A/C=BGM・B=SFX・D=voice、Timer 3共有、75Hz描画/入力/SFX・300Hz logic、Stage/sprite/data基盤を保全する。GAME OVER音声中はA/Bでタイトル/再開始しない。音声完了後だけ従来のrelease→pressでタイトル復帰を許可する。外部API/ネットワーク/商用TTS/第三者素材/Personal Voiceなし。commit/push/stash/reset/checkout禁止。
- 完了条件: BGM/SFX hardware gainの0→0、1→1、2→1、3→2、4→3、31→23回帰とlogical table不変、title/game-over音声のasset/metadata/header/cart検証、最終死亡分岐・重複防止・Timer 3/channel D排他・入力gateのgame回帰、全verify、Gearlynxで両voiceのTimer 3/DAC/underrun/完了遷移とA/B/C音量、LNX、`GAME_VERSION_STRING=0.37.0`、ROM SHA-256、ライセンス注記、README/design/.briefs記録。

#### APS-036 実装結果

- output gain: `sound_hardware_volume()`をMIKEY出力段の共通helperとして追加し、channel A/C/BへのVOL書込値だけを`floor(logical*3/4)`、非zero最低1へ変換。境界`0→0, 1→1, 2→1, 3→2, 4→3, 31→23`と0〜31全域を回帰。MML/SFX table、note/wave/duration/priority、envelopeから生成される`SoundOutput.volume`はfull-scaleのまま。channel D DACは別streamでhelper非適用。
- asset/generator: APS-036時点ではmacOSローカル音声から承認文言「お前は弱かった」を生成し、8 kHz mono IMA ADPCM low-nibble-first、10,119 samples、5,060 bytesとして追加した。`generate-title-voice.py`を複数assetのgenerate/strict verifyへ一般化し、title metadata/headerは当時不変。両旧生成物・hash・生成依存はAPS-037で完全に削除し、VOICEVOX Nemo男性2へ差替え済み。
- cart/runtime: 3-entry directory（entry 0 resident、entry 1 title、entry 2 GAME OVER）へ拡張。最終titleはblock 44/offset 19/cart offset 45,075/length 8,778、GAME OVERはblock 52/offset 605/cart offset 53,853/length 5,060で、両ROM payloadがchecked-in assetとbyte一致。両clipは既存128-byte 5 buffer、3段queue、専用IRQ、Timer 3/channel Dを共有し、active中startを拒否。GAME OVER再生時間は10,119/7,936.508=約1.275秒。
- state machine/UI: 最終爆発SFXが実完了した更新だけ`game_over_voice_pending=1`。非最終死亡はpending/completeとも0。GAME OVER画面を描いて`VOICE...`を表示後に一回だけblocking streamを開始し、完了でpending clear/complete set。再生中A/B無視、完了時も`restart_armed=0`、held FIREでは遷移せずrelease→press後だけタイトルへ戻る。重複complete、final boss、環境死亡、完全初期化をhost回帰。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 542、sound 351、IMA 13,862、sprite 712 checks、strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、両voice metadata/SHA/header、3-entry cart、LNX成功。ASan/UBSan付きgame 542/sound 351/IMA 13,862/sprite 712/smoke 8、`make smoke-host` 8件、`git diff --check`成功。
- 性能: `make perf-host`終了コード0。`--sync`はelapsed 1,002,358 us、75 draw/300 logic/75 sound、logic 299.29 Hz、game speed x1.00。host通常game性能でありLynx実機音声IRQ負荷の根拠にはしない。
- Gearlynx voice: titleはTimer 3 `backup=0x7D control=0xD8`、17,555 IRQ、全17,555 DAC sampleがC89 IMA referenceと一致、`remaining=0 active=0 underrun=0`、停止後zero、channel A BGM開始。GAME OVERはlives=0/dying=1/爆発SFX最終stepをpause注入し、ROMの`update_player_death()`で最終死亡分岐を実行。10,119 IRQ、全10,119 DAC sample一致、underrun 0、A/C/B停止、held A中は`restart_armed=0`、releaseでarmed、pressでTITLEへ一回遷移。両voiceとも126 us/7,936.508 Hz、channel Dのgain非適用を確認。
- Gearlynx v003再現性修正: 差戻し後の現行scriptでは最終爆発SFX注入から10,119 sampleの音声経路へ到達したが、release→press確認が`controller_macro`の固定`wait=5`に依存し、同一ROMで初回FAIL・再実行PASSを再現した。起動後の`stage=1/phase=TITLE`、release後の`game_over=1/restart_armed=1`、press後の`game_over=0/phase=TITLE`を各5秒期限付きmemory pollへ変更。復帰押下保持中も8 poll連続でTITLE、`title_start_armed=0`、`title_voice_pending=0`を確認する。修正後の単独GAME OVER検証を連続2回成功し、各回Timer 3 IRQ 10,119、全DAC sample一致、underrun 0、停止zero、BGM非再開、release→press復帰を確認。runtime/game/sound/asset/ROM変更なし。
- Gearlynx gain/visual: channel Aでlogical→MIKEY `5→3, 8→6, 11→8, ... 17→12`、channel Cで`1→1, 2→1, 3→2, ... 16→12`、channel B shot SFXで`15→11, 19→14, 22→16, 24→18, 28→21`を実測し全sampleが75%式一致。Bは短いSFXを確実に測るためStage 1 NORMALでshot SoundStateをpause注入し、gameplay発火経路はhost回帰で別検証。APS-034 visual scriptもStage 1〜3 NORMAL/BOSSを連続2回成功。
- ROM/RAM: `GAME_VERSION_STRING=0.37.0`、LNX 58,977 bytes、SHA-256 `5485be23efff5a1aae133f5438ee9e9206c0035e66db3c100ad1a43aa667908a`。TITLEVOICE 8,778 bytes、GAMEVOICE 5,060 bytes。BSS `0xB130..0xB61C`（1,261 bytes）、C stack開始`0xB838`、残余539 bytes。
- 設計差分/未確認: ブリーフ許可どおり3 directory entryを採用。既存`title_voice*`名のstream実装を共用化し、新規driver複製なし。GAME OVER音声中は画面を先に一度描画してblocking pumpするため静止画を維持し、通常75Hz/300Hzは音声外で不変。Gearlynxの最終死亡は爆発SFX最終stepからの実遷移で、全17 tickを含む連続実プレイはhost回帰のみ。Atari Lynx実機のIRQ負荷/DAC音質/音量バランス、日本語聴感、Lynx I/II差、長時間反復は未確認。旧生成物と配布制約はAPS-037で削除・解消済み。commit/push/stash/reset/checkout、外部API/ネットワーク/Personal Voice/第三者素材/BIOS取得なし。

### APS-035: タイトル音声の再生レート復帰

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-09。実機聴感・コミット・pushなし）
- 目的: V0.34.0のTimer 3 backup 62（63 us、15,873.016 Hz）によるタイトル音声が早すぎたユーザー確認を受け、asset/IMA ADPCM内容を変えずTimer 3/channel Dの消費レートだけを半分へ戻す。backup 125、period 126 us、7,936.508 Hz（V0.33相当）とし、17,555 samplesの計算再生時間を約2.211930秒へ復帰する。
- 保全条件: `assets/voice/title-start.adpcm`、TTS/変換script、cart entry、IMA codec、専用IRQ/5 buffer/3段queue、タイトルarmed→一回開始→完了一回`game_start()`、再生中FIRE無視、A/C=BGM、B=SFX、Timer 0/2/7、75Hz描画・入力/SFX、300Hz logic、APS-034のJSON/stage/sprite/paletteを変更しない。既存高速化のqueue/IRQはrateだけの変更で不要な巻戻しをしない。commit/push/stash/reset/checkout禁止。
- 完了条件: source/header/comments/Gearlynx検証scriptの期待値をbackup 125・126 us・7,936.508 Hzへ整合し、ADPCM SHA-256不変、タイトル完了遷移、underrun=0、Timer 3/channel D停止とchannel A BGM開始をGearlynxで実測する。`make clean && ./scripts/verify.sh`、`make perf-host`、LNX検査、`git diff --check`、`GAME_VERSION_STRING=0.36.0`、ROM SHA-256、README/design/本台帳/.briefs記録を満たす。Lynx実機の音質/負荷は未確認のまま明記する。

#### APS-035 実装結果

- rate: `src/title_voice_stream.s`のTimer 3 reloadだけを62から125へ変更。1 us clock、backup 125、周期126 us、実効7,936.508 Hz。17,555 samplesの計算再生時間2.211930秒。APS-033の15,873.016 Hz・約1.106秒・約1 octave高ピッチ化を取り消し、V0.33相当へ復帰した。
- 保全: 専用IRQ、exact IMA decoder、128-byte 5 buffer、3段queue、連続pump/title gateは維持。TTS/変換script、IMA codec、cart directory、A/C=BGM・B=SFX、Timer 0/2/7、75 Hz描画/入力/SFX、300 Hz logic、APS-034のJSON/generator/sprite/paletteへ変更なし。`assets/voice/title-start.adpcm`は8,778 bytes、SHA-256 `2c8e8402f6b059de5e746b7513be97626f3301a0aba6f2644da62b82d5b30c6a`で不変。最終cart entry 1はblock 43/offset 603/cart offset 44,635/length 8,778、ROM内dataも同SHA-256。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 538、sound 316、IMA 8,797、sprite 712 checks、clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header成功。ASan/UBSan付きgame 538/sound 316/IMA 8,797/sprite 712、`make smoke-host` 8件、`git diff --check`成功。
- 性能: `make perf-host`終了コード0。`--sync`はelapsed 1,002,681 us、75 draw/300 logic/75 sound、logic 299.20 Hz、game speed x1.00。host通常game性能でありLynx実機の音声IRQ負荷の根拠にはしない。
- Gearlynx: Gearlynx 1.2.21 headless MCPでTimer 3 `backup=0x7D control=0xD8 enabled/reload/interrupt=true period_us=126 effective_rate_hz=7936.508`を実測。17,555 Timer 3 IRQ、17,555 DAC sampleが一対一で、全sample列はC89 IMA referenceとbyte完全一致。`remaining=0 active=0 underrun=0`、channel D停止後20 poll以上zero、完了後channel A BGM開始を確認。game 538件の既存回帰でarmed→一回開始→再生中入力無視→完了一回だけ開始も維持。
- ROM: `GAME_VERSION_STRING=0.36.0`、LNX `magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=53,477 bytes`、SHA-256 `0163b38fd83bc15aeaa6065c85853028d94257d350c563ad630dc275447a573e`。
- 設計差分: ブリーフどおりTimer 3 reloadと直結するコメント・検証期待値・現行文書だけを変更。APS-033の履歴記録は維持し、APS-035現行仕様を追記。音声asset/codec/cart/runtime queue/state machine、game/stage/sound実装の変更なし。
- 未確認: Atari Lynx実機の7,936.508 Hz IRQ負荷、DAC音質、日本語聴感、Lynx I/II差、長時間反復耐久。Gearlynxは機械検証であり実機聴感の代替ではない。コミット、push、stash、reset、checkout、asset再生成、外部依存/素材/BIOS取得なし。

### APS-034: カラー表示・stage data authoring基盤

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-09。実機・GUI editor・コミット・pushなし）
- 基点: APS-031〜033を含む未コミット`GAME_VERSION_STRING=0.34.0`作業ツリー。既存差分を保全する。
- 目的: Lynx同時16色制約内で自機・通常敵・ボスを各3〜4色の色付き水平ラン/パーツ描画へ拡張し、Stage 1〜3の初期敵配置・敵種・移動・出現タイミング・発射位相・背景/環境/ボス参照をhost側JSON authoring→厳格検証→ROM用C table生成へ移行する。
- 保全条件: 外部素材/依存/ROMパーサなし。固有既存ゲームの輪郭・配色・名称・攻撃模倣なし。既存のStage 1〜3挙動、敵数上限4、敵弾上限16、75Hz描画・入力1回/描画・300Hzロジック、BGM/SFX/音声を保全する。GUI editorは対象外。commit/push/stash/reset/checkout禁止。
- 完了条件: JSON schema/strict host validator/generator/CI verify統合、範囲・画面外spawn・ID参照検証、生成C tableと移行前Stage挙動の固定回帰、カラーsprite回帰、LNX/Gearlynx表示確認、`GAME_VERSION_STRING=0.35.0`、ROM SHA-256、ISSUES/design/.briefs記録。GUI editorの残要件を明記する。

#### APS-034 実装結果

- authoring/generator: `assets/stages/stages.json`へ3 theme、3 stage、3 formation、9 enemy type、3 boss、7 boss step、3 environment/16 event、自機・9通常敵・3 bossの2-frame spriteを集約。Python 3標準libraryだけの`scripts/generate-stage-data.py`が重複/未知/欠落key、型、C整数域、密ID、参照/未参照、3 stage/4 slot、spawn/respawn/fire、boss/script/event、grid/role/寸法/3〜4色/最大20 runを検証し、`build/gen/stage_data.{c,h}`と`build/gen/sprite_data.{c,h}`を生成する。ROM内JSON parser・文字列ID・外部dependencyなし。
- 移行/描画: `game.c`のhardcoded Stage/formation/boss/environment tableを生成tableへ置換。phase尺、移動式、4敵/16敵弾/12自機弾、操作、score、75Hz描画・入力1回/描画・300Hz logicは維持。`main.c`は全13 spriteを共通horizontal-run rendererへ統合し、各Stageの最初の描画/Stage番号変更時だけ32-byte Lynx paletteを設定する。index 0〜5はStage theme、6〜15は固定role。
- 回帰: canonical table snapshot `tests/golden/stage-data-v034.json`のSHA-256は`eea07bb60c67cc94bf6586c84c97d9df56871ae2b7c7116c15ca7e94f42a6779`。validator/generator 35件、既存game 538件、sprite 712件で全table/offset/count、palette role、run境界、3〜4色、2 frame差、boss sprite/collision寸法を固定。旧hardcoded tableは除去したため決定的長期GameStateの旧/新二重実行は追加せず、全authoring値goldenと既存GameState回帰の組合せで同値を検査した。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 538、sound 316、IMA 8,797、sprite 712 checks、clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header成功。ASan/UBSan付きgame 538/sound 316/IMA 8,797/sprite 712/smoke 8件、`make smoke-host` 8件、`make perf-host`、`git diff --check`成功。
- 性能: `make perf-host`の`--sync`はelapsed 1,001,196 us、75 draw/300 logic/75 sound、logic 299.64 Hz、game speed x1.00。host計測でありLynx実機性能の根拠にはしない。
- Gearlynx: Gearlynx 1.2.21 headless MCPへ最終LNXをロードし、GameStateの正規phase遷移を使ってStage 1〜3のNORMAL/BOSSを描画。各StageのMIKEY `0xFDA0..0xFDBF`が生成32-byte paletteと一致し、全6画面で自機・通常敵またはboss・Stage固有背景のcolor frameを取得。`evidence/APS-034/`へPNG 6枚と再現手順を保存。BIOS/外部ROM取得なし。
- Gearlynx決定性是正（v003）: Dev Front再実行時の`stage 1 did not enter active BOSS`を受け、Devも旧固定sleep版で`stage 2 did not enter NORMAL`を再現。phase判定・描画同期の`time.sleep(2.0/0.5)`を廃止し、安定TITLE poll→pause、INTRO/WARNING終端注入、`phase` CPU write breakpoint、`_game_update_logic` execute breakpoint 8回でtarget描画とdouble-buffer swapを同期する方式へ変更した。最終ROM SHA-256 `07e96cb7f79cd57407606e7f70e2fa9529a1e35dedb31a524dcece9b0465bb2f`で連続2回、各回Stage 1〜3 NORMAL/BOSS・palette・boss active・PNG 6枚を成功。BOSS 3枚は色付きbossがfront bufferにあることを目視した。
- v003再検証: `make clean && ./scripts/verify.sh`終了コード0。stage 35、game 538、sound 316、IMA 8,797、sprite 712 checks、clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header成功。LNX 53,477 bytes、SHA-256は上記から不変。`python3 scripts/verify-stage-visuals-gearlynx.py`連続2回成功。state注入はINTRO/WARNING終端からの正規遷移・描画回帰であり、Stage 1開始からの連続playthrough、通常phase全尺、実機・GUI連続playthroughは未確認。
- ROM/RAM: `GAME_VERSION_STRING=0.35.0`、LNX 53,477 bytes、SHA-256 `07e96cb7f79cd57407606e7f70e2fa9529a1e35dedb31a524dcece9b0465bb2f`。0.34.0基点53,618 bytes比-141 bytes。CODE `0x93D0`=37,840 bytes（-612）、RODATA `0x17E7`=6,119 bytes（+471）、DATA `0x0131`不変、BSS `0x04EB`（+1）。BSS終端`0xB46A`、C stack開始`0xB838`、残余973 bytes（+140）。ADPCM cart dataは8,778 bytes、SHA-256 `2c8e8402f6b059de5e746b7513be97626f3301a0aba6f2644da62b82d5b30c6a`で不変。
- GUI editor残要件: schema-aware form/grid、ID rename参照一括更新、palette role preview、2-frame onion-skin、run/rect/rangeの入力中表示、formation/environment timeline、path付きvalidation、canonical JSONのatomic保存。JSON以外の正本やROM parserは追加しない。
- 未確認: Atari Lynx実機のpalette/描画性能・ちらつき・入力追従・視認性、Gearlynx GUIでの連続実プレイと難易度。headless evidenceはstate注入を使った6画面検査で、Stage 1開始から全3 Stageを通したplaythroughではない。コミット、push、stash、reset、checkout、外部依存/素材/BIOS取得なし。

### APS-033: タイトル音声の16kHz再生レート化

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-09。実機聴感・コミット・pushなし）
- 基点: 未コミットのAPS-031/APS-032完了状態（`GAME_VERSION_STRING=0.33.0`）。既存差分を保全する。
- 目的: `assets/voice/title-start.adpcm`（8 kHz生成済みIMA ADPCM、17,555 samples、8,778 bytes）を再生成・再合成せず、Timer 3/channel D DACの消費レートだけを16 kHzへ変更して、タイトル音声の再生時間を約半分（約1.097秒）にする。
- 保全条件: ADPCM asset、入力文言、TTS/変換script、BGM/SFX、A-C配線、75Hz描画・入力1回/描画・300Hzロジックを変更しない。タイトルのarmed→音声開始→完了後`game_start()`、再生中FIRE無視、終了時Timer 3/channel D停止を維持する。コミット・push・stash・reset・checkout禁止。
- 注意: これはsample rateを2倍にする方式であり、音声のピッチも約1 octave上昇する。pitch保持の自然な速度変更ではない。16 kHz IRQによる実機CPU負荷・欠落・音質は未確認として残す。
- 完了条件: MIKEY Timer 3の実際のreload/periodを根拠付きで16 kHzへ設定し、Gearlynxでchannel Dの設定レート・ADPCM変化・underrun=0・安定停止・完了後channel A/BGM開始を確認する。必要なhost/game回帰、`make clean && ./scripts/verify.sh`、LNX検査、ROM SHA-256、`GAME_VERSION_STRING=0.34.0`、設計/README/本台帳/.briefs記録を満たす。ROM内data SHA-256がAPS-032と不変であることも確認する。

#### APS-033 実装結果

- rate: Gearlynx 1.2.21のTimer実装でcounterは0の次tickにborrowするため周期は`backup + 1`。Timer 3の1 us clockでbackup 62を採用し、63 us/sample = 15,873.016 Hz（16 kHz比-0.7937%、APS-032 backup 125/126 us/7,936.508 Hzの正確な2倍）。17,555 samplesの計算再生時間1.105965秒。61/62交互reloadによる16 kHz exactはIRQ分岐・書込増を避けるため不採用。
- asset/cart: `assets/voice/title-start.adpcm`は17,555 samples、8,778 bytes、SHA-256 `2c8e8402f6b059de5e746b7513be97626f3301a0aba6f2644da62b82d5b30c6a`でAPS-032から不変。生成/変換script、IMA C codec、cartridge directory構造は無変更。最終entry 1はblock 43/offset 744/cart offset 44,776/length 8,778でROM内dataも同SHA-256。
- IRQ/decode: 単純reload変更ではcc65共通IRQ walk込みの復号が63 us期限を超えてunderrunしたため、再生中だけ元vectorを保存する専用IRQへ切替。16 code indexed jump table、事前計算difference/next-step table、6502 overflow flagによるpredictor clampでexact IMA復号を短縮。Timer 2等の同時pendingは`callirq`へ委譲し、その間に発生したTimer 3 borrowを消さず同じIRQで処理。完了/stopでTimer 3/channel Dをzero化し元vectorを復元。
- producer/state: 128-byte compressed buffer 5本（current 1、assembly 3段queue、prefetch 1）へ拡張。開始入力受理後は約1.106秒のtitle gate内でpumpを連続実行し、入力/logic/drawを進めずVBlankを維持する。再生中FIRE無視、完了一回だけ`game_title_voice_complete()`→`game_start()`、A/C=BGM・B=SFX・Timer 0/2/7は維持。BSS終端`0xB4F6`、C stack開始`0xB838`、残余833 bytes。
- Gearlynx: Timer 3 `backup=0x3E control=0xD8 enabled/reload/interrupt=true period_us=63`を実測。17,555 Timer 3 IRQ、17,555 DAC sampleが一対一で、全sample列はC89 IMA referenceとbyte完全一致。`remaining=0 active=0 underrun=0`、停止後20 poll以上zero、channel A BGM開始を確認。既存BGM回帰はchannel Aが8秒で7音程、channel Cが20秒で3音程変化してPASS。
- 自動検証: `make clean && ./scripts/verify.sh`終了コード0。game 538件、sound 316件、IMA 8,797 checks、clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header成功。ASan/UBSan付きgame 538/sound 316/IMA 8,797/smoke 8件、`make smoke-host` 8件、`git diff --check`成功。
- 性能: `make perf-host`終了コード0。`--sync`はelapsed 1,002,690 us、75 draw/300 logic/75 sound、logic 299.20 Hz、game speed x1.00。title専用IRQはGearlynx全sample/全IRQ一対一とunderrun 0で別途実動検証。
- ROM: `GAME_VERSION_STRING=0.34.0`、LNX `magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=53,618 bytes`、SHA-256 `1d2c3560b87a4d5fa6bda92faf1c47bca4df03db1c35819e481963f055066923`。
- 設計差分: ブリーフの「消費rateだけ」から、16 kHzで実測したdecoder/producer underrun解消に必要な範囲として専用IRQ、3段queue、5-buffer、blocking title gateまで変更。asset/IMA形式/cart構造/BGM/SFX/通常時速度は保全。音声再生中のタイトルanimation停止は、再生中入力無視と完了後一回遷移を確実にするための明示差分。
- 未確認: Atari Lynx実機の16 kHz IRQ負荷、DAC音質、日本語聴感、Lynx I/II差、長時間反復耐久。ピッチは約1 octave上昇し、pitch保持の自然な速度変更ではない。コミット、push、stash、reset、checkout、asset再生成、外部依存/素材/BIOS取得なし。

### APS-032: タイトル開始音声「わしは宇宙の帝王ザカリテ」統合

- 状態: 実装・自動検証・Gearlynx機械検証完了（Dev、2026-08-08。実機聴感・配布用音声置換・コミット・pushなし）
- 基点: APS-031プロトタイプを含む未コミットV0.32.0作業ツリー。既存差分を保全する。
- 目的: ユーザー提供文言「わしは宇宙の帝王ザカリテ」をmacOSローカルTTSのみで生成し、8 kHz mono IMA ADPCMとして同梱、タイトル開始入力→音声再生完了→`game_start()`へ統合する。
- 保全条件: 外部API/ネットワーク/商用TTS/外部素材なし。75Hz描画・入力1回/描画・300Hzロジック、BGM4倍/SFX75Hz、既存開始アーム規則、BGM/SFX/A-C配線、ゲームオーバーを保全する。再生中入力は重複開始しない。ゲームオーバー音声は対象外。
- 完了条件: 再生成可能な文言入力・ローカル変換スクリプト・最終圧縮データ・ライセンス注記、タイトル遷移/完了/重複入力の回帰、cc65リアルタイム復号の検証、LNX/Gearlynx/ROM SHA-256を記録する。自然長8 kHz IMA ADPCMがresident RAMまたは実時間復号に不適合なら無断の短縮/PCM変更をせず、実測と比較案を報告する。`GAME_VERSION_STRING`は`0.33.0`へ更新する。

#### APS-032 実装結果

- TTS/asset: APS-032時点ではmacOSローカル音声から入力`わしは宇宙の帝王ザカリテ`を8 kHz mono signed 16-bit PCMへ一時変換後、low-nibble-first IMA ADPCMへ圧縮した。自然長17,555 samples=2.194375秒、8,778 bytes。AIFF/WAVは一時directoryだけで削除し、Git対象はtext/ADPCM/JSON metadata/header/script/license noteだった。旧生成物・hash・生成依存はAPS-037で完全に削除済み。
- ライセンス: APS-032時点の旧生成物に関する配布制約とlicense noteはAPS-037の公開可能なVOICEVOX Nemo男性2差替えにより削除。現行条件は`assets/voice/LICENSE.md`を正本とする。
- cart/RAM: 自然長8,778 bytesはAPS-031 resident余地6,262 bytesを超えるため短縮・PCM化・sample rate変更を行わず、custom 2-entry Lynx cartを採用。entry 0=resident executable、entry 1=cartridge-only ADPCM。final entry 1はblock 42/offset 794/cart offset 43,802/length 8,778でassetとbyte同一。BSS終端`0xAFB5`、C stack開始`0xB838`、残余2,179 bytes。resident executable cart長43,583 bytes（APS-031比+3,521）、最終LNX 52,644 bytes（同+12,582）。
- decoder/backend: mainlineは128-byte compressed buffer 2本へcartを先読み。Timer 3/125 us IRQごとに65SC02 assemblyがIMA 1 nibbleを復号し、predictor high byteをsigned 8-bit channel D DACへ書く。89 step×8 magnitudeのdifferenceはbuild-time table化し、static conservative estimateはcommon IRQ chain込み約300〜410 cycles/sample（4MHzで500、3.6MHz仮定450 cycle/sample予算）。A/C=BGM、B=SFX、Timer 0/2/7へ無変更。
- 状態機械: armed後最初のFIREは`title_voice_pending`だけを設定。同一描画内の残りlogic updateと再生中FIREを無視し、完了一回だけ`game_title_voice_complete()`→`game_start()`。invalid/length 0はskipして開始。非title全経路でTimer 3/channel D/queueを停止。GAME OVER音声は未実装。
- 回帰: game 538件（APS-031 534→+4: pending/重複入力/完了一回/再開始）、sound 316件、IMA 8,797 checks（既存14相当+実asset全8,778 byte/17,555 sample検査）、startup smoke 8件。clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header、`git diff --check`成功。ASan/UBSan付きgame 538/sound 316/IMA 8,797/smoke 8件成功。
- Gearlynx: `verify-title-voice-gearlynx.py`でchannel D 225 polls中176 nonzero、39 distinct、完了後20回以上zero、`remaining=0 active=0 underrun=0`、channel A BGM開始を確認。MCP trace 983 DAC writesの先頭256 sampleがC89 referenceとbyte完全一致（driver明示zero write 4回後）。既存channel Aは8秒で4音程、channel Cは25秒で3音程変化してPASS。`make smoke-gearlynx`はROM起動/monitor待受後、一般input/state protocol不在の既知仕様で終了コード3 `UNVERIFIED`。
- 性能: `make perf-host`成功。`--sync`はelapsed 1,003,816 us、75 draw/300 logic/75 sound、logic 298.86 Hz、game speed x1.00。ホスト通常game性能でありtitle IRQ負荷の実機計測ではない。IRQ実時間適合はGearlynx全sample完走・underrun 0で補完した。
- ROM: `GAME_VERSION_STRING=0.33.0`、LNX `magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=52644 bytes`、SHA-256 `383f8d82e90574c2bcf587e7529d4c6deb71d9b2a5119d558bfa89bb4a24925c`。
- version是正: v001検証中の中間ROMに用いた版数は最終成果物の版数へ持ち越さず、ユーザー指定および完了条件どおり最終版を`0.33.0`へ統一。採用実装はdirect IRQ+precomputed difference tableのみで、C ring/mainline assemblyはGearlynxでproducer underrunを検出したため不採用。
- v002再検証: `make clean && ./scripts/verify.sh`終了コード0。game 538件、sound 316件、IMA 8,797 checks、clang strict C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、voice metadata/SHA/header、2-entry cart、LNX header成功。`strings -a dist/asteroid-patrol.lnx`でROM内表示文字列`V0.33.0`を確認し、`git diff --check`成功。versionと直接連動する文書・生成ROM以外のAPS-031/032実装、テスト意味、音声assetは無変更。
- 変更範囲: APS-031差分を保全し、`assets/voice/`、`cfg/lynx-voice.cfg`、`src/cart_directory.s`、`src/title_voice*.{c,s,inc}`、`include/title_voice*.h`、voice/cart/Gearlynx scripts、`game.h/c`、`main.c`、game/smoke/IMA tests、Makefile、README、design/APS-032設計、本台帳、versionを追加・更新。BGM/SFX table、MML、低音ベース、`sound.c/h`、ゲーム速度定数は無変更。
- 未確認: Atari Lynx実機のIRQ cycle/sample欠落/音質/Lynx I・II音量差、Gearlynx GUI/実機スピーカーでの日本語聴感、公開配布用音声への置換。コミット、push、stash、reset、checkout、BIOS/外部ROM取得なし。

### APS-031: タイトル開始時の短音声再生 — 技術調査・実現性プロトタイプ

- 状態: 調査・最小プロトタイプ・自動検証完了（Dev、2026-08-08。実音声/タイトル統合/コミット・pushなし）
- 基点: 発行ブリーフはAPS-030未コミット`0.31.0`を前提としたが、着手時の実ツリーはAPS-030を含む`4d648d9121cab5b587f6fa1005d48f2822747070`がHEADで、既存差分は本項と未追跡`.briefs/APS-031/`のみだった。この実基点から既存成果を保全した。
- 目的: タイトル画面で開始入力を受けた際に「ゲームスタート」と聞こえる短音声を将来再生できるか、MIKEY/cc65/既存OSS/現行A=C=BGM、B=SFXのバックエンドに基づき判定する。MIKEYにハードウェアADPCMデコーダがなければCPU復号+MIKEY direct PCM(DAC)出力を比較し、タイトル専用でゲーム中負荷・BGM/SFXとの競合を避ける。
- 保全条件: 75Hz描画・入力1回/描画・300Hzロジック・BGM4倍/SFX75Hz、既存BGM/SFXデータとMIKEY A/B/C配線、低音ベース音色を変更しない。無断の外部音声素材・商用TTS・APIキー・BIOS/外部ROM・ライブラリ導入、stash/commit/push禁止。
- 完了条件: 根拠付きの実現可否、推奨codec/sample-rate/ROM・CPU概算、入力遷移/重複入力/チャンネル競合の設計を記録する。合法的な自作・生成不要の非発話テストデータで、採用候補パイプラインのC89ホスト回帰とLynx ROMビルドを行う。実在「ゲームスタート」音源の同梱はユーザー選択まで行わない。`ISSUES.md`、`.briefs/APS-031/v001.md`、必要な設計書を更新し、検証結果・ROM SHA-256・未確認事項を記録する。

#### APS-031 調査・プロトタイプ結果

- 実現性: MIKEYには4本の8-bit DAC `AUD0OUT`〜`AUD3OUT`があるが、ADPCM専用decoder/DMA/block-stateレジスタはない。cc65 V2.19 `_mikey.h`/`lynx.inc`/`lynx-snd.s`、Furnace `efd85a2`、lynxcc HandyMusic `e63e91e`を照合し、動作実績のあるsample経路はいずれもCPU/Timer IRQがsigned 8-bit sampleを`AUDxOUT`へ書く方式と判定した。根拠URL・該当行は`docs/plan/aps-031-audio-feasibility.md`へ固定した。
- 推奨: 実音声を0.75秒以下へ編集できる場合は8 kHz・mono・signed 8-bit PCMを第一候補とする（6,000 bytes/0.75秒、復号不要）。1秒は8,000 bytesで現行resident RAM余地を超える。超過時は4-bit IMA ADPCM（4,000 bytes/秒）を第二候補とするが、C版decoderのcc65 real-time性能は未証明のため、65SC02最適化またはring bufferとcycle計測を別途合格させる。
- codec: `include/ima_adpcm.h`/`src/ima_adpcm.c`へ動的確保・浮動小数なしのC89 encoder/decoderを追加。16-bit predictor、89段step table、index/predictor clamp、IMA low-nibble-first byte decode、signed 16-bit PCM→MIKEY signed 8-bit DAC byte変換を実装した。`tests/test_ima_adpcm.c`は既知vector、clamp、DAC端点、決定的な非発話triangle 512 sampleの独立decode状態一致・誤差上限を14件で検証する。実在音声/外部sampleはない。
- PCM backend: `src/pcm_stream.s`をcc65 interruptorとして追加し、Timer 3を125 us（8 kHz）で駆動してresident PCMを未使用channel D `AUD3OUT`へ送る。source差替/length 0/完了/明示stopでTimer 3・channel D control・DAC出力を停止する。既存channel A/C/B、Timer 0/2/7、TGI、`src/main.c`へ書かず、game flowから未呼出のため通常動作は不変。将来は開始edgeを一度だけ受理、再生中の重複入力無視、完了観測一回で`game_start()`、全ゲーム経路でPCM停止とする。
- 容量/CPU: 基点ROM 38,553 bytes・SHA-256 `54d1b06d2ccdc3920264e858d265763c8eeb68328501e1c66ac1ed317f666022`から、codec+backend込みROM 40,062 bytes（+1,509 bytes）へ増加。最終mapはBSS終端`0x9FC1`、C stack開始`0xB838`、resident余地6,262 bytes。4 MHz/8 kHzは500 cycle/sample（実効3.6 MHz仮定で450）、PCM IRQ chain静的概算は約130〜180 cycle/sample（約26〜40%、実機未計測）。タイトル専用以外では使用しない。
- 自動検証: 最終コード状態の`make clean && ./scripts/verify.sh`は終了コード0（ゲーム534件、サウンド316件、IMA ADPCM 14件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、assembly、shell lint、LNX検査）。ASan/UBSan付きゲーム534件・サウンド316件・IMA ADPCM 14件・スモーク7件、`make smoke-host` 7件、`git diff --check`も終了コード0。
- 性能/ROM: `make perf-host`終了コード0。`--sync`は75描画/300ロジック/75音tick、`logic_hz=299.20`、`game_speed_x=1.00`。LNXは`magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=40062 bytes`、SHA-256 `44c94ace32ed1894eb49626bd9e419434e2524c8b39b53d4f6878fb16ee797ca`。`include/version.h`はROM作成規則に従い`0.32.0`。
- Gearlynx: 最終ROMの`make smoke-gearlynx`はheadless起動とdebug monitor待受を確認し、入力/state protocol不在の既知理由で終了コード3 `UNVERIFIED`（make終了コード2）。既存音声回帰はchannel A `--seconds 8`で5音程変化、channel C `--seconds 20`で3音程変化してPASSした。asset未同梱・game flow未統合のためchannel D PCM自体は再生していない。
- 変更範囲: `.gitignore`（手書きassembly追跡例外）、`Makefile`、`docs/plan/design.md`、`docs/plan/aps-031-audio-feasibility.md`、`include/ima_adpcm.h`、`include/pcm_stream.h`、`include/version.h`、`src/ima_adpcm.c`、`src/pcm_stream.s`、`tests/test_ima_adpcm.c`、本台帳、`.briefs/APS-031/v001.md`。`src/main.c`、game/soundロジック、MML/生成音楽データ、SFX/BGM table、A/B/C backend、速度定数は無変更。
- 未確認: Atari Lynx実機のTimer 3 IRQ負荷・channel D DAC音質・Lynx I/II差、Gearlynx/実機でのPCM sample欠落、IMA decoderのcc65 cycle/sample、実在「ゲームスタート」の長さ・権利・話者・生成/収録方法。コミット、push、stash、reset、checkout、外部依存/音声素材/TTS/API/BIOS/外部ROMの取得・導入なし。

### APS-030: 全体4倍速化・自機爆発SE完了同期

- 状態: 最終要件実装・検証完了（Dev、2026-08-08。コミット・pushなし）
- 優先度: 高
- 基点: APS-029の未コミット`0.29.0`作業ツリー。APS-029の変更(75Hz描画・入力1回/描画・ロジック2回/描画=150Hz)をそのまま保全する。
- 目的: ユーザーの「音楽テンポも倍」「敵を含む全体を約2倍速」要望のうち、APS-029で未対応だったBGMメロディ/ベースの演奏進行だけを75Hz実時間比2.00倍へ変更する。敵を含むゲームロジックはAPS-029で既に150Hz化済みであり、本課題では再変更しない。
- 設計判断: `sound_tick()`は描画フレームごと1回のまま、BGMの共有`advance_music()`だけを非freeze時に1 tickあたり2回進める。出力投影は従来どおりフレームごと1回、SFXの`advance_sfx()`は従来どおり1回に固定する。これによりMMLの`SoundStep.duration`・ベースデータ・SFX長を変更せず、メロディとベースを同じBGM専用2倍進行に載せ、BGM loopの実時間だけを半分にする。
- 保全条件: `game_sound_tick()`/`sound_tick()`の呼出回数、75Hz描画/入力、APS-029の150Hzロジック、SFX duration・優先度・保留CLEAR、死亡中`freeze_bgm`、stage切替、`sound_stop_all()`を維持する。ユーザー確認済みの低音ベース無音化によるプー音対策は別問題であり、`assets/music/*_bass.mml`、ベース音色、音量、休符、durationを一切変更しない。
- 完了条件: BGM専用2倍進行を最小差分で実装し、メロディ/ベースのphase lock、freeze中は両方不進行でSFXだけ1 tick進行、stage切替/stop_allの既存規則、SFX長不変を回帰テストで保証する。`include/version.h`を`0.30.0`へ更新し、`make clean && ./scripts/verify.sh`、ASan/UBSan、`git diff --check`、LNX検査、ROM SHA-256、Gearlynxの既存機械確認を実行・記録する。コミット・push・stash操作は禁止。

#### APS-030 最終要件(v002)

- ユーザー確認済みの`0.30.0`に対し、ゲームロジックをさらに2倍、すなわち75Hz描画ごとに4回・300Hz（基準75Hz比4.00倍）へ変更する。描画75Hz、入力1回/描画、`game_sound_tick()`/SFX tick 1回/描画は維持する。
- BGMメロディ/ベースは基準テンポ比4.00倍とする。MMLデータは変更せず、`sound_tick()`1回の非freeze時にBGM共有カーソルだけ4回進める。SFXカーソルは1回だけ進め、全SFXの長さ・優先度・保留規則を維持する。
- 自機撃墜SFXだけを短いnoise主体・減衰する爆発音へ変更する。他SFX、低音ベースのnote/wave/volume/rest/duration、プー音対策は変更しない。
- 自機死亡開始時にBGMを停止し、死亡中は爆発SFXだけを進める。非最終ライフのプレイヤー復帰・敵/弾更新再開は固定32ロジック更新ではなく、実際の`SOUND_SFX_PLAYER_EXPLOSION`完了を条件にする。完了後に現StageのBGMを曲頭から再開する。最終ライフは爆発SFX完了後にGAME OVERへ遷移し、BGMを再開しない。
- 300Hzの性能は`make perf-host`（75描画/300ロジック/75音tickの実測）とGearlynxヘッドレス/MCPの起動・BGM継続確認で検査する。実機CPU負荷・GUI実プレイのFPS/難易度は測定不能なら未確認として明記する。

#### APS-030 v001暫定実装・検証結果

- 実装: `src/sound.c`に`MUSIC_ADVANCES_PER_SOUND_TICK=2`を追加し、`sound_tick()`の論理出力投影は1回、非freeze時の共有`advance_music()`は2回、`advance_sfx()`は1回の構成へ変更。メロディとベースは同じ共有進行ループに維持。`sound_tick()`/`game_sound_tick()`呼出回数、MML/SFXテーブル、ゲームロジック、MIKEYバックエンドは無変更。
- 回帰: `tests/test_sound.c`で1 sound tickあたりメロディ/ベース各2 duration tick・SFX 1 tick、freeze中のBGM両voice停止とSFX 1 tick進行、全3曲が元loop長の半分の描画フレームで同時にstep 0へ復帰、stage切替/stop_allを検証。`tests/test_game.c`で75描画フレーム=150ロジック更新・75 sound tick・150 BGM duration進行を統合確認。`include/version.h`は`0.30.0`、README/designはBGM専用2倍・SFX 75Hzへ整合。
- 自動検証: 最終状態の`make clean && ./scripts/verify.sh`は終了コード0（ゲーム521件、サウンド287件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査）。ASan/UBSan付きゲーム521件・サウンド287件・スモーク7件、`make smoke-host`（7件）、`git diff --check`も終了コード0。
- ROM: `make rom`成功。`./scripts/inspect-lnx.sh dist/asteroid-patrol.lnx`: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=38340 bytes`。SHA-256: `078e0851c8bc158e1b598c107bf3ea5d1bb781cbe46310780069234c482c01f0`。
- Gearlynx: `python3 scripts/verify-audio-gearlynx.py --seconds 8 --channel 0`は4音程変化でPASS。指定どおりの`--seconds 8 --channel 2`は先頭ベース音だけを観測して閾値未達（既知のheadless実時間遅延とStage 1ベース先頭duration 135のため）。補完の`--seconds 20 --channel 2`では8.45秒時点に2音目へ変化してPASSし、channel Cが無音・固着していないことを確認。テンポの聴感・Atari Lynx実機音質は未確認。
- 保全確認: APS-029由来の`include/game.h`・README/design/test_game差分を保全。APS-030では変更禁止の`include/game.h`、`src/game.c`、`src/main.c`、`tests/perf_bench.c`、`assets/music/*.mml`、生成音楽データ、SFXテーブルを変更していない。コミット・push・stash操作なし。

#### APS-030 v002最終実装・検証結果

- 速度・BGM: `include/game.h`を`4/1`へ更新し、75Hz描画ごとに4ロジック更新（300Hz、基準75Hz比4.00倍）へ変更。`src/sound.c`の`MUSIC_ADVANCES_PER_SOUND_TICK=4`により、出力投影とSFXカーソルは1回/描画のまま、非死亡時の共有BGMカーソル（メロディ/ベース）だけ4回進める。MML・生成音楽データ・低音ベースのnote/wave/volume/rest/durationは無変更。
- 爆発・同期: 自機爆発SFXだけをmetallic 2 tick + noise 4/5/6 tick、音量31→27→21→13の短いnoise主体減衰コンター（合計17 sound tick）へ変更。`sound_stop_bgm()`で死亡開始時にメロディ/ベースだけを即時停止し、`sound_sfx_is_active()`で爆発SFXの実完了を判定する。活動中は300Hzロジックでも死亡状態を維持し、`explosion_timer`は描画配列保護のため31で飽和するが復帰条件には使わない。非最終ライフは完了後に現Stage BGMを曲頭から再開、最終ライフはBGMを再開せずGAME OVERへ遷移する。
- 回帰: `tests/test_game.c`で75描画=300ロジック/75 sound tick/300 BGM duration、4/1実行中の爆発未完了時の復帰禁止、完了後の非最終再出撃・現Stage BGM曲頭復帰、最終GAME OVER・BGM非復帰、戦闘/環境凍結、爆発表示index飽和を検証。`tests/test_sound.c`でBGM4進行/SFX1進行、メロディ/ベースphase lock、BGM単独停止、SFX状態API、爆発17 tickのnoise主体減衰、他6種SFX全ステップのバイト同値を固定回帰。`include/version.h`は`0.31.0`。
- 自動検証: 最終コード状態の`make clean && ./scripts/verify.sh`は終了コード0（ゲーム534件、サウンド316件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査）。ASan/UBSan付きゲーム534件・サウンド316件・スモーク7件、`make smoke-host`（7件）、`git diff --check`も終了コード0。
- 性能計測: `make perf-host`終了コード0。`--sync`: `elapsed_us=1002247`、75描画/300ロジック/75音tick、`logic_hz=299.33`、`game_speed_x=1.00`。`--unthrottled`: 3,121,032描画/12,484,128ロジック/3,121,032音tick。固定5,000,000描画は20,000,000ロジック/5,000,000音tick（最終通常経路`elapsed_us=1509948`）。ホスト計測でありLynx実機FPS/CPU負荷の根拠にはしない。
- ROM: `make rom`成功。`./scripts/inspect-lnx.sh dist/asteroid-patrol.lnx`: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=38553 bytes`。SHA-256: `54d1b06d2ccdc3920264e858d265763c8eeb68328501e1c66ac1ed317f666022`。
- Gearlynx: `make smoke-gearlynx`はヘッドレスROM起動とdebug monitor待受を確認し、入力/stateプロトコル不在のため仕様どおり終了コード3 `UNVERIFIED`（make終了コード2）。`python3 scripts/verify-audio-gearlynx.py --seconds 8 --channel 0`は6音程変化、`--seconds 20 --channel 2`は3音程変化でPASSし、メロディ/ベースの継続演奏を確認。headless計測は実時間進行が通常プレイと異なるため、BGM4倍・爆発音の聴感を保証しない。
- 保全確認: 差分は`ISSUES.md`、`README.md`、`docs/plan/design.md`、`include/game.h`、`include/sound.h`、`include/version.h`、`src/game.c`、`src/sound.c`、`tests/test_game.c`、`tests/test_sound.c`。`src/main.c`、`tests/perf_bench.c`、`assets/music/*.mml`、`tools/mml2c.c`、生成音楽データ、他6種SFX、MIKEYバックエンドは無変更。コミット・push・stash・reset・checkout、BIOS/外部ROM/素材操作なし。
- 未確認: Atari Lynx実機のCPU負荷・FPS・入力追従・音質、Gearlynx GUIでの実プレイ難易度、BGM4倍と爆発音の聴感。

### APS-029: 75Hz表示を維持したゲームロジックの2倍速化

- 状態: 検証完了（Dev、2026-08-08。コミット・pushなし）
- 優先度: 高
- 基点: `b1236ad`(APS-028完了時点のmain)。起票時の作業ツリーはクリーン。
- 目的: ユーザーの「BGMが遅い」「ゲーム全体の動きを2倍くらいの速さにして」というフィードバックに対し、BGM/SFXのテンポと75Hz描画・入力サンプリングを変えず、ゲーム内ロジック(移動、当たり判定、AI、進行、クールダウン等)だけを基準75Hz比で2.00倍へ変更する。BGMの曲データ・duration値は本課題の変更対象外。
- 設計判断: 現行`5/4`(4描画フレームで`1,1,1,2`更新、93.75Hz)から、`2/1`(各描画フレームで必ず`2`更新、150Hz)へ変更する。これは基準75Hz比で厳密に2.00倍、現行比で1.60倍であり、剰余の変動が無く入力を同一フレーム内の2更新にだけ再利用する決定的な方式である。`5/2`(187.5Hz、基準比2.50倍・現行比2倍)は「約2倍」を超え難易度変化が大きすぎるため不採用。`7/4`/`9/4`等の分数は約1.75/2.25倍で余剰更新のフレーム偏りを持ち、2.00倍を正確に満たさないため不採用。`8/4`は2.00倍だが`2/1`と等価で不要に複雑なため不採用。
- 保全条件: `tgi_setframerate(75u)`、`tgi_busy()`待機、描画/`tgi_updatedisplay()`、入力取得、`game_sound_tick()`、MIKEY反映を各描画フレームで1回だけに保つ。追加ロジック更新へ音tickを載せず、BGM/SFXのduration・テンポ・優先度・停止/凍結規則を変えない。浮動小数、動的確保、外部ライブラリ、BIOS/ROM/素材、stashへの操作を禁止する。
- バランス上の注意: ロジック更新回数に結び付く自機/敵/弾の移動、敵射撃、弾発射クールダウン、Stage/phaseタイマ、死亡/無敵時間はすべて基準比2.00倍(現行比1.60倍)となる。相対比率は保たれる一方、プレイヤーの反応時間は短縮されるため、実プレイで難易度が過大なら敵弾速・発射間隔・敵移動などの再調整を別課題で判断する。本課題では個別バランス値を変更しない。
- 完了条件: `include/game.h`の更新比定数、`tests/test_game.c`の各描画フレーム2更新・150Hzロジック/75Hz音tickを検証する回帰、必要な`tests/perf_bench.c`/README/design.md/ISSUES.mdの倍率記載、`include/version.h`の`GAME_VERSION_STRING`を`0.29.0`へ更新を行う。`make clean && ./scripts/verify.sh`、ASan/UBSan付きホストテスト、`git diff --check`、LNX検査、ROM SHA-256を実行・記録する。Gearlynxは可能な範囲で起動・目視/操作または既存MCP検証を行い、未達なら理由を記録する。コミット・pushは行わない。

#### APS-029 実装・検証結果

- 変更ファイル: `include/game.h`（ロジックスケジューラを`2/1`へ変更）、`tests/test_game.c`（各75Hz描画フレーム2更新、75描画フレームで150ロジック更新・75音tickを回帰）、`include/version.h`（`GAME_VERSION_STRING`を`0.29.0`へ更新）、`README.md`/`docs/plan/design.md`（150Hz・基準75Hz比2.00倍・BGM/SFX tick 75Hzの記述整合）、`ISSUES.md`（本項）。`src/main.c`/`src/game.c`/`src/sound.c`/音楽データはAPS-029のため変更していない。
- スケジューラ実装: 既存`game_logic_updates_for_draw_frame()`の定数参照を維持し、剰余0から各描画フレームに必ず2回を返す`2/1`方式へ変更。Lynx main loopの`tgi_busy()`待機、75Hz設定、入力1回、ロジック更新、`game_sound_tick()`1回、MIKEY反映、描画順序は無変更。
- 自動検証: 最終ツリーで`make clean && ./scripts/verify.sh`を終了コード0（ゲーム521件、サウンド279件、clang厳格C89/warnings-as-errors、cc65 2.19 `-W error`、shell lint、LNX検査）で再実行済み。
- ASan/UBSan: `clang -std=c89 -pedantic -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer`でゲーム521件、サウンド279件、スモーク7件を全て終了コード0。`make smoke-host`（7件）、`make perf-host`、`sh -n scripts/*.sh`、`git diff --check`も終了コード0。
- 性能計測: `make perf-host`終了コード0。`--sync`: 75描画/150ロジック/75音tick、`logic_hz=149.54`、`game_speed_x=1.00`。固定500万描画では1000万ロジック・500万音tick。`legacy median=793083us`、`optimized median=791960us`、paired delta median=`4829us`。
- ROM: `make rom`成功。`./scripts/inspect-lnx.sh dist/asteroid-patrol.lnx`: `LNX header OK: magic=LYNX version=1 bank0_page=1024 bank1_page=0 size=38322 bytes`。SHA-256: `55af2918f2950246e6f92c2c867f08a7246a9496229ab0abc25a925fb926fe7f`。
- Gearlynx: `make smoke-gearlynx`でヘッドレスROM起動とdebug monitor待受を確認したが、リポジトリに入力/stateプロトコルがなく終了コード3の`UNVERIFIED`（make経由の終了コード2）。GUI目視・速度の主観評価・実機での難易度/CPU負荷は未確認。
- 設計との差分: なし。個別の敵/自機/弾速度、発射間隔、クールダウン、HP、進行タイマ、BGM/SFXデータ・duration・テンポ、75Hz描画/入力/音tickを変更していない。
- 懸念: ロジック更新は基準75Hz比2.00倍（APS-028完了時点の1.25倍比では1.60倍）となるため、実プレイ上の反応時間短縮・難易度上昇はユーザーのGearlynx操作で確認し、必要なら別課題でバランス調整する。

### APS-028: 音程レジスタのLFSR周期未補正を修正(真の根本原因)

- 状態: 実装・全自動検証合格・コミット待ち(Fable、2026-08-08。ISSUES.md/.briefsはRyokoが検収時に追記)
- 優先度: 高
- 基点: APS-027完了時点(991c8d5)
- 目的: APS-024(きらきら星差し替え)以降、APS-026(integrate+envelope)・APS-027(DC平衡LFSRタップ再選定)と2回対策しても解消しなかった「常時鳴り続けるブー音」の真因を、OSSチップチューントラッカーFurnace(tildearrow/furnace、`src/engine/platform/lynx.cpp`)の実装と比較して特定する。
- 発見(確定的): MIKEYの1チャンネルは、タイマーunderflow1回につき1エッジを出力するのではなく、**LFSRを1ビット進めるだけ**で、可聴波形はLFSRが1周期を完了して初めて繰り返す。つまり体感周波数は`f_underflow / LFSR周期長`(TONE/NOISE=6、METALLIC=63、PULSE=8)。APS-013由来の`sound_pitch_registers`は、この周期長で割る補正を一度も行っていなかった。結果、全チャンネルの音程は意図の3〜31倍低い周波数(62〜220Hz帯)で鳴っており、これが一貫して聞こえていた「低い唸り・ブー音」の正体だった。APS-026/027はintegrateモードやDCバイアスというレジスタレベルの副次的な問題には正しく対処していたが、この音程計算自体の誤りには触れていなかったため、根本解決に至っていなかった。加えて、旧テーブルは音階も均一な約1.075倍刻みで、mml2cのnote id(1〜16、(octave-1)*7+degreeでハ長調の音階度数を符号化)が期待する平均律ハ長調とズレていたため、旋律の音程間隔も圧縮されていた。
- 実装: `sound_pitch_registers`を波形ごと(TONE/METALLIC/NOISE/PULSE)× 16音のテーブルへ拡張し、各波形のLFSR周期長で正しく割った上でreload/prescalerを再計算した(note id 1=C4〜16=D6、A4=440Hzの平均律ハ長調、TONE/NOISE最大誤差0.21%、METALLIC最大誤差3.60%、PULSE最大誤差0.39%)。生成スクリプト`scripts/gen-pitch-tables.py`を追加し、以後はこのスクリプトで再生成する(手書き禁止のコメントをテーブル冒頭に明記)。`sound_backend_apply()`の参照を`sound_pitch_registers[note-1]`から`sound_pitch_registers[wave][note-1]`へ変更。
- Ryoko独立検証: `verify.sh`実行、ゲーム524件・サウンド279件PASS、cc65/LNXビルド成功。TONE note1(id=1)の実測値(reload=0x9e, prescaler=2)を手計算で検算: period=(158+1)×2^2=636µs→underflow周波数1572.3Hz→LFSR周期6で除算→262.05Hz(C4理論値261.63Hzと誤差0.16%、Fableの申告値と整合)。ROM: `dist/asteroid-patrol.lnx` 38,328 bytes、SHA-256 `1b4bba04956b6e5cf4de9b0cd550a3e6b92fe42b36746013d5e6408f70548a11`。
- 過去3回との違い: APS-026/027はレジスタの「意図通りの設定」を検証していたが、その意図(音程計算式)自体が誤っていたため、機械検証では捕捉できなかった。今回はFurnaceという実際に動作実績のある独立実装とfrequency計算式を突き合わせたことで、この構造的な誤りを発見できた。
- 残課題: 最終的な聴感評価はユーザーが行う。バージョン番号は`0.28.0`(ROM作成のたびに必ず更新する運用ルールに準拠)。

### APS-027: 「ブー」音の根本修正(DC平衡LFSRタップ再選定)+タイトル画面バージョン表示

- 状態: 実装完了・レビュー待ち(2026-08-08)
- 優先度: 高
- 起票日: 2026-08-08
- 基点: `f655b78`(APS-026完了時点のHEAD)。worktree `atari-lynx-shooter-aps027-wt`(detached)で作業。
- 目的: APS-026(integrateビット全チャンネル一律有効化+音量エンベロープ)に対しユーザーから「和らいでいない。ブー、という音」とフィードバック。レジスタレベルでは意図通り(control=0x3B、volume減衰)だったため、Gearlynxの`AdvanceLFSR()`実装を基に原理から原因を調査した。

#### 「ブー」音の技術的原因(調査で確定)

MIKEYのintegrateモード(control bit5)は、タイマーunderflowごとに出力レジスタへ`±volume`を**累積**する(`acc += data_in ? +vol : -vol`、-128〜+127へクランプ。Gearlynx `mikey_inline.h` `AdvanceLFSR()`)。累積が発散しないためには、LFSRが出力するビット列の1周期内の1と0の個数が**等しい(DC平衡)**必要がある。ところがAPS-013由来の`sound_wave_registers`は非integrate前提で選ばれており、全波形が不平衡だった(`scripts/sim-mikey-lfsr.py`によるGearlynx互換シミュレーションで確認):

| 波形 | feedback/shift_low | 周期 | 1の数-0の数 | integrate時のクランプ張り付き率 |
|---|---|---|---|---|
| TONE | 0x3f/0xac | 7 tick | -1 | 42.7% |
| METALLIC | 0x36/0x5a | 63 tick | -1 | 17.4% |
| NOISE | 0x1f/0x7f | 6 tick | +4 | 83.2% |
| PULSE | 0x24/0xb4 | 9 tick | +1 | 33.2% |

不平衡が1でも、underflowごとに`±volume`ずつ一方向へドリフトするため、音符開始から数十tick(数ms〜数十ms)で累積器が-128/+127のレールに到達して張り付く。以後の出力は「レール上の小さなリップル+周期ごとの大きな段差」に退化し、聴感上は低く歪んだ唸り(=「ブー」)になる。音量エンベロープ(0x11→0x05)はレール付近のリップル幅を変えるだけでほぼ聞こえない。GearlynxのMCP経由で旧ROMのoutputレジスタを直接読み、実機挙動でも張り付きを裏付けた(下記検証)。

#### 採用した対策

1. **integrateを波形ごとの属性に変更**(`SoundWaveRegister.integrate`)。全チャンネル一律のOR(APS-026)を廃止。
2. **TONE/PULSEをDC平衡パターンへ再選定**。単一タップk+下位k+1ビット均一シードのLFSRはtwisted ring counterに退化し、「1がk+1個→0がk+1個」の完全平衡列を恒久的に出力する。integrateと組み合わせると振幅`(k+1)*volume`のクリーンな**三角波**になる(NESの三角波チャンネルに相当する柔らかい音色。ドリフトゼロ、クランプ率0%をシミュレーションで確認):
   - TONE: `feedback=0x04`(tap2)/`shift_low=0x07` → 周期6三角波(旧矩形周期7 → 一律約+2.7半音の移調。旋律の音程関係は不変)
   - PULSE: `feedback=0x08`(tap3)/`shift_low=0x0f` → 周期8三角波(旧周期9 → 一律約+2半音)
3. **METALLIC/NOISEはintegrate非適用のままAPS-013値を維持**。両者の不平衡な擬似ランダム列をintegrateすると上記ドローンが再現する上、硬い音色はSFX・アクセントとして意図的なため。
4. **outputレジスタ(offset 2)を音符セットアップ時とサイレンス時に0へリセット**(`SOUND_REG_OUTPUT`新設)。integrate累積器が前の音符/SFXの残留値から開始してクランプへ押し出されるのを防ぎ、チャンネル無効時に残留値がDCとしてミックスされ続けるのも解消。
5. 音量エンベロープ(APS-026)は維持。三角波では振幅が`(k+1)*volume`でvolumeに線形比例するため、エンベロープが初めて聴感に反映される。
6. 最大音量でもクランプ非到達を確認: TONE最大vol27→振幅81、PULSE最大vol30→振幅120(<127)。

#### タイトル画面バージョン表示(同スコープの追加要件)

- `include/version.h`を新規作成し`#define GAME_VERSION_STRING "0.27.0"`を単一定義とした。
- `src/main.c`がincludeし、タイトル画面のみ`tgi_outtextxy(52u, 90u, "V" GAME_VERSION_STRING)`で操作説明の下に表示(160x102内、Gearlynxスクリーンショットで目視確認)。ゲームロジック・入力・HUD・表示タイミングは不変。
- `Makefile`の`build/main.o`依存へ`include/version.h`を追加。

#### 検証(2026-08-08)

- `make clean && ./scripts/verify.sh`: `PASS: 524 game logic checks` / `PASS: 279 sound logic checks`、clang C89構文検査・cc65ビルド・リンク・`LNX header OK`(38,198 bytes)すべて成功。
- `scripts/verify-audio-gearlynx.py --seconds 8 --channel 0`: 3回のピッチ変化(`0xFA→0xB8→0xAC`)、`--seconds 30 --channel 2`: 2ピッチ(`0xFA→0xC6`)でAPS-025/026と同一の演奏進行を確認(headless実行はポーリングにより実時間より大幅に遅い既知挙動)。
- `scripts/verify-audio-output-acc.py`(新規、outputレジスタ=integrate累積器を直接サンプリング):
  - 新ROM channel 0: feedback=0x04/control=0x3B、output範囲-45〜+35、**レール(-128/127)到達0%**、レベルがエンベロープに追従して多段変化。
  - 新ROM channel 2: feedback=0x04/control=0x3B、範囲-25〜+23、レール到達0%。
  - (比較)main側distの旧ROM(APS-026以前のビルド): control=0x1B(integrate無し)、output=±17の2値のみ=「BEEP」時代の生矩形波を実測。
- ROM: `dist/asteroid-patrol.lnx` SHA-256 `9f24edf18bb9df6590eba8618fcdc5eddb5cbe6e583a4e6c8a5af99119f7a3d7`

#### 残課題

- **最終的な聴感評価はユーザーが行う**(三角波化で「ブー」が消え「BEEP」より柔らかくなる原理的根拠はあるが、音の良し悪しの判定は人間の領分)。
- TONE/PULSEの一律移調(+2.7/+2半音)により、Stage 3でw0ベース(移調)とw1メロディ(非移調)の相対チューニングが約2.7半音ずれる。w1は非調和的なmetallic音色のため実害は小さい見込みだが、聴感確認対象。
- 詳細な調査過程(試して捨てた案を含む)は`.briefs/APS-027/v001.md`参照。

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
## APS-053 Phase 2 — static Suzy layer migration (2026-08-12)

- `src/static_layer.c` と生成済み `src/static_layer_data.c` を追加。`tgi_clear`、宇宙/空/洞窟の静的背景、HUD矩形・3x5 glyph・区切り線を、TGIドライバの現行描画先へ `tgi_sprite()` で投入するSuzy SCB描画へ移行。可動物・フェーズオーバーレイ・TGI double-buffer swapは維持。
- 背景レイアウトのC配列を `scripts/generate-static-layer.py` がpacked Suzy dataへ変換。透明pen 0、背景色/惑星2色、周期テクスチャのwrap、HUD文字列の既存配置を維持。
- `SCB_REHVST_PAL` 1個を再利用し、`TYPE_NONCOLL` / `NO_COLLIDE` を設定。`tgi_sprite()` がTGI内部の`DRAWPAGE`を使うため、`DISPADR`/固定bufferアドレスへの依存なし。
- 追加静的データにより通常/計測CFGのMAIN容量を超えたため、APS-052のGearlynx実測stack使用312 bytes・未使用ガード1272 bytesを根拠に、C stack予約を通常`0x031E`、計測`0x01A8`へ縮小。実行時stack high-water再検証が必要。
- `GAME_VERSION_STRING=0.53.0`。通常LNX 61,443 bytes、計測LNX 61,783 bytes。`make verify`、通常/計測LNX header、host logic/sound/IMA/sprite tests PASS。Suzy背景のpixel差分証跡と既存stage visual verifierは未完了（stage visual verifierはプレイヤー状態同期でFAIL）。
