"""Unit tests for xs_momentum_jt."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.xs_momentum_jt.strategy import CrossSectionalMomentumJT


def _panel(symbols_to_drift: dict[str, float], years: float = 2) -> pd.DataFrame:
    """Build a deterministic exponential panel with one drift per symbol."""
    n_days = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n_days, freq="B")
    data = {
        sym: 100.0 * np.exp(drift * np.arange(n_days)) for sym, drift in symbols_to_drift.items()
    }
    return pd.DataFrame(data, index=idx)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CrossSectionalMomentumJT(), StrategyProtocol)


def test_metadata() -> None:
    s = CrossSectionalMomentumJT()
    assert s.name == "xs_momentum_jt"
    assert s.family == "trend"
    assert s.paper_doi == "10.1111/j.1540-6261.1993.tb04702.x"
    assert s.asset_classes == ("equity",)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"formation_months": 0}, "formation_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 6, "formation_months": 6}, "skip_months.*formation_months"),
        ({"top_pct": 0.0}, "top_pct"),
        ({"top_pct": 0.6}, "top_pct"),
        ({"min_positions_per_side": 0}, "min_positions_per_side"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CrossSectionalMomentumJT(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert CrossSectionalMomentumJT().generate_signals(empty).empty


def test_aligned_to_input() -> None:
    prices = _panel({f"S{i}": 0.0005 - 0.0001 * i for i in range(10)})
    weights = CrossSectionalMomentumJT().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == list(prices.columns)


def test_winner_is_long_loser_is_short() -> None:
    """The highest-drift asset should be in the long side; the lowest
    in the short side, after warm-up."""
    drifts = {f"S{i}": 0.0010 - 0.00015 * i for i in range(10)}  # S0 strongest, S9 weakest
    prices = _panel(drifts, years=2)
    strategy = CrossSectionalMomentumJT(top_pct=0.1, min_positions_per_side=1)
    weights = strategy.generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=9)]
    # Winner should be long on every mature bar.
    assert (mature["S0"] > 0).all()
    # Loser should be short on every mature bar.
    assert (mature["S9"] < 0).all()


def test_long_short_is_dollar_neutral() -> None:
    """Row sums should be ~0 when long_only=False and both sides are populated."""
    drifts = {f"S{i}": 0.0010 - 0.00015 * i for i in range(10)}
    prices = _panel(drifts, years=2)
    weights = CrossSectionalMomentumJT(top_pct=0.2).generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=9)]
    row_sums = mature.sum(axis=1)
    assert (row_sums.abs() < 1e-9).all(), (
        f"row sums should be ~0 for dollar-neutral L/S; got max |sum|={row_sums.abs().max()}"
    )


def test_long_only_mode_has_no_shorts() -> None:
    drifts = {f"S{i}": 0.0010 - 0.00015 * i for i in range(10)}
    prices = _panel(drifts, years=2)
    weights = CrossSectionalMomentumJT(long_only=True, top_pct=0.1).generate_signals(prices)
    assert (weights >= 0).all().all()
    # And the long book sums to ~1 after warm-up.
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=9)]
    assert np.allclose(mature.sum(axis=1), 1.0)


def test_warmup_weights_are_zero() -> None:
    drifts = {f"S{i}": 0.0005 - 0.0001 * i for i in range(10)}
    prices = _panel(drifts, years=2)
    weights = CrossSectionalMomentumJT(formation_months=6).generate_signals(prices)
    warmup_cutoff = prices.index[0] + pd.offsets.DateOffset(months=5)
    warmup = weights.loc[weights.index < warmup_cutoff]
    assert (warmup == 0.0).all().all()


def test_deterministic() -> None:
    drifts = {f"S{i}": 0.0005 - 0.0001 * i for i in range(10)}
    prices = _panel(drifts, years=2)
    a = CrossSectionalMomentumJT().generate_signals(prices)
    b = CrossSectionalMomentumJT().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_rejects_bad_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CrossSectionalMomentumJT().generate_signals([1, 2, 3])  # type: ignore[arg-type]
    prices = _panel({"A": 0.0005, "B": 0.0003})
    bad = prices.copy()
    bad.iloc[5, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CrossSectionalMomentumJT().generate_signals(bad)
