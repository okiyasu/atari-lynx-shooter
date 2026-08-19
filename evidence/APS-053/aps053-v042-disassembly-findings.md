# APS-053 v042 — ディスアセンブル調査結果

- 前版: `.briefs/APS-053/v042.md`(Dev宛、Fable5判断v041に基づく調査依頼)
- 調査専任。プロダクションコード変更なし、コミットなし。全ビルドは `/tmp/aps053-disasm/`, `/tmp/aps053-oirs/` で実施し、リポジトリ内の生成物は一切書き換えていない(`git status --short` の追跡ファイル差分は開始時と同じ20行のまま)。

## 手法

1. `src/main.c`(`-DCADENCE_PROBE` 付き)を `cl65 -T -l` でca65リスティング化し、`movable_append`/`movable_append_solid`/`movable_append_sprite` の生成コードを命令単位で精査。
2. cc65ランタイムヘルパー(`ldaxysp`/`staxysp`/`staspidx`/`pusha`/`pushax`/`decsp5`/`addysp`/`pushwysp`/`leaa0sp`)のソース(`.cache/cc65-2.19/source/libsrc/runtime/*.s`)から実体を読み、65C02サイクル表(標準6502+65C02拡張分)で各ルーチンの呼び出しコストを算出。
3. Pythonスクリプトでリスティングの命令バイトを機械的に解析し、区間ごと(共通prefix/first_of_group分岐のみ/共通suffix)にサイクル和を集計。
4. `src/main.c` のみ `-Oirs`(`ROM_CFLAGS` 相当)でビルドし直し、cadence版ROM・release配置ROMの両方をリンクして実測(gearlynx実機、v040のbreakdownハーネス`scripts/verify-phase-3r-gate-a-breakdown-gearlynx.py`を再利用)。

## 1. カテゴリ別コスト内訳(机上見積り、`movable_append`本体、65C02サイクル)

`first_of_group=0`(継続オブジェクト、34体中の大半)のパス:

| カテゴリ | 内容 | サイクル | 比率 |
|---|---|---:|---:|
| (a) 引数push・呼び出しオーバーヘッド | `pusha`/`decsp5`/`addysp`呼び出し、ソフトスタック経由の引数再読出し(`ldaxysp`×9, `staxysp`×1) | ~620 | 85% |
| (b) 配列インデクシング乗算 | なし(`movable_append`本体には無し。spriteラッパー側に`mulax9`あり、下記参照) | 0 | 0% |
| (c) 16bit演算 | なし(`movable_append`本体は8/16bitのstore中心。加算は無し) | 0 | 0% |
| (d) 構造体書き込み本体 | 実際の `STA (ptr1),y` 系命令の正味コスト | ~108 | 15% |
| **合計** | | **728** | 100% |

`first_of_group=1`(グループ先頭、SCBに34体中5〜6体のみ該当)は上記に **+560サイクル**(penpal[0..2]書き込み、`staspidx`×3 + `pushax` + `pushwysp`×2)が追加され、合計 **1,288サイクル**。

呼び出し元ラッパーを含めた「オブジェクト1件あたり」の机上見積り(`movable_append_solid`/`movable_append_sprite` の引数マーシャリング分を加算):

| 経路 | 継続(first=0) | グループ先頭(first=1) |
|---|---:|---:|
| solid系(隕石/落石/弾/パワーアイテム) | 1,143 cy | 1,703 cy |
| sprite系(プレイヤー/敵/ボス) | 1,561 cy | 2,121 cy |

sprite系のみ追加で発生する内訳:
- **(b) 配列インデクシング乗算**: `def = &game_sprite_definitions[sprite_id]` の添字計算に `mulax9`(定数9倍、`sizeof(GameSpriteDefinition)`)ランタイム呼び出しあり(~33 cy/回)。`GAME_SPRITE_COUNT`が9の倍数でない構造体サイズのため、cc65は専用シフト加算ルーチンを生成(乗算ライブラリ全体`tosumul`等は使われていない)。
- **(c) 16bit演算**: `x + dx`, `y + dy`(アンカー補正、符号拡張つき16bit加算)に ~170 cy。

## 2. tick→サイクル換算則

> **【v044訂正】** 本節は当初「1 tick = 1 CPUサイクル」を前提としていたが、これは誤りだったことがFable5の算術検証(`.briefs/APS-053/v044.md`「重要な訂正」節、証跡`evidence/APS-053/README.md`「v044 tick→CPUサイクル換算則の訂正記」)により判明した。正しくは**1 tick ≈ 4.4〜5.0倍のシステムクロック相当**であり、以下の原文は歴史的記録として残すが、突合結果は訂正後の節を参照すること。

