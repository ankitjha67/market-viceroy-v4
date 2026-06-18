"""Unit tests for the point-in-time as-of join (no look-ahead)."""

from __future__ import annotations

import pandas as pd
import pytest
from mv.intelligence.asof import asof_join


def _ts(day: int) -> pd.Timestamp:
    return pd.Timestamp(f"2024-01-{day:02d}", tz="UTC")


def _decisions() -> pd.DataFrame:
    return pd.DataFrame({"instrument": ["AAPL", "AAPL", "AAPL"], "ts": [_ts(5), _ts(10), _ts(15)]})


def _features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument": ["AAPL", "AAPL", "AAPL"],
            # pe known as-of day 1 then day 10; sentiment as-of day 5.
            "ts": [_ts(1), _ts(10), _ts(5)],
            "feature_name": ["pe", "pe", "sentiment"],
            "value": [10.0, 12.0, 0.5],
        }
    )


def test_backward_join_uses_most_recent_past_value() -> None:
    out = asof_join(_decisions(), _features()).set_index("ts")
    # Day 5: pe from day 1 (10), sentiment exact match day 5 (0.5).
    assert out.loc[_ts(5), "pe"] == 10.0
    assert out.loc[_ts(5), "sentiment"] == 0.5
    # Day 10: pe updates to 12 (exact match), sentiment still 0.5.
    assert out.loc[_ts(10), "pe"] == 12.0
    # Day 15: latest pe 12, sentiment 0.5.
    assert out.loc[_ts(15), "pe"] == 12.0


def test_no_future_value_leaks() -> None:
    out = asof_join(_decisions(), _features()).set_index("ts")
    # The day-10 pe (12) must NOT appear at the day-5 decision.
    assert out.loc[_ts(5), "pe"] == 10.0
    assert out.loc[_ts(5), "pe__asof_ts"] == _ts(1)


def test_matched_effective_ts_is_at_or_before_decision() -> None:
    out = asof_join(_decisions(), _features())
    for _, row in out.iterrows():
        assert row["pe__asof_ts"] <= row["ts"]
        assert row["sentiment__asof_ts"] <= row["ts"]


def test_missing_history_is_nan() -> None:
    # A decision before any feature -> NaN.
    decisions = pd.DataFrame({"instrument": ["AAPL"], "ts": [_ts(1)]})
    features = pd.DataFrame(
        {"instrument": ["AAPL"], "ts": [_ts(5)], "feature_name": ["pe"], "value": [10.0]}
    )
    out = asof_join(decisions, features)
    assert pd.isna(out.iloc[0]["pe"])


def test_handles_mixed_instrument_dtypes() -> None:
    # ClickHouse returns `instrument` as StringDtype; decisions use object.
    # merge_asof rejects mismatched `by` dtypes unless we coerce (regression guard).
    decisions = pd.DataFrame({"instrument": ["AAPL"], "ts": [_ts(10)]})  # object dtype
    features = pd.DataFrame(
        {
            "instrument": pd.array(["AAPL"], dtype="string"),  # StringDtype
            "ts": [_ts(1)],
            "feature_name": ["pe"],
            "value": [10.0],
        }
    )
    out = asof_join(decisions, features)
    assert out.iloc[0]["pe"] == 10.0


def test_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="decisions missing"):
        asof_join(pd.DataFrame({"ts": [_ts(1)]}), _features())
    with pytest.raises(ValueError, match="features missing"):
        asof_join(_decisions(), pd.DataFrame({"instrument": ["AAPL"], "ts": [_ts(1)]}))
