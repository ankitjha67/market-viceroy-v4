"""Unit tests for ichimoku_cloud."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.ichimoku_cloud.strategy import IchimokuCloud


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(IchimokuCloud(), StrategyProtocol)


def test_metadata() -> None:
    s = IchimokuCloud()
    assert s.name == "ichimoku_cloud"
    assert s.family == "trend"
    assert s.tenkan_window == 9
    assert s.kijun_window == 26
    assert s.senkou_b_window == 52


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"tenkan_window": 0}, "tenkan_window"),
        ({"kijun_window": 9, "tenkan_window": 9}, "kijun_window.*tenkan_window"),
        ({"senkou_b_window": 26, "kijun_window": 26}, "senkou_b_window.*kijun_window"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        IchimokuCloud(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert IchimokuCloud().generate_signals(empty).empty


def test_uptrend_is_long_after_warmup() -> None:
    """On a monotone uptrend the close is always above its own past
    highs → above the cloud → long signal."""
    prices = _panel({"SPY": 0.001}, years=2)
    weights = IchimokuCloud().generate_signals(prices)
    # Warmup: 52 (senkou_b) + 26 (projection) = 78 bars.
    mature = weights.iloc[80:]
    assert (mature > 0).all().all()


def test_downtrend_is_short_after_warmup() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = IchimokuCloud().generate_signals(prices)
    mature = weights.iloc[80:]
    assert (mature < 0).all().all()


def test_long_only_on_downtrend_is_flat() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = IchimokuCloud(long_only=True).generate_signals(prices)
    assert (weights.iloc[80:] == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001}, years=2)
    weights = IchimokuCloud().generate_signals(prices)
    # Before the cloud is computable (< 52 + 26 bars).
    assert (weights.iloc[:50] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = IchimokuCloud().generate_signals(prices)
    b = IchimokuCloud().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
