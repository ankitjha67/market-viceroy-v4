"""Tests for the Phase 2 Polygon placeholder adapter (ADR-004)."""

from __future__ import annotations

from datetime import datetime

import pytest
from alphakit.data.errors import PolygonNotConfiguredError
from alphakit.data.options.polygon_adapter import PolygonAdapter


def test_polygon_fetch_chain_raises_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``POLYGON_API_KEY`` the placeholder directs to synthetic-options."""
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    adapter = PolygonAdapter()
    with pytest.raises(PolygonNotConfiguredError, match="POLYGON_API_KEY") as excinfo:
        adapter.fetch_chain("SPY", datetime(2024, 1, 2))
    # Placeholder contract (ADR-004): message must direct callers at the
    # synthetic-options substitute, not just state that the key is missing.
    assert "synthetic-options" in str(excinfo.value)


def test_polygon_fetch_chain_raises_not_implemented_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a key the placeholder points at the Phase 3 roadmap."""
    monkeypatch.setenv("POLYGON_API_KEY", "test-key-not-real")
    adapter = PolygonAdapter()
    with pytest.raises(NotImplementedError, match="Phase 3"):
        adapter.fetch_chain("SPY", datetime(2024, 1, 2))


def test_polygon_fetch_raises_not_implemented_regardless_of_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``fetch`` is out of scope for the Phase 2 placeholder either way."""
    adapter = PolygonAdapter()
    # Without key.
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    with pytest.raises(NotImplementedError, match="placeholder"):
        adapter.fetch(["SPY"], datetime(2024, 1, 2), datetime(2024, 1, 10))
    # With key.
    monkeypatch.setenv("POLYGON_API_KEY", "test-key-not-real")
    with pytest.raises(NotImplementedError, match="placeholder"):
        adapter.fetch(["SPY"], datetime(2024, 1, 2), datetime(2024, 1, 10))
