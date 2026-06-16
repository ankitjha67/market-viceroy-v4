"""Unit tests for global_inflation_momentum."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.global_inflation_momentum.strategy import (
    GlobalInflationMomentum,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _paired_panel(
    countries: dict[str, tuple[float, float]],
    *,
    years: float = 4,
) -> pd.DataFrame:
    """Build a paired CPI_/BOND_ panel.

    countries: mapping country_label -> (cpi_drift, bond_drift).
    """
    index = _daily_index(years)
    n = len(index)
    cols: dict[str, np.ndarray] = {}
    for label, (cpi_drift, bond_drift) in countries.items():
        cols[f"CPI_{label}"] = 100.0 * np.exp(cpi_drift * np.arange(n))
        cols[f"BOND_{label}"] = 100.0 * np.exp(bond_drift * np.arange(n))
    return pd.DataFrame(cols, index=index)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(GlobalInflationMomentum(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = GlobalInflationMomentum()
    assert s.name == "global_inflation_momentum"
    assert s.family == "rates"
    assert s.paper_doi == "10.3905/jpm.2014.40.3.087"
    assert s.rebalance_frequency == "monthly"


def test_constructor_rejects_bad_args() -> None:
    with pytest.raises(ValueError, match="cpi_lookback_months"):
        GlobalInflationMomentum(cpi_lookback_months=0)
    with pytest.raises(ValueError, match="cpi_lookback_months"):
        GlobalInflationMomentum(cpi_lookback_months=-1)


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["CPI_US", "BOND_US", "CPI_DE", "BOND_DE"],
        dtype=float,
    )
    assert GlobalInflationMomentum().generate_signals(empty).empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        GlobalInflationMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame(
        {"CPI_US": [100.0], "BOND_US": [100.0], "CPI_DE": [100.0], "BOND_DE": [100.0]},
        index=[0],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        GlobalInflationMomentum().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _paired_panel({"US": (0.0001, 0.0002), "DE": (0.0001, 0.0001)})
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        GlobalInflationMomentum().generate_signals(p)


def test_rejects_unknown_column_naming() -> None:
    """Columns not following CPI_/BOND_ convention must raise."""
    idx = _daily_index(2)
    bad = pd.DataFrame(
        {"CPI_US": 100.0, "BOND_US": 100.0, "OTHER": 100.0},
        index=idx,
    )
    with pytest.raises(ValueError, match="naming convention"):
        GlobalInflationMomentum().generate_signals(bad)


def test_rejects_unmatched_cpi_column() -> None:
    """CPI_X without BOND_X must raise."""
    idx = _daily_index(2)
    bad = pd.DataFrame({"CPI_US": 100.0, "BOND_DE": 100.0}, index=idx)
    with pytest.raises(ValueError, match="missing matching"):
        GlobalInflationMomentum().generate_signals(bad)


def test_rejects_unmatched_bond_column() -> None:
    """BOND_X without CPI_X must raise."""
    idx = _daily_index(2)
    bad = pd.DataFrame(
        {"CPI_US": 100.0, "BOND_US": 100.0, "BOND_DE": 100.0},
        index=idx,
    )
    with pytest.raises(ValueError, match="missing matching"):
        GlobalInflationMomentum().generate_signals(bad)


def test_rejects_single_country() -> None:
    """Cross-sectional rank requires >= 2 countries."""
    idx = _daily_index(2)
    bad = pd.DataFrame({"CPI_US": 100.0, "BOND_US": 100.0}, index=idx)
    with pytest.raises(ValueError, match=">= 2 countries"):
        GlobalInflationMomentum().generate_signals(bad)


def test_warmup_weights_are_zero() -> None:
    p = _paired_panel(
        {"US": (0.0001, 0.0001), "DE": (0.0002, 0.0002), "JP": (0.0003, 0.0001)},
        years=2,
    )
    w = GlobalInflationMomentum(cpi_lookback_months=12).generate_signals(p)
    cutoff = p.index[0] + pd.offsets.DateOffset(months=12)
    warmup = w.loc[w.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_high_inflation_country_gets_short_bond() -> None:
    """Country with highest inflation momentum → bonds expected to
    underperform → strategy goes SHORT that country's bond.
    """
    p = _paired_panel(
        {
            "US": (0.0001, 0.0001),  # low inflation
            "DE": (0.0002, 0.0001),  # mid inflation
            "JP": (0.0005, 0.0001),  # high inflation
        }
    )
    w = GlobalInflationMomentum(cpi_lookback_months=12).generate_signals(p)
    final = w.iloc[-1]
    assert final["BOND_JP"] < 0, f"high-inflation JP must be short, got {final['BOND_JP']}"
    assert final["BOND_US"] > 0, f"low-inflation US must be long, got {final['BOND_US']}"
    assert final["BOND_DE"] == 0.0, f"mid-inflation DE must be flat, got {final['BOND_DE']}"


def test_cpi_columns_have_zero_weight() -> None:
    """CPI_ columns are informational only — zero weight always."""
    p = _paired_panel(
        {"US": (0.0001, 0.0001), "DE": (0.0005, 0.0001)},
    )
    w = GlobalInflationMomentum().generate_signals(p)
    assert (w["CPI_US"] == 0.0).all()
    assert (w["CPI_DE"] == 0.0).all()


def test_dollar_neutral_when_active() -> None:
    """Bond weights sum to zero on active rows."""
    p = _paired_panel(
        {"US": (0.0001, 0.0001), "DE": (0.0003, 0.0001), "JP": (0.0005, 0.0001)},
    )
    w = GlobalInflationMomentum().generate_signals(p)
    bond_cols = [c for c in w.columns if c.startswith("BOND_")]
    mature = w[bond_cols].iloc[-1]
    assert abs(mature.sum()) < 1e-9


def test_constant_cpi_emits_zero_signals() -> None:
    """Constant CPI levels → zero inflation momentum → zero weights."""
    p = _paired_panel({"US": (0.0, 0.0001), "DE": (0.0, 0.0001), "JP": (0.0, 0.0001)})
    w = GlobalInflationMomentum().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    bond_cols = [c for c in w.columns if c.startswith("BOND_")]
    assert (w[bond_cols].to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    p = _paired_panel(
        {"US": (0.0001, 0.0001), "DE": (0.0003, 0.0001), "JP": (0.0005, 0.0001)},
    )
    w1 = GlobalInflationMomentum().generate_signals(p)
    w2 = GlobalInflationMomentum().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
