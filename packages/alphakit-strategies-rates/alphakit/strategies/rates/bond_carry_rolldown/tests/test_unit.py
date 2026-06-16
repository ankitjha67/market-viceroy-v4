"""Unit tests for bond_carry_rolldown."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.bond_carry_rolldown.strategy import BondCarryRolldown


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _two_leg(*, short_drift: float, target_drift: float, years: float = 3) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "SHY": 100.0 * np.exp(short_drift * np.arange(n)),
            "TLT": 100.0 * np.exp(target_drift * np.arange(n)),
        },
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(BondCarryRolldown(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = BondCarryRolldown()
    assert s.name == "bond_carry_rolldown"
    assert s.family == "rates"
    assert s.paper_doi == "10.1016/j.jfineco.2017.11.002"  # KMPV 2018
    assert s.rebalance_frequency == "daily"
    assert "bond" in s.asset_classes


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
        BondCarryRolldown(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SHY", "TLT"], dtype=float)
    assert BondCarryRolldown().generate_signals(empty).empty


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match="exactly 2 columns"):
        BondCarryRolldown().generate_signals(pd.DataFrame({"TLT": 100.0}, index=idx))


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        BondCarryRolldown().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"SHY": [100.0], "TLT": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        BondCarryRolldown().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _two_leg(short_drift=0.0001, target_drift=0.0001)
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        BondCarryRolldown().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    p = _two_leg(short_drift=0.0, target_drift=-0.0005, years=2)
    w = BondCarryRolldown(zscore_window=252).generate_signals(p)
    assert (w.iloc[:251].to_numpy() == 0.0).all()


def test_target_underperforms_triggers_long() -> None:
    """Target persistently under-performs the short-end → log_spread is
    low → z < -entry_threshold → strategy goes long the target.

    In real-world terms: the target bond has been losing relative to
    the short-end (curve has been steepening), so the carry+rolldown
    available going forward is high → long the target.
    """
    p = _two_leg(short_drift=0.001, target_drift=0.0)
    w = BondCarryRolldown(zscore_window=126, entry_threshold=1.0).generate_signals(p)
    final = w.iloc[-1]
    assert final["SHY"] == 0.0, "short leg must be zero (informational only)"
    assert final["TLT"] == 1.0, f"target leg must be long, got {final['TLT']}"


def test_target_outperforms_does_not_trigger() -> None:
    """When the target out-performs the short-end (curve flattening,
    log_spread rising), z-score is positive — never crosses the
    negative entry threshold — so the strategy stays out.
    """
    p = _two_leg(short_drift=0.0, target_drift=0.001)
    w = BondCarryRolldown(zscore_window=126, entry_threshold=1.0).generate_signals(p)
    assert (w.to_numpy() == 0.0).all()


def test_short_leg_is_always_zero() -> None:
    """The short-end column is informational only — its weight is
    always zero, regardless of signal state.
    """
    p = _two_leg(short_drift=0.001, target_drift=0.0)
    w = BondCarryRolldown(zscore_window=126, entry_threshold=1.0).generate_signals(p)
    assert (w["SHY"] == 0.0).all()


def test_signal_is_zero_or_one_only() -> None:
    """Long-only strategy: weight on target is in {0.0, 1.0}, never
    negative or fractional.
    """
    p = _two_leg(short_drift=0.001, target_drift=0.0)
    w = BondCarryRolldown(zscore_window=126).generate_signals(p)
    target_unique = set(np.unique(w["TLT"]))
    assert target_unique <= {0.0, 1.0}, (
        f"target weight values must be in {{0,1}}, got {target_unique}"
    )


def test_constant_spread_emits_zero_signals() -> None:
    p = _two_leg(short_drift=0.0003, target_drift=0.0003)
    w = BondCarryRolldown(zscore_window=252).generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    p = _two_leg(short_drift=0.0001, target_drift=-0.0001)
    w1 = BondCarryRolldown().generate_signals(p)
    w2 = BondCarryRolldown().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
