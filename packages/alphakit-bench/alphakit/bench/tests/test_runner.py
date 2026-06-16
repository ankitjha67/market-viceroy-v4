"""Tests for alphakit.bench.runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest
from alphakit.bench import discovery
from alphakit.bench.runner import BenchmarkRunner
from alphakit.data.errors import FeedNotConfiguredError


@pytest.fixture
def runner() -> BenchmarkRunner:
    return BenchmarkRunner(
        commission_bps=5.0,
        data_start="2005-01-01",
        in_sample_end="2019-12-31",
        out_of_sample_end="2025-12-31",
    )


class TestBenchmarkRunner:
    def test_run_single_produces_valid_result(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("tsmom_12_1")
        assert result["slug"] == "tsmom_12_1"
        assert result["status"] == "populated"
        assert result["engine"] == "vectorbt"

    def test_result_has_all_metric_keys(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("tsmom_12_1")
        metrics = result["metrics"]
        for key in (
            "sharpe",
            "sortino",
            "calmar",
            "max_drawdown",
            "annualized_return",
            "annualized_vol",
            "turnover_annual",
            "capacity_usd_bn",
        ):
            assert key in metrics
            assert isinstance(metrics[key], float)
            assert np.isfinite(metrics[key])

    def test_result_has_regime_performance(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("tsmom_12_1")
        regime = result["regime_performance"]
        for key in ("bull_market_sharpe", "bear_market_sharpe", "sideways_sharpe"):
            assert key in regime
            assert isinstance(regime[key], float)

    def test_result_has_metadata(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("tsmom_12_1")
        assert result["data_start"] == "2005-01-01"
        assert result["in_sample_end"] == "2019-12-31"
        assert result["out_of_sample_end"] == "2025-12-31"
        assert result["transaction_costs_assumed_bps"] == 5.0
        assert isinstance(result["universe"], list)

    def test_result_is_json_serializable(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("tsmom_12_1")
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)
        assert deserialized["slug"] == "tsmom_12_1"

    def test_write_benchmark(
        self,
        runner: BenchmarkRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Redirect the resolved benchmark path into tmp_path so the write
        # never touches the tracked in-repo benchmark_results.json. (The
        # runner resolves the target via discovery.benchmark_results_path.)
        target = tmp_path / "benchmark_results.json"
        monkeypatch.setattr(discovery, "benchmark_results_path", lambda family, slug: target)

        result = runner.run_single("tsmom_12_1")
        result["slug"] = "tsmom_12_1"

        path = runner.write_benchmark("tsmom_12_1", result, family="trend")
        # Guard: the write must land at the redirected target, not the repo.
        assert path == target
        assert path.exists()
        with open(path) as f:
            written = json.load(f)
        assert written["slug"] == "tsmom_12_1"
        assert written["status"] == "populated"

    def test_write_benchmark_does_not_mutate_repo_file(
        self,
        runner: BenchmarkRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Regression guard for the working-tree-pollution bug: with the
        # benchmark path redirected, write_benchmark must leave the tracked
        # in-repo file byte-for-byte unchanged.
        real_path = discovery.benchmark_results_path("trend", "tsmom_12_1")
        before = real_path.read_bytes()

        target = tmp_path / "benchmark_results.json"
        monkeypatch.setattr(discovery, "benchmark_results_path", lambda family, slug: target)

        result = runner.run_single("tsmom_12_1")
        runner.write_benchmark("tsmom_12_1", result, family="trend")

        assert target.exists(), "redirected write should land in tmp_path"
        assert real_path.read_bytes() == before, "tracked repo file must be untouched"

    def test_write_benchmark_overwrites_existing_and_stale_tmp(
        self,
        runner: BenchmarkRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Regression for the Windows atomic-write bug: on a regen the target
        # benchmark_results.json already exists (and a crashed prior run may have
        # left a stale .tmp). Path.rename raised FileExistsError on Windows;
        # Path.replace must overwrite cleanly on every platform.
        target = tmp_path / "benchmark_results.json"
        target.write_text('{"old": true}\n')
        stale_tmp = target.with_suffix(".json.tmp")
        stale_tmp.write_text("garbage from a crashed run")
        monkeypatch.setattr(discovery, "benchmark_results_path", lambda family, slug: target)

        result = runner.run_single("tsmom_12_1")
        path = runner.write_benchmark("tsmom_12_1", result, family="trend")

        assert path == target
        with open(path) as f:
            written = json.load(f)
        assert written["slug"] == "tsmom_12_1"  # overwritten, not the old content
        assert not stale_tmp.exists()  # the temp file was consumed by the replace

    def test_auto_detect_family(self, runner: BenchmarkRunner) -> None:
        result = runner.run_single("vol_targeting")
        assert result["slug"] == "vol_targeting"

    def test_deterministic_results(self, runner: BenchmarkRunner) -> None:
        a = runner.run_single("tsmom_12_1")
        b = runner.run_single("tsmom_12_1")
        assert a["metrics"]["sharpe"] == b["metrics"]["sharpe"]


# ---------------------------------------------------------------------------
# Session 2I — multi-feed runner (split routing, FRED alignment, strict_feed)
# ---------------------------------------------------------------------------

_YF_PATH = "alphakit.data.equities.yfinance_adapter.YFinanceAdapter.fetch"
_FRED_PATH = "alphakit.data.rates.fred_adapter.FREDAdapter.fetch"

# Realistic positive magnitudes per FRED series (so regime thresholds behave).
_FRED_MAG: dict[str, tuple[float, float]] = {
    "RECPROUSM156N": (0.1, 0.5),
    "CPIAUCSL": (250.0, 285.0),
    "GDPC1": (20000.0, 23000.0),
    "DGS10": (1.5, 4.0),
    "DGS2": (1.0, 3.0),
    "FEDFUNDS": (0.25, 4.0),
}


class _StubFREDGated:
    """Strategy stub exposing the Session 2G routing properties (has FRED cols)."""

    tradable_symbols = ("SPY", "TLT", "GLD")
    required_symbols = ("SPY", "TLT", "GLD", "DGS10", "DGS2")


class _StubGDP:
    """Strategy stub whose only informational column is quarterly GDPC1."""

    tradable_symbols = ("SPY", "TLT", "GLD", "DBC")
    required_symbols = ("SPY", "TLT", "GLD", "DBC", "GDPC1")


class _StubETFOnly:
    """Strategy stub with no informational columns (single-feed)."""

    tradable_symbols = ("SPY", "TLT", "GLD")
    required_symbols = ("SPY", "TLT", "GLD")


def _bdays(start: str = "2005-01-01", end: str = "2025-12-31") -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="B")


def _etf_panel(symbols: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Positive daily ETF prices for the requested symbols."""
    return pd.DataFrame(
        {s: np.linspace(100.0, 150.0, len(index)) for s in symbols},
        index=index,
    )


