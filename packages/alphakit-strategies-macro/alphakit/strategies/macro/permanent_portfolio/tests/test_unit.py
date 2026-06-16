"""Unit tests for permanent_portfolio signal generation.

Strategy is a static 25/25/25/25 allocator across four ETF legs
(SPY, TLT, GLD, SHY). Tests verify constant target weights, monthly
rebalance cadence, sum-to-1 invariant, missing-column handling,
non-positive-price rejection, constructor validation, and protocol
conformance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.permanent_portfolio.strategy import PermanentPortfolio


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _flat_panel(symbols: list[str], years: float, base_price: float = 100.0) -> pd.DataFrame:
    """Constant prices for each symbol — strategy weights are independent of
    price level so a flat panel is sufficient for most tests."""
    index = _daily_index(years)
    return pd.DataFrame({sym: np.full(len(index), base_price) for sym in symbols}, index=index)


def _trending_panel(symbols: list[str], years: float, daily_drift: float) -> pd.DataFrame:
    """Exponentially-trending panel for tests that need price movement."""
    index = _daily_index(years)
    data = {sym: 100.0 * np.exp(daily_drift * np.arange(len(index))) for sym in symbols}
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(PermanentPortfolio(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = PermanentPortfolio()
    assert s.name == "permanent_portfolio"
    assert s.family == "macro"
    assert s.paper_doi == "10.2139/ssrn.3168697"  # Estrada 2018
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "gold", "cash")


def test_required_symbols_are_default_four() -> None:
    s = PermanentPortfolio()
    assert s.required_symbols == ("SPY", "TLT", "GLD", "SHY")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"equity_symbol": ""}, "equity_symbol"),
        ({"bonds_symbol": ""}, "bonds_symbol"),
        ({"gold_symbol": ""}, "gold_symbol"),
        ({"cash_symbol": ""}, "cash_symbol"),
        ({"target_weights": (0.25, 0.25, 0.25)}, "exactly 4 entries"),
        ({"target_weights": (0.25, 0.25, 0.25, 0.25, 0.25)}, "exactly 4 entries"),
        ({"target_weights": (0.30, 0.30, 0.30, 0.20)}, "sum to 1.0"),
        ({"target_weights": (-0.10, 0.30, 0.40, 0.40)}, "positive"),
        ({"target_weights": (0.0, 0.25, 0.25, 0.50)}, "positive"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        PermanentPortfolio(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        PermanentPortfolio(equity_symbol="SPY", bonds_symbol="SPY")


def test_constructor_accepts_custom_symbols() -> None:
    s = PermanentPortfolio(
        equity_symbol="VTI",
        bonds_symbol="EDV",
        gold_symbol="IAU",
        cash_symbol="BIL",
    )
    assert s.required_symbols == ("VTI", "EDV", "IAU", "BIL")


def test_constructor_accepts_custom_weights() -> None:
    s = PermanentPortfolio(target_weights=(0.30, 0.20, 0.30, 0.20))
    assert s.target_weights == (0.30, 0.20, 0.30, 0.20)


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "GLD", "SHY"],
        dtype=float,
    )
    weights = PermanentPortfolio().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY", "TLT", "GLD", "SHY"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "TLT", "GLD", "SHY"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        PermanentPortfolio().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {
            "SPY": [100.0, 101.0],
            "TLT": [100.0, 101.0],
            "GLD": [100.0, 101.0],
            "SHY": [100.0, 100.5],
        },
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        PermanentPortfolio().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        PermanentPortfolio().generate_signals(prices)


def test_rejects_missing_required_symbols() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD"], years=2)  # missing SHY
    with pytest.raises(KeyError, match="SHY"):
        PermanentPortfolio().generate_signals(prices)


def test_ignores_extra_columns() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY", "EFA", "DBC"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)
    # Output only includes the four required symbols
    assert list(weights.columns) == ["SPY", "TLT", "GLD", "SHY"]


# ---------------------------------------------------------------------------
# Economic behaviour: static 25/25/25/25 at every rebalance
# ---------------------------------------------------------------------------
def test_emits_exactly_25_percent_on_each_leg_at_month_ends() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)

    # Find the month-end bars in the output.
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    month_end_mask = idx.to_series().groupby(idx.to_period("M")).transform("max") == idx.to_series()
    month_end_weights = weights.loc[month_end_mask]

    np.testing.assert_allclose(month_end_weights.to_numpy(), 0.25, atol=1e-12)


def test_weights_sum_to_one_after_first_rebalance() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)
    # First month-end onwards, weights sum to 1.0 every bar (forward-filled).
    first_month_end = pd.Timestamp("2018-01-31")
    sums = weights.loc[weights.index >= first_month_end].sum(axis=1)
    np.testing.assert_allclose(sums.to_numpy(), 1.0, atol=1e-12)


def test_weights_are_zero_before_first_rebalance() -> None:
    """No warm-up; bars before the first month-end carry zero weight by
    construction (the strategy emits its first 25/25/25/25 at the first
    available month-end)."""
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)
    first_month_end = pd.Timestamp("2018-01-31")
    pre = weights.loc[weights.index < first_month_end]
    assert (pre.to_numpy() == 0.0).all()


def test_all_weights_non_negative() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=3)
    weights = PermanentPortfolio().generate_signals(prices)
    assert (weights.to_numpy() >= -1e-12).all()


def test_weights_change_only_at_month_ends() -> None:
    """Daily weights are piecewise-constant within months (constant 0.25 from
    the first month-end onward; no intra-month variation)."""
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = PermanentPortfolio().generate_signals(prices)
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    for col in weights.columns:
        by_month = weights[col].groupby(idx.to_period("M")).nunique()
        assert (by_month <= 2).all(), (
            f"{col}: weights must be piecewise-constant within months "
            f"(max nunique in any month is {by_month.max()})"
        )


def test_custom_weights_emitted_verbatim() -> None:
    custom = (0.30, 0.20, 0.30, 0.20)
    strategy = PermanentPortfolio(target_weights=custom)
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    weights = strategy.generate_signals(prices)

    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    month_end_mask = idx.to_series().groupby(idx.to_period("M")).transform("max") == idx.to_series()
    month_end_row = weights.loc[month_end_mask].iloc[0]
    np.testing.assert_allclose(month_end_row.to_numpy(), np.asarray(custom), atol=1e-12)


def test_weights_independent_of_price_path() -> None:
    """The strategy is a static allocator; trending prices produce the same
    target weights as flat prices."""
    flat = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=2)
    trending = _trending_panel(["SPY", "TLT", "GLD", "SHY"], years=2, daily_drift=0.001)
    w_flat = PermanentPortfolio().generate_signals(flat)
    w_trend = PermanentPortfolio().generate_signals(trending)
    pd.testing.assert_frame_equal(w_flat, w_trend)


def test_deterministic_output() -> None:
    prices = _flat_panel(["SPY", "TLT", "GLD", "SHY"], years=3)
    w1 = PermanentPortfolio().generate_signals(prices)
    w2 = PermanentPortfolio().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_custom_symbols_propagate_to_columns() -> None:
    strategy = PermanentPortfolio(
        equity_symbol="VTI",
        bonds_symbol="EDV",
        gold_symbol="IAU",
        cash_symbol="BIL",
    )
    prices = _flat_panel(["VTI", "EDV", "IAU", "BIL"], years=2)
    weights = strategy.generate_signals(prices)
    assert list(weights.columns) == ["VTI", "EDV", "IAU", "BIL"]
