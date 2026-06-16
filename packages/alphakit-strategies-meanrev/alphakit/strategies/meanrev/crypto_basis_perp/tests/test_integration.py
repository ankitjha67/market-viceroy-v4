"""Integration test for crypto_basis_perp."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.meanrev.crypto_basis_perp.strategy import CryptoBasisPerp


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
def test_crypto_basis_perp_runs() -> None:
    prices = _panel()
    result = vectorbt_bridge.run(strategy=CryptoBasisPerp(), prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "crypto_basis_perp"
    for key in ("sharpe", "sortino", "calmar", "max_drawdown"):
        assert np.isfinite(result.metrics[key])


@pytest.mark.integration
def test_crypto_basis_perp_deterministic() -> None:
    prices = _panel(seed=1)
    a = vectorbt_bridge.run(strategy=CryptoBasisPerp(), prices=prices)
    b = vectorbt_bridge.run(strategy=CryptoBasisPerp(), prices=prices)
    pd.testing.assert_frame_equal(a.weights, b.weights)
