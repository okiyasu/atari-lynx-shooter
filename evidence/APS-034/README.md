# APS-034 Gearlynx表示検証

- 実行日: 2026-08-09 JST
- emulator: Gearlynx 1.2.21、headless MCP
- ROM: `dist/asteroid-patrol.lnx`、53,477 bytes
- ROM SHA-256: `07e96cb7f79cd57407606e7f70e2fa9529a1e35dedb31a524dcece9b0465bb2f`
- 実行: `python3 scripts/verify-stage-visuals-gearlynx.py`

最終ROMとsymbol/mapをGearlynxへ読み込み、安定したTITLE到達を短間隔pollしてpauseした。main BSS内の`GameState`をStage introまたはwarning終端へ設定後、`phase`へのCPU write breakpointでゲーム本体の正規NORMAL/BOSS遷移を通過前に捕捉した。続けて`_game_update_logic`のexecute breakpointを8回捕捉し、300Hz logic 2描画分を進めてtarget phase描画とdouble-buffer swapを完了させた。hostの固定`time.sleep()`はphase判定・描画同期に使用しない。

各画面でStage番号・phaseを、BOSSでは`boss.active=1`を検査した。MIKEY palette register `0xFDA0..0xFDBF`の32 bytesをgenerator出力と照合し、front bufferの自機・通常敵またはboss・Stage固有背景・色付きspriteを目視後にPNG保存した。2026-08-09、SHA-256 `07e96cb7f79cd57407606e7f70e2fa9529a1e35dedb31a524dcece9b0465bb2f`の同一ROMで連続2回、全6画面の検査に成功した。BIOS/外部ROMは取得・使用していない。

| Stage | NORMAL | BOSS |
|---|---|---|
| 1 | `stage1-normal.png` | `stage1-boss.png` |
| 2 | `stage2-normal.png` | `stage2-boss.png` |
| 3 | `stage3-normal.png` | `stage3-boss.png` |

headless state注入による表示回帰であり、INTRO/WARNING終端からNORMAL/BOSSへの正規遷移、生成palette、active boss、遷移後のfront bufferを検査する。Stage 1開始からStage 3までの連続実プレイ、通常phase全尺、Atari Lynx実機の性能・ちらつき・視認性は未確認。
