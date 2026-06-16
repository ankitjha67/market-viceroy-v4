"""Tests for the ``scripts/regenerate_benchmarks.py`` ``--feed real`` path (Session 2I).

The Tier-2 (FRED-gated) strategies can be regenerated either on synthetic
panels (``--feed synthetic``, default, unchanged) or against real
yfinance + FRED data (``--feed real``) via the multi-feed
``BenchmarkRunner(strict_feed=True)``. These tests cover:

* the prerequisite fail-loud (``FRED_API_KEY`` unset → ``FeedNotConfiguredError``
  with an actionable message),
* ``data_source`` stamping for both feeds, and
* a cheap end-to-end real-feed regen with the two adapters mocked, so no
  network is touched and no benchmark file on disk is clobbered.

The script lives under ``scripts/`` (not an importable package), so it is
loaded by path via :mod:`importlib`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from alphakit.bench import discovery
from alphakit.data.errors import FeedNotConfiguredError

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "regenerate_benchmarks.py"
_spec = importlib.util.spec_from_file_location("regenerate_benchmarks", _SCRIPT)
assert _spec is not None and _spec.loader is not None
regen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(regen)

_REGIME_SLUG = "recession_probability_rotation"


def test_require_fred_real_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--feed real`` without FRED_API_KEY fails loud with an actionable message."""
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(FeedNotConfiguredError) as exc:
        regen._require_fred_real()
    msg = str(exc.value)
    assert "FRED_API_KEY" in msg
    assert "export FRED_API_KEY" in msg  # Linux/macOS setup
    assert "SetEnvironmentVariable" in msg  # Windows setup
    assert "--feed real" in msg  # the re-run command


def test_require_fred_real_with_key_and_package_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a key set and ``fredapi`` importable, the prerequisite check is a no-op."""
    pytest.importorskip("fredapi")
    monkeypatch.setenv("FRED_API_KEY", "dummy-key-for-prereq-check")
    regen._require_fred_real()  # must not raise


def test_regen_tier2_real_stamps_data_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real path passes no prices, runs strict, and stamps ``yfinance+fred-real``."""
    written: list[dict[str, Any]] = []
    ctor_kwargs: list[dict[str, Any]] = []

    class StubRunner:
        def __init__(self, **kwargs: Any) -> None:
            ctor_kwargs.append(kwargs)

        def run_single(
            self, slug: str, prices: Any = None, *, family: str | None = None
        ) -> dict[str, Any]:
            assert prices is None, "real path must let the runner fetch (no pre-loaded prices)"
            return {
                "slug": slug,
                "status": "populated",
                "metrics": {"sharpe": 0.42},
                "universe": ["SPY", "TLT", "GLD", "RECPROUSM156N"],
            }

        def write_benchmark(
            self, slug: str, result: dict[str, Any], *, family: str | None = None
        ) -> None:
            written.append(result)

    monkeypatch.setattr(regen, "BenchmarkRunner", StubRunner)
    ok, msg = regen.regen_tier2_real(_REGIME_SLUG)

    assert ok, msg
    assert written and written[-1]["data_source"] == "yfinance+fred-real"
    assert any(k.get("strict_feed") is True for k in ctor_kwargs), "real regen must run strict_feed"


