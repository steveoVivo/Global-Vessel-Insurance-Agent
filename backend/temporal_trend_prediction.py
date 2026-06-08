"""Holt linear trend model for per-flag accident-rate forecasting.

The model is fitted on a flag's historical yearly accident rates and used to
project rates 3 years into the future.  Walk-forward (expanding-window)
validation is provided for offline evaluation.

Usage (standalone evaluation):
    python temporal_trend_prediction.py

Usage (from data_pipeline):
    from temporal_trend_prediction import predict
"""

import warnings
from dataclasses import dataclass, field

from statsmodels.tsa.holtwinters import Holt

# Minimum number of valid data points required to fit the model
MIN_TRAIN_POINTS = 5

# Number of years to project forward
FORECAST_HORIZON = 3


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PredictedPoint:
    """A single year's model-predicted accident rate."""
    year:          int
    accident_rate: float

    def to_dict(self) -> dict:
        return {"year": self.year, "accident_rate": self.accident_rate}


@dataclass
class ValidationRound:
    """One step of walk-forward validation: train up to train_end_year, predict the next."""
    train_end_year: int
    predicted_rate: float
    actual_rate:    float

    @property
    def error(self) -> float:
        return self.predicted_rate - self.actual_rate

    @property
    def abs_error(self) -> float:
        return abs(self.error)


@dataclass
class ValidationResult:
    """Aggregate walk-forward validation outcome for a single flag."""
    flag_key: str
    rounds:   list[ValidationRound] = field(default_factory=list)

    @property
    def mae(self) -> float:
        """Mean Absolute Error across all validation rounds."""
        if not self.rounds:
            return float("nan")
        return sum(r.abs_error for r in self.rounds) / len(self.rounds)

    @property
    def mape(self) -> float:
        """Mean Absolute Percentage Error, computed only over rounds where actual > 0."""
        valid_rounds = [r for r in self.rounds if r.actual_rate > 0]
        if not valid_rounds:
            return float("nan")
        return sum(abs(r.error) / r.actual_rate for r in valid_rounds) / len(valid_rounds) * 100


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

class HoltTrendModel:
    """Holt's linear exponential smoothing fitted to an accident-rate series.

    Wraps statsmodels Holt with automatic parameter optimization and clips
    forecasts to zero (accident rates cannot be negative).
    """

    def __init__(self, rates: list[float]):
        if len(rates) < MIN_TRAIN_POINTS:
            raise ValueError(f"Need at least {MIN_TRAIN_POINTS} points, got {len(rates)}")
        self._rates     = rates
        self._model_fit = None

    def fit(self) -> "HoltTrendModel":
        """Fit the model, suppressing convergence warnings from statsmodels."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model_fit = Holt(
                self._rates, initialization_method="estimated"
            ).fit(optimized=True)
        return self

    def forecast(self, horizon: int = FORECAST_HORIZON) -> list[float]:
        """Return `horizon` projected values, clipped to non-negative."""
        if self._model_fit is None:
            raise RuntimeError("Call fit() before forecast()")
        raw_forecast = self._model_fit.forecast(horizon)
        return [max(0.0, float(v)) for v in raw_forecast]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict(yearly_data: list[dict], horizon: int = FORECAST_HORIZON) -> list[dict]:
    """Forecast accident rates for the next `horizon` years using Holt's model.

    Args:
        yearly_data: list of dicts from compute_temporal_trends(), each with
                     keys: year, accident_rate, exposure, has_fleet_data.
        horizon:     number of years to project forward.

    Returns:
        List of {year, accident_rate} dicts for each projected year.
        Returns an empty list when there are fewer than MIN_TRAIN_POINTS valid points.
    """
    # Only use years where fleet data exists (exposure > 0 ensures a meaningful rate)
    valid_points = [p for p in yearly_data if p["has_fleet_data"] and p["exposure"] > 0]
    if len(valid_points) < MIN_TRAIN_POINTS:
        return []

    historical_rates = [p["accident_rate"] for p in valid_points]
    last_year        = valid_points[-1]["year"]

    try:
        model         = HoltTrendModel(historical_rates).fit()
        forecast_vals = model.forecast(horizon)
    except Exception:
        return []

    return [
        PredictedPoint(year=last_year + i + 1, accident_rate=forecast_vals[i]).to_dict()
        for i in range(horizon)
    ]


def walk_forward_validate(
    yearly_data: list[dict],
    min_train: int = MIN_TRAIN_POINTS,
) -> ValidationResult | None:
    """Walk-forward (expanding-window) validation of the Holt model.

    Iterates from min_train to len(valid)-1, training on [0:t] and predicting t,
    then comparing against the actual value.

    Returns None if there are not enough valid points for at least one round.
    """
    valid_points = [p for p in yearly_data if p["has_fleet_data"] and p["exposure"] > 0]
    if len(valid_points) <= min_train:
        return None

    flag_key = yearly_data[0].get("flag_key", "unknown") if yearly_data else "unknown"
    result   = ValidationResult(flag_key=flag_key)

    for t in range(min_train, len(valid_points)):
        train_rates = [p["accident_rate"] for p in valid_points[:t]]
        actual_rate = valid_points[t]["accident_rate"]
        train_end   = valid_points[t - 1]["year"]

        try:
            model    = HoltTrendModel(train_rates).fit()
            forecast = model.forecast(horizon=1)
        except Exception:
            continue

        result.rounds.append(ValidationRound(
            train_end_year = train_end,
            predicted_rate = forecast[0],
            actual_rate    = actual_rate,
        ))

    return result if result.rounds else None
