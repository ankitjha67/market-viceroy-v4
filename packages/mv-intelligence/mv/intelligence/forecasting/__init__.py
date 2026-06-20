"""Forecasting layer (PRD §4.4) — point-in-time, leakage-checked, no-FRED-train.

:class:`~mv.intelligence.forecasting.gbm.GBMForecaster` is the deterministic
default; :class:`~mv.intelligence.forecasting.deep.FinBERTSentiment` /
:class:`~mv.intelligence.forecasting.deep.LSTMForecaster` are the optional offline
deep forecasters (``forecasting-deep`` extra) with deterministic fallbacks.
"""

from __future__ import annotations

from mv.intelligence.forecasting.base import Forecaster, fit_window, guard_training_sources
from mv.intelligence.forecasting.deep import FinBERTSentiment, LSTMForecaster
from mv.intelligence.forecasting.gbm import GBMForecaster

__all__ = [
    "FinBERTSentiment",
    "Forecaster",
    "GBMForecaster",
    "LSTMForecaster",
    "fit_window",
    "guard_training_sources",
]
