"""Gradient-boosting forecaster (the deterministic CI default; PRD §4.4).

A seeded scikit-learn ``GradientBoostingRegressor`` over point-in-time features —
**deterministic** (fixed ``random_state`` → identical predictions across runs),
**FRED-no-train** guarded, and **leakage-free** (trains only on the point-in-time
window). This is the forecaster the per-push gate exercises and the fallback the
deep forecasters degrade to. Money/forecasts are plain floats (vectorized math).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from mv.intelligence.forecasting.base import guard_training_sources


class GBMForecaster:
    """A seeded gradient-boosting forecaster (deterministic, FRED-no-train)."""

    def __init__(self, *, seed: int = 0, n_estimators: int = 100, max_depth: int = 3) -> None:
        self._seed = seed
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._model: object | None = None

    def fit(self, features: pd.DataFrame, target: pd.Series, *, sources: Sequence[str]) -> None:
        """Train on ``(features, target)``; ``sources`` are checked for FRED."""
        guard_training_sources(sources)  # FR-D11/BR-006 — never train on FRED
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(
            random_state=self._seed,
            n_estimators=self._n_estimators,
            max_depth=self._max_depth,
        )
        model.fit(features.to_numpy(dtype=float), target.to_numpy(dtype=float))
        self._model = model

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Forecast for each row of ``features`` (raises if not yet fit)."""
        if self._model is None:
            raise RuntimeError("GBMForecaster.predict called before fit")
        out: np.ndarray = self._model.predict(features.to_numpy(dtype=float))  # type: ignore[attr-defined]
        return out


__all__ = ["GBMForecaster"]
