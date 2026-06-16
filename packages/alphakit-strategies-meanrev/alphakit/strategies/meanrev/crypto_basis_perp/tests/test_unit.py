"""Unit tests for crypto_basis_perp."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.crypto_basis_perp.strategy import CryptoBasisPerp


def _volatile_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    """High-vol crypto-like random walk."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0, 0.03, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["BTC", "ETH"])


def test_satisfies_protocol() -> None:
    assert isinstance(CryptoBasisPerp(), StrategyProtocol)


def test_metadata() -> None:
    s = CryptoBasisPerp()
    assert s.name == "crypto_basis_perp"
    assert s.family == "meanrev"
    assert s.fast_period == 5
    assert s.slow_period == 30
    assert s.threshold == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_period": 0}, "fast_period"),
        ({"slow_period": 0}, "slow_period"),
        ({"fast_period": 30, "slow_period": 30}, "fast_period.*slow_period"),
        ({"zscore_lookback": 1}, "zscore_lookback"),
        ({"threshold": 0.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CryptoBasisPerp(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["BTC"], dtype=float)
    assert CryptoBasisPerp().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _volatile_panel()
    s = CryptoBasisPerp(fast_period=5, slow_period=30, zscore_lookback=20)
    weights = s.generate_signals(prices)
    warmup = 30 + 20  # slow_period + zscore_lookback
    assert (weights.iloc[:warmup] == 0.0).all().all()


def test_volatile_data_generates_signals() -> None:
    prices = _volatile_panel(years=3)
    weights = CryptoBasisPerp(threshold=1.5).generate_signals(prices)
    mature = weights.iloc[60:]
    assert (mature != 0).any().any(), "Expected non-zero signals on volatile data"


def test_long_only_mode() -> None:
    prices = _volatile_panel()
    weights = CryptoBasisPerp(threshold=1.5, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _volatile_panel()
    weights = CryptoBasisPerp(threshold=1.5).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _volatile_panel()
    a = CryptoBasisPerp().generate_signals(prices)
    b = CryptoBasisPerp().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