def test_regen_tier2_synthetic_default_stamps_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default synthetic path is unchanged: a panel is passed and stamped fixture."""
    written: list[dict[str, Any]] = []

    class StubRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def run_single(
            self, slug: str, prices: Any = None, *, family: str | None = None
        ) -> dict[str, Any]:
            assert prices is not None, "synthetic path must pass a pre-built panel"
            return {"slug": slug, "status": "populated", "metrics": {"sharpe": 0.1}}

        def write_benchmark(
            self, slug: str, result: dict[str, Any], *, family: str | None = None
        ) -> None:
            written.append(result)

    monkeypatch.setattr(regen, "BenchmarkRunner", StubRunner)
    ok, msg = regen.regen_tier2(_REGIME_SLUG)

    assert ok, msg
    assert written and written[-1]["data_source"] == "synthetic-fixture"


def test_regen_tier2_real_integration_mocked_feeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end real regen with both adapters mocked: no network, no disk write.

    Drives the actual ``BenchmarkRunner(strict_feed=True)`` multi-feed path —
    the tradable columns come from the (mocked) yfinance adapter and the
    informational columns from the (mocked) FRED adapter — and asserts the
    written result is populated and stamped ``yfinance+fred-real``.
    """
    strategy = discovery.instantiate("macro", _REGIME_SLUG)
    universe = list(discovery.load_config("macro", _REGIME_SLUG)["universe"])
    informational = [s for s in universe if s not in set(strategy.tradable_symbols)]

    panel = regen._TIER2_PANELS[_REGIME_SLUG]()
    tradable = [c for c in panel.columns if c not in set(informational)]
    etf = panel[tradable]
    fred = panel[informational]

    def fake_yf(self: Any, *args: Any, **kwargs: Any) -> Any:
        return etf

    def fake_fred(self: Any, *args: Any, **kwargs: Any) -> Any:
        return fred

    monkeypatch.setattr("alphakit.data.equities.yfinance_adapter.YFinanceAdapter.fetch", fake_yf)
    monkeypatch.setattr("alphakit.data.rates.fred_adapter.FREDAdapter.fetch", fake_fred)

    written: list[dict[str, Any]] = []

    def fake_write(
        self: Any, slug: str, result: dict[str, Any], *, family: str | None = None
    ) -> None:
        written.append(result)

    monkeypatch.setattr(regen.BenchmarkRunner, "write_benchmark", fake_write)

    ok, msg = regen.regen_tier2_real(_REGIME_SLUG)

    assert ok, msg
    assert written, "expected a benchmark result to be written"
    result = written[-1]
    assert result["data_source"] == "yfinance+fred-real"
    assert result["status"] == "populated"
    assert "sharpe" in result["metrics"]


# ---------------------------------------------------------------------------
# Session 2J — commodity --feed real (yfinance-futures only).
# cot_speculator_position was deferred from this regen path in S2J-2.8 and
# moves to Session 2K (architectural symbol→market-code mapping work). Its
# routing tests live in ``test_runner.py::TestCotIntegrationMultiFeed`` —
# those continue to exercise the multi-feed dispatch independent of the
# regen script.
# ---------------------------------------------------------------------------

_FRONT_MONTH_SLUGS = (
    "commodity_tsmom",
    "crack_spread",
    "crush_spread",
    "grain_seasonality",
    "metals_momentum",
    "wti_brent_spread",
)


def test_require_commodity_real_without_yfinance_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """``commodity --feed real`` without yfinance importable fails loud."""
    import builtins
    import sys as _sys

    real_import = builtins.__import__

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "yfinance" or name.startswith("yfinance."):
            raise ImportError("simulated: no yfinance")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.delitem(_sys.modules, "yfinance", raising=False)
    with pytest.raises(SystemExit) as exc:
        regen._require_commodity_real()
    assert "yfinance" in str(exc.value)
    assert "commodity --feed real" in str(exc.value)


@pytest.mark.parametrize("slug", _FRONT_MONTH_SLUGS)
def test_regen_commodity_real_stamps_yfinance_futures(
    monkeypatch: pytest.MonkeyPatch, slug: str
) -> None:
    """Each of the 6 front-month commodity strategies stamps ``yfinance-futures-real``."""
    written: list[dict[str, Any]] = []
    ctor_kwargs: list[dict[str, Any]] = []

    class StubRunner:
        def __init__(self, **kwargs: Any) -> None:
            ctor_kwargs.append(kwargs)

        def run_single(
            self, slug: str, prices: Any = None, *, family: str | None = None
        ) -> dict[str, Any]:
            assert prices is None, "commodity real path must let the runner fetch"
            assert family == "commodity"
            return {
                "slug": slug,
                "status": "populated",
                "metrics": {"sharpe": 0.33},
                "universe": ["CL=F", "NG=F"],
            }

        def write_benchmark(
            self, slug: str, result: dict[str, Any], *, family: str | None = None
        ) -> None:
            written.append(result)

    monkeypatch.setattr(regen, "BenchmarkRunner", StubRunner)
    ok, msg = regen.regen_commodity_real(slug)

    assert ok, msg
    assert written and written[-1]["data_source"] == "yfinance-futures-real"
    assert any(k.get("strict_feed") is True for k in ctor_kwargs)


def test_main_commodity_requires_feed_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """``commodity`` mode without ``--feed real`` fails with an actionable message."""
    import sys as _sys

    monkeypatch.setattr(_sys, "argv", ["regenerate_benchmarks.py", "commodity"])
    with pytest.raises(SystemExit) as exc:
        regen.main()
    msg = str(exc.value)
    assert "--feed real" in msg
    assert "second-month" in msg  # mentions the constraint for the 3 blocked
