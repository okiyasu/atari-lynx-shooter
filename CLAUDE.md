# Atari Lynx Shooter — 開発指示

- 対象は Atari Lynx（160x102、16色）。cc65 2.19 の公式 Lynx ターゲットを使用する。
- ROM は `cl65 -t lynx` で生成し、ツールチェーンはローカルキャッシュへ再現可能に構築する。
- `lynxboot.img`、BIOS、外部ROM、外部素材を取得・同梱・生成しない。
- ゲームロジックは可能な限りプラットフォーム非依存に保ち、ホスト側 clang テストを通す。
- 実装完了前にクリーンROMビルド、warnings-as-errors、ロジックテスト、LNXヘッダ検査を実行する。
- コミットおよびpushは禁止。依存物と生成物は `.gitignore` 対象にする。
- 作業実績、検証結果、設計との差分、未確認事項は `ISSUES.md` に記録する。

