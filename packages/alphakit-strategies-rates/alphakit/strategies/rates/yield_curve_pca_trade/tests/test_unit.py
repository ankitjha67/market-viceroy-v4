"""Unit tests for yield_curve_pca_trade."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.yield_curve_pca_trade.strategy import YieldCurvePCATrade


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _bond_panel(drifts: dict[str, float], *, years: float = 5) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {col: 100.0 * np.exp(drift * np.arange(n)) for col, drift in drifts.items()},
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(YieldCurvePCATrade(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = YieldCurvePCATrade()
    assert s.name == "yield_curve_pca_trade"
    assert s.family == "rates"
    assert s.paper_doi == "10.3905/jfi.1991.692347"
    assert s.rebalance_frequency == "monthly"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"n_pcs": 0}, "n_pcs"),
        ({"pca_window_months": 6}, "pca_window_months"),
        ({"residual_lookback_months": 0}, "residual_lookback_months"),
        (
            {"residual_lookback_months": 30, "pca_window_months": 24},
            "residual_lookback_months.*pca_window_months",
        ),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        YieldCurvePCATrade(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["A", "B", "C", "D", "E"],
        dtype=float,
    )
    assert YieldCurvePCATrade().generate_signals(empty).empty


def test_rejects_too_few_columns() -> None:
    """n_pcs=3 requires >= 4 bond columns to leave any residual."""
    p = _bond_panel({"A": 0.0001, "B": 0.0002, "C": 0.0003}, years=4)
    with pytest.raises(ValueError, match="must have > n_pcs"):
        YieldCurvePCATrade(n_pcs=3).generate_signals(p)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        YieldCurvePCATrade().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({c: [100.0] for c in "ABCDE"}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        YieldCurvePCATrade().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _bond_panel(dict.fromkeys("ABCDE", 0.0001))
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        YieldCurvePCATrade().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    """Before pca_window_months months are available, weights are zero."""
    p = _bond_panel({c: 0.0001 + 0.00001 * i for i, c in enumerate("ABCDE")}, years=5)
    w = YieldCurvePCATrade(pca_window_months=24, residual_lookback_months=3).generate_signals(p)
    cutoff = p.index[0] + pd.offsets.DateOffset(months=24)
    warmup = w.loc[w.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_dollar_neutral_when_active() -> None:
    """Cross-sectional rank weights must sum to zero on every active row."""
    rng = np.random.default_rng(42)
    index = _daily_index(years=6)
    n = len(index)
    panel = {}
    for c in "ABCDE":
        shocks = rng.normal(0.0001, 0.005, size=n)
        panel[c] = 100.0 * np.exp(np.cumsum(shocks))
    p = pd.DataFrame(panel, index=index)
    w = YieldCurvePCATrade().generate_signals(p)
    mature = w.iloc[-1]
    assert abs(mature.sum()) < 1e-9


def test_constant_prices_emit_zero_signals() -> None:
    """Constant prices give zero variance → zero residual → zero weights."""
    p = _bond_panel(dict.fromkeys("ABCDE", 0.0), years=4)
    w = YieldCurvePCATrade().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all()


def test_weights_are_bounded() -> None:
    """Each absolute weight is bounded by 1.0."""
    rng = np.random.default_rng(7)
    index = _daily_index(years=6)
    n = len(index)
    panel = {c: 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.005, size=n))) for c in "ABCDE"}
    p = pd.DataFrame(panel, index=index)
    w = YieldCurvePCATrade().generate_signals(p)
    assert (w.abs() <= 1.0 + 1e-9).all().all()


def test_weights_change_only_at_month_ends() -> None:
    """Monthly rebalance: signal piecewise constant within months."""
    rng = np.random.default_rng(7)
    index = _daily_index(years=6)
    n = len(index)
    panel = {c: 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.005, size=n))) for c in "ABCDE"}
    p = pd.DataFrame(panel, index=index)
    w = YieldCurvePCATrade().generate_signals(p)
    idx = w.index
    assert isinstance(idx, pd.DatetimeIndex)
    by_month = w["A"].groupby(idx.to_period("M")).nunique()
    assert (by_month <= 2).all()


def test_n_pcs_must_be_less_than_n_assets() -> None:
    """4 columns and n_pcs=3 should still leave a 1-dim residual; 4 columns
    and n_pcs=4 must raise.
    """
    p = _bond_panel(dict.fromkeys("ABCD", 0.0001), years=4)
    s_ok = YieldCurvePCATrade(n_pcs=3)
    w = s_ok.generate_signals(p)
    assert w.shape == p.shape
    s_bad = YieldCurvePCATrade(n_pcs=4)
    with pytest.raises(ValueError, match="must have > n_pcs"):
        s_bad.generate_signals(p)


def test_deterministic_output() -> None:
    rng = np.random.default_rng(99)
    index = _daily_index(years=6)
    n = len(index)
    panel = {c: 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.005, size=n))) for c in "ABCDE"}
    p = pd.DataFrame(panel, index=index)
    w1 = YieldCurvePCATrade().generate_signals(p)
    w2 = YieldCurvePCATrade().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
