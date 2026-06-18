"""Unit tests for walk-forward (synthetic prices; proves no look-ahead)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bench.validation.walk_forward import walk_forward
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226

_SYMBOL = "SPY"


def _prices(n: int, *, seed: int = 0, drift: float = 0.0005) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 0.01, n)
    series = 100.0 * np.exp(np.cumsum(steps))
    index = pd.date_range("2010-01-01", periods=n, freq="B")
    return pd.DataFrame({_SYMBOL: series}, index=index)


def test_walk_forward_produces_windows() -> None:
    result = walk_forward(
        EMACross1226(long_only=True),
        _prices(500),
        test_size=60,
        step=60,
        min_train=120,
    )
    assert len(result.windows) >= 4
    assert result.oos_returns.size == sum(w.n_obs for w in result.windows)
    assert np.isfinite(result.aggregate_sharpe)
    assert 0.0 <= result.positive_window_fraction <= 1.0
    assert np.isfinite(result.worst_window_sharpe)


def test_no_look_ahead() -> None:
    # Mutating prices AFTER an early window's end must not change that window.
    base = _prices(500, seed=1)
    mutated = base.copy()
    mutated.iloc[300:] *= 1.5  # arbitrary future shock

    r_base = walk_forward(EMACross1226(long_only=True), base, test_size=60, step=60, min_train=120)
    r_mut = walk_forward(
        EMACross1226(long_only=True), mutated, test_size=60, step=60, min_train=120
    )
    # Windows entirely before index 300 are identical (no future leakage).
    for wb, wm in zip(r_base.windows, r_mut.windows, strict=False):
        if wb.end <= 300:
            assert wb.sharpe == pytest.approx(wm.sharpe, abs=1e-9)


def test_rejects_insufficient_data() -> None:
    with pytest.raises(ValueError, match="not enough data"):
        walk_forward(
            EMACross1226(long_only=True), _prices(100), test_size=60, step=30, min_train=252
        )


def test_rejects_bad_sizes() -> None:
    with pytest.raises(ValueError, match="positive"):
        walk_forward(EMACross1226(long_only=True), _prices(500), test_size=0, step=10)
