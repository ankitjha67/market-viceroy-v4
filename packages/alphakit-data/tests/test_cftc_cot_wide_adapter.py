"""Unit + substrate-boundary tests for :mod:`alphakit.data.positioning.cftc_cot_wide_adapter`.

The long-format ``CFTCCOTAdapter`` is tested separately in
``test_cftc_cot_adapter.py`` and via the shared contract harness in
``test_adapter_contract.py``. This module covers the Session 2K-1 wide-format
variant: OI-normalised net speculator positioning, wide DataFrame indexed by
COT report date with columns = requested market codes.
"""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from alphakit.data.errors import OfflineModeError
from alphakit.data.positioning.cftc_cot_wide_adapter import CFTCCOTWideAdapter


def _build_cot_zip_with_oi(
    rows: list[tuple[str, str, int, int, int, int, int]],
) -> io.BytesIO:
    """Return a ``BytesIO`` ZIP containing a minimal COT CSV with Open Interest.

    Each row: (date, market_code, nc_long, nc_short, comm_long, comm_short, oi).
    Headers match the new ``/files/dea/history/`` archive layout — the wide
    adapter additionally reads the ``"Open Interest (All)"`` column.
    """
    header = (
        '"As of Date in Form YYYY-MM-DD","CFTC Contract Market Code",'
        '"Open Interest (All)",'
        '"Noncommercial Positions-Long (All)","Noncommercial Positions-Short (All)",'
        '"Commercial Positions-Long (All)","Commercial Positions-Short (All)"\n'
    )
    body = "\n".join(f"{d},{m},{oi},{nl},{ns},{cl},{cs}" for d, m, nl, ns, cl, cs, oi in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("annual.txt", header + body + "\n")
    buf.seek(0)
    return buf


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def test_fetch_raises_offline_mode_error_when_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    with pytest.raises(OfflineModeError, match="cftc-cot-wide"):
        CFTCCOTWideAdapter().fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_returns_wide_format_oi_normalised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two market codes, two weeks each — wide DataFrame indexed by date with
    columns = requested codes; values = (NC_long − NC_short) / OI ∈ [-1, +1]."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_wide_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    def fake_get(_url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        # (date, market, nc_long, nc_short, comm_long, comm_short, oi)
        return _FakeResponse(
            _build_cot_zip_with_oi(
                [
                    (
                        "2024-01-02",
                        "067651",
                        300,
                        100,
                        400,
                        500,
                        1_000,
                    ),  # WTI net +200, oi 1000 → +0.20
                    ("2024-01-09", "067651", 200, 200, 500, 500, 1_000),  # WTI net 0
                    (
                        "2024-01-02",
                        "088691",
                        600,
                        200,
                        300,
                        700,
                        2_000,
                    ),  # Gold net +400, oi 2000 → +0.20
                    ("2024-01-09", "088691", 100, 300, 700, 500, 2_000),  # Gold net −200 → −0.10
                ]
            ).getvalue()
        )

    monkeypatch.setattr("requests.get", fake_get)
    df = CFTCCOTWideAdapter().fetch(
        ["067651", "088691"], datetime(2024, 1, 1), datetime(2024, 1, 31)
    )

    # Wide shape: index = COT report dates, columns = requested market codes in order.
    assert list(df.columns) == ["067651", "088691"]
    assert len(df) == 2
    expected = pd.DataFrame(
        {"067651": [0.20, 0.00], "088691": [0.20, -0.10]},
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-09"]),
    )
    pd.testing.assert_frame_equal(df, expected, check_names=False, check_freq=False)


def test_fetch_filters_by_market_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Rows for unrequested market codes are excluded; requested column is wide."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_wide_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    def fake_get(_url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        return _FakeResponse(
            _build_cot_zip_with_oi(
                [
                    ("2024-01-02", "067651", 300, 100, 400, 500, 1_000),
                    ("2024-01-02", "888888", 999, 999, 999, 999, 999),  # noise — should be filtered
                ]
            ).getvalue()
        )

    monkeypatch.setattr("requests.get", fake_get)
    df = CFTCCOTWideAdapter().fetch(["067651"], datetime(2024, 1, 1), datetime(2024, 1, 31))
    assert list(df.columns) == ["067651"]
    assert df["067651"].iloc[0] == pytest.approx(0.20)


