"""Generic time-series predictor — Prophet with moving-average fallback.

Domain plugins use this for any kind of time-series forecasting
(prices, demand, health metrics, etc.).

Graceful degradation: if Prophet is not installed, uses simple
moving-average prediction.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Optional: only import prophet if available
try:
    from prophet import Prophet

    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.info("prophet not installed — using moving-average fallback for predictions")


@dataclass
class PredictionResult:
    """Result of a time-series prediction."""

    predicted_value: float
    confidence_lower: float
    confidence_upper: float
    method: str  # "prophet" or "moving_average"
    horizon_days: int
    data_points_used: int


class TimeSeriesPredictor:
    """Predicts future values from historical time-series data.

    Uses Prophet when available, falls back to moving-average.
    """

    def predict(
        self,
        dates: list[str | datetime],
        values: list[float],
        horizon_days: int = 7,
    ) -> PredictionResult | None:
        """Predict future value from historical data.

        Args:
            dates: List of date strings (YYYY-MM-DD) or datetime objects.
            values: List of corresponding numeric values.
            horizon_days: Number of days ahead to predict.

        Returns:
            PredictionResult or None if insufficient data.
        """
        if len(dates) < 3 or len(dates) != len(values):
            logger.warning(
                "Insufficient data for prediction: %d dates, %d values",
                len(dates),
                len(values),
            )
            return None

        if PROPHET_AVAILABLE:
            try:
                return self._prophet_predict(dates, values, horizon_days)
            except Exception as exc:
                logger.warning("Prophet prediction failed, falling back: %s", exc)

        return self._moving_average_predict(values, horizon_days)

    def _prophet_predict(
        self,
        dates: list[str | datetime],
        values: list[float],
        horizon_days: int,
    ) -> PredictionResult:
        """Predict using Facebook Prophet."""
        import pandas as pd

        df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": values})

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=horizon_days)
        forecast = model.predict(future)

        last_row = forecast.iloc[-1]
        return PredictionResult(
            predicted_value=round(float(last_row["yhat"]), 2),
            confidence_lower=round(float(last_row["yhat_lower"]), 2),
            confidence_upper=round(float(last_row["yhat_upper"]), 2),
            method="prophet",
            horizon_days=horizon_days,
            data_points_used=len(values),
        )

    def _moving_average_predict(
        self,
        values: list[float],
        horizon_days: int,
    ) -> PredictionResult:
        """Simple moving-average fallback prediction."""
        window = min(7, len(values))
        recent = values[-window:]
        avg = sum(recent) / len(recent)

        # Estimate trend from recent data
        if len(recent) >= 3:
            trend = (recent[-1] - recent[0]) / len(recent)
        else:
            trend = 0.0

        predicted = avg + trend * horizon_days

        # Simple confidence interval based on data spread
        spread = max(recent) - min(recent) if len(recent) > 1 else avg * 0.1
        margin = spread * 0.5

        return PredictionResult(
            predicted_value=round(predicted, 2),
            confidence_lower=round(predicted - margin, 2),
            confidence_upper=round(predicted + margin, 2),
            method="moving_average",
            horizon_days=horizon_days,
            data_points_used=len(values),
        )
