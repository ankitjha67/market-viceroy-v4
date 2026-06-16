"""Unit tests for crypto_funding_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.crypto_funding_carry.strategy import CryptoFundingCarry


def _crypto_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0, 0.03, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["BTC", "ETH"])


def test_satisfies_protocol() -> None:
    assert isinstance(CryptoFundingCarry(), StrategyProtocol)


def test_metadata() -> None:
    s = CryptoFundingCarry()
    assert s.name == "crypto_funding_carry"
    assert s.family == "carry"
    assert s.fast_period == 5
    assert s.slow_period == 30
    assert s.threshold == 0.005


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_period": 0}, "fast_period"),
        ({"slow_period": 0}, "slow_period"),
        ({"fast_period": 30, "slow_period": 30}, "fast_period.*slow_period"),
        ({"threshold": 0.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CryptoFundingCarry(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["BTC"], dtype=float)
    assert CryptoFundingCarry().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _crypto_panel()
    weights = CryptoFundingCarry(fast_period=5, slow_period=30).generate_signals(prices)
    # rolling(30, min_periods=30) → first valid at index 29, so first 29 rows zero
    assert (weights.iloc[:29] == 0.0).all().all()


def test_volatile_data_generates_signals() -> None:
    prices = _crypto_panel(years=3)
    weights = CryptoFundingCarry(threshold=0.003).generate_signals(prices)
    mature = weights.iloc[35:]
    assert (mature != 0).any().any(), "Expected non-zero signals"


def test_long_only_mode() -> None:
    prices = _crypto_panel()
    weights = CryptoFundingCarry(threshold=0.003, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _crypto_panel()
    weights = CryptoFundingCarry(threshold=0.003).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _crypto_panel()
    a = CryptoFundingCarry().generate_signals(prices)
    b = CryptoFundingCarry().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
