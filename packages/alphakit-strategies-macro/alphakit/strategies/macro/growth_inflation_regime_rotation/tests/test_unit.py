"""Unit tests for growth_inflation_regime_rotation signal generation.

Second consumer of the regime-state primitive — tests verify:

1. The informational-column pattern extended to TWO informational
   columns (CPIAUCSL + GDPC1 both carry weight = 0.0).
2. Publication-lag handling applied to BOTH columns separately,
   with CPI YoY computed AFTER the lag.
3. 4-cell regime classification (growth × inflation cross).
4. Weight integrity (tradable weights sum to 1.0; informational
   columns always exactly 0.0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.growth_inflation_regime_rotation.strategy import (
    GrowthInflationRegimeRotation,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2015-01-01", periods=n_days, freq="B")


def _build_panel(
    years: float = 5,
    cpi_yoy_target: float = 2.0,
    gdp_growth: float = 3.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a 6-column panel (SPY/TLT/GLD/DBC/CPIAUCSL/GDPC1).

    Both CPI and GDP are constructed as *level* series compounding at
    the target YoY rate, so the strategy's internal YoY computation
    recovers ``cpi_yoy_target`` and ``gdp_growth`` respectively.
    """
    index = _daily_index(years)
    n = len(index)
    rng = np.random.default_rng(seed)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.014, size=n)))

    # CPI index growing at the target YoY rate (daily compounding).
    daily_cpi_growth = (1.0 + cpi_yoy_target / 100.0) ** (1.0 / 252.0) - 1.0
    cpi = 250.0 * np.exp(np.cumsum(np.full(n, np.log(1.0 + daily_cpi_growth))))

    # GDP *level* (chained dollars) growing at the target YoY rate.
    daily_gdp_growth = (1.0 + gdp_growth / 100.0) ** (1.0 / 252.0) - 1.0
    gdp = 20000.0 * np.exp(np.cumsum(np.full(n, np.log(1.0 + daily_gdp_growth))))

    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DBC": dbc,
            "CPIAUCSL": cpi,
            "GDPC1": gdp,
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(GrowthInflationRegimeRotation(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = GrowthInflationRegimeRotation()
    assert s.name == "growth_inflation_regime_rotation"
    assert s.family == "macro"
    assert s.paper_doi == "10.3905/jpm.2014.40.3.087"  # IMR 2014
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "gold", "commodities")


def test_required_symbols_are_six() -> None:
    s = GrowthInflationRegimeRotation()
    assert s.required_symbols == (
        "SPY",
        "TLT",
        "GLD",
        "DBC",
        "CPIAUCSL",
        "GDPC1",
    )
    assert s.tradable_symbols == ("SPY", "TLT", "GLD", "DBC")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"equity_symbol": ""}, "equity_symbol"),
        ({"cpi_column": ""}, "cpi_column"),
        ({"gdp_column": ""}, "gdp_column"),
        ({"cpi_lag_months": -1}, "cpi_lag_months must be non-negative"),
        ({"gdp_lag_months": -1}, "gdp_lag_months must be non-negative"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        GrowthInflationRegimeRotation(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_tradable() -> None:
    with pytest.raises(ValueError, match="distinct"):
        GrowthInflationRegimeRotation(equity_symbol="SPY", bonds_symbol="SPY")


def test_constructor_rejects_informational_overlap() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        GrowthInflationRegimeRotation(cpi_column="SPY")


def test_constructor_rejects_bad_regime_weights_keys() -> None:
    with pytest.raises(ValueError, match="keys must be exactly"):
        GrowthInflationRegimeRotation(regime_weights={"rising_rising": (0.25, 0.25, 0.25, 0.25)})


def test_constructor_rejects_regime_weights_not_summing_to_one() -> None:
    bad = {
        "rising_rising": (0.5, 0.5, 0.5, 0.5),  # sums to 2.0
        "rising_falling": (0.60, 0.40, 0.0, 0.0),
        "falling_rising": (0.0, 0.20, 0.40, 0.40),
        "falling_falling": (0.15, 0.70, 0.15, 0.0),
    }
    with pytest.raises(ValueError, match="sum to 1"):
        GrowthInflationRegimeRotation(regime_weights=bad)


def test_constructor_rejects_negative_regime_weight() -> None:
    bad = {
        "rising_rising": (-0.1, 0.4, 0.3, 0.4),
        "rising_falling": (0.60, 0.40, 0.0, 0.0),
        "falling_rising": (0.0, 0.20, 0.40, 0.40),
        "falling_falling": (0.15, 0.70, 0.15, 0.0),
    }
    with pytest.raises(ValueError, match="non-negative"):
        GrowthInflationRegimeRotation(regime_weights=bad)


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    cols = ["SPY", "TLT", "GLD", "DBC", "CPIAUCSL", "GDPC1"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    weights = GrowthInflationRegimeRotation().generate_signals(empty)
    assert weights.empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        GrowthInflationRegimeRotation().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_informational_column() -> None:
    panel = _build_panel(years=3).drop(columns=["GDPC1"])
    with pytest.raises(KeyError, match="GDPC1"):
        GrowthInflationRegimeRotation().generate_signals(panel)


def test_rejects_non_positive_tradable_prices() -> None:
    panel = _build_panel(years=3)
    panel.loc[panel.index[10], "SPY"] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        GrowthInflationRegimeRotation().generate_signals(panel)


def test_accepts_negative_gdp_growth() -> None:
    """GDP growth rate can be negative (recessions); informational
    column is not positivity-checked."""
    panel = _build_panel(years=5, gdp_growth=-2.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    assert not weights.empty


# ---------------------------------------------------------------------------
# Informational-column pattern (two columns)
# ---------------------------------------------------------------------------
def test_both_informational_columns_carry_zero_weight() -> None:
    panel = _build_panel(years=5, cpi_yoy_target=2.0, gdp_growth=3.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    assert (weights["CPIAUCSL"] == 0.0).all()
    assert (weights["GDPC1"] == 0.0).all()


# ---------------------------------------------------------------------------
# 4-cell regime classification
# ---------------------------------------------------------------------------
def test_goldilocks_regime_rising_growth_falling_inflation() -> None:
    """High growth (3% > 2% threshold) + low inflation (1.5% < 2.5%)
    → goldilocks → 60% SPY / 40% TLT."""
    panel = _build_panel(years=5, cpi_yoy_target=1.5, gdp_growth=3.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.60, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.40, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.0, abs=1e-9)
    assert final["DBC"] == pytest.approx(0.0, abs=1e-9)


def test_overheating_regime_rising_growth_rising_inflation() -> None:
    """High growth (3% > 2%) + high inflation (4% > 2.5%) → overheating
    → 40% SPY / 20% GLD / 40% DBC."""
    panel = _build_panel(years=5, cpi_yoy_target=4.0, gdp_growth=3.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.40, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.0, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.20, abs=1e-9)
    assert final["DBC"] == pytest.approx(0.40, abs=1e-9)


def test_stagflation_regime_falling_growth_rising_inflation() -> None:
    """Low growth (1% < 2%) + high inflation (4% > 2.5%) → stagflation
    → 20% TLT / 40% GLD / 40% DBC."""
    panel = _build_panel(years=5, cpi_yoy_target=4.0, gdp_growth=1.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.0, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.20, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.40, abs=1e-9)
    assert final["DBC"] == pytest.approx(0.40, abs=1e-9)


def test_deflation_regime_falling_growth_falling_inflation() -> None:
    """Low growth (1% < 2%) + low inflation (1% < 2.5%) → deflation
    → 15% SPY / 70% TLT / 15% GLD."""
    panel = _build_panel(years=5, cpi_yoy_target=1.0, gdp_growth=1.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.15, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.70, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.15, abs=1e-9)
    assert final["DBC"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Publication-lag handling (LOAD-BEARING — applied to BOTH columns)
# ---------------------------------------------------------------------------
def test_publication_lag_applied_to_gdp_column() -> None:
    """Verify the GDP column is lagged before the internal YoY computation.

    Because YoY is a 12-month smoother, a level series cannot produce an
    instantaneous YoY step. Instead this test injects a sharp one-time
    *jump* in the GDP level (which produces a detectable YoY spike) and
    compares ``gdp_lag_months=0`` vs ``gdp_lag_months=1``: the regime
    classification at the jump month must differ by exactly one month
    between the two lag settings — proving the ``.shift(lag_months)`` is
    applied.
    """
    index = _daily_index(years=5)
    n = len(index)
    rng = np.random.default_rng(7)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.014, size=n)))
    # Low stable inflation (1.0% YoY → "falling" inflation dimension).
    daily_cpi_growth = (1.0 + 1.0 / 100.0) ** (1.0 / 252.0) - 1.0
    cpi = 250.0 * np.exp(np.cumsum(np.full(n, np.log(1.0 + daily_cpi_growth))))

    # GDP level: flat (0% YoY → falling growth) for the first ~30 months,
    # then jumps up +10% (so trailing-12m YoY > 2% threshold → rising
    # growth) starting at a specific month-end and stays elevated.
    month_ends = pd.Series(index, index=index).groupby(index.to_period("M")).max().to_list()
    jump_date = month_ends[29]  # month-end 30
    gdp = pd.Series(20000.0, index=index, dtype=float)
    gdp.loc[gdp.index >= jump_date] = 22000.0  # +10% jump → YoY spike

    panel = pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DBC": dbc,
            "CPIAUCSL": cpi,
            "GDPC1": gdp.to_numpy(),
        },
        index=index,
    )

    w_lag0 = GrowthInflationRegimeRotation(gdp_lag_months=0).generate_signals(panel)
    w_lag1 = GrowthInflationRegimeRotation(gdp_lag_months=1).generate_signals(panel)

    me_30 = month_ends[29]  # the jump month

    # With lag=0: at month-end 30 the strategy sees the jumped GDP level
    # → YoY spike → rising growth → goldilocks (60% SPY).
    assert w_lag0.loc[me_30, "SPY"] == pytest.approx(0.60, abs=1e-9), (
        f"lag=0 month-end 30 should be goldilocks (sees jumped GDP); "
        f"got SPY {w_lag0.loc[me_30, 'SPY']}"
    )
    # With lag=1: at month-end 30 the strategy sees the pre-jump (flat)
    # GDP level → 0% YoY → falling growth → deflation (70% TLT).
    assert w_lag1.loc[me_30, "TLT"] == pytest.approx(0.70, abs=1e-9), (
        f"lag=1 month-end 30 should be deflation (sees pre-jump GDP); "
        f"got TLT {w_lag1.loc[me_30, 'TLT']}"
    )


def test_publication_lag_applied_to_cpi_column() -> None:
    """Verify the CPI column is lagged before the internal YoY computation.

    Mirror of the GDP lag test using a CPI-level jump. With low stable
    GDP growth (rising) so the goldilocks/overheating distinction is
    driven purely by the CPI inflation dimension.
    """
    index = _daily_index(years=5)
    n = len(index)
    rng = np.random.default_rng(13)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.014, size=n)))

    # GDP level growing at a stable 3% YoY (rising growth dimension).
    daily_gdp = (1.0 + 0.03) ** (1.0 / 252.0) - 1.0
    gdp = 20000.0 * np.exp(np.cumsum(np.full(n, np.log(1.0 + daily_gdp))))

    # CPI level: flat (0% YoY → falling inflation) until a +10% jump
    # (YoY spike > 2.5% → rising inflation) at month-end 30.
    month_ends = pd.Series(index, index=index).groupby(index.to_period("M")).max().to_list()
    jump_date = month_ends[29]
    cpi = pd.Series(250.0, index=index, dtype=float)
    cpi.loc[cpi.index >= jump_date] = 275.0  # +10% jump

    panel = pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DBC": dbc,
            "CPIAUCSL": cpi.to_numpy(),
            "GDPC1": gdp,
        },
        index=index,
    )

    w_lag0 = GrowthInflationRegimeRotation(cpi_lag_months=0).generate_signals(panel)
    w_lag1 = GrowthInflationRegimeRotation(cpi_lag_months=1).generate_signals(panel)

    me_30 = month_ends[29]

    # rising growth + (lag0: rising inflation) → overheating (40% SPY / 40% DBC)
    assert w_lag0.loc[me_30, "DBC"] == pytest.approx(0.40, abs=1e-9), (
        f"lag=0 month-end 30 should be overheating (sees jumped CPI); "
        f"got DBC {w_lag0.loc[me_30, 'DBC']}"
    )
    # rising growth + (lag1: falling inflation) → goldilocks (60% SPY / 40% TLT)
    assert w_lag1.loc[me_30, "SPY"] == pytest.approx(0.60, abs=1e-9), (
        f"lag=1 month-end 30 should be goldilocks (sees pre-jump CPI); "
        f"got SPY {w_lag1.loc[me_30, 'SPY']}"
    )


