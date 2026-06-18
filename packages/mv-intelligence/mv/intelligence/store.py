"""ClickHouse-backed point-in-time feature store (PRD FR-I2).

Long-format writes/reads of feature observations. The frame-shape validation is
pure (unit-tested); the ClickHouse I/O is gated (``# pragma: no cover``),
exercised by the CI integration job. Consumers align features to decision times
with :func:`mv.intelligence.asof.asof_join` (or ClickHouse ``ASOF JOIN``).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

FEATURE_COLUMNS: tuple[str, ...] = ("instrument", "feature_name", "ts", "value", "source")


def validate_feature_frame(frame: pd.DataFrame) -> None:
    """Raise ``ValueError`` if ``frame`` lacks the canonical feature columns."""
    missing = [col for col in FEATURE_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(f"feature frame missing columns: {missing}")


class FeatureStore:
    """Read/write the ``features`` table (injected clickhouse-connect client)."""

    def __init__(self, clickhouse_client: Any) -> None:
        self._ch = clickhouse_client

    def write(self, frame: pd.DataFrame) -> int:  # pragma: no cover - DB I/O
        """Insert feature rows; return the number written."""
        validate_feature_frame(frame)
        data = list(frame[list(FEATURE_COLUMNS)].itertuples(index=False, name=None))
        self._ch.insert("features", data, column_names=list(FEATURE_COLUMNS))
        return len(frame)

    def read(
        self, instrument: str, *, feature_name: str | None = None
    ) -> pd.DataFrame:  # pragma: no cover - DB I/O
        """Read an instrument's features (optionally one feature_name), ts-ordered."""
        query = (
            "SELECT instrument, feature_name, ts, value, source "
            "FROM features WHERE instrument = %(instrument)s"
        )
        params: dict[str, Any] = {"instrument": instrument}
        if feature_name is not None:
            query += " AND feature_name = %(feature_name)s"
            params["feature_name"] = feature_name
        query += " ORDER BY feature_name, ts"
        result: pd.DataFrame = self._ch.query_df(query, parameters=params)
        return result
