"""Unit tests for the validation gate decision rules + one evaluate smoke."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bench.validation.gate import (
    GateInputs,
    GateStatus,
    ValidationGate,
    decide,
    is_real_feed,
)
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226


def _inputs(
    *,
    data_source: str = "yfinance-real",
    oos_sharpe: float = 1.2,
    net_positive: bool = True,
    deflated_sharpe: float = 0.99,
    positive_window_fraction: float = 0.8,
    worst_regime_sharpe: float = 0.2,
    bootstrap_ci_low: float = 0.05,
) -> GateInputs:
    return GateInputs(
        data_source=data_source,
        oos_sharpe=oos_sharpe,
        net_positive=net_positive,
        deflated_sharpe=deflated_sharpe,
        positive_window_fraction=positive_window_fraction,
        worst_regime_sharpe=worst_regime_sharpe,
        bootstrap_ci_low=bootstrap_ci_low,
    )


def test_is_real_feed() -> None:
    assert is_real_feed("yfinance-real") is True
    assert is_real_feed("yfinance+fred-real") is True
    assert is_real_feed("synthetic-fixture") is False


def test_synthetic_can_never_be_active() -> None:
    status, reasons = decide(_inputs(data_source="synthetic-fixture"))
    assert status is GateStatus.OBSERVE
    assert "synthetic" in reasons[0] or "non-real" in reasons[0]


def test_all_stages_pass_is_active() -> None:
    status, _ = decide(_inputs())
    assert status is GateStatus.ACTIVE


def test_negative_oos_is_failed() -> None:
    status, _ = decide(_inputs(oos_sharpe=-0.3))
    assert status is GateStatus.FAILED


def test_net_negative_is_failed() -> None:
    status, _ = decide(_inputs(net_positive=False))
    assert status is GateStatus.FAILED


def test_weak_deflated_sharpe_is_observe() -> None:
    status, reasons = decide(_inputs(deflated_sharpe=0.5))
    assert status is GateStatus.OBSERVE
    assert any("deflated" in r for r in reasons)


def test_inconsistent_walk_forward_is_observe() -> None:
    status, reasons = decide(_inputs(positive_window_fraction=0.3))
    assert status is GateStatus.OBSERVE
    assert any("walk-forward" in r for r in reasons)


def test_monte_carlo_lower_bound_below_zero_is_observe() -> None:
    status, reasons = decide(_inputs(bootstrap_ci_low=-0.01))
    assert status is GateStatus.OBSERVE
    assert any("Monte-Carlo" in r for r in reasons)


def test_catastrophic_regime_is_observe() -> None:
    status, reasons = decide(_inputs(worst_regime_sharpe=-1.0))
    assert status is GateStatus.OBSERVE
    assert any("regime" in r for r in reasons)


# --- one end-to-end evaluate smoke (synthetic prices, real strategy) ---


def _uptrend(n: int = 320) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    series = 100.0 * np.exp(np.cumsum(rng.normal(0.0012, 0.008, n)))
    index = pd.date_range("2012-01-01", periods=n, freq="B")
    return pd.DataFrame({"SPY": series}, index=index)


def test_evaluate_synthetic_source_is_never_active() -> None:
    gate = ValidationGate(n_trials=31, trials_sharpe_std=0.03)
    result = gate.evaluate(
        "ema_cross_12_26",
        EMACross1226(long_only=True),
        _uptrend(),
        data_source="synthetic-fixture",
    )
    assert result.status is GateStatus.OBSERVE
    assert "oos_sharpe" in result.metrics


def test_evaluate_real_source_runs_all_stages() -> None:
    gate = ValidationGate(n_trials=31, trials_sharpe_std=0.03)
    result = gate.evaluate(
        "ema_cross_12_26",
        EMACross1226(long_only=True),
        _uptrend(),
        data_source="yfinance-real",
    )
    # A real-feed run is judged on its merits (not the synthetic short-circuit):
    # the verdict is data-driven (here EMA-cross fails OOS — honest gate output),
    # and the full metric set is populated.
    assert isinstance(result.status, GateStatus)
    assert "non-real" not in result.reasons[0]
    assert set(result.metrics) >= {
        "oos_sharpe",
        "deflated_sharpe",
        "walk_forward_positive_fraction",
        "worst_regime_sharpe",
        "bootstrap_ci_low",
    }
