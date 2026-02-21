# K-Bar AI プロジェクトメモ

## プロジェクト概要
- 競馬AI予想アプリ（個人利用→将来外部公開）
- 方針書: `C:\Users\unoen\Downloads\競馬AI予想アプリ_総合方針まとめ_2.md`
- 進捗管理: `docs/progress.md`（セッション開始時に必ず確認）

## 技術スタック
- Backend: FastAPI + PostgreSQL + SQLAlchemy async + LightGBM
- Frontend: Next.js 15 + React 19 + Tailwind CSS 4
- ML: LightGBM + SHAP（日本語説明）

## セッション開始手順
1. `make dev-all` で Docker + API + Frontend を一括起動
2. `docs/progress.md` を確認して前回の状況を把握
3. CLAUDE.md にも起動手順あり

## 重要な決定事項（2026-02-20）
- データ取得: 方式C（netkeiba/Yahoo!スクレイピング + JRA-VAN後日追加）
- JRA-VANは実運用3ヶ月後から導入（開発中は不要）
- スクレイピングにはPlaywright使用、間隔3-10秒ランダム

## E2Eテスト状況（2026-02-21）
- DB マイグレーション適用済み、Playwright インストール済み
- 2/22(土) 36レース出馬表取得済み（フェブラリーS含む）
- AI予想497頭分生成済み
- オッズは前日深夜は未配信 → 朝以降にscrape-odds再実行
- racecourse_name/race_name が null → shutubaパーサー要調査

## 既知の問題
- features.py: `include_upcoming=True` で未来レースも含める修正済み
- bet_service.py: nullable フィールドクリア修正済み
- horse_service.py: 適性計算の未確定レース除外修正済み

## ユーザーの好み
- 日本語でのコミュニケーション
- コストを最小限に抑えたい
- 方針書に沿った段階的な開発を希望
- セッション間の継続性を重視（progress.md活用）