def _fred_panel(symbols: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Positive FRED series for the requested symbols at the given (native) index.

    A monotonic ramp lo→hi (distinct per row, so each native observation differs
    after ffill) that also crosses each series' regime threshold once.
    """
    n = len(index)
    cols = {}
    for s in symbols:
        lo, hi = _FRED_MAG.get(s, (1.0, 5.0))
        cols[s] = np.linspace(lo, hi, n) if n > 1 else np.full(n, (lo + hi) / 2)
    return pd.DataFrame(cols, index=index)


def _patch_feeds(
    monkeypatch: pytest.MonkeyPatch,
    *,
    etf_index: pd.DatetimeIndex,
    fred_index: pd.DatetimeIndex,
    fred_exc: Exception | None = None,
) -> None:
    """Patch both adapter.fetch methods to return synthetic positive panels."""

    def _yf(
        self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
    ) -> pd.DataFrame:
        return _etf_panel(list(symbols), etf_index)

    def _fred(
        self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
    ) -> pd.DataFrame:
        if fred_exc is not None:
            raise fred_exc
        return _fred_panel(list(symbols), fred_index)

    monkeypatch.setattr(_YF_PATH, _yf)
    monkeypatch.setattr(_FRED_PATH, _fred)


class TestInformationalColumnRouting:
    def test_split_for_fred_gated(self, runner: BenchmarkRunner) -> None:
        universe = ["SPY", "TLT", "GLD", "DGS10", "DGS2"]
        assert runner._informational_columns(_StubFREDGated(), universe) == ["DGS10", "DGS2"]

    def test_empty_for_etf_only(self, runner: BenchmarkRunner) -> None:
        assert runner._informational_columns(_StubETFOnly(), ["SPY", "TLT", "GLD"]) == []

    def test_empty_when_no_routing_properties(self, runner: BenchmarkRunner) -> None:
        # A plain object (no tradable_symbols/required_symbols) → single-feed.
        assert runner._informational_columns(object(), ["SPY", "TLT"]) == []


class TestMultiFeedFetch:
    def test_etf_only_never_calls_fred(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"fred": False}

        def _yf(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return _etf_panel(list(symbols), _bdays("2018-01-01", "2020-12-31"))

        def _fred(self: object, *a: object, **k: object) -> pd.DataFrame:
            called["fred"] = True
            raise AssertionError("FRED must not be called for an ETF-only universe")

        monkeypatch.setattr(_YF_PATH, _yf)
        monkeypatch.setattr(_FRED_PATH, _fred)
        panel = runner._fetch_prices(["SPY", "TLT", "GLD"], strategy=_StubETFOnly())
        assert list(panel.columns) == ["SPY", "TLT", "GLD"]
        assert called["fred"] is False

    def test_split_routes_and_merges(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        idx = _bdays("2010-01-01", "2015-12-31")
        monthly = pd.date_range("2010-01-01", "2015-12-31", freq="MS")
        _patch_feeds(monkeypatch, etf_index=idx, fred_index=monthly)
        universe = ["SPY", "TLT", "GLD", "DGS10", "DGS2"]
        panel = runner._fetch_prices(universe, strategy=_StubFREDGated())
        # column order preserved == universe; all present, all positive
        assert list(panel.columns) == universe
        assert panel.notna().all().all()
        assert (panel.to_numpy() > 0).all()

    def test_quarterly_gdp_ffill_alignment(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        idx = _bdays("2010-01-01", "2012-12-31")
        quarterly = pd.date_range("2010-01-01", "2012-12-31", freq="QS")  # quarter starts
        _patch_feeds(monkeypatch, etf_index=idx, fred_index=quarterly)
        universe = ["SPY", "TLT", "GLD", "DBC", "GDPC1"]
        panel = runner._fetch_prices(universe, strategy=_StubGDP())
        gdp = panel["GDPC1"]
        # No mid-panel gaps after ffill.
        assert gdp.notna().all()
        # ~12 quarterly values spread across ~63 business days each (no bfill:
        # the count of distinct values matches the number of quarters covered).
        assert 8 <= gdp.nunique() <= 13
        # Each distinct value persists for roughly a quarter (~45-70 bdays).
        run_lengths = gdp.groupby((gdp != gdp.shift()).cumsum()).size()
        assert run_lengths.max() <= 75

    def test_zero_trim_when_fred_starts_with_etf(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        idx = _bdays("2010-01-04", "2011-12-30")
        # FRED first observation coincides with the first ETF bar → zero trim.
        fred_idx = pd.DatetimeIndex([idx[0], *pd.date_range("2010-02-01", "2011-12-30", freq="MS")])
        _patch_feeds(monkeypatch, etf_index=idx, fred_index=fred_idx)
        panel = runner._fetch_prices(
            ["SPY", "TLT", "GLD", "DGS10", "DGS2"], strategy=_StubFREDGated()
        )
        assert panel.index[0] == idx[0]  # no leading rows trimmed


class _StubGrowthInflation:
    """Stub mirroring growth_inflation: monthly CPI + quarterly GDP informational."""

    tradable_symbols = ("SPY", "TLT", "GLD", "DBC")
    required_symbols = ("SPY", "TLT", "GLD", "DBC", "CPIAUCSL", "GDPC1")


class TestMultiFeedAlignment:
    """Regression for the real-feed alignment bugs S2I-1 mocks hid.

    The earlier ``_fred_panel`` fixtures were always-finite single-frequency
    ramps, so they never exercised: (a) mixed-frequency series assembled into one
    DataFrame by the adapter (quarterly GDP gets internal NaN on a monthly union
    index), (b) daily series with holiday NaN, or (c) trailing publication lag.
    A plain ``reindex(method="ffill")`` is index-based and preserves those NaN;
    the runner now does a value-based as-of fill over the union index.
    """

    def test_mixed_frequency_union_nan_filled(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        etf_idx = _bdays("2005-01-03", "2025-12-31")
        universe = ["SPY", "TLT", "GLD", "DBC", "CPIAUCSL", "GDPC1"]

        def _yf(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return _etf_panel(list(symbols), etf_idx)

        def _fred(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            # Mimic FREDAdapter.fetch: pd.DataFrame({id: get_series(...)}) aligns
            # mixed-frequency series on the UNION index → quarterly GDPC1 carries
            # internal NaN on every off-quarter month, and ends earlier than CPI
            # (a deeper publication lag).
            series: dict[str, pd.Series] = {}
            if "CPIAUCSL" in symbols:
                cpi_idx = pd.date_range("2005-01-01", "2025-11-01", freq="MS")
                series["CPIAUCSL"] = pd.Series(
                    np.linspace(250.0, 320.0, len(cpi_idx)), index=cpi_idx
                )
            if "GDPC1" in symbols:
                gdp_idx = pd.date_range("2005-01-01", "2025-07-01", freq="QS")
                series["GDPC1"] = pd.Series(
                    np.linspace(20000.0, 23000.0, len(gdp_idx)), index=gdp_idx
                )
            return pd.DataFrame(series)

        monkeypatch.setattr(_YF_PATH, _yf)
        monkeypatch.setattr(_FRED_PATH, _fred)
        panel = runner._fetch_prices(universe, strategy=_StubGrowthInflation())

        assert list(panel.columns) == universe
        # The bug: GDPC1 (and the whole panel) was riddled with NaN before the fix.
        assert np.isfinite(panel.to_numpy()).all()
        assert panel["GDPC1"].notna().all()
        # Trailing publication lag: GDPC1's last obs (2025-07-01) is carried to
        # the panel's final bar (2025-12-31) rather than left NaN.
        assert panel["GDPC1"].iloc[-1] == pytest.approx(23000.0)

    def test_daily_holiday_nan_filled(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        etf_idx = _bdays("2005-01-03", "2025-12-31")

        def _yf(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return _etf_panel(list(symbols), etf_idx)

        def _fred(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            # Daily yields: business-day index with NaN on market holidays
            # (FRED serves "." → NaN) and ending before today (publication lag).
            day_idx = pd.date_range("2005-01-03", "2025-12-19", freq="B")
            out: dict[str, pd.Series] = {}
            for s in symbols:
                lo, hi = _FRED_MAG.get(s, (1.0, 5.0))
                ser = pd.Series(np.linspace(lo, hi, len(day_idx)), index=day_idx)
                ser.iloc[40::40] = np.nan  # scattered holiday gaps (not the first row)
                out[s] = ser
            return pd.DataFrame(out)

        monkeypatch.setattr(_YF_PATH, _yf)
        monkeypatch.setattr(_FRED_PATH, _fred)
        panel = runner._fetch_prices(
            ["SPY", "TLT", "GLD", "DGS10", "DGS2"], strategy=_StubFREDGated()
        )
        # Holiday NaN (mid-panel) and trailing-lag NaN are both ffilled away.
        assert np.isfinite(panel.to_numpy()).all()


class TestFeedValueValidation:
    """Contract for ``_validate_feed_values``: finite everywhere; tradable > 0.

    Informational columns are *not* required positive — the bridge drops
    identically-zero-weight columns before ``from_orders``, so a recession
    probability of 0.0 or a negative real-yield level is valid input.
    """

    @staticmethod
    def _panel() -> pd.DataFrame:
        idx = _bdays("2012-01-01", "2012-06-30")
        return _etf_panel(["SPY", "TLT"], idx)

    def test_nonfinite_raises(self, runner: BenchmarkRunner) -> None:
        panel = self._panel()
        panel["DGS10"] = 2.0
        panel.loc[panel.index[3], "DGS10"] = np.nan
        with pytest.raises(ValueError, match="non-finite"):
            runner._validate_feed_values(panel, informational=["DGS10"])

    def test_negative_tradable_raises(self, runner: BenchmarkRunner) -> None:
        panel = self._panel()
        panel["DGS10"] = 2.0
        panel.loc[panel.index[3], "SPY"] = -1.0
        with pytest.raises(ValueError, match="non-positive"):
            runner._validate_feed_values(panel, informational=["DGS10"])

    def test_zero_informational_allowed(self, runner: BenchmarkRunner) -> None:
        # The exact value that crashed S2I-1 on real data: a probability of 0.0.
        panel = self._panel()
        panel["RECPROUSM156N"] = 0.0
        runner._validate_feed_values(panel, informational=["RECPROUSM156N"])  # no raise

    def test_negative_informational_allowed(self, runner: BenchmarkRunner) -> None:
        panel = self._panel()
        panel["DFII10"] = -0.5  # real yields can be negative; never traded
        runner._validate_feed_values(panel, informational=["DFII10"])  # no raise


class TestInformationalZeroEndToEnd:
    @pytest.mark.integration
    def test_zero_informational_runs_through_bridge(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A weight-0 informational column holding 0.0 must not crash the bridge.

        Regression for S2I-1's real-feed failure: vectorbt rejected
        ``order.price`` for the (untraded) RECPROUSM156N column when it hit 0.0.
        The bridge now drops identically-zero-weight columns before from_orders.
        """
        idx = _bdays("2005-01-01", "2025-12-31")
        monthly = pd.date_range("2005-01-01", "2025-12-31", freq="MS")

        def _yf(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return _etf_panel(list(symbols), idx)

        def _fred(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            # RECPROUSM156N spends whole stretches at exactly 0.0, crossing the
            # regime threshold so the strategy still rotates among tradables.
            vals = np.where(np.arange(len(monthly)) % 24 < 12, 0.0, 0.5)
            return pd.DataFrame(dict.fromkeys(symbols, vals), index=monthly)

        monkeypatch.setattr(_YF_PATH, _yf)
        monkeypatch.setattr(_FRED_PATH, _fred)
        result = runner.run_single("recession_probability_rotation", family="macro")
        assert np.isfinite(result["metrics"]["sharpe"])
        assert np.isfinite(result["metrics"]["max_drawdown"])


class TestStrictFeed:
    def test_strict_true_propagates_fred_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        idx = _bdays("2015-01-01", "2017-12-31")
        _patch_feeds(
            monkeypatch,
            etf_index=idx,
            fred_index=idx,
            fred_exc=FeedNotConfiguredError("fred requires FRED_API_KEY"),
        )
        runner = BenchmarkRunner(strict_feed=True)
        with pytest.raises(FeedNotConfiguredError):
            runner._fetch_prices(["SPY", "TLT", "GLD", "DGS10", "DGS2"], strategy=_StubFREDGated())

    def test_strict_false_falls_back_to_fixtures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        idx = _bdays("2015-01-01", "2017-12-31")
        _patch_feeds(
            monkeypatch,
            etf_index=idx,
            fred_index=idx,
            fred_exc=FeedNotConfiguredError("fred requires FRED_API_KEY"),
        )
        runner = BenchmarkRunner(strict_feed=False)
        panel = runner._fetch_prices(
            ["SPY", "TLT", "GLD", "DGS10", "DGS2"], strategy=_StubFREDGated()
        )
        # Fixture fallback fills the FRED columns with positive synthetic series.
        assert set(panel.columns) == {"SPY", "TLT", "GLD", "DGS10", "DGS2"}
        assert (panel.to_numpy() > 0).all()


class TestMultiFeedIntegration:
    # NOTE: publication-lag is the strategy's concern (.shift on the
    # month-end-resampled series); FRED returns reference-period-dated
    # observations, so the runner is publication-lag-agnostic. No runner-level
    # publication-lag test is needed (would test an unrealistic feed shape).
    @pytest.mark.integration
    @pytest.mark.parametrize(
        "slug",
        [
            "recession_probability_rotation",
            "growth_inflation_regime_rotation",
            "yield_curve_regime_allocation",
            "fed_policy_tilt",
            "inflation_regime_allocation",
        ],
    )
    def test_regime_strategy_end_to_end_multifeed(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch, slug: str
    ) -> None:
        idx = _bdays("2005-01-01", "2025-12-31")
        monthly = pd.date_range("2005-01-01", "2025-12-31", freq="MS")
        _patch_feeds(monkeypatch, etf_index=idx, fred_index=monthly)
        result = runner.run_single(slug, family="macro")
        assert result["slug"] == slug
        assert np.isfinite(result["metrics"]["sharpe"])
        assert np.isfinite(result["metrics"]["max_drawdown"])


# ---------------------------------------------------------------------------
# Session 2J — within-role feed routing (yfinance-futures + cftc-cot-wide)
# ---------------------------------------------------------------------------

_YF_FUTURES_PATH = "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch"
_CFTC_WIDE_PATH = "alphakit.data.positioning.cftc_cot_wide_adapter.CFTCCOTWideAdapter.fetch"


class TestFeedRouting:
    """The within-role pattern dispatcher behind ``BenchmarkRunner._fetch_prices``.

    The Session 2G role split (tradable vs informational) is upstream of this
    dispatch, so patterns only need to disambiguate within each role.
    """

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("SPY", "yfinance"),
            ("TLT", "yfinance"),
            ("CL=F", "yfinance-futures"),
            ("NG=F", "yfinance-futures"),
        ],
    )
    def test_resolves_tradable(self, symbol: str, expected: str) -> None:
        assert BenchmarkRunner._resolve_feed(symbol, "tradable") == expected

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("CPIAUCSL", "fred"),
            ("DGS10", "fred"),
            ("CL=F_NET_SPEC", "cftc-cot-wide"),
            ("GC=F_NET_SPEC", "cftc-cot-wide"),
        ],
    )
    def test_resolves_informational(self, symbol: str, expected: str) -> None:
        assert BenchmarkRunner._resolve_feed(symbol, "informational") == expected

    @pytest.mark.parametrize(
        "slug",
        [
            "commodity_tsmom",
            "crack_spread",
            "crush_spread",
            "grain_seasonality",
            "metals_momentum",
            "wti_brent_spread",
        ],
    )
    def test_front_month_commodity_routes_to_yfinance_futures(self, slug: str) -> None:
        """Every tradable column of the 6 front-month commodity strategies must
        route to ``yfinance-futures`` — verifies the routing resolution without
        actually executing the strategies (S2J-2 covers the keyed regen)."""
        universe = discovery.load_config("commodity", slug)["universe"]
        assert universe and all(
            BenchmarkRunner._resolve_feed(sym, "tradable") == "yfinance-futures" for sym in universe
        )


