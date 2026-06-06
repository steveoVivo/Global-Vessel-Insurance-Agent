"""Holt's linear trend prediction with walk-forward validation.

Usage (evaluation):
    python temporal_trend_prediction.py

Usage (from data_pipeline):
    from temporal_trend_prediction import predict, walk_forward_validate
"""
import warnings
from dataclasses import dataclass, field

from statsmodels.tsa.holtwinters import Holt

MIN_TRAIN_POINTS = 5   # minimum points needed to fit the model
HORIZON          = 3   # years to forecast


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PredictedPoint:
    year: int
    accident_rate: float

    def to_dict(self) -> dict:
        return {
            "year":          self.year,
            "accident_rate": self.accident_rate,
        }


@dataclass
class ValidationRound:
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
    flag_key: str
    rounds:   list[ValidationRound] = field(default_factory=list)

    @property
    def mae(self) -> float:
        if not self.rounds:
            return float("nan")
        return sum(r.abs_error for r in self.rounds) / len(self.rounds)

    @property
    def mape(self) -> float:
        valid = [r for r in self.rounds if r.actual_rate > 0]
        if not valid:
            return float("nan")
        return sum(abs(r.error) / r.actual_rate for r in valid) / len(valid) * 100


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

class HoltTrendModel:
    """Wrapper around statsmodels Holt that fits on a rate series."""

    def __init__(self, rates: list[float]):
        if len(rates) < MIN_TRAIN_POINTS:
            raise ValueError(f"Need at least {MIN_TRAIN_POINTS} points, got {len(rates)}")
        self._rates = rates
        self._model_fit = None

    def fit(self) -> "HoltTrendModel":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._model_fit = Holt(
                self._rates, initialization_method="estimated"
            ).fit(optimized=True)
        return self

    def forecast(self, horizon: int = HORIZON) -> list[float]:
        if self._model_fit is None:
            raise RuntimeError("Call fit() first")
        raw = self._model_fit.forecast(horizon)
        return [max(0.0, float(v)) for v in raw]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict(yearly: list[dict], horizon: int = HORIZON) -> list[dict]:
    """Return Holt linear trend predictions for the next `horizon` years.

    Args:
        yearly: list of dicts with keys: year, accident_rate, exposure, has_fleet_data
        horizon: number of years to forecast

    Returns:
        list of dicts: [{year, accident_rate}, ...]
        Empty list if there are fewer than MIN_TRAIN_POINTS valid data points.
    """
    valid = [p for p in yearly if p["has_fleet_data"] and p["exposure"] > 0]
    if len(valid) < MIN_TRAIN_POINTS:
        return []

    rates     = [p["accident_rate"] for p in valid]
    last_year = valid[-1]["year"]

    try:
        model    = HoltTrendModel(rates).fit()
        forecast = model.forecast(horizon)
    except Exception:
        return []

    return [
        PredictedPoint(
            year          = last_year + i + 1,
            accident_rate = forecast[i],
        ).to_dict()
        for i in range(horizon)
    ]


def walk_forward_validate(yearly: list[dict], min_train: int = MIN_TRAIN_POINTS) -> ValidationResult | None:
    """Walk-forward (expanding window) validation.

    For each step from min_train to len(valid)-1:
        - Train on valid[0:t]
        - Predict valid[t]
        - Compare against actual

    Returns None if there are not enough points for even one validation round.
    """
    valid = [p for p in yearly if p["has_fleet_data"] and p["exposure"] > 0]
    if len(valid) <= min_train:
        return None

    flag_key = yearly[0].get("flag_key", "unknown") if yearly else "unknown"
    result   = ValidationResult(flag_key=flag_key)

    for t in range(min_train, len(valid)):
        train_rates = [p["accident_rate"] for p in valid[:t]]
        actual_rate = valid[t]["accident_rate"]
        train_end   = valid[t - 1]["year"]

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
