"""Unit tests for :mod:`alphakit.data.positioning.cftc_cot_adapter`.

Cross-cutting guarantees live in ``test_adapter_contract.py``. This
module covers CFTC-specific behaviour: URL year-range expansion, ZIP
parsing, output-schema correctness, market-code filtering, and
date-range filtering.
"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from alphakit.data.errors import OfflineModeError
from alphakit.data.positioning.cftc_cot_adapter import CFTCCOTAdapter


def _build_cot_zip(rows: list[tuple[str, str, int, int, int, int]]) -> io.BytesIO:
    """Return a ``BytesIO`` holding a ZIP containing a minimal COT CSV.

    Each row: (date, market_code, nc_long, nc_short, comm_long, comm_short).
    Headers match the new ``/files/dea/history/`` archive layout (S2J-2.8 column
    rename). Column names with spaces and parens are quoted per CSV convention.
    """
    header = (
        '"As of Date in Form YYYY-MM-DD","CFTC Contract Market Code",'
        '"Noncommercial Positions-Long (All)","Noncommercial Positions-Short (All)",'
        '"Commercial Positions-Long (All)","Commercial Positions-Short (All)"\n'
    )
    body = "\n".join(f"{d},{m},{nl},{ns},{cl},{cs}" for d, m, nl, ns, cl, cs in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # New archive members are named ``annual.txt`` (single CSV per ZIP);
        # the adapter reads ``zf.namelist()[0]`` so any name works in tests,
        # but using ``annual.txt`` keeps the fixture true to real layout.
        z.writestr("annual.txt", header + body + "\n")
    buf.seek(0)
    return buf


class _FakeResponse:
    """Minimal ``requests.Response`` stand-in: ``.content`` + no-op
    ``.raise_for_status()``. The S2J-2.5 adapter switch to ``requests``
    reads ``response.content`` (bytes) and asserts via ``raise_for_status``;
    tests mock ``requests.get`` to return one of these.
    """

    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _wrap_response(legacy_urlopen: Callable[..., io.BytesIO]) -> Callable[..., _FakeResponse]:
    """Adapt a ``urlopen``-style fake (returns BytesIO) to a ``requests.get``
    fake (returns ``_FakeResponse``). Lets the original test fixtures keep
    their shape while exercising the new HTTP path.
    """

    def _get(url: str, timeout: float | None = None, **_: Any) -> _FakeResponse:
        return _FakeResponse(legacy_urlopen(url).getvalue())

    return _get


def test_fetch_raises_offline_mode_error_when_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))

    adapter = CFTCCOTAdapter()
    with pytest.raises(OfflineModeError, match="cftc-cot"):
        adapter.fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_returns_long_format_with_expected_columns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_adapter.ratelimit_acquire", lambda _n: None
    )

    def fake_urlopen(_url: str, timeout: float | None = None) -> io.BytesIO:
        return _build_cot_zip(
            [("2024-01-02", "067651", 100, 200, 300, 400)],
        )

    monkeypatch.setattr("requests.get", _wrap_response(fake_urlopen))

    adapter = CFTCCOTAdapter()
    df = adapter.fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    expected_columns = {
        "date",
        "market_code",
        "long_positions",
        "short_positions",
        "net_positions",
        "commercial_long",
        "commercial_short",
        "speculative_long",
        "speculative_short",
    }
    assert set(df.columns) == expected_columns
    assert len(df) == 1
    row = df.iloc[0]
    assert row["market_code"] == "067651"
    assert int(row["speculative_long"]) == 100
    assert int(row["speculative_short"]) == 200
    assert int(row["commercial_long"]) == 300
    assert int(row["commercial_short"]) == 400
    assert int(row["long_positions"]) == 400  # 100 + 300
    assert int(row["short_positions"]) == 600  # 200 + 400
    assert int(row["net_positions"]) == -200  # 400 - 600


def test_fetch_filters_by_market_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_adapter.ratelimit_acquire", lambda _n: None
    )

    def fake_urlopen(_url: str, timeout: float | None = None) -> io.BytesIO:
        return _build_cot_zip(
            [
                ("2024-01-02", "067651", 100, 200, 300, 400),
                ("2024-01-02", "023391", 50, 60, 70, 80),  # WTI — should be excluded
            ],
        )

    monkeypatch.setattr("requests.get", _wrap_response(fake_urlopen))

    adapter = CFTCCOTAdapter()
    df = adapter.fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert len(df) == 1
    assert df.iloc[0]["market_code"] == "067651"


def test_fetch_filters_by_date_range(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_adapter.ratelimit_acquire", lambda _n: None
    )

    def fake_urlopen(_url: str, timeout: float | None = None) -> io.BytesIO:
        return _build_cot_zip(
            [
                ("2023-12-26", "067651", 50, 60, 70, 80),  # out of range
                ("2024-01-02", "067651", 100, 200, 300, 400),
                ("2024-01-09", "067651", 110, 210, 310, 410),
                ("2024-01-16", "067651", 120, 220, 320, 420),  # out of range
            ],
        )

    monkeypatch.setattr("requests.get", _wrap_response(fake_urlopen))

    adapter = CFTCCOTAdapter()
    df = adapter.fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert len(df) == 2
    dates = sorted(pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d").tolist())
    assert dates == ["2024-01-02", "2024-01-09"]


def test_fetch_spans_multiple_years(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_adapter.ratelimit_acquire", lambda _n: None
    )

    fetched_urls: list[str] = []

    def fake_urlopen(url: str, timeout: float | None = None) -> io.BytesIO:
        fetched_urls.append(url)
        year = url.rsplit("deacot", 1)[-1].rstrip(".zip")
        return _build_cot_zip(
            [(f"{year}-06-15", "067651", 100, 200, 300, 400)],
        )

    monkeypatch.setattr("requests.get", _wrap_response(fake_urlopen))

    adapter = CFTCCOTAdapter()
    df = adapter.fetch(["067651"], datetime(2023, 6, 1), datetime(2024, 7, 1))

    assert len(fetched_urls) == 2
    assert "deacot2023" in fetched_urls[0]
    assert "deacot2024" in fetched_urls[1]
    assert len(df) == 2


# ---------------------------------------------------------------------------
# Session 2J-2.5 — urllib → requests switch (Windows SSL cert verify failure)
# ---------------------------------------------------------------------------


def test_fetch_raises_if_requests_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The S2J-2.5 ``requests`` import is lazy and surfaces a clear error
    when the package is unavailable — mirrors the EIA adapter pattern."""
    import builtins
    import sys

    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.positioning.cftc_cot_adapter.ratelimit_acquire", lambda _n: None
    )

    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "requests" or name.startswith("requests."):
            raise ImportError("simulated: no requests")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.delitem(sys.modules, "requests", raising=False)

    adapter = CFTCCOTAdapter()
    with pytest.raises(ImportError, match="requests"):
        adapter.fetch(["067651"], datetime(2024, 1, 2), datetime(2024, 1, 10))


