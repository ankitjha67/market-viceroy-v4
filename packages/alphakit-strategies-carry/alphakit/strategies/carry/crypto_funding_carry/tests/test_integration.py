"""Integration test for crypto_funding_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.carry.crypto_funding_carry.strategy import CryptoFundingCarry


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    cfgs = {"BTC": (0.001, 0.03), "ETH": (0.0008, 0.035), "SOL": (0.0005, 0.04)}
    return pd.DataFrame(
        {sym: 100.0 * np.exp(np.cumsum(rng.normal(d, v, size=n))) for sym, (d, v) in cfgs.items()},
        index=idx,
    )


@pytest.mark.integration
def test_crypto_funding_carry_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=CryptoFundingCarry(), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "crypto_funding_carry"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_crypto_funding_carry_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=CryptoFundingCarry(), prices=prices)
    b = vectorbt_bridge.run(strategy=CryptoFundingCarry(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
