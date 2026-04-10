"""Tests for core/ml/predictor.py — time-series prediction."""

import pytest

from core.ml.predictor import TimeSeriesPredictor, PredictionResult


class TestMovingAveragePredictor:
    """Test the moving-average fallback prediction."""

    def test_predict_simple_series(self):
        predictor = TimeSeriesPredictor()
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        values = [100.0, 102.0, 104.0, 106.0, 108.0]

        result = predictor.predict(dates, values, horizon_days=3)
        assert result is not None
        assert isinstance(result, PredictionResult)
        assert result.method == "moving_average"
        assert result.predicted_value > 0
        assert result.confidence_lower <= result.predicted_value
        assert result.confidence_upper >= result.predicted_value
        assert result.horizon_days == 3
        assert result.data_points_used == 5

    def test_predict_stable_series(self):
        predictor = TimeSeriesPredictor()
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
        values = [100.0, 100.0, 100.0, 100.0]

        result = predictor.predict(dates, values, horizon_days=7)
        assert result is not None
        # Stable series should predict close to 100
        assert abs(result.predicted_value - 100.0) < 10.0

    def test_predict_insufficient_data(self):
        predictor = TimeSeriesPredictor()
        dates = ["2024-01-01", "2024-01-02"]
        values = [100.0, 102.0]

        result = predictor.predict(dates, values)
        assert result is None

    def test_predict_mismatched_lengths(self):
        predictor = TimeSeriesPredictor()
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        values = [100.0, 102.0]

        result = predictor.predict(dates, values)
        assert result is None

    def test_predict_upward_trend(self):
        predictor = TimeSeriesPredictor()
        dates = [f"2024-01-{i:02d}" for i in range(1, 11)]
        values = [100.0 + i * 10 for i in range(10)]

        result = predictor.predict(dates, values, horizon_days=5)
        assert result is not None
        # Should predict higher than last value
        assert result.predicted_value > values[-1] * 0.8

    def test_predict_downward_trend(self):
        predictor = TimeSeriesPredictor()
        dates = [f"2024-01-{i:02d}" for i in range(1, 11)]
        values = [200.0 - i * 5 for i in range(10)]

        result = predictor.predict(dates, values, horizon_days=3)
        assert result is not None
        # Should predict lower than last value
        assert result.predicted_value < values[0]

    def test_prediction_result_fields(self):
        result = PredictionResult(
            predicted_value=105.5,
            confidence_lower=100.0,
            confidence_upper=111.0,
            method="moving_average",
            horizon_days=7,
            data_points_used=30,
        )
        assert result.predicted_value == 105.5
        assert result.method == "moving_average"
        assert result.horizon_days == 7