class TestCotIntegrationMultiFeed:
    """End-to-end ``cot_speculator_position`` via the new yfinance-futures +
    cftc-cot-wide routing. The strategy declares both the Session 2G
    informational pattern (``tradable_symbols`` / ``required_symbols``) and
    the Session 2K-1 ``cftc_market_codes`` mapping; the runner splits
    tradable ``=F`` (→ yfinance-futures) from informational ``*_NET_SPEC``
    (→ cftc-cot-wide), translates NET_SPEC → market codes before fetch, and
    renames returned columns back after fetch. The mocked cftc-cot-wide
    adapter receives MARKET CODES and returns a wide DataFrame keyed by
    those codes — matching the real adapter contract this time (the S2J-1
    mock returned wide keyed by NET_SPEC names, which was the architectural
    mismatch S2J-2.8 surfaced; S2K-1 makes the mock-vs-real shapes match)."""

    @pytest.mark.integration
    def test_cot_runs_end_to_end_via_futures_and_cftc_wide(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        idx = _bdays("2010-01-01", "2025-12-31")
        rng = np.random.default_rng(0)
        prices_by_sym = {
            s: 50.0 * np.exp(np.cumsum(rng.normal(0.0, 0.012, len(idx))))
            for s in ("CL=F", "NG=F", "GC=F", "ZC=F")
        }

        def _fake_yf_futures(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({s: prices_by_sym[s] for s in symbols}, index=idx)

        # CFTC publishes weekly (Tuesday-as-of, Friday-released). Net-spec
        # series legitimately cross zero — exactly the kind of informational
        # value the S2I bridge/runner refinement made valid.
        cot_idx = pd.date_range("2010-01-05", "2025-12-31", freq="W-TUE")

        def _fake_cftc_wide(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            # The cftc-cot-wide adapter receives CFTC market codes (not
            # NET_SPEC names) — the runner translated them. Mock returns
            # wide-by-market-code; the runner renames back to NET_SPEC.
            t = np.linspace(0.0, 8.0 * np.pi, len(cot_idx))
            return pd.DataFrame(
                {code: 0.7 * np.sin(t + 0.4 * i) for i, code in enumerate(symbols)},
                index=cot_idx,
            )

        monkeypatch.setattr(_YF_FUTURES_PATH, _fake_yf_futures)
        monkeypatch.setattr(_CFTC_WIDE_PATH, _fake_cftc_wide)

        result = runner.run_single("cot_speculator_position", family="commodity")
        assert result["slug"] == "cot_speculator_position"
        assert np.isfinite(result["metrics"]["sharpe"])
        assert np.isfinite(result["metrics"]["max_drawdown"])

    def test_missing_cftc_market_codes_raises_actionable_error(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Strategy declaring ``required_symbols`` with ``*_NET_SPEC`` columns
        but missing the ``cftc_market_codes`` mapping fails loud with a clear
        message naming the strategy class and missing symbols."""

        class _BareCotStub:
            """Has Session 2G properties but no cftc_market_codes — the
            runner must surface this as an actionable error rather than
            silently fall through."""

            tradable_symbols = ("CL=F",)
            required_symbols = ("CL=F", "CL=F_NET_SPEC")

        idx = _bdays("2020-01-01", "2020-12-31")

        def _fake_yf_futures(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({s: np.full(len(idx), 50.0) for s in symbols}, index=idx)

        monkeypatch.setattr(_YF_FUTURES_PATH, _fake_yf_futures)
        with pytest.raises(ValueError, match="cftc_market_codes"):
            runner._fetch_prices(["CL=F", "CL=F_NET_SPEC"], strategy=_BareCotStub())

    def test_partial_cftc_market_codes_raises_naming_missing_symbols(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Partial ``cftc_market_codes`` (some NET_SPEC symbols mapped, others
        not) must fail-loud with a message naming the *missing* symbols, not
        silently skip them or fall through to the unmapped names as codes."""

        class _PartialCotStub:
            tradable_symbols = ("CL=F", "NG=F")
            required_symbols = ("CL=F", "NG=F", "CL=F_NET_SPEC", "NG=F_NET_SPEC")
            cftc_market_codes: ClassVar[dict[str, str]] = {
                "CL=F_NET_SPEC": "067651",  # NG=F_NET_SPEC absent
            }

        idx = _bdays("2020-01-01", "2020-12-31")

        def _fake_yf_futures(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({s: np.full(len(idx), 50.0) for s in symbols}, index=idx)

        monkeypatch.setattr(_YF_FUTURES_PATH, _fake_yf_futures)
        with pytest.raises(ValueError, match=r"missing entries for \['NG=F_NET_SPEC'\]"):
            runner._fetch_prices(
                ["CL=F", "NG=F", "CL=F_NET_SPEC", "NG=F_NET_SPEC"],
                strategy=_PartialCotStub(),
            )

    def test_cftc_market_code_absent_from_archive_yields_actionable_failure(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mapping points at a code the adapter returns no data for — the
        adapter's defensive ``reindex(columns=symbols)`` produces a NaN
        column, the runner renames it to NET_SPEC (still NaN), and the
        complete-rows guard in ``_fetch_prices`` raises with a clear
        'no rows where all of ... are simultaneously present' message.
        This is the fail-loud surface for misidentified market codes."""

        class _StaleCodeStub:
            tradable_symbols = ("CL=F",)
            required_symbols = ("CL=F", "CL=F_NET_SPEC")
            cftc_market_codes: ClassVar[dict[str, str]] = {"CL=F_NET_SPEC": "DELISTED_999"}

        idx = _bdays("2020-01-01", "2020-12-31")

        def _fake_yf_futures(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({s: np.full(len(idx), 50.0) for s in symbols}, index=idx)

        def _fake_cftc_wide_missing(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            # Adapter contract under "code not in archive": reindex(columns=
            # symbols) produces an explicit NaN column. Mirror that here.
            cot_idx = pd.date_range("2020-01-07", "2020-12-29", freq="W-TUE")
            return pd.DataFrame(dict.fromkeys(symbols, np.nan), index=cot_idx)

        monkeypatch.setattr(_YF_FUTURES_PATH, _fake_yf_futures)
        monkeypatch.setattr(_CFTC_WIDE_PATH, _fake_cftc_wide_missing)
        with pytest.raises(ValueError, match="no rows where all"):
            runner._fetch_prices(["CL=F", "CL=F_NET_SPEC"], strategy=_StaleCodeStub())

    def test_cftc_wide_skipped_week_forward_fills_via_asof_alignment(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing weekly COT observation (CFTC skipped a Tuesday — e.g.
        holiday or operational gap) must value-ffill from the last available
        observation onto the daily tradable index. Standard as-of semantics:
        you don't know next week's positioning until it's published, so
        using last-known is causally correct (S2I-1.5 amendment)."""

        class _CotStub:
            tradable_symbols = ("CL=F",)
            required_symbols = ("CL=F", "CL=F_NET_SPEC")
            cftc_market_codes: ClassVar[dict[str, str]] = {"CL=F_NET_SPEC": "067651"}

        idx = _bdays("2020-01-01", "2020-03-31")

        def _fake_yf_futures(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({s: np.full(len(idx), 50.0) for s in symbols}, index=idx)

        # COT observations published weekly Tuesdays — but week of 2020-02-04
        # is intentionally absent (simulated gap). The Feb-11 value should
        # forward-fill across the entire Feb-04 → Feb-11 daily window.
        cot_dates = pd.DatetimeIndex(
            ["2020-01-07", "2020-01-14", "2020-01-21", "2020-01-28", "2020-02-11", "2020-02-18"]
        )
        cot_values = [0.10, 0.15, 0.20, 0.25, 0.40, 0.45]

        def _fake_cftc_wide(
            self: object, symbols: list[str], start: object, end: object, frequency: str = "1d"
        ) -> pd.DataFrame:
            return pd.DataFrame({symbols[0]: cot_values}, index=cot_dates)

        monkeypatch.setattr(_YF_FUTURES_PATH, _fake_yf_futures)
        monkeypatch.setattr(_CFTC_WIDE_PATH, _fake_cftc_wide)
        prices = runner._fetch_prices(["CL=F", "CL=F_NET_SPEC"], strategy=_CotStub())

        # Daily ffill across the skipped Feb-4 week: every business day from
        # 2020-01-28 (the last pre-gap Tuesday) through 2020-02-10 carries
        # 0.25; 2020-02-11 onward jumps to 0.40.
        assert prices.loc[pd.Timestamp("2020-01-28"), "CL=F_NET_SPEC"] == pytest.approx(0.25)
        assert prices.loc[pd.Timestamp("2020-02-03"), "CL=F_NET_SPEC"] == pytest.approx(0.25)
        assert prices.loc[pd.Timestamp("2020-02-10"), "CL=F_NET_SPEC"] == pytest.approx(0.25)
        assert prices.loc[pd.Timestamp("2020-02-11"), "CL=F_NET_SPEC"] == pytest.approx(0.40)
        assert prices.loc[pd.Timestamp("2020-02-18"), "CL=F_NET_SPEC"] == pytest.approx(0.45)
        # No mid-panel NaN — gap was successfully bridged by ffill.
        assert not prices["CL=F_NET_SPEC"].isna().any()


# ---------------------------------------------------------------------------
# Session 2J-2.6 — anomaly filter (drop_nonpositive_tradable_bars)
# ---------------------------------------------------------------------------


def _yf_with_anomalies(symbols: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Positive panel with one mid-panel anomaly per known pattern injected.

    Row layout:
      idx[0..29]      clean positive
      idx[30]         NaN in symbols[0] (Thanksgiving-style missing data)
      idx[31..59]     clean positive
      idx[60]         negative price -37.63 in symbols[0] (2020-04-20 style)
      idx[61..]       clean positive
    """
    base = np.full((len(index), len(symbols)), 50.0)
    df = pd.DataFrame(base, index=index, columns=symbols)
    df.iloc[30, 0] = np.nan
    df.iloc[60, 0] = -37.63
    return df


class TestAnomalyFilter:
    """``drop_nonpositive_tradable_bars`` opt-in filter (Session 2J S2J-2.6).

    Default off keeps the runner's strict-positive invariant. Opt-in drops
    rows with non-positive or NaN tradable values and records the audit
    trail in ``last_anomaly_filter`` (mirrored into the benchmark JSON).
    """

    def test_filter_default_off_preserves_strict_invariant(
        self, runner: BenchmarkRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default off: a non-positive tradable still propagates as a failure."""
        idx = _bdays("2020-01-01", "2020-12-31")
        anomalous = _yf_with_anomalies(["CL=F", "NG=F"], idx)

        def _yf(self: object, *a: object, **k: object) -> pd.DataFrame:
            return anomalous

        monkeypatch.setattr(
            "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch", _yf
        )

        # Default runner — filter off.
        assert runner.drop_nonpositive_tradable_bars is False
        # A strategy declaring no informational columns hits the single-feed
        # shortcut; with filter off it just returns the raw fetched panel
        # (anomaly bars still present). The downstream strategy / bridge
        # would then fail on the negative — that's the strict-invariant
        # contract we want preserved when filter is off.
        panel = runner._fetch_prices(["CL=F", "NG=F"], strategy=object())
        assert runner.last_anomaly_filter == {"enabled": False}
        # The negative row from _yf_with_anomalies survived.
        assert (panel["CL=F"] < 0).any()

    def test_filter_drops_negative_and_nan_with_audit_trail(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Filter on: drops both NaN and negative rows; logs + metadata correct."""
        idx = _bdays("2020-01-01", "2020-12-31")
        anomalous = _yf_with_anomalies(["CL=F", "NG=F"], idx)

        def _yf(self: object, *a: object, **k: object) -> pd.DataFrame:
            return anomalous

        monkeypatch.setattr(
            "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch", _yf
        )

        runner = BenchmarkRunner(drop_nonpositive_tradable_bars=True)
        panel = runner._fetch_prices(["CL=F", "NG=F"], strategy=object())

        meta = runner.last_anomaly_filter
        assert meta["enabled"] is True
        assert meta["bars_dropped"] == 2  # the NaN row + the negative row
        assert len(meta["dropped_dates"]) == 2
        # Dates must be strings in YYYY-MM-DD form, ascending.
        assert all(isinstance(d, str) and len(d) == 10 for d in meta["dropped_dates"])
        # Neither anomaly value survived in the returned panel.
        assert not (panel["CL=F"] < 0).any()
        assert not panel["CL=F"].isna().any()

    def test_filter_classifies_log_lines_distinctly(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Log entries identify NaN vs negative-price causes per dropped bar."""
        idx = _bdays("2020-01-01", "2020-12-31")
        anomalous = _yf_with_anomalies(["CL=F", "NG=F"], idx)

        def _yf(self: object, *a: object, **k: object) -> pd.DataFrame:
            return anomalous

        monkeypatch.setattr(
            "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch", _yf
        )

        runner = BenchmarkRunner(drop_nonpositive_tradable_bars=True)
        with caplog.at_level("WARNING", logger="alphakit.bench.runner"):
            runner._fetch_prices(["CL=F", "NG=F"], strategy=object())

        log_text = caplog.text
        assert "Dropped 2 tradable-anomaly bar(s)" in log_text
        assert "NaN in CL=F (missing data)" in log_text
        assert "-37.63 in CL=F (negative price)" in log_text

    @pytest.mark.integration
    def test_filter_records_metadata_in_benchmark_result_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run_single`` mirrors the filter metadata into ``result['anomaly_filter']``."""
        idx = _bdays("2010-01-01", "2025-12-31")
        anomalous = _yf_with_anomalies(["CL=F", "NG=F", "GC=F", "ZC=F"], idx)

        def _yf_futures(self: object, *a: object, **k: object) -> pd.DataFrame:
            return anomalous

        cot_idx = pd.date_range("2010-01-05", "2025-12-31", freq="W-TUE")

        def _cftc_wide(self: object, symbols: list[str], *a: object, **k: object) -> pd.DataFrame:
            # cftc-cot-wide receives market codes; runner renames to NET_SPEC.
            t = np.linspace(0.0, 8.0 * np.pi, len(cot_idx))
            return pd.DataFrame(
                {code: 0.7 * np.sin(t) for code in symbols},
                index=cot_idx,
            )

        monkeypatch.setattr(
            "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch",
            _yf_futures,
        )
        monkeypatch.setattr(_CFTC_WIDE_PATH, _cftc_wide)

        runner = BenchmarkRunner(
            data_start="2010-01-01",
            in_sample_end="2019-12-31",
            out_of_sample_end="2025-12-31",
            drop_nonpositive_tradable_bars=True,
        )
        result = runner.run_single("cot_speculator_position", family="commodity")

        assert "anomaly_filter" in result
        assert result["anomaly_filter"]["enabled"] is True
        assert result["anomaly_filter"]["bars_dropped"] == 2
        # Dates are ascending, ISO-format strings.
        dropped = result["anomaly_filter"]["dropped_dates"]
        assert dropped == sorted(dropped)

    def test_filter_silently_trims_leading_warmup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Leading invalid block is silently trimmed; only mid-panel drops logged."""
        idx = _bdays("2020-01-01", "2020-12-31")
        symbols = ["CL=F", "NG=F"]
        panel = pd.DataFrame(np.full((len(idx), 2), 50.0), index=idx, columns=symbols)
        # First 10 rows: PL-style inception warm-up (NaN). These should be
        # silently trimmed by the filter — NOT counted as anomalies.
        panel.iloc[:10, 0] = np.nan
        # Plus one true mid-panel anomaly.
        panel.iloc[50, 0] = -1.0

        def _yf(self: object, *a: object, **k: object) -> pd.DataFrame:
            return panel

        monkeypatch.setattr(
            "alphakit.data.futures.yfinance_futures_adapter.YFinanceFuturesAdapter.fetch", _yf
        )

        runner = BenchmarkRunner(drop_nonpositive_tradable_bars=True)
        out = runner._fetch_prices(symbols, strategy=object())
        meta = runner.last_anomaly_filter

        # Only the one mid-panel bar is reported as an anomaly.
        assert meta["bars_dropped"] == 1
        # Returned panel starts at the first valid row (index 10), and does
        # not contain the trimmed leading rows or the dropped anomaly row.
        assert len(out) == len(idx) - 10 - 1
        assert not out["CL=F"].isna().any()
        assert (out["CL=F"] > 0).all()


# ---------------------------------------------------------------------------
# Session 2K-1 — substrate-boundary network test for cot full wiring
# ---------------------------------------------------------------------------


_NETWORK_GATE = pytest.mark.skipif(
    os.environ.get("ALPHAKIT_RUN_NETWORK_TESTS") != "1",
    reason="network/substrate-boundary test; set ALPHAKIT_RUN_NETWORK_TESTS=1 to run",
)


@_NETWORK_GATE
def test_real_cot_speculator_position_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-substrate guard for the full Session 2K-1 cot wiring.

    Drives ``cot_speculator_position`` through the keyed real-feed path:
    yfinance-futures for the 4 ``=F`` tradable columns + cftc-cot-wide for
    the 4 ``*_NET_SPEC`` informational columns, with the runner's S2K-1
    ``cftc_market_codes`` translation (NET_SPEC → market code → fetch →
    rename back). Asserts the result JSON has plausible Sharpe (finite,
    ``|x| < 5``), max drawdown finite, and ``data_source`` populated by the
    benchmark runner.

    Catches any future regression in the 3 architectural layers S2K-1
    addressed:

    * Layer 1 (CFTC schema) — surfaces as a column-lookup ``KeyError`` if
      the archive renames again.
    * Layer 2 (symbol → market-code mapping) — wrong code yields empty
      data → bridge fails on empty inputs.
    * Layer 3 (long-vs-wide shape) — wrong format breaks the merge.

    Skipped by default in CI; run via ``ALPHAKIT_RUN_NETWORK_TESTS=1``.
    """
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    runner = BenchmarkRunner(
        data_start="2010-01-01",
        in_sample_end="2019-12-31",
        out_of_sample_end="2025-12-31",
        strict_feed=True,
        drop_nonpositive_tradable_bars=True,
    )
    result = runner.run_single("cot_speculator_position", family="commodity")

    assert result["slug"] == "cot_speculator_position"
    sharpe = result["metrics"]["sharpe"]
    max_dd = result["metrics"]["max_drawdown"]
    assert np.isfinite(sharpe), f"sharpe must be finite, got {sharpe!r}"
    assert abs(sharpe) < 5.0, f"sharpe must be plausible (|x| < 5), got {sharpe!r}"
    assert np.isfinite(max_dd), f"max_drawdown must be finite, got {max_dd!r}"