def test_fetch_oi_zero_yields_nan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Open-interest=0 rows must produce ``NaN`` (not ``inf``) so the runner's
    finite check surfaces the anomaly via the existing fail-loud contract."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_wide_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    def fake_get(_url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        return _FakeResponse(
            _build_cot_zip_with_oi(
                [
                    ("2024-01-02", "067651", 100, 50, 200, 250, 0),  # oi=0 → NaN
                    ("2024-01-09", "067651", 100, 50, 200, 250, 1_000),
                ]
            ).getvalue()
        )

    monkeypatch.setattr("requests.get", fake_get)
    df = CFTCCOTWideAdapter().fetch(["067651"], datetime(2024, 1, 1), datetime(2024, 1, 31))
    assert pd.isna(df["067651"].iloc[0])
    assert df["067651"].iloc[1] == pytest.approx(0.05)


def test_fetch_reindexes_missing_symbols_to_nan_columns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A requested code with no rows in the archive becomes an explicit
    NaN column (same defensive ``reindex(columns=symbols)`` contract as the
    S2J-2.7 yfinance-futures adapter)."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_wide_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    def fake_get(_url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        return _FakeResponse(
            _build_cot_zip_with_oi(
                [("2024-01-02", "067651", 300, 100, 400, 500, 1_000)],
            ).getvalue()
        )

    monkeypatch.setattr("requests.get", fake_get)
    df = CFTCCOTWideAdapter().fetch(
        ["067651", "NEVER_IN_DATA"], datetime(2024, 1, 1), datetime(2024, 1, 31)
    )
    assert list(df.columns) == ["067651", "NEVER_IN_DATA"]
    assert df["067651"].iloc[0] == pytest.approx(0.20)
    assert df["NEVER_IN_DATA"].isna().all()


def test_fetch_spans_multiple_years(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mirror of the long-format adapter's multi-year test: the
    ``for year in range(start.year, end.year + 1)`` loop + ``pd.concat``
    path is the common backtest case but otherwise un-exercised by the
    single-year mock tests. Guards the per-year HTTP fetch + concat +
    cross-year date-parse against regression."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_wide_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    # Year-specific payloads keyed off the URL the adapter requests, so the
    # concat path receives genuinely-different per-year frames (not the
    # same fixture twice).
    payloads = {
        2023: _build_cot_zip_with_oi(
            [("2023-12-26", "067651", 300, 100, 400, 500, 1_000)]  # net +200 / 1000 = +0.20
        ).getvalue(),
        2024: _build_cot_zip_with_oi(
            [("2024-01-02", "067651", 100, 300, 500, 400, 1_000)]  # net -200 / 1000 = -0.20
        ).getvalue(),
    }
    fetched_years: list[int] = []

    def fake_get(url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        year = next(y for y in payloads if str(y) in url)
        fetched_years.append(year)
        return _FakeResponse(payloads[year])

    monkeypatch.setattr("requests.get", fake_get)
    df = CFTCCOTWideAdapter().fetch(["067651"], datetime(2023, 12, 1), datetime(2024, 1, 31))

    assert fetched_years == [2023, 2024], "adapter must request both archive years"
    assert len(df) == 2
    assert df.index[0] == pd.Timestamp("2023-12-26")
    assert df.index[1] == pd.Timestamp("2024-01-02")
    assert df["067651"].iloc[0] == pytest.approx(0.20)
    assert df["067651"].iloc[1] == pytest.approx(-0.20)


_NETWORK_GATE = pytest.mark.skipif(
    os.environ.get("ALPHAKIT_RUN_NETWORK_TESTS") != "1",
    reason="network/substrate-boundary test; set ALPHAKIT_RUN_NETWORK_TESTS=1 to run",
)


@_NETWORK_GATE
def test_real_cftc_cot_wide_adapter_value_range(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Real-fetch substrate-boundary guard: every finite value is in ``[-1, +1]``.

    Downloads the 2024 archive against the 4 cot strategy market codes and
    asserts the OI-normalisation maths is correct end-to-end. Catches:

    * a future schema rename that breaks the OI column lookup (would
      produce NaN/inf instead of a clean ratio),
    * any market-code misidentification (a wrong code might still parse
      but produce values outside the bounded range if e.g. OI is missing),
    * the adapter's reindex contract under real conditions.

    Skipped by default; run via ``ALPHAKIT_RUN_NETWORK_TESTS=1``.
    """
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))

    df = CFTCCOTWideAdapter().fetch(
        symbols=["067651", "03565B", "088691", "002602"],
        start=datetime(2024, 1, 1),
        end=datetime(2024, 12, 31),
    )

    assert not df.empty
    assert list(df.columns) == ["067651", "03565B", "088691", "002602"]
    arr = df.to_numpy(dtype=float)
    finite_mask = np.isfinite(arr)
    assert finite_mask.any(), "no finite values returned"
    finite_vals = arr[finite_mask]
    assert (finite_vals >= -1.0).all(), f"min = {finite_vals.min()} below -1.0"
    assert (finite_vals <= 1.0).all(), f"max = {finite_vals.max()} above +1.0"
