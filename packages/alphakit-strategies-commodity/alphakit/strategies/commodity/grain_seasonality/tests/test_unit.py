"""Unit tests for grain_seasonality signal generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.grain_seasonality.strategy import GrainSeasonality


def _full_year_prices(year: int = 2020) -> pd.DataFrame:
    index = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="B")
    n = len(index)
    return pd.DataFrame(
        {"ZC=F": np.full(n, 5.0), "ZS=F": np.full(n, 12.0), "ZW=F": np.full(n, 6.0)},
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(GrainSeasonality(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = GrainSeasonality()
    assert s.name == "grain_seasonality"
    assert s.family == "commodity"
    assert s.paper_doi == "10.1002/fut.10017"  # Sørensen 2002
    assert s.rebalance_frequency == "monthly"
    assert "commodity" in s.asset_classes


def test_default_universe_is_three_grains() -> None:
    s = GrainSeasonality()
    assert s.front_symbols == ["ZC=F", "ZS=F", "ZW=F"]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
def test_constructor_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        GrainSeasonality(universe=[])


def test_constructor_rejects_unknown_symbol() -> None:
    with pytest.raises(ValueError, match="no seasonal calendar"):
        GrainSeasonality(universe=["XX=F"])


def test_constructor_rejects_empty_string_symbol() -> None:
    with pytest.raises(ValueError, match="non-empty strings"):
        GrainSeasonality(universe=[""])


def test_constructor_accepts_subset() -> None:
    s = GrainSeasonality(universe=["ZC=F"])
    assert s.front_symbols == ["ZC=F"]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    s = GrainSeasonality()
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=s.front_symbols,
        dtype=float,
    )
    weights = s.generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == s.front_symbols


def test_output_is_aligned_to_input() -> None:
    prices = _full_year_prices()
    weights = GrainSeasonality().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["ZC=F", "ZS=F", "ZW=F"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        GrainSeasonality().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {"ZC=F": [5.0, 5.0], "ZS=F": [12.0, 12.0], "ZW=F": [6.0, 6.0]},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        GrainSeasonality().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _full_year_prices()
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        GrainSeasonality().generate_signals(prices)


def test_rejects_missing_columns() -> None:
    prices = pd.DataFrame(
        {"ZC=F": [5.0, 5.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="ZS=F"):
        GrainSeasonality().generate_signals(prices)


# ---------------------------------------------------------------------------
# Calendar-rule behaviour
# ---------------------------------------------------------------------------
def test_corn_long_window() -> None:
    """ZC=F is long in Apr-Jun, short in Sep-Nov, flat otherwise."""
    prices = _full_year_prices()
    weights = GrainSeasonality().generate_signals(prices)
    assert isinstance(prices.index, pd.DatetimeIndex)
    months = prices.index.month

    long_mask = pd.Series(months, index=prices.index).isin([4, 5, 6])
    short_mask = pd.Series(months, index=prices.index).isin([9, 10, 11])
    flat_mask = ~(long_mask | short_mask)

    assert (weights.loc[long_mask, "ZC=F"] == 1.0).all()
    assert (weights.loc[short_mask, "ZC=F"] == -1.0).all()
    assert (weights.loc[flat_mask, "ZC=F"] == 0.0).all()


def test_soybean_long_window() -> None:
    prices = _full_year_prices()
    weights = GrainSeasonality().generate_signals(prices)
    assert isinstance(prices.index, pd.DatetimeIndex)
    months = prices.index.month

    long_mask = pd.Series(months, index=prices.index).isin([5, 6, 7])
    short_mask = pd.Series(months, index=prices.index).isin([10, 11, 12])
    flat_mask = ~(long_mask | short_mask)

    assert (weights.loc[long_mask, "ZS=F"] == 1.0).all()
    assert (weights.loc[short_mask, "ZS=F"] == -1.0).all()
    assert (weights.loc[flat_mask, "ZS=F"] == 0.0).all()


def test_wheat_long_window() -> None:
    prices = _full_year_prices()
    weights = GrainSeasonality().generate_signals(prices)
    assert isinstance(prices.index, pd.DatetimeIndex)
    months = prices.index.month

    long_mask = pd.Series(months, index=prices.index).isin([2, 3, 4])
    short_mask = pd.Series(months, index=prices.index).isin([7, 8])
    flat_mask = ~(long_mask | short_mask)

    assert (weights.loc[long_mask, "ZW=F"] == 1.0).all()
    assert (weights.loc[short_mask, "ZW=F"] == -1.0).all()
    assert (weights.loc[flat_mask, "ZW=F"] == 0.0).all()


def test_signal_is_in_valid_set() -> None:
    """Output values are in {-1.0, 0.0, +1.0}."""
    prices = _full_year_prices()
    weights = GrainSeasonality().generate_signals(prices)
    values = weights.to_numpy()
    assert ((values == 0.0) | (values == 1.0) | (values == -1.0)).all()


def test_subset_universe_only_emits_specified_legs() -> None:
    """Restricting the universe emits signals only on the chosen legs."""
    prices = _full_year_prices()
    weights = GrainSeasonality(universe=["ZC=F"]).generate_signals(prices)
    assert list(weights.columns) == ["ZC=F"]


def test_calendar_repeats_year_over_year() -> None:
    """The same calendar dates produce the same signal in different years."""
    prices_2020 = _full_year_prices(2020)
    prices_2024 = _full_year_prices(2024)
    w_2020 = GrainSeasonality().generate_signals(prices_2020)
    w_2024 = GrainSeasonality().generate_signals(prices_2024)
    # Compare same calendar months across years.
    assert isinstance(w_2020.index, pd.DatetimeIndex)
    assert isinstance(w_2024.index, pd.DatetimeIndex)
    for month in range(1, 13):
        m_2020 = w_2020.loc[w_2020.index.month == month]
        m_2024 = w_2024.loc[w_2024.index.month == month]
        for col in w_2020.columns:
            assert m_2020[col].iloc[0] == m_2024[col].iloc[0], (
                f"calendar must be year-invariant for month={month}, col={col}"
            )


def test_deterministic_output() -> None:
    prices = _full_year_prices()
    w1 = GrainSeasonality().generate_signals(prices)
    w2 = GrainSeasonality().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
