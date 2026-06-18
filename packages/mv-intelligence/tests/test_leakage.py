"""Unit tests for the leakage check — must PASS clean and CATCH leaky panels."""

from __future__ import annotations

import pandas as pd
import pytest
from mv.intelligence.asof import asof_join
from mv.intelligence.leakage import LeakageError, asof_columns, assert_no_lookahead


def _ts(day: int) -> pd.Timestamp:
    return pd.Timestamp(f"2024-02-{day:02d}", tz="UTC")


def test_clean_asof_panel_passes() -> None:
    decisions = pd.DataFrame({"instrument": ["AAPL", "AAPL"], "ts": [_ts(5), _ts(10)]})
    features = pd.DataFrame(
        {
            "instrument": ["AAPL", "AAPL"],
            "ts": [_ts(1), _ts(8)],
            "feature_name": ["pe", "pe"],
            "value": [10.0, 11.0],
        }
    )
    panel = asof_join(decisions, features)
    assert_no_lookahead(panel)  # no raise — backward join is point-in-time


def test_future_dated_feature_is_caught() -> None:
    # A deliberately leaky panel: the feature is dated AFTER the decision.
    panel = pd.DataFrame(
        {
            "instrument": ["AAPL"],
            "ts": [_ts(5)],
            "pe": [12.0],
            "pe__asof_ts": [_ts(9)],  # known on day 9, used on day 5 -> leak
        }
    )
    with pytest.raises(LeakageError, match="look-ahead"):
        assert_no_lookahead(panel)


def test_forward_join_leaks_and_is_caught() -> None:
    # Simulate a buggy forward as-of join and confirm the check catches it.
    decisions = pd.DataFrame({"instrument": ["AAPL"], "ts": [_ts(5)]})
    future = pd.DataFrame(
        {"instrument": ["AAPL"], "ts": [_ts(9)], "pe__asof_ts": [_ts(9)], "pe": [12.0]}
    ).sort_values("ts")
    leaky = pd.merge_asof(
        decisions.sort_values("ts"), future, on="ts", by="instrument", direction="forward"
    )
    with pytest.raises(LeakageError):
        assert_no_lookahead(leaky)


def test_asof_columns_detected() -> None:
    panel = pd.DataFrame(columns=["ts", "pe", "pe__asof_ts", "sentiment", "sentiment__asof_ts"])
    assert set(asof_columns(panel)) == {"pe__asof_ts", "sentiment__asof_ts"}


def test_missing_ts_column_raises() -> None:
    with pytest.raises(ValueError, match="decision-time column"):
        assert_no_lookahead(pd.DataFrame({"pe__asof_ts": [_ts(1)]}))