# ---------------------------------------------------------------------------
# Weight integrity
# ---------------------------------------------------------------------------
def test_tradable_weights_sum_to_one_after_warmup() -> None:
    panel = _build_panel(years=5, cpi_yoy_target=2.0, gdp_growth=3.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    # Past the 13-month warmup (12mo CPI YoY + 1mo lag)
    mature = weights.iloc[300:]
    tradable_sums = mature[["SPY", "TLT", "GLD", "DBC"]].sum(axis=1)
    nonzero = tradable_sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(tradable_sums[nonzero].to_numpy(), 1.0, atol=1e-9)


def test_all_weights_non_negative() -> None:
    panel = _build_panel(years=5, cpi_yoy_target=3.0, gdp_growth=1.0)
    weights = GrowthInflationRegimeRotation().generate_signals(panel)
    assert (weights.to_numpy() >= -1e-9).all()


def test_warmup_weights_are_zero() -> None:
    """CPI YoY needs 12 months + cpi_lag; before that, weights are zero."""
    panel = _build_panel(years=5, cpi_yoy_target=2.0, gdp_growth=3.0)
    weights = GrowthInflationRegimeRotation(cpi_lag_months=1).generate_signals(panel)
    # First ~13 months should be zero (12mo YoY + 1mo lag).
    idx = panel.index
    cutoff = idx[0] + pd.offsets.DateOffset(months=13)
    warmup = weights.loc[weights.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    panel = _build_panel(years=4, cpi_yoy_target=2.0, gdp_growth=3.0)
    w1 = GrowthInflationRegimeRotation().generate_signals(panel)
    w2 = GrowthInflationRegimeRotation().generate_signals(panel)
    pd.testing.assert_frame_equal(w1, w2)
