"""Unit tests for swap_spread_mean_rev."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.swap_spread_mean_rev.strategy import SwapSpreadMeanRev


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _two_leg(*, treasury_drift: float, swap_drift: float, years: float = 3) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "IEF": 100.0 * np.exp(treasury_drift * np.arange(n)),
            "IRS_10Y": 100.0 * np.exp(swap_drift * np.arange(n)),
        },
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(SwapSpreadMeanRev(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = SwapSpreadMeanRev()
    assert s.name == "swap_spread_mean_rev"
    assert s.family == "rates"
    assert s.paper_doi == "10.1093/rfs/hhl026"
    assert s.rebalance_frequency == "daily"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"zscore_window": 10}, "zscore_window"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"entry_threshold": 0.5, "exit_threshold": 1.0}, "exit_threshold.*entry_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        SwapSpreadMeanRev(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["IEF", "IRS"], dtype=float)
    assert SwapSpreadMeanRev().generate_signals(empty).empty


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match="exactly 2 columns"):
        SwapSpreadMeanRev().generate_signals(pd.DataFrame({"IEF": 100.0}, index=idx))


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        SwapSpreadMeanRev().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"IEF": [100.0], "IRS": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        SwapSpreadMeanRev().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _two_leg(treasury_drift=0.0001, swap_drift=0.0001)
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        SwapSpreadMeanRev().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    p = _two_leg(treasury_drift=0.0, swap_drift=-0.0005, years=2)
    w = SwapSpreadMeanRev(zscore_window=252).generate_signals(p)
    assert (w.iloc[:251].to_numpy() == 0.0).all()


def test_treasury_outperforms_triggers_long_swap_short_treasury() -> None:
    """When Treasury persistently out-performs swap-rate proxy, the
    log-price spread (log P_treasury - log P_swap) is high → z > +1σ →
    "swap rich" entry: long swap (+1), short Treasury (-1).
    """
    p = _two_leg(treasury_drift=0.001, swap_drift=0.0)
    w = SwapSpreadMeanRev(zscore_window=126).generate_signals(p)
    final = w.iloc[-1]
    assert final["IEF"] == -1.0
    assert final["IRS_10Y"] == +1.0


def test_swap_outperforms_triggers_long_treasury_short_swap() -> None:
    """When swap-rate proxy persistently out-performs Treasury, log-price
    spread is low → z < -1σ → "swap cheap" entry: long Treasury (+1),
    short swap (-1).
    """
    p = _two_leg(treasury_drift=0.0, swap_drift=0.001)
    w = SwapSpreadMeanRev(zscore_window=126).generate_signals(p)
    final = w.iloc[-1]
    assert final["IEF"] == +1.0
    assert final["IRS_10Y"] == -1.0


def test_legs_are_dollar_neutral_when_active() -> None:
    p = _two_leg(treasury_drift=0.001, swap_drift=0.0)
    w = SwapSpreadMeanRev(zscore_window=126).generate_signals(p)
    np.testing.assert_array_equal(w["IEF"].to_numpy(), -w["IRS_10Y"].to_numpy())


def test_constant_spread_emits_zero_signals() -> None:
    p = _two_leg(treasury_drift=0.0003, swap_drift=0.0003)
    w = SwapSpreadMeanRev(zscore_window=252).generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    p = _two_leg(treasury_drift=0.0001, swap_drift=-0.0001)
    w1 = SwapSpreadMeanRev().generate_signals(p)
    w2 = SwapSpreadMeanRev().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
