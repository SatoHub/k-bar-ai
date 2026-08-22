# 仕様書（specs）

大規模変更・高リスク変更の**実装前**に仕様を固めるための置き場。

- ファイル名: `YYYYMMDD-<トピック>.md`
- テンプレートは `specification` スキル（`~/.claude/skills/specification/SKILL.md`）が持っている。
- **小さな修正で仕様書を作らないこと**（それ自体が Over Engineering）。

## ここに書くべきもの

- 認証・認可
- 既存データがある DB マイグレーション
- アーキテクチャ変更
- 複数システム連携（外部API・スクレイパー・スケジューラをまたぐもの）
- 大規模リファクタリング
- 後戻りが高コストな判断を含むもの

## ここに書かないもの

- 調査結果や学びのメモ → `docs/YYYYMMDD-トピック.md`
- 進捗 → `docs/progress.md`
- 既知バグ → `docs/20260228-bug-registry.md`