`scripts/verify-phase-3r-gate-a-breakdown-gearlynx.py` のタイマー定義(スクリプト冒頭コメント、当時の文言 `"timer": "get_6502_status().total_ticks, CPU-cycle-exact..."` — v040 evidence JSON内にも同一文言。この「CPU-cycle-exact」表現はv044で誤りと判明し、スクリプト側は修正済み):

> (誤) `get_6502_status().total_ticks` = gearlynxエミュレータ内部のCPUサイクルカウンタ。1 tick = 1 CPUサイクル(65C02、Lynx CPU固有クロック)。

これは `scripts/calibrate-cadence-ticks-gearlynx.py` の docstring が言及する「Timer 2カウンタtick」(ハードウェアタイマーのプリスケール値、v016のロジックコスト計測で使用)とは**別物**であることに注意(この点はv044訂正後も変わらず正しい)。v040/v041/本調査の (i)(ii)(iii) 分離診断・9,423 tick/objectはすべて `total_ticks` 経由の値であり、この計測ロジック自体(breakpoint位置・差分計算)はv044訂正後も無効化されない。ただし(誤)で述べた「追加の換算係数は不要(1 tick = 1 cycle)」は誤りで、CPUサイクル単位に変換するには4.4〜5.0で除算する必要がある。

### 突合結果(v044訂正後)

- 机上見積り(本調査、`movable_append`本体+直接ラッパーのみ): **1,143〜2,121 サイクル/オブジェクト**(経路・first_of_groupで変動)
- 実測(v041、`-O`のみ・既存ビルド): **9,423 tick/オブジェクト**。CPUサイクルへ換算すると `9,423 ÷ 4.4〜5.0 ≈ 1,885〜2,141 サイクル/オブジェクト`(v044訂正)
- **突合: 訂正後の実測換算値(1,885〜2,141 cy)は机上見積り(1,143〜2,121 cy)とほぼ一致する**。当初「実測は机上見積りの4.4〜8.2倍」「調査範囲では実測の15〜23%しか説明できず残り77〜85%が未解明」としていた結論は、tick=cycleという誤った前提に基づく計算ミスであり、**残差は解消済み**。追加のディスアセンブル調査は不要と判断する(v044確認)。

## 3. `-Oirs` A/B実測

### ビルド

- `src/main.c` を `-DCADENCE_PROBE` 付き `-Oirs` でビルドし、既存の他オブジェクト(`build/*.o`、変更なし)とリンクしてcadence版ROMを作成(`/tmp/aps053-oirs/dist/asteroid-patrol-cadence-oirs.lnx`)。リンク成功。
- 同様に `-DCADENCE_PROBE` 無しの `-Oirs` main.o を実際のrelease configで(`cfg/lynx-voice.cfg`)リンクし、production相当のROMサイズ影響も確認(`/tmp/aps053-oirs/dist/asteroid-patrol-oirs.lnx`)。リンク成功。

### gate(a) breakdownハーネス再実行結果(v040ハーネスそのまま再利用)

| ビルド | empty scb_build (median) | full scb_build (median) | 差分/33体 |
|---|---:|---:|---:|
| `-O`のみ(既存、v040実測値) | 69,031 tick | 379,997 tick | **9,423 tick/obj** |
| `-Oirs`(本調査) | 61,308 tick | 302,088 tick | **7,296 tick/obj** |

**削減率: 22.6%**(9,423 → 7,296)。empty fixtureの絶対値も69,031→61,308(11.2%減)で、`-Oirs`は全体に効くが劇的ではない。

### なぜ23%程度に留まるか(リスティング比較で確認)

`-Oirs`版のリスティング(`movable_append`)を確認したところ、`-Oi`(ランタイム関数インライン化)は実際に効いている:`jsr ldaxysp`(旧: 呼び出し6cy+ボディ20cy=26cy)が `lda (sp),y / sta ptr1+1 / dey / lda (sp),y / sta ptr1`(呼び出しオーバーヘッド無し、10cy相当)へインライン展開されていることを確認(13箇所中、頻出パターンは軒並みインライン化)。**JSR/RTSのペア(12cy/回)は除去されるが、"ソフトスタックから引数を毎回読み直す"というアクセスパターン自体は消えない**。これは `movable_append` の6引数(sprctl0, penpal, data, x, y, first_of_group)がC呼び出し規約のソフトスタック経由で渡されており、`-Or`(register変数の尊重)はソースで `register` 宣言された**ローカル変数**に対してのみ有効で、関数**引数**自体は対象外のため。つまり `-Oirs` だけでは「引数マーシャリングの構造」そのものは解消されず、削減分は主にJSR/RTS往復コストの除去に留まる。