_NETWORK_GATE = pytest.mark.skipif(
    os.environ.get("ALPHAKIT_RUN_NETWORK_TESTS") != "1",
    reason="network/substrate-boundary test; set ALPHAKIT_RUN_NETWORK_TESTS=1 to run",
)


@_NETWORK_GATE
def test_real_cftc_download_returns_long_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Substrate-boundary regression guard for CFTC HTTPS / SSL.

    Performs a real ZIP download from cftc.gov and asserts the adapter
    still produces the long-format frame. Skipped by default (CI does
    not set ``ALPHAKIT_RUN_NETWORK_TESTS``); intended for local /
    pre-release verification. Catches future Windows SSL config issues
    (the Session 2J-2.5 ``urlopen → requests`` switch root cause), and
    any CFTC URL / archive-layout change that would break parsing.
    """
    # Clear ALPHAKIT_OFFLINE before the real-network call — without this, an
    # operator-environment ``ALPHAKIT_OFFLINE=1`` would short-circuit
    # ``CFTCCOTAdapter.fetch`` with an ``OfflineModeError`` and the
    # substrate-boundary test would fail for the wrong reason. PR #22
    # post-merge CodeRabbit catch.
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    df = CFTCCOTAdapter().fetch(
        symbols=["067651"],  # NYMEX WTI Light Sweet Crude — PHYSICAL (verified S2K-1)
        start=datetime(2024, 11, 1),
        end=datetime(2024, 11, 30),
    )
    assert not df.empty
    expected = {
        "date",
        "market_code",
        "long_positions",
        "short_positions",
        "net_positions",
    }
    assert expected.issubset(df.columns)


@_NETWORK_GATE
def test_real_cftc_archive_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-archive substrate-boundary guard for the S2J-2.8 column rename.

    Downloads one CFTC ZIP and asserts that the 6 column constants the
    adapter reads (``_COL_DATE``, ``_COL_MARKET``, ``_COL_NC_LONG``,
    ``_COL_NC_SHORT``, ``_COL_COMM_LONG``, ``_COL_COMM_SHORT``) all exist
    in the archive's ``annual.txt`` header. Catches a future CFTC schema
    rename the way the legacy ``Report_Date_as_YYYY-MM-DD`` →
    ``"As of Date in Form YYYY-MM-DD"`` move broke the pre-S2J-2.8 adapter.

    Distinct from ``test_real_cftc_download_returns_long_format`` (which
    asserts the *output* contract) — this asserts the *input* schema
    invariant the adapter depends on.
    """
    import csv
    import io as _io
    from datetime import datetime

    import requests
    from alphakit.data.positioning.cftc_cot_adapter import (
        _COL_COMM_LONG,
        _COL_COMM_SHORT,
        _COL_DATE,
        _COL_MARKET,
        _COL_NC_LONG,
        _COL_NC_SHORT,
        _COT_URL_TEMPLATE,
    )

    url = _COT_URL_TEMPLATE.format(year=datetime.now().year - 1)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf, zf.open(zf.namelist()[0]) as handle:
        header_line = handle.read(20_000).decode("latin-1", errors="replace").split("\n")[0]
    cols = next(csv.reader(_io.StringIO(header_line)))

    expected = {
        _COL_DATE,
        _COL_MARKET,
        _COL_NC_LONG,
        _COL_NC_SHORT,
        _COL_COMM_LONG,
        _COL_COMM_SHORT,
    }
    missing = expected - set(cols)
    assert not missing, (
        f"CFTC archive schema drifted from adapter constants — missing columns: "
        f"{sorted(missing)}. First 15 columns seen: {cols[:15]}"
    )
