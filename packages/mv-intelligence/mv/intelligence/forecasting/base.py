"""Forecaster protocol + the point-in-time fit guard (PRD §4.4, FR-I; CLAUDE.md #2/#3).

A forecaster turns a point-in-time feature panel into a forward forecast feature.
Two non-negotiables are enforced **before any fit**:

- **FRED no-train (FR-D11/BR-006):** a forecaster may not train on FRED-derived
  features — :func:`assert_no_fred_in_training` rejects them.
- **No look-ahead (CLAUDE.md #2):** training rows must be strictly *before* the
  as-of time; :func:`fit_window` slices the panel point-in-time so a forecast at
  ``t`` only ever sees data ``< t``.

The GBM forecaster (sklearn) is the deterministic default; the deep forecasters
are an optional offline extra with a GBM/rule-based fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
from mv.intelligence.guardrail import assert_no_fred_in_training


@runtime_checkable
class Forecaster(Protocol):
    """Fit on a point-in-time panel, predict the next-step forecast."""

    def fit(self, features: pd.DataFrame, target: pd.Series, *, sources: Sequence[str]) -> None:
        """Train; ``sources`` are the feature provenances (FRED-no-train check)."""
        ...

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Forecast for each row of ``features``."""
        ...


def guard_training_sources(sources: Sequence[str]) -> None:
    """Raise if any training source is FRED-derived (FR-D11/BR-006)."""
    assert_no_fred_in_training(sources)


def fit_window(
    features: pd.DataFrame, target: pd.Series, *, as_of: datetime
) -> tuple[pd.DataFrame, pd.Series]:
    """Slice ``(features, target)`` to rows **strictly before** ``as_of`` (no look-ahead).

    The index must be a ``DatetimeIndex``. Returns the point-in-time training
    window; a forecast made at ``as_of`` therefore never sees data at or after it.
    """
    if not isinstance(features.index, pd.DatetimeIndex):
        raise TypeError("features must have a DatetimeIndex for a point-in-time fit")
    mask = features.index < pd.Timestamp(as_of)
    return features.loc[mask], target.loc[mask]


__all__ = ["Forecaster", "fit_window", "guard_training_sources"]
