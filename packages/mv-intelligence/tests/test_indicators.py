"""Unit tests for the technical indicators (known values + causality)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from mv.intelligence.indicators import (
    bollinger_percent_b,
    drawdown,
    ema,
    macd,
    momentum,
    rolling_volatility,
    rsi,
    sma,
    zscore,
)

_SYM = "AAPL"


def _frame(values: list[float]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(values), freq="B")
    return pd.DataFrame({_SYM: values}, index=index)


def test_sma_known_value() -> None:
    out = sma(_frame([1.0, 2.0, 3.0, 4.0]), 2)
    assert np.isnan(out[_SYM].iloc[0])
    assert out[_SYM].iloc[1] == 1.5
    assert out[_SYM].iloc[3] == 3.5


def test_ema_first_valid_equals_sma_seed() -> None:
    out = ema(_frame([1.0, 2.0, 3.0]), 3)
    # adjust=False, min_periods=3 -> first two NaN, third defined.
    assert out[_SYM].iloc[:2].isna().all()
    assert np.isfinite(out[_SYM].iloc[2])


def test_momentum() -> None:
    out = momentum(_frame([100.0, 100.0, 200.0]), 2)
    assert out[_SYM].iloc[2] == 1.0  # doubled over 2 bars


def test_rsi_all_gains_is_100() -> None:
    out = rsi(_frame([float(i) for i in range(1, 20)]), 14)
    assert out[_SYM].iloc[-1] == 100.0


def test_rsi_all_losses_is_0() -> None:
    out = rsi(_frame([float(i) for i in range(20, 1, -1)]), 14)
    assert out[_SYM].iloc[-1] == 0.0


def test_drawdown_at_peak_is_zero_then_negative() -> None:
    out = drawdown(_frame([100.0, 110.0, 99.0]))
    assert out[_SYM].iloc[1] == 0.0  # new high
    assert out[_SYM].iloc[2] == pytest.approx(99.0 / 110.0 - 1.0)


def test_zscore_centered() -> None:
    out = zscore(_frame([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    assert np.isfinite(out[_SYM].iloc[-1])


def test_macd_and_bollinger_shapes() -> None:
    prices = _frame([float(i) for i in range(1, 40)])
    assert macd(prices).shape == prices.shape
    assert rolling_volatility(prices, 5).shape == prices.shape
    pb = bollinger_percent_b(prices, 20)
    assert pb.shape == prices.shape


def test_indicators_are_causal() -> None:
    # Mutating a FUTURE bar must not change an earlier indicator value.
    base = _frame([float(i) for i in range(1, 30)])
    mutated = base.copy()
    mutated.iloc[25:] *= 2.0
    a = sma(base, 5)[_SYM].iloc[:20]
    b = sma(mutated, 5)[_SYM].iloc[:20]
    pd.testing.assert_series_equal(a, b)
