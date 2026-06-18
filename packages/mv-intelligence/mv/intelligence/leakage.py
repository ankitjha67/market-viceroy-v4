"""Point-in-time leakage check (PRD FR-V6) — the Phase-3 exit gate.

Given an as-of-joined panel (from :func:`mv.intelligence.asof.asof_join`, which
carries a ``<name>__asof_ts`` per feature), verify that **no feature's effective
timestamp is after the decision timestamp it was attached to**. A green leakage
check is the Phase-3 exit criterion — and it is only meaningful if it *fails* on
a leaky panel (a forward-dated feature, a forward join, or a producer that
stamped a feature by period-end instead of when it became knowable).
"""

from __future__ import annotations

import pandas as pd
from mv.intelligence.asof import ASOF_TS_SUFFIX


class LeakageError(Exception):
    """A feature was attached to a decision earlier than it was knowable."""


def asof_columns(panel: pd.DataFrame) -> list[str]:
    """The ``<name>__asof_ts`` columns in an as-of-joined panel."""
    return [col for col in panel.columns if col.endswith(ASOF_TS_SUFFIX)]


def assert_no_lookahead(panel: pd.DataFrame, *, ts_col: str = "ts") -> None:
    """Raise :class:`LeakageError` if any feature is dated after its decision time.

    Args:
        panel: An as-of-joined panel with a decision ``ts_col`` and one or more
            ``<name>__asof_ts`` effective-time columns.
        ts_col: The decision-time column.

    Raises:
        ValueError: If ``ts_col`` is absent.
        LeakageError: If any ``<name>__asof_ts`` exceeds the decision time.
    """
    if ts_col not in panel.columns:
        raise ValueError(f"panel missing decision-time column {ts_col!r}")
    for asof_col in asof_columns(panel):
        future = panel[asof_col].notna() & (panel[asof_col] > panel[ts_col])
        if bool(future.any()):
            raise LeakageError(
                f"look-ahead in {asof_col!r}: {int(future.sum())} feature value(s) "
                "dated after the decision time"
            )
