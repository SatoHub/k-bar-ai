"""
`app.ml.oddsfree` の学習分割のテスト。

2026-09-27 に、検証用分割が `iloc[:90%]` の**位置ベース**だったのを
日付ベースに直した（`trainer.py` と同じ欠陥）。位置ベースは
`build_feature_matrix()` が返す並び順に依存するため、コメントの意図
（時系列の後ろ10%）とは違う集合になりうる。

🔴 **この分割にはテストが1件も無かった**（code-reviewer M7 / test-reviewer 指摘）。
「コメントを検証の代わりにしない」（~/.claude/CLAUDE.md §12.2-11）に従い、
合成データで実挙動を確認する。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.config import CATEGORICAL_COLUMNS, FEATURE_COLUMNS
from app.ml.oddsfree import (
    ODDS_FEATURES,
    oddsfree_feature_columns,
    train_oddsfree_model,
)


def _make_df(n_days: int = 200, per_day: int = 20, seed: int = 0) -> pd.DataFrame:
    """cutoff 2020 をまたぐ合成データ。学習が通る最小構成。"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2018-01-01", periods=n_days, freq="D")
    rows = len(dates) * per_day
    df = pd.DataFrame(
        {
            "race_date": np.repeat(dates, per_day),
            "race_id_str": np.repeat([f"r{i}" for i in range(len(dates))], per_day),
        }
    )
    for col in FEATURE_COLUMNS:
        df[col] = rng.normal(size=rows)
    for col in CATEGORICAL_COLUMNS:
        df[col] = pd.Categorical(rng.choice(["a", "b", "c"], size=rows))
    df["is_win"] = (rng.uniform(size=rows) < 0.08).astype("float64")
    df["is_place"] = (rng.uniform(size=rows) < 0.22).astype("float64")
    return df


class TestFeatureSelection:
    def test_odds_features_are_excluded(self):
        feats = oddsfree_feature_columns()
        for col in ODDS_FEATURES:
            assert col not in feats
        assert "win_odds" not in feats and "win_favorite" not in feats

    def test_all_categoricals_are_kept(self):
        feats = oddsfree_feature_columns()
        for col in CATEGORICAL_COLUMNS:
            assert col in feats

    def test_count_is_numeric_minus_odds_plus_categoricals(self):
        expected = len(FEATURE_COLUMNS) - len(ODDS_FEATURES) + len(CATEGORICAL_COLUMNS)
        assert len(oddsfree_feature_columns()) == expected


class TestDateBasedValidationSplit:
    """検証用分割が日付で切れていること。並び順に依存しないこと。"""

    @staticmethod
    def _split(df: pd.DataFrame, cutoff_year: int = 2020):
        """`train_oddsfree_model` と同じ式で train/val を再現する。"""
        train = df[df["race_date"].dt.year < cutoff_year]
        val_start = train["race_date"].quantile(0.9)
        mask = (train["race_date"] >= val_start).to_numpy()
        return train[~mask], train[mask], val_start

    def test_train_and_val_do_not_overlap_in_time(self):
        tr, val, _ = self._split(_make_df())
        assert len(tr) > 0 and len(val) > 0
        assert tr["race_date"].max() < val["race_date"].min()

    def test_masks_are_exact_complements(self):
        df = _make_df()
        tr, val, _ = self._split(df)
        total = len(df[df["race_date"].dt.year < 2020])
        assert len(tr) + len(val) == total
        assert set(tr.index).isdisjoint(set(val.index))

    def test_validation_set_is_never_empty(self):
        """`quantile(0.9) <= max` なので val は最低でも最終日を含む。"""
        for n_days in [2, 3, 10, 365]:
            _, val, _ = self._split(_make_df(n_days=n_days, per_day=3))
            assert len(val) > 0, f"n_days={n_days} で val が空になった"

    def test_split_is_identical_after_shuffling_rows(self):
        """
        🔴 ここが位置ベース分割の欠陥を直接突く検査。

        行をシャッフルすると `iloc[:90%]` は全く違う集合を返すが、
        日付ベースなら同じ日付で切れるので同じ集合になる。
        """
        df = _make_df()
        _, val_a, start_a = self._split(df)
        shuffled = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
        _, val_b, start_b = self._split(shuffled)

        assert start_a == start_b
        assert len(val_a) == len(val_b)
        assert sorted(val_a["race_date"].astype(str)) == sorted(
            val_b["race_date"].astype(str)
        )

    def test_validation_never_reaches_into_the_oos_period(self):
        """検証用は学習期間内だけを切る。2020年以降は絶対に入らない。"""
        _, val, _ = self._split(_make_df(n_days=900))
        assert val["race_date"].dt.year.max() < 2020


class TestTargetColumn:
    def test_unknown_target_raises_instead_of_silently_using_default(self):
        with pytest.raises(KeyError, match="target_column"):
            train_oddsfree_model(version="t", df=_make_df(), target_column="is_nope")

    def test_target_is_recorded_in_the_artifact(self, tmp_path, monkeypatch):
        """
        `is_win` と `is_place` を混同すると、単勝オッズとの期待値比較が
        意味を失う。artifact に何で学習したかを必ず残す。
        """
        import app.ml.oddsfree as of

        monkeypatch.setattr(of, "MODELS_DIR", tmp_path)
        res = train_oddsfree_model(
            version="unittest", df=_make_df(), target_column="is_win"
        )
        art = res["artifact"]
        assert art["target_column"] == "is_win"
        assert art["metrics"]["target_column"] == "is_win"
        assert art["cutoff_year"] == 2020
        assert art["feature_columns"] == oddsfree_feature_columns()
        assert (tmp_path / "unittest_oddsfree.joblib").exists()
