"""Unit tests for cot_speculator_position signal generation.

Contrarian COT speculator-positioning trade. Tests cover protocol
conformance, constructor validation, shape contracts, the
contrarian economic behaviour on synthetic positioning series,
the Friday-for-Tuesday lag, and edge cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.cot_speculator_position.strategy import (
    COTSpeculatorPosition,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _build_panel(
    front_to_position_map: dict[str, str],
    front_prices: dict[str, float],
    position_series: dict[str, np.ndarray],
    years: float,
) -> pd.DataFrame:
    """Build a price + positioning panel.

    Front prices are constant; positioning series are passed in
    so each test can shape the rolling-percentile dynamics
    explicitly.
    """
    index = _daily_index(years)
    n = len(index)
    data: dict[str, np.ndarray] = {}
    for front, pos_col in front_to_position_map.items():
        data[front] = np.full(n, front_prices[front])
        data[pos_col] = position_series[pos_col]
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(COTSpeculatorPosition(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = COTSpeculatorPosition()
    assert s.name == "cot_speculator_position"
    assert s.family == "commodity"
    assert s.paper_doi == "10.1111/0022-1082.00253"  # de Roon-Nijman-Veld 2000
    assert s.rebalance_frequency == "weekly"
    assert "commodity" in s.asset_classes


def test_default_universe_is_4_commodities() -> None:
    s = COTSpeculatorPosition()
    assert len(s.front_symbols) == 4
    assert len(s.position_columns) == 4
    expected_fronts = {"CL=F", "NG=F", "GC=F", "ZC=F"}
    assert set(s.front_symbols) == expected_fronts


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"front_to_position_map": {}}, "non-empty"),
        ({"front_to_position_map": {"": "X"}}, "non-empty strings"),
        ({"front_to_position_map": {"X": "X"}}, "must differ"),
        ({"percentile_lookback_weeks": 3}, "percentile_lookback_weeks"),
        ({"extreme_long_threshold": 50.0}, "extreme_long_threshold"),
        ({"extreme_long_threshold": 100.1}, "extreme_long_threshold"),
        ({"extreme_short_threshold": 50.0}, "extreme_short_threshold"),
        ({"extreme_short_threshold": -0.1}, "extreme_short_threshold"),
        ({"cot_lag_days": -1}, "cot_lag_days"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        COTSpeculatorPosition(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    s = COTSpeculatorPosition()
    cols = s.front_symbols + s.position_columns
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    weights = s.generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == s.front_symbols


def test_output_columns_match_front_symbols() -> None:
    fmap = {"CL=F": "CL_POS", "NG=F": "NG_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=4, cot_lag_days=0
    )
    n = 200
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    rng = np.random.default_rng(0)
    prices = pd.DataFrame(
        {
            "CL=F": np.full(n, 80.0),
            "NG=F": np.full(n, 2.5),
            "CL_POS": np.clip(0.5 + 0.05 * rng.normal(0, 1.0, size=n), 0.05, 0.95),
            "NG_POS": np.clip(0.5 + 0.05 * rng.normal(0, 1.0, size=n), 0.05, 0.95),
        },
        index=index,
    )
    weights = s.generate_signals(prices)
    assert list(weights.columns) == ["CL=F", "NG=F"]
    assert weights.index.equals(prices.index)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        COTSpeculatorPosition().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    s = COTSpeculatorPosition()
    cols = s.front_symbols + s.position_columns
    prices = pd.DataFrame({c: [1.0, 2.0] for c in cols}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        s.generate_signals(prices)


def test_rejects_missing_columns() -> None:
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(front_to_position_map=fmap, percentile_lookback_weeks=4)
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="missing"):
        s.generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(front_to_position_map=fmap, percentile_lookback_weeks=4)
    n = 200
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": np.full(n, 0.5)},
        index=index,
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        s.generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour
# ---------------------------------------------------------------------------
def test_extreme_long_positioning_emits_short_signal() -> None:
    """Positioning at the top of its history → short the asset."""
    fmap = {"CL=F": "CL_POS"}
    # Use small percentile_lookback so we can build up enough history.
    s = COTSpeculatorPosition(
        front_to_position_map=fmap,
        percentile_lookback_weeks=8,  # 40 trading days
        extreme_long_threshold=90.0,
        extreme_short_threshold=10.0,
        cot_lag_days=0,  # disable lag for clean test
    )
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    # Positioning rises monotonically — last value is at the top of the
    # rolling history.
    pos = np.linspace(0.1, 0.9, n)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    weights = s.generate_signals(prices)
    # After the lookback fills (day 40), the most recent point is
    # always the rolling-window max → percentile = 100 → short.
    mature = weights.iloc[60:]
    assert (mature["CL=F"] == -1.0).all(), "monotone-rising positioning must emit short"


def test_extreme_short_positioning_emits_long_signal() -> None:
    """Positioning at the bottom of its history → long the asset."""
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap,
        percentile_lookback_weeks=8,
        extreme_long_threshold=90.0,
        extreme_short_threshold=10.0,
        cot_lag_days=0,
    )
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos = np.linspace(0.9, 0.1, n)  # monotonically falling
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    weights = s.generate_signals(prices)
    mature = weights.iloc[60:]
    assert (mature["CL=F"] == 1.0).all(), "monotone-falling positioning must emit long"


def test_neutral_positioning_emits_zero_signal() -> None:
    """Positioning at the median of its history → flat."""
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap,
        percentile_lookback_weeks=8,
        cot_lag_days=0,
    )
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    rng = np.random.default_rng(0)
    pos = 0.5 + 0.05 * rng.normal(0, 1.0, size=n)
    pos = np.clip(pos, 0.05, 0.95)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    weights = s.generate_signals(prices)
    # Random gaussian positioning → most days the percentile is in
    # the middle → flat signal dominates.
    mature = weights.iloc[60:]
    fraction_flat = (mature["CL=F"] == 0.0).mean()
    assert fraction_flat >= 0.7, (
        f"random positioning should produce mostly-flat signals; got {fraction_flat:.2f}"
    )


def test_warmup_signal_is_zero() -> None:
    """Within the percentile lookback window, signal is zero."""
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=0
    )
    n = 100
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos = np.linspace(0.1, 0.9, n)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    weights = s.generate_signals(prices)
    # Lookback = 8 weeks * 5 days = 40 days. Before day 40 → no signal.
    warmup = weights.iloc[:38]
    assert (warmup["CL=F"] == 0.0).all()


def test_cot_lag_shifts_signal() -> None:
    """The cot_lag_days parameter must shift the signal forward."""
    fmap = {"CL=F": "CL_POS"}
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos = np.linspace(0.1, 0.9, n)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )

    no_lag = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=0
    ).generate_signals(prices)
    with_lag = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=5
    ).generate_signals(prices)

    # The lagged signal is the unlagged signal shifted forward by 5 days.
    # So with_lag.iloc[i] == no_lag.iloc[i - 5] (when both are post-warmup).
    for i in range(60, n):
        assert with_lag["CL=F"].iloc[i] == no_lag["CL=F"].iloc[i - 5]


def test_signal_is_in_valid_set() -> None:
    """Output values must be in {-1.0, 0.0, +1.0}."""
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=0
    )
    rng = np.random.default_rng(7)
    n = 500
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos = np.cumsum(rng.normal(0, 0.01, size=n)) + 0.5  # bounded random walk
    pos = np.clip(pos, 0.05, 0.95)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    weights = s.generate_signals(prices)
    values = weights["CL=F"].to_numpy()
    assert ((values == 0.0) | (values == 1.0) | (values == -1.0)).all()


def test_deterministic_output() -> None:
    fmap = {"CL=F": "CL_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=0
    )
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos = np.linspace(0.1, 0.9, n)
    prices = pd.DataFrame(
        {"CL=F": np.full(n, 80.0), "CL_POS": pos},
        index=index,
    )
    w1 = s.generate_signals(prices)
    w2 = s.generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_per_asset_signals_independent() -> None:
    """Each commodity gets its own independent percentile rank."""
    fmap = {"CL=F": "CL_POS", "NG=F": "NG_POS"}
    s = COTSpeculatorPosition(
        front_to_position_map=fmap, percentile_lookback_weeks=8, cot_lag_days=0
    )
    n = 250
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    pos_long = np.linspace(0.1, 0.9, n)  # CL ending extreme-long
    pos_short = np.linspace(0.9, 0.1, n)  # NG ending extreme-short
    prices = pd.DataFrame(
        {
            "CL=F": np.full(n, 80.0),
            "NG=F": np.full(n, 2.5),
            "CL_POS": pos_long,
            "NG_POS": pos_short,
        },
        index=index,
    )
    weights = s.generate_signals(prices)
    final = weights.iloc[-1]
    assert final["CL=F"] == -1.0, "CL extreme-long → short"
    assert final["NG=F"] == 1.0, "NG extreme-short → long"
