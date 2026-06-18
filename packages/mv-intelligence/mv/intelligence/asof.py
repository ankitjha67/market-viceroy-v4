"""Point-in-time as-of join (PRD FR-I2) — the no-look-ahead linchpin.

Aligns sparse, point-in-time features (fundamentals, sentiment, ...) to a set of
decision timestamps using a **backward** as-of join: each feature value is the
most recent observation whose effective timestamp is at or before the decision
time. Never a future value. The matched effective timestamp is retained per
feature (``<name>__asof_ts``) so :mod:`mv.intelligence.leakage` can verify the
panel carries no look-ahead. Pure (no I/O) and fully unit-tested.
"""

from __future__ import annotations

import pandas as pd

ASOF_TS_SUFFIX = "__asof_ts"

# Long feature-frame columns.
INSTRUMENT = "instrument"
TS = "ts"
FEATURE_NAME = "feature_name"
VALUE = "value"


def asof_join(
    decisions: pd.DataFrame,
    features: pd.DataFrame,
    *,
    instrument_col: str = INSTRUMENT,
    ts_col: str = TS,
    name_col: str = FEATURE_NAME,
    value_col: str = VALUE,
) -> pd.DataFrame:
    """Attach each feature's most-recent at-or-before value to ``decisions``.

    Args:
        decisions: The query points — at least ``[instrument_col, ts_col]``.
        features: Long feature frame ``[instrument_col, ts_col, name_col,
            value_col]`` (``ts_col`` is the feature's *effective* time — filing
            date for fundamentals, publish time for sentiment).

    Returns:
        ``decisions`` widened with one ``<name>`` value column and one
        ``<name>__asof_ts`` column (the matched effective time) per feature.
        Missing history yields NaN.

    Raises:
        ValueError: If required columns are absent.
    """
    for col in (instrument_col, ts_col):
        if col not in decisions.columns:
            raise ValueError(f"decisions missing column {col!r}")
    for col in (instrument_col, ts_col, name_col, value_col):
        if col not in features.columns:
            raise ValueError(f"features missing column {col!r}")

    out: pd.DataFrame = decisions.sort_values(ts_col).reset_index(drop=True)
    # Coerce the merge `by` key to a consistent dtype: a feature frame read back
    # from ClickHouse comes as StringDtype, decisions as object — merge_asof
    # rejects mismatched `by` dtypes.
    out[instrument_col] = out[instrument_col].astype("object")
    for name, group in features.groupby(name_col, sort=True):
        right = group[[instrument_col, ts_col, value_col]].copy()
        right[instrument_col] = right[instrument_col].astype("object")
        right[f"{name}{ASOF_TS_SUFFIX}"] = right[ts_col]
        right = right.rename(columns={value_col: str(name)}).sort_values(ts_col)
        out = pd.merge_asof(
            out,
            right,
            on=ts_col,
            by=instrument_col,
            direction="backward",
            allow_exact_matches=True,
        )
    return out
