# ツールチェーン調査

確認日: 2026-08-02

## cc65

- [cc65 Lynx固有資料](https://cc65.github.io/doc/lynx.html)は、`cl65 -t lynx -o game.lnx main.c`で起動可能なカートイメージを作れると説明している。
- 標準グラフィックドライバは`lynx-160-102-16.tgi`（160x102、16色、割り込み駆動ダブルバッファ）、標準ジョイスティックドライバは`lynx-stdjoy.joy`。
- [cc65 Users Guide](https://cc65.github.io/doc/cc65.html)の警告制御を使う。固定版2.19では警告種別`error`を有効にする`-W error`がwarnings-as-errors相当であり、現行資料の長形式`--warnings-as-errors`はまだ受理されない。
- [cc65 Releases](https://github.com/cc65/cc65/releases)と[Homebrew cc65](https://formulae.brew.sh/formula/cc65)を確認。安定版2.19をGitタグ`V2.19`、コミット`555282497c3ecf8b313d87d5973093af19c35bd5`に固定する。
- `scripts/install-cc65.sh`は第三者コードを`.cache/`へ浅く取得し、コミットを照合して`.cache/cc65-2.19/install`へビルド・インストールする。キャッシュはGit管理しない。
- タグ`V2.19`の公式ソースは、実行時のバージョン文字列を`cl65 V2.18 - Git 5552824`と表示する。タグ名と完全コミットを正として検証し、短縮コミット`5552824`もキャッシュ検査に使う。

## macOSエミュレータ

第一候補は[Gearlynx 1.2.21](https://github.com/drhelius/Gearlynx)。Apple Silicon/Intel版とHomebrew caskがあり、LNX/homebrew ROMとコマンドラインからのROM読込をサポートする。**動作にはBIOSが必須**で、公式READMEはオリジナルBIOS（MD5 `fcd403db69f54290b51035d82f835e7b`）を推奨する。

代替は[Mednafen 1.32.1 Lynx資料](https://mednafen.github.io/documentation/lynx.html)および[Homebrew formula](https://formulae.brew.sh/formula/mednafen)。**512バイトのLynx boot ROMを`lynxboot.img`という名前でMednafenベースディレクトリに置く必要がある**。

BIOS/boot ROMは著作権対象であり、本プロジェクトは取得、同梱、生成を一切行わない。ユーザーが合法的に用意したBIOSだけをエミュレータ側に設定する。
