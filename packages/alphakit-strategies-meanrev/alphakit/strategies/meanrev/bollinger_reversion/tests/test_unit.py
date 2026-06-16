"""Unit tests for bollinger_reversion."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.bollinger_reversion.strategy import BollingerReversion


def _panel(drifts: dict[str, float], years: float = 1, noise: float = 0.0) -> pd.DataFrame:
    """Synthetic price panel with exponential drift + optional noise."""
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            sym: 100.0 * np.exp(drift * np.arange(n) + noise * rng.standard_normal(n))
            for sym, drift in drifts.items()
        },
        index=idx,
    )


def _mean_reverting_panel(symbols: list[str], years: float = 2, seed: int = 42) -> pd.DataFrame:
    """Synthetic prices that oscillate around a stable mean — ideal for Bollinger."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data: dict[str, np.ndarray] = {}
    for sym in symbols:
        # OU-like process: dx = theta*(mu - x)*dt + sigma*dW
        x = np.zeros(n)
        x[0] = 100.0
        for i in range(1, n):
            x[i] = x[i - 1] + 0.1 * (100.0 - x[i - 1]) + 2.0 * rng.standard_normal()
        data[sym] = np.maximum(x, 1.0)  # keep positive
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(BollingerReversion(), StrategyProtocol)


def test_metadata() -> None:
    s = BollingerReversion()
    assert s.name == "bollinger_reversion"
    assert s.family == "meanrev"
    assert s.period == 20
    assert s.num_std == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"period": 0}, "period"),
        ({"period": 1}, "period"),
        ({"num_std": 0.0}, "num_std"),
        ({"num_std": -1.0}, "num_std"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        BollingerReversion(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert BollingerReversion().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _mean_reverting_panel(["SPY"])
    weights = BollingerReversion(period=20).generate_signals(prices)
    # First 19 bars (period-1) must be zero due to rolling window warmup
    assert (weights.iloc[:19] == 0.0).all().all()


def test_mean_reverting_generates_signals() -> None:
    """A mean-reverting series should trigger both long and short signals."""
    prices = _mean_reverting_panel(["SPY", "EFA"], years=3)
    weights = BollingerReversion(period=20, num_std=1.5).generate_signals(prices)
    mature = weights.iloc[25:]
    # Must have some long signals (positive weights)
    assert (mature > 0).any().any(), "Expected some long signals on mean-reverting data"
    # Must have some short signals (negative weights)
    assert (mature < 0).any().any(), "Expected some short signals on mean-reverting data"


def test_noisy_uptrend_triggers_overbought() -> None:
    """A noisy uptrend should breach the upper band on large up-jumps."""
    # Smooth drifts never breach Bollinger bands — noise is needed.
    prices = _panel({"SPY": 0.002}, years=2, noise=0.02)
    weights = BollingerReversion(period=20, num_std=1.5).generate_signals(prices)
    mature = weights.iloc[30:]
    # Noisy uptrend → occasional price above upper band → short signals
    assert (mature < 0).any().any(), "Expected overbought (short) signals in noisy uptrend"


def test_long_only_mode() -> None:
    """long_only=True should clip all short signals to zero."""
    prices = _mean_reverting_panel(["SPY"], years=3)
    weights = BollingerReversion(period=20, num_std=1.5, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    """Weights should be in [-1/n, +1/n] per asset."""
    prices = _mean_reverting_panel(["SPY", "EFA", "AGG"], years=2)
    weights = BollingerReversion(period=20, num_std=1.5).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _mean_reverting_panel(["SPY", "EFA"])
    a = BollingerReversion().generate_signals(prices)
    b = BollingerReversion().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_custom_parameters() -> None:
    """Strategy respects custom period and num_std."""
    s = BollingerReversion(period=30, num_std=1.5)
    assert s.period == 30
    assert s.num_std == 1.5
    prices = _mean_reverting_panel(["SPY"], years=2)
    weights = s.generate_signals(prices)
    # Warmup matches custom period
    assert (weights.iloc[:29] == 0.0).all().all()
