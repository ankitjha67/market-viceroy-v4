"""Tests for alphakit.data.registry.FeedRegistry."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pandas as pd
import pytest
from alphakit.core.data import OptionChain
from alphakit.core.protocols import raise_chain_not_supported
from alphakit.data.registry import FeedRegistry


class _StubFeed:
    """Minimal DataFeedProtocol implementation used as a registry fixture."""

    def __init__(self, name: str) -> None:
        self.name = name

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        return pd.DataFrame({s: [1.0] for s in symbols})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    """Reset the FeedRegistry before and after every test."""
    FeedRegistry.clear()
    yield
    FeedRegistry.clear()


def test_register_and_get_roundtrip() -> None:
    feed = _StubFeed("alpha")
    FeedRegistry.register(feed)
    assert FeedRegistry.get("alpha") is feed


def test_register_duplicate_raises_value_error() -> None:
    FeedRegistry.register(_StubFeed("alpha"))
    with pytest.raises(ValueError, match=r"'alpha' already registered"):
        FeedRegistry.register(_StubFeed("alpha"))


def test_get_unknown_key_lists_registered_feeds() -> None:
    FeedRegistry.register(_StubFeed("beta"))
    FeedRegistry.register(_StubFeed("alpha"))
    with pytest.raises(KeyError) as exc:
        FeedRegistry.get("ghost")
    msg = str(exc.value)
    assert "'ghost'" in msg
    # Message lists registered feeds sorted alphabetically.
    assert "alpha" in msg and "beta" in msg
    assert msg.index("alpha") < msg.index("beta")


def test_list_returns_sorted_names() -> None:
    FeedRegistry.register(_StubFeed("gamma"))
    FeedRegistry.register(_StubFeed("alpha"))
    FeedRegistry.register(_StubFeed("beta"))
    assert FeedRegistry.list() == ["alpha", "beta", "gamma"]


def test_clear_removes_all() -> None:
    FeedRegistry.register(_StubFeed("alpha"))
    FeedRegistry.register(_StubFeed("beta"))
    FeedRegistry.clear()
    assert FeedRegistry.list() == []


def test_register_independent_instances_same_name_still_rejected() -> None:
    """Two separate instances sharing a name must still raise."""
    FeedRegistry.register(_StubFeed("alpha"))
    second = _StubFeed("alpha")
    with pytest.raises(ValueError):
        FeedRegistry.register(second)


def test_get_returns_same_instance_across_calls() -> None:
    feed = _StubFeed("alpha")
    FeedRegistry.register(feed)
    assert FeedRegistry.get("alpha") is FeedRegistry.get("alpha")


# ---------------------------------------------------------------------------
# Session 2J S2J-1.5 — registry-population regression guard.
#
# Adapters register themselves at module-import time via
# ``FeedRegistry.register(...)``. The S2J router dispatches via
# ``FeedRegistry.get(name)``, so the registry MUST be populated by the time the
# runner is imported in production. The in-process autouse ``clean_registry``
# fixture above wipes the registry between tests, and pytest's own collection
# imports plenty of modules, so an in-process assertion can't catch a missing
# import-time registration — these regression checks spawn a fresh Python
# subprocess that imports nothing but ``alphakit.data`` (or the runner) and
# asserts every expected feed is registered. The adapter modules must be
# imported by ``alphakit/data/__init__.py`` for their ``register(...)`` side
# effects to fire. (Bug fixed in S2J-1.5 after Codex caught it on PR #22 —
# tests passed in-process because monkeypatch's ``setattr`` on string
# adapter-method paths forced the import as a side effect, which production
# paths do not.)
# ---------------------------------------------------------------------------

_EXPECTED_FEEDS = (
    "yfinance",
    "fred",
    "yfinance-futures",
    "cftc-cot",
    "cftc-cot-wide",
    "eia",
    "polygon",
    "synthetic-options",
)


def _subprocess_assert_registered(setup: str) -> None:
    """Run ``setup`` in a fresh subprocess and assert every expected feed is
    registered. Fails with the subprocess stderr if any feed is missing."""
    import subprocess
    import sys

    names = ", ".join(repr(n) for n in _EXPECTED_FEEDS)
    code = (
        f"{setup}\n"
        "from alphakit.data.registry import FeedRegistry\n"
        f"for n in ({names},):\n"
        "    FeedRegistry.get(n)\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"registry missing adapters in fresh process\nstderr: {result.stderr}\n"
        f"stdout: {result.stdout}"
    )
    assert "OK" in result.stdout


def test_data_package_import_registers_all_adapters() -> None:
    """``import alphakit.data`` alone must register every adapter."""
    _subprocess_assert_registered("import alphakit.data")


def test_runner_import_path_registers_all_adapters() -> None:
    """The production code path — ``from alphakit.bench.runner import
    BenchmarkRunner`` — must trigger the same registrations transitively."""
    _subprocess_assert_registered("from alphakit.bench.runner import BenchmarkRunner")
