"""Tests for prediction and SHAP explanation generation."""

import numpy as np

from app.ml.config import FEATURE_LABEL_JA
from app.ml.predictor import _generate_explanation


class TestSHAPExplanation:
    """Test SHAP-based Japanese explanation generation."""

    def _make_feature_data(self):
        """Create sample feature names and values."""
        import pandas as pd

        feature_names = [
            "horse_avg_finish_3", "jockey_win_rate", "win_odds",
            "distance_m", "horse_age",
        ]
        feature_row = pd.Series(
            [2.5, 0.15, 8.0, 1600, 3],
            index=feature_names,
        )
        return feature_names, feature_row

    def test_explanation_starts_with_prefix(self):
        """Explanation should start with 'この馬の予想根拠:'."""
        feature_names, feature_row = self._make_feature_data()
        shap_values = np.array([0.15, 0.10, -0.08, 0.03, -0.02])

        result = _generate_explanation(shap_values, feature_names, feature_row)
        assert result.startswith("この馬の予想根拠:"), \
            f"Expected prefix 'この馬の予想根拠:', got: {result[:20]}"

    def test_explanation_uses_japanese_labels(self):
        """Explanation should use Japanese labels from FEATURE_LABEL_JA."""
        feature_names, feature_row = self._make_feature_data()
        shap_values = np.array([0.15, 0.10, -0.08, 0.03, -0.02])

        result = _generate_explanation(shap_values, feature_names, feature_row)

        # Top feature by abs SHAP is horse_avg_finish_3 (0.15)
        expected_ja = FEATURE_LABEL_JA["horse_avg_finish_3"]
        assert expected_ja in result, \
            f"Expected '{expected_ja}' in explanation, got: {result}"

    def test_explanation_shows_direction(self):
        """Positive SHAP should show '高い', negative should show '低い'."""
        feature_names, feature_row = self._make_feature_data()
        shap_values = np.array([0.15, -0.10, 0.08, 0.03, -0.02])

        result = _generate_explanation(shap_values, feature_names, feature_row)

        # horse_avg_finish_3 has +0.15 → 高い
        assert "高い" in result, f"Expected '高い' for positive SHAP, got: {result}"
        # jockey_win_rate has -0.10 → 低い
        assert "低い" in result, f"Expected '低い' for negative SHAP, got: {result}"

    def test_explanation_respects_top_n(self):
        """Should only include top_n features."""
        feature_names, feature_row = self._make_feature_data()
        shap_values = np.array([0.15, 0.10, -0.08, 0.03, -0.02])

        result = _generate_explanation(
            shap_values, feature_names, feature_row, top_n=2,
        )

        # Should have exactly 2 reasons (separated by '、')
        reasons = result.replace("この馬の予想根拠: ", "").split("、")
        assert len(reasons) == 2, \
            f"Expected 2 reasons with top_n=2, got {len(reasons)}: {reasons}"

    def test_explanation_contains_shap_values(self):
        """Explanation should include numeric SHAP contribution values."""
        feature_names, feature_row = self._make_feature_data()
        shap_values = np.array([0.15, 0.10, -0.08, 0.03, -0.02])

        result = _generate_explanation(shap_values, feature_names, feature_row)

        assert "+0.150" in result, f"Expected '+0.150' in explanation, got: {result}"
