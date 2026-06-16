"""Executable documentation tests — verify README's public API claims actually work.

Prevents drift between docs and code. If you change BacktestResult's
public API, this test forces the README quickstart to stay in sync.
"""

from __future__ import annotations

import math

import pandas as pd
from alphakit.core.protocols import BacktestResult


def _make_result() -> BacktestResult:
    return BacktestResult(
        equity_curve=pd.Series([1.0, 1.05, 1.03]),
        returns=pd.Series([0.0, 0.05, -0.019]),
        weights=pd.DataFrame({"A": [1.0, 1.0, 1.0]}),
        metrics={
            "sharpe": 0.75,
            "sortino": 0.55,
            "calmar": 0.73,
            "max_drawdown": -0.08,
            "final_equity": 111823.48,
            "total_return": 0.118,
            "annualized_return": 0.059,
            "annualized_vol": 0.079,
        },
        meta={},
    )


def test_readme_quickstart_sharpe_access() -> None:
    """README quickstart: print(f'Sharpe: {result.sharpe:.2f}')."""
    result = _make_result()
    assert result.sharpe == 0.75
    assert f"{result.sharpe:.2f}" == "0.75"


def test_readme_quickstart_max_dd_access() -> None:
    """README quickstart: print(f'Max DD: {result.max_dd:.2%}')."""
    result = _make_result()
    assert result.max_dd == -0.08
    assert f"{result.max_dd:.2%}" == "-8.00%"


def test_all_convenience_accessors_present() -> None:
    """All 8 metric keys have top-level property accessors."""
    result = _make_result()
    assert result.sharpe == 0.75
    assert result.sortino == 0.55
    assert result.calmar == 0.73
    assert result.max_dd == -0.08
    assert result.final_equity == 111823.48
    assert result.total_return == 0.118
    assert result.annualized_return == 0.059
    assert result.annualized_vol == 0.079


def test_missing_metric_returns_nan() -> None:
    """Missing metrics return NaN, not KeyError."""
    result = BacktestResult(
        equity_curve=pd.Series([1.0]),
        returns=pd.Series([0.0]),
        weights=pd.DataFrame({"A": [1.0]}),
        metrics={},
        meta={},
    )
    assert math.isnan(result.sharpe)
    assert math.isnan(result.max_dd)
    assert math.isnan(result.sortino)
    assert math.isnan(result.calmar)
    assert math.isnan(result.final_equity)
    assert math.isnan(result.total_return)
    assert math.isnan(result.annualized_return)
    assert math.isnan(result.annualized_vol)


def test_structured_metrics_still_accessible() -> None:
    """Advanced users can still access the full metrics dict."""
    result = _make_result()
    assert isinstance(result.metrics, dict)
    assert result.metrics["sharpe"] == 0.75
    assert result.metrics["max_drawdown"] == -0.08
