"""Unit tests for the regime-consistency criterion."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bench.validation.regime import regime_consistency


def _returns(values: np.ndarray) -> pd.Series:
    index = pd.date_range("2015-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=index)


def test_returns_three_regimes_and_worst() -> None:
    rng = np.random.default_rng(0)
    result = regime_consistency(_returns(rng.normal(0.0005, 0.01, 500)))
    assert set(result.per_regime) == {
        "bull_market_sharpe",
        "bear_market_sharpe",
        "sideways_sharpe",
    }
    assert result.worst_sharpe == min(result.per_regime.values())


def test_catastrophic_regime_fails_floor() -> None:
    rng = np.random.default_rng(1)
    # Strong negative drift -> at least one regime well below the floor.
    result = regime_consistency(_returns(rng.normal(-0.01, 0.02, 500)), floor=-0.5)
    assert result.passed is False
