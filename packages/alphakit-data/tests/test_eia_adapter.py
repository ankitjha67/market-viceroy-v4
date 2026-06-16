"""Unit tests for :mod:`alphakit.data.futures.eia_adapter`.

Cross-cutting guarantees live in ``test_adapter_contract.py``. This
module covers adapter-specific behaviour: missing API key, offline
mode, URL / params construction, JSON parsing, and multi-symbol
assembly.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from alphakit.data.errors import FeedNotConfiguredError, OfflineModeError
from alphakit.data.futures.eia_adapter import EIAAdapter


def _install_fake_requests(
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    values_by_series: dict[str, list[tuple[str, float]]],
) -> None:
    """Install a fake ``requests`` module recording call args + returning canned JSON."""
    fake = types.ModuleType("requests")

    class FakeResponse:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def json(self) -> dict[str, Any]:
            return self._data

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, params: dict[str, Any] | None = None, **_kwargs: Any) -> FakeResponse:
        calls.append({"url": url, "params": dict(params or {})})
        series_id = url.rsplit("/", 1)[-1]
        rows = values_by_series.get(series_id, [])
        return FakeResponse(
            {
                "response": {
                    "data": [{"period": period, "value": str(value)} for period, value in rows]
                }
            }
        )

    fake.get = fake_get  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", fake)


def test_fetch_raises_feed_not_configured_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))

    adapter = EIAAdapter()
    with pytest.raises(FeedNotConfiguredError, match="EIA_API_KEY"):
        adapter.fetch(["PET.WTISPLC.W"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_raises_offline_mode_error_when_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    monkeypatch.setenv("EIA_API_KEY", "test-key")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))

    adapter = EIAAdapter()
    with pytest.raises(OfflineModeError, match="eia"):
        adapter.fetch(["PET.WTISPLC.W"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_builds_url_with_api_key_and_date_range(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("EIA_API_KEY", "abc123")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("alphakit.data.futures.eia_adapter.ratelimit_acquire", lambda _n: None)

    calls: list[dict[str, Any]] = []
    _install_fake_requests(
        monkeypatch,
        calls,
        {"PET.WTISPLC.W": [("2024-01-02", 70.5), ("2024-01-03", 71.2)]},
    )

    adapter = EIAAdapter()
    adapter.fetch(["PET.WTISPLC.W"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/PET.WTISPLC.W")
    assert calls[0]["params"]["api_key"] == "abc123"
    assert calls[0]["params"]["start"] == "2024-01-02"
    assert calls[0]["params"]["end"] == "2024-01-10"


def test_fetch_parses_multi_symbol_response_into_wide_frame(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("EIA_API_KEY", "abc123")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("alphakit.data.futures.eia_adapter.ratelimit_acquire", lambda _n: None)

    _install_fake_requests(
        monkeypatch,
        [],
        {
            "PET.WTISPLC.W": [("2024-01-02", 70.0), ("2024-01-03", 71.0)],
            "NG.RNGWHHD.D": [("2024-01-02", 2.5), ("2024-01-03", 2.6)],
        },
    )

    adapter = EIAAdapter()
    df = adapter.fetch(
        ["PET.WTISPLC.W", "NG.RNGWHHD.D"],
        datetime(2024, 1, 2),
        datetime(2024, 1, 10),
    )

    assert list(df.columns) == ["PET.WTISPLC.W", "NG.RNGWHHD.D"]
    assert len(df) == 2
    assert df.loc[df.index[0], "PET.WTISPLC.W"] == 70.0
    assert df.loc[df.index[-1], "NG.RNGWHHD.D"] == 2.6


def test_fetch_handles_empty_response_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A series with no data points yields an empty column, not a crash."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("EIA_API_KEY", "abc123")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("alphakit.data.futures.eia_adapter.ratelimit_acquire", lambda _n: None)

    _install_fake_requests(monkeypatch, [], {"EMPTY.SERIES": []})

    adapter = EIAAdapter()
    df = adapter.fetch(["EMPTY.SERIES"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert "EMPTY.SERIES" in df.columns
    assert df.empty or len(df) == 0


def test_fetch_missing_requests_library_raises_import_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("EIA_API_KEY", "abc123")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "requests", None)

    adapter = EIAAdapter()
    with pytest.raises(ImportError, match="requests"):
        adapter.fetch(["PET.WTISPLC.W"], datetime(2024, 1, 2), datetime(2024, 1, 10))