### リンク成否・ROMサイズ差分

| | CODE segment | ファイルサイズ | release MAIN領域の残り headroom |
|---|---:|---:|---:|
| 既存(`-O`) | 0x876E (34,670B) | 59,065B | 0x1258 (4,696B) |
| `-Oirs` | 0x8C78 (35,960B) | 60,355B | **0x2AE (686B)** |

`COMPACT_ROM_CFLAGS`(`-O`のみ)の存在理由がROMサイズ制約であったという既知の疑義は**実測で裏付けられた**: `main.c`を`-Oirs`化するとCODEセグメントが+1,290B(+2.7%)増え、release configのMAIN領域の空き headroomが 4,696B→686B(約85%減)まで圧迫される。数値上はまだリンク可能(reject/overflowはしない)だが、他モジュールの今後の増量余地はほぼ消える。**速度面で22.6%減という小さい効果に対し、サイズ面の代償は不釣り合いに大きい** — `-Oirs`単純適用はコストパフォーマンスが悪いという評価になる。

## 4. 前提凍結

`include/game.h` の `GAME_LOGIC_UPDATES_MAX=12u` を含む既存WIPは調査中一切変更していない。A/B計測の両ビルドとも既存WIPを含んだ状態のツリーに対して行った(v040/v041同様、絶対値の比較可能性を優先)。

## 完了条件の確認

- `make clean && ./scripts/verify.sh`: 全PASS(host testsテスト625+351+14949+14+197件、lint、release ROMビルド・inspect含む)
- release ROM SHA256: `23958e87e89b212d30cc5cda8a5abe92b13b661593273a6f81cf8496a6449aac` — 調査開始前・終了後で**変更なし**(v038/v040のevidence記載のSHA256とも一致)

## 上位ホットスポット3件

1. **関数呼び出し境界そのもの(引数マーシャリング)** — `movable_append_solid`/`movable_append_sprite` → `movable_append` の6引数受け渡し。継続オブジェクトで728cy中約620cy(85%)がこのカテゴリ。`-Oirs`でJSR/RTS往復コストは減るが、ソフトスタック経由の読み書きパターン自体は残る。
2. **first_of_groupパレット書き込みブロック** — グループ先頭オブジェクトのみ+560cy(`staspidx`×3等)。34体中5〜6体(各movable種別の先頭)にのみ発生するため平均寄与は小さいが、個々の発生コストは大きい。
3. **sprite系ラッパーの添字乗算+16bit補正演算** — `movable_append_sprite`のみ、solid経路比+約420cy(`mulax9`によるsprite_id×9添字計算+dx/dy符号拡張加算)。敵・ボス・プレイヤーが多いフレームほど影響大。

## 各最適化案の予測削減量

| 案 | 予測削減 | 根拠・留意点 |
|---|---|---|
| ①コンパイラフラグ調整のみ(`-Oirs`化) | **▲22.6%**(実測済み) | ROMサイズ+2.7%・release headroom▲85%の代償あり。費用対効果は低いと判断 |
| ②`movable_append`の引数を一部`register`宣言してzero page/レジスタ変数化 | 見積り: ▲10〜20%程度(未実測) | cc65の組込みregister変数は4スロット(計8B)限定。6引数10Bを全部は収まらないため部分適用に留まる。`-Oirs`との併用が前提 |
| ③静的チェーン再設計(SCB事前構築+差分更新、v039案) | 見積り: 対象外(構造変更のため本調査の射程外) | 呼び出し境界自体を減らせる可能性はあるが、設計変更を伴うため別途検証が必要 |
| ④`movable_append`をアセンブリ手書きに置き換え、引数をzero page直接受け渡し | 見積り: ▲60〜80%程度(未実測、推測) | JSR/RTS往復と引数再読出しパターンを完全排除できれば728cy→150〜300cy程度まで理論上は縮小可能。ただし`-Oirs`実測(23%減)ほどの現実の歩留まりになるかは未検証であり、過度な期待は禁物。呼び出し規約を手動制御する分、保守性・バグ混入リスクは上がる |

①は費用対効果が低いため非推奨。②は低リスクな追加検証候補。③④は設計判断・実装工数を伴うため、Fable5の次判断待ち。
