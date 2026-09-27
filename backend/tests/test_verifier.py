"""app.ml.verifier の ROI 計算のテスト（DB 不要）。

ROI は金銭に関わる計算なので、分母・分子・除外条件を個別に検証する。
"""

import pandas as pd

from app.ml.verifier import BET_UNIT_YEN, _win_roi


def _bets(rows: list[tuple]) -> pd.DataFrame:
    """(win_odds, actual_position) のリストから最小の DataFrame を作る。"""
    return pd.DataFrame(rows, columns=["win_odds", "actual_position"])


class TestWinRoi:
    def test_single_win(self) -> None:
        """1点だけ賭けて的中 → ROI = オッズ（100円 × 3.0 / 100円）。"""
        r = _win_roi(_bets([(3.0, 1)]))
        assert r["bets"] == 1
        assert r["stake"] == BET_UNIT_YEN
        assert r["payout"] == 300
        assert r["roi"] == 3.0

    def test_all_losses(self) -> None:
        r = _win_roi(_bets([(3.0, 2), (5.0, 8)]))
        assert r["payout"] == 0
        assert r["roi"] == 0.0
        assert r["stake"] == 2 * BET_UNIT_YEN

    def test_mixed(self) -> None:
        """2点賭けて1点的中(2.0倍) → 払戻200 / 賭金200 = 1.0。"""
        r = _win_roi(_bets([(2.0, 1), (9.0, 5)]))
        assert r["roi"] == 1.0

    def test_pending_race_is_excluded(self) -> None:
        """
        着順未確定（actual_position が NaN）の行を分母に入れないこと。

        ⚠️ 回帰テスト。オッズ取得ジョブは結果より先に win_odds を埋めるため、
        除外しないと未確定レースが「賭けたがハズレ」として ROI を押し下げる
        （codex レビューで検出）。
        """
        r = _win_roi(_bets([(3.0, 1), (4.0, None)]))
        assert r["bets"] == 1, "未確定レースが分母に入っている"
        assert r["skipped"] == 1
        assert r["roi"] == 3.0

    def test_missing_odds_is_excluded(self) -> None:
        """オッズが無い行は賭けられないので除外すること。"""
        r = _win_roi(_bets([(3.0, 1), (None, 1)]))
        assert r["bets"] == 1
        assert r["skipped"] == 1

    def test_zero_or_negative_odds_is_excluded(self) -> None:
        r = _win_roi(_bets([(0.0, 1), (-1.0, 1)]))
        assert r["bets"] == 0
        assert r["roi"] is None, "賭けが0件なら ROI は None（0.0 と区別する）"

    def test_empty_returns_none_not_zero(self) -> None:
        """
        賭けが0件のとき ROI は None。

        0.0 を返すと「賭けたが全部外れた」と区別できず、
        beats_takeout の判定を誤らせる。
        """
        r = _win_roi(_bets([]))
        assert r["roi"] is None
        assert r["stake"] == 0
