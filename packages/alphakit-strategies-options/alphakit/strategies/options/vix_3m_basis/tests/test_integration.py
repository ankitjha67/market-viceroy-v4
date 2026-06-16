"""Integration test for vix_3m_basis."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.options.vix_3m_basis.strategy import VIX3MBasis


def _synthetic_vix_3m_panel(n: int = 252, seed: int = 42) -> pd.DataFrame:
    """Plausible ^VIX + ^VIX3M panel with regime variation."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-02", periods=n, freq="B")
    spot = np.zeros(n)
    longer = np.zeros(n)
    spot[0] = 18.0
    longer[0] = 20.0
    for t in range(1, n):
        spike = rng.uniform() < 0.05
        innov = rng.normal(0, 1.0)
        if spike:
            innov += rng.uniform(5.0, 15.0)
        spot[t] = max(spot[t - 1] + 0.15 * (18.0 - spot[t - 1]) + innov, 9.0)
        # ^VIX3M moves more slowly than spot (3-month CMI smoothing).
        longer[t] = max(
            longer[t - 1] + 0.05 * (spot[t - 1] + 1.5 - longer[t - 1]) + rng.normal(0, 0.3),
            9.0,
        )
    return pd.DataFrame({"^VIX": spot, "^VIX3M": longer}, index=idx)


def test_full_3m_basis_runs_through_vectorbt_bridge() -> None:
    prices = _synthetic_vix_3m_panel()
    strategy = VIX3MBasis()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "vix_3m_basis"
    assert result.meta["paper_doi"] == "10.1016/j.jimonfin.2015.10.005"
    assert np.isfinite(result.metrics["sharpe"])

    # ^VIX is signal-only.
    assert (result.weights["^VIX"] == 0.0).all()
    # ^VIX3M is traded based on basis sign.
    longer_w = result.weights["^VIX3M"].to_numpy()
    assert (longer_w == 1.0).any() or (longer_w == -1.0).any()
