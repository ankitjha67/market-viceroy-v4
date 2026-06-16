"""Unit tests for fx_carry_g10."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.fx_carry_g10.strategy import FXCarryG10


def _fx_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    """Synthetic FX panel with diverse drifts to create carry spread."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    # 9 G10 currencies with different drifts (carry proxy)
    syms = [
        "AUDUSD",
        "CADUSD",
        "CHFUSD",
        "EURUSD",
        "GBPUSD",
        "JPYUSD",
        "NOKUSD",
        "NZDUSD",
        "SEKUSD",
    ]
    data = {}
    for i, sym in enumerate(syms):
        drift = 0.0003 * (i - 4)  # range: -0.0012 to +0.0012
        noise = 0.008 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(FXCarryG10(), StrategyProtocol)


def test_metadata() -> None:
    s = FXCarryG10()
    assert s.name == "fx_carry_g10"
    assert s.family == "carry"
    assert s.lookback == 63
    assert s.n_long == 3
    assert s.n_short == 3


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"n_long": 0}, "n_long"),
        ({"n_short": 0}, "n_short"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FXCarryG10(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["EURUSD"], dtype=float)
    assert FXCarryG10().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2018-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"EURUSD": 100.0 + np.arange(200) * 0.01}, index=idx)
    weights = FXCarryG10().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _fx_panel()
    weights = FXCarryG10(lookback=63).generate_signals(prices)
    # pct_change(63) → first 63 rows are NaN → zero
    assert (weights.iloc[:63] == 0.0).all().all()


def test_generates_long_and_short() -> None:
    prices = _fx_panel()
    weights = FXCarryG10().generate_signals(prices)
    mature = weights.iloc[70:]
    assert (mature > 0).any().any(), "Expected long positions"
    assert (mature < 0).any().any(), "Expected short positions"


def test_long_basket_size() -> None:
    """Top 3 currencies should get equal positive weight."""
    prices = _fx_panel()
    weights = FXCarryG10(n_long=3, n_short=3).generate_signals(prices)
    mature = weights.iloc[70:]
    # At each row, count long positions (> 0)
    n_longs = (mature > 0).sum(axis=1)
    # Most rows should have exactly 3 longs (unless ties)
    assert (n_longs == 3).mean() > 0.8, "Expected 3 long positions most of the time"


def test_long_only_mode() -> None:
    prices = _fx_panel()
    weights = FXCarryG10(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _fx_panel()
    a = FXCarryG10().generate_signals(prices)
    b = FXCarryG10().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
