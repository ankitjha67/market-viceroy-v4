"""Integration test for vix_term_structure_roll.

Mocks yfinance responses for ^VIX and VIX=F to verify the
strategy runs end-to-end through vectorbt_bridge without
network access. Real-data shape verification deferred to
Session 2H.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import BacktestResult
from alphakit.strategies.options.vix_term_structure_roll.strategy import (
    VIXTermStructureRoll,
)


def _synthetic_vix_panel(n: int = 252, seed: int = 42) -> pd.DataFrame:
    """Plausible VIX spot + futures series with regime variation.

    Spot follows a mean-reverting process around 18 with
    occasional vol spikes; futures follow with a regime-varying
    offset that produces both contango (most days) and
    backwardation (during spike days). This mimics empirical
    VIX-futures basis dynamics.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-02", periods=n, freq="B")
    spot = np.zeros(n)
    front = np.zeros(n)
    spot[0] = 18.0
    front[0] = 19.5  # initial contango
    for t in range(1, n):
        # Spot: mean-revert to 18 with occasional spikes.
        spike = rng.uniform() < 0.05  # 5 % chance of vol spike
        innov = rng.normal(0, 1.0)
        if spike:
            innov += rng.uniform(5.0, 15.0)
        spot[t] = spot[t - 1] + 0.15 * (18.0 - spot[t - 1]) + innov
        spot[t] = max(spot[t], 9.0)
        # Futures: drift toward spot + noise; in spike regimes
        # spot >> futures (backwardation) because futures lag.
        front[t] = front[t - 1] + 0.10 * (spot[t - 1] + 1.0 - front[t - 1]) + rng.normal(0, 0.5)
        front[t] = max(front[t], 9.0)
    return pd.DataFrame({"^VIX": spot, "VIX=F": front}, index=idx)


def test_full_basis_trade_runs_through_vectorbt_bridge() -> None:
    prices = _synthetic_vix_panel()
    strategy = VIXTermStructureRoll()
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "vix_term_structure_roll"
    assert result.meta["paper_doi"] == "10.3905/jod.2014.21.3.054"
    assert np.isfinite(result.metrics["sharpe"])

    # Spot is signal-only; weight 0 throughout.
    assert (result.weights["^VIX"] == 0.0).all()
    # Futures weight is sign of basis; expect both +1 and -1
    # over a regime-varying panel.
    futures_w = result.weights["VIX=F"].to_numpy()
    assert (futures_w == 1.0).any(), "expected at least one backwardation bar"
    assert (futures_w == -1.0).any(), "expected at least one contango bar"


def test_basis_sign_drives_signal() -> None:
    """Sanity: where basis > 0, signal = +1; where basis < 0,
    signal = -1."""
    prices = _synthetic_vix_panel()
    strategy = VIXTermStructureRoll()
    weights = strategy.generate_signals(prices)
    basis = prices["^VIX"] - prices["VIX=F"]
    # Where basis > 1e-6, weight should be +1.
    backwardation_mask = basis > 1e-6
    if backwardation_mask.any():
        assert (weights["VIX=F"][backwardation_mask] == 1.0).all()
    # Where basis < -1e-6, weight should be -1.
    contango_mask = basis < -1e-6
    if contango_mask.any():
        assert (weights["VIX=F"][contango_mask] == -1.0).all()
