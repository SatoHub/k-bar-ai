# Step 2 実装記録: 予想 → 照合 → 記録の自動化

**日付:** 2026-02-19

## 実装完了内容

### 新規パッケージ
- `lightgbm>=4.5.0`, `scikit-learn>=1.6.0`, `shap>=0.46.0`, `joblib>=1.4.0`

### 新規ファイル

| ファイル | 内容 |
|----------|------|
| `app/ml/__init__.py` | MLパッケージ初期化 |
| `app/ml/config.py` | ML設定定数（特徴量一覧、LGBMパラメータ、日本語ラベル） |
| `app/ml/features.py` | 特徴量エンジニアリング（shift(1)で未来漏洩防止） |
| `app/ml/trainer.py` | LightGBM学習パイプライン（時系列分割、early stopping） |
| `app/ml/predictor.py` | 予測 + SHAP日本語説明生成 |
| `app/ml/verifier.py` | 予測 vs 実績の照合 |
| `app/ml/evaluator.py` | モデル評価レポート |
| `app/schemas/prediction.py` | 予測APIスキーマ |
| `app/services/prediction_service.py` | 予測API用サービス層 |
| `app/api/v1/predictions.py` | 予測・モデルAPIエンドポイント |
| `tests/test_features.py` | 特徴量テスト（8テスト、漏洩検証含む） |
| `tests/test_predictor.py` | SHAP日本語説明テスト（5テスト） |

### 変更ファイル
- `pyproject.toml`: ML依存パッケージ追加
- `.gitignore`: `backend/models/` 追加
- `app/pipeline/cli.py`: train/predict/verify/evaluate コマンド追加
- `app/api/v1/__init__.py`: predictions router 登録
- `Makefile`: train/predict/verify-model/evaluate ターゲット追加

### APIエンドポイント
- `GET /api/v1/predictions/{race_id}` — レース予測取得
- `GET /api/v1/models` — モデル一覧
- `GET /api/v1/models/{version}/metrics` — モデル性能

### CLIコマンド
```bash
uv run python -m app.pipeline.cli train --version v1.0.0 --cutoff 2020
uv run python -m app.pipeline.cli predict --version v1.0.0 --date 2021-01-10
uv run python -m app.pipeline.cli verify --model-version v1.0.0
uv run python -m app.pipeline.cli evaluate --model-version v1.0.0
```

### テスト結果
- 全17テスト PASSED（既存4 + 新規13）
- ruff lint: All checks passed

## 次のステップ
1. CSVデータがDBに入っている状態で `train --version v1.0.0` を実行
2. テストデータで `predict --date 2021-01-10` を実行
3. `verify --model-version v1.0.0` で照合
4. Step 3: フロントエンド構築（Next.js + Tailwind CSS 4）
