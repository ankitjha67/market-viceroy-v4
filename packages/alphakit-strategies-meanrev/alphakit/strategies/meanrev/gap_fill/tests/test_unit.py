"""Unit tests for gap_fill."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.gap_fill.strategy import GapFill


def _volatile_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0, 0.025, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["SPY", "EFA"])


def test_satisfies_protocol() -> None:
    assert isinstance(GapFill(), StrategyProtocol)


def test_metadata() -> None:
    s = GapFill()
    assert s.name == "gap_fill"
    assert s.family == "meanrev"
    assert s.lookback == 20
    assert s.gap_threshold == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"lookback": 1}, "lookback"),
        ({"gap_threshold": 0.0}, "gap_threshold"),
        ({"gap_threshold": -1.0}, "gap_threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        GapFill(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert GapFill().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _volatile_panel()
    weights = GapFill(lookback=20).generate_signals(prices)
    # First ~21 rows: 1 for pct_change NaN + 20 for rolling window warmup
    assert (weights.iloc[:21] == 0.0).all().all()


def test_volatile_data_generates_signals() -> None:
    """High-volatility data with a lower threshold should trigger gap signals."""
    prices = _volatile_panel()
    weights = GapFill(lookback=20, gap_threshold=1.5).generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature != 0.0).any().any(), "Expected nonzero gap-fill signals on volatile data"


def test_long_only_mode() -> None:
    prices = _volatile_panel()
    weights = GapFill(lookback=20, gap_threshold=1.5, long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_weights_bounded() -> None:
    """Weights should be in [-1/n, +1/n] per asset."""
    prices = _volatile_panel()
    weights = GapFill(lookback=20, gap_threshold=1.5).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _volatile_panel()
    a = GapFill().generate_signals(prices)
    b = GapFill().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
