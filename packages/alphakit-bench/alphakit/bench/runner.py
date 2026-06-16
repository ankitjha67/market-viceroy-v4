"""BenchmarkRunner — orchestrates strategy benchmarking end-to-end.

Loads a strategy via its slug, fetches price data, splits into
train/OOS periods, runs backtest via vectorbt_bridge, computes
extended metrics, and writes benchmark_results.json atomically.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from alphakit.bench import discovery, metrics
from alphakit.bridges import vectorbt_bridge
from alphakit.data.registry import FeedRegistry

_logger = logging.getLogger(__name__)


def _get_commit_sha() -> str | None:
    """Get current git commit SHA, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


class BenchmarkRunner:
    """Run a strategy benchmark and produce benchmark_results.json.

    Parameters
    ----------
    commission_bps
        Round-trip commission in basis points.
    data_start
        Start date for price data (training begins here).
    in_sample_end
        End of in-sample / start of out-of-sample.
    out_of_sample_end
        End of out-of-sample period.
    initial_cash
        Starting cash for the backtest.
    strict_feed
        Feed-resolution policy. ``False`` (default) preserves the
        CI/test-safe behavior: if a real feed is unavailable (missing
        package, unconfigured ``FRED_API_KEY``, offline mode, network
        failure), the runner falls back to deterministic fixtures.
        ``True`` (set by ``scripts/regenerate_benchmarks.py --feed
        real``) makes any such failure raise loudly rather than
        silently substituting fixtures — per the Session 2H
        "silent fixture fallback is a trap" lesson.
    """

    def __init__(
        self,
        *,
        commission_bps: float = 5.0,
        data_start: str = "2005-01-01",
        in_sample_end: str = "2019-12-31",
        out_of_sample_end: str = "2025-12-31",
        initial_cash: float = 100_000.0,
        strict_feed: bool = False,
        drop_nonpositive_tradable_bars: bool = False,
    ) -> None:
        self.commission_bps = commission_bps
        self.data_start = data_start
        self.in_sample_end = in_sample_end
        self.out_of_sample_end = out_of_sample_end
        self.initial_cash = initial_cash
        self.strict_feed = strict_feed
        # Session 2J S2J-2.6: opt-in anomaly filter. Drops tradable rows whose
        # any tradable column is ``<= 0`` or ``NaN`` (e.g. 2020-04-20 WTI's
        # negative settlement, Thanksgiving NaN gaps in futures data). Default
        # off — the runner's strict-positive contract is preserved. The
        # ``commodity --feed real`` regen path turns it on; see
        # ``docs/known-data-anomalies.md``.
        self.drop_nonpositive_tradable_bars = drop_nonpositive_tradable_bars
        # Populated by ``_apply_anomaly_filter`` and surfaced into the
        # benchmark result by ``run_single``. ``enabled=False`` for runs with
        # the filter off; ``enabled=True`` records what the filter dropped.
        self.last_anomaly_filter: dict[str, Any] = {"enabled": False}

    def run_single(
        self,
        slug: str,
        prices: pd.DataFrame | None = None,
        *,
        family: str | None = None,
    ) -> dict[str, Any]:
        """Benchmark a single strategy, returning the Appendix C dict.

        Parameters
        ----------
        slug
            Strategy slug (e.g. ``"tsmom_12_1"``).
        prices
            Optional pre-loaded price DataFrame. If None, attempts to
            load from alphakit-data fixtures or yfinance.
        family
            Strategy family. Auto-detected from slug if not provided.
        """
        if family is None:
            family, slug = discovery.find_strategy(slug)

        # Reset the anomaly-filter audit at the start of each run so a stale
        # value from a prior ``run_single`` on this same runner instance can't
        # leak into this run's result JSON. Important when the caller supplies
        # ``prices=...`` directly (no ``_fetch_prices`` → no filter call), and
        # for any reuse pattern (e.g. cluster analysis iterating a single
        # runner over many strategies). Caught by CodeRabbit on PR #22 S2J-2.7.
        self.last_anomaly_filter = {"enabled": False}

        strategy = discovery.instantiate(family, slug)
        config = discovery.load_config(family, slug)
        universe = config.get("universe", ["SPY", "EFA", "AGG"])

        # Get price data
        if prices is None:
            prices = self._fetch_prices(universe, strategy=strategy)

        # Filter to OOS period only for benchmark metrics
        oos_start = pd.Timestamp(self.in_sample_end) + pd.Timedelta(days=1)
        oos_end = pd.Timestamp(self.out_of_sample_end)

        # But we need the full history for warm-up — run on all data,
        # then slice metrics to OOS period
        full_result = vectorbt_bridge.run(
            strategy=strategy,
            prices=prices,
            initial_cash=self.initial_cash,
            commission_bps=self.commission_bps,
        )

        # Slice to OOS period for metrics
        oos_mask = (full_result.returns.index >= oos_start) & (full_result.returns.index <= oos_end)
        oos_returns = full_result.returns[oos_mask]
        oos_weights = full_result.weights[oos_mask]

        # If not enough OOS data, fall back to full period
        if len(oos_returns) < 60:
            oos_returns = full_result.returns
            oos_weights = full_result.weights

        # Compute metrics
        returns_arr = oos_returns.to_numpy()
        from alphakit.core.metrics.drawdown import max_drawdown
        from alphakit.core.metrics.returns import calmar_ratio, sharpe_ratio, sortino_ratio

        sharpe = sharpe_ratio(returns_arr)
        sortino = sortino_ratio(returns_arr)
        calmar = calmar_ratio(returns_arr)
        mdd = max_drawdown(returns_arr)
        ann_ret = float(np.mean(returns_arr) * 252) if len(returns_arr) > 0 else 0.0
        ann_vol = float(np.std(returns_arr, ddof=1) * np.sqrt(252)) if len(returns_arr) > 1 else 0.0

        # Extended metrics
        to = metrics.turnover_annual(oos_weights)
        cap = metrics.capacity_estimate_bn(to)
        regime = metrics.regime_performance(oos_returns)

        result = {
            "slug": slug,
            "status": "populated",
            "note": "Generated by alphakit-bench BenchmarkRunner.",
            "benchmark_date": date.today().isoformat(),
            "data_start": self.data_start,
            "in_sample_end": self.in_sample_end,
            "out_of_sample_end": self.out_of_sample_end,
            "universe": universe,
            "metrics": {
                "sharpe": round(sharpe, 4),
                "sortino": round(sortino, 4),
                "calmar": round(calmar, 4),
                "max_drawdown": round(mdd, 4),
                "annualized_return": round(ann_ret, 4),
                "annualized_vol": round(ann_vol, 4),
                "turnover_annual": round(to, 2),
                "capacity_usd_bn": round(cap, 1),
            },
            "regime_performance": {k: round(v, 4) for k, v in regime.items()},
            "transaction_costs_assumed_bps": self.commission_bps,
            "commit_sha": _get_commit_sha(),
            "engine": "vectorbt",
            # Anomaly filter audit trail (Session 2J S2J-2.6). Present only when
            # the filter was enabled — keeps the v0.2.1 / v0.2.0 schema clean
            # for runs that didn't opt in. See docs/known-data-anomalies.md.
            **(
                {"anomaly_filter": self.last_anomaly_filter}
                if self.last_anomaly_filter.get("enabled")
                else {}
            ),
        }
        return result

    def write_benchmark(
        self,
        slug: str,
        result: dict[str, Any],
        *,
        family: str | None = None,
    ) -> Path:
        """Write benchmark_results.json atomically with backup.

        Returns the path to the written file.
        """
        if family is None:
            family, slug = discovery.find_strategy(slug)

        path = discovery.benchmark_results_path(family, slug)

        # Backup existing file
        if path.exists():
            backup = path.with_suffix(".json.bak")
            shutil.copy2(path, backup)

        # Atomic write via temp file. Open in "w" so a stale .tmp from a crashed
        # prior run is overwritten, and use ``Path.replace`` (atomic, overwrites
        # the destination on both POSIX and Windows) rather than ``Path.rename``,
        # which raises FileExistsError on Windows when the target already exists
        # — the common regen case where benchmark_results.json is already there.
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(result, f, indent=2, default=str)
            f.write("\n")
        tmp.replace(path)
        return path

    def _informational_columns(self, strategy: object | None, universe: list[str]) -> list[str]:
        """Return the universe symbols that are informational (non-tradable).

        A strategy that exposes both ``tradable_symbols`` and
        ``required_symbols`` (the Session 2G informational-column pattern)
        routes its non-tradable inputs (e.g. FRED series) to the FRED feed.
        Strategies lacking either property — i.e. every non-regime strategy —
        return ``[]`` and take the single-feed path unchanged.
        """
        tradable = getattr(strategy, "tradable_symbols", None)
        required = getattr(strategy, "required_symbols", None)
        if not tradable or not required:
            return []
        tradable_set = set(tradable)
        return [s for s in universe if s not in tradable_set]

    @staticmethod
    def _resolve_feed(symbol: str, role: Literal["tradable", "informational"]) -> str:
        """Map ``symbol`` to a ``FeedRegistry``-registered adapter name.

        Within-role pattern dispatch. The runner has already classified every
        symbol as tradable or informational via the Session 2G informational-
        column pattern (see ``_informational_columns``), so the pattern only
        needs to disambiguate **within** each role — there is no risk of, e.g.,
        an ETF ticker being mistaken for a FRED series ID, because they arrive
        here already separated by role.

        Rules:

        * **Tradable**
          * ``"...=F"`` (Yahoo futures suffix) → ``"yfinance-futures"``
          * everything else (ETFs, equities) → ``"yfinance"``
        * **Informational**
          * ``"..._NET_SPEC"`` (CFTC COT net-speculator positioning) →
            ``"cftc-cot-wide"`` (the Session 2K-1 wide-format adapter; the
            runner translates NET_SPEC names to CFTC market codes via the
            strategy's ``cftc_market_codes`` mapping before the fetch and
            renames returned columns back after)
          * everything else (FRED series IDs) → ``"fred"``

        A future strategy that needs to break the convention — e.g. an
        EIA-anchored commodity using non-suffixed series IDs — can either
        extend the patterns here or carry an explicit strategy-side override
        (a ``feed_map`` property hooked in above this dispatcher). YAGNI today;
        the seam is intentional.
        """
        if role == "tradable":
            return "yfinance-futures" if symbol.endswith("=F") else "yfinance"
        return "cftc-cot-wide" if symbol.endswith("_NET_SPEC") else "fred"

    def _fetch_prices(self, universe: list[str], strategy: object | None = None) -> pd.DataFrame:
        """Fetch a price panel for ``universe``, routing each symbol per feed.

        Each universe symbol is classified as tradable or informational by the
        Session 2G ``_informational_columns`` pattern, then routed to a
        ``FeedRegistry``-registered adapter via ``_resolve_feed`` (within-role
        ticker patterns: ``=F`` → yfinance-futures, ``_NET_SPEC`` → cftc-cot;
        defaults to yfinance / fred respectively). Symbols sharing a feed are
        fetched in one adapter call. The tradable panel is concatenated
        horizontally; the informational panel(s) are union-aligned and
        value-based-ffilled onto the tradable business-day index (the S2I-1.5
        as-of fill that handles mixed-frequency and holiday NaN), then merged.

        Behaviour preserved from Session 2I: ``strict_feed`` controls fail-loud
        vs deterministic-fixture fallback, the leading-NaN trim removes warm-up,
        and ``_validate_feed_values`` enforces the tradable-> 0 / informational-
        finite contract. Strategies without informational columns return their
        tradable panel as-is (no validation, matching the pre-S2J single-feed
        path used by every ETF-only and yfinance-real benchmark).
        """
        # Expand the fetch target to the strategy's full required column set.
        # Regime strategies' ``config.universe`` already contains every column
        # they read (tradable + informational), so this is a no-op for them.
        # ``cot_speculator_position`` only lists tradable futures in
        # ``config.universe``; its informational ``*_NET_SPEC`` columns live in
        # a separate config field and are surfaced via ``required_symbols``.
        # Using the union preserves caller-defined column order while
        # appending any informational columns the strategy needs.
        tradable_decl = getattr(strategy, "tradable_symbols", None)
        required_decl = getattr(strategy, "required_symbols", None)
        if tradable_decl and required_decl:
            full_universe = list(dict.fromkeys([*universe, *required_decl]))
        else:
            full_universe = list(universe)

        informational_set = set(self._informational_columns(strategy, full_universe))
        tradable_symbols = [s for s in full_universe if s not in informational_set]
        informational_symbols = [s for s in full_universe if s in informational_set]

        # Tradable: group by resolved feed; one adapter call per feed; concat.
        tradable_by_feed: dict[str, list[str]] = {}
        for s in tradable_symbols:
            tradable_by_feed.setdefault(self._resolve_feed(s, "tradable"), []).append(s)
        tradable_parts = [self._fetch_feed(syms, feed) for feed, syms in tradable_by_feed.items()]
        tradable_df = (
            pd.concat(tradable_parts, axis=1).sort_index()
            if len(tradable_parts) > 1
            else tradable_parts[0]
        )

        if not informational_symbols and len(tradable_parts) == 1:
            # Single-feed path (no informational, one tradable feed):
            # byte-identical to the pre-S2J shortcut for ETF-only /
            # yfinance-real benchmarks when the anomaly filter is off
            # (default). With the filter on, applies the silent leading-trim +
            # mid-panel anomaly drop. Multi-feed tradable panels fall through
            # to the explicit trim/validate path below.
            tradable_df = self._apply_anomaly_filter(tradable_df, tradable_symbols)
            return tradable_df

        if not informational_symbols:
            # Multi-feed tradable, no informational: still go through the
            # leading-trim + ``_validate_feed_values`` path. There is no
            # informational alignment to do; ``tradable_df`` is already the
            # concatenated panel.
            merged = tradable_df.loc[:, full_universe]
            complete = merged.notna().all(axis=1)
            if not complete.any():
                raise ValueError(f"no rows where all of {full_universe} are simultaneously present")
            merged = merged.loc[complete.idxmax() :]
            merged = self._apply_anomaly_filter(merged, tradable_symbols)
            self._validate_feed_values(merged, informational_symbols)
            return merged

        # Informational: group by resolved feed; one adapter call per feed.
        informational_by_feed: dict[str, list[str]] = {}
        for s in informational_symbols:
            informational_by_feed.setdefault(self._resolve_feed(s, "informational"), []).append(s)

        informational_parts: list[pd.DataFrame] = []
        for feed, syms in informational_by_feed.items():
            if feed == "cftc-cot-wide":
                # The cftc-cot-wide adapter speaks CFTC market codes, not the
                # strategy's ``*_NET_SPEC`` names. The strategy declares the
                # mapping (``cftc_market_codes``); the runner translates here
                # so the adapter contract stays uniform (symbols-in /
                # wide-DataFrame-out, no strategy-aware logic adapter-side).
                # Session 2K-1, per the S2J-2.8 architectural-depth lesson.
                codes_map = getattr(strategy, "cftc_market_codes", None)
                if not codes_map:
                    raise ValueError(
                        "cftc-cot-wide routing requires a 'cftc_market_codes' "
                        "mapping on the strategy. Add a {NET_SPEC_name: "
                        "market_code} dict to the strategy class. "
                        f"(Symbols requested: {syms})"
                    )
                missing = [s for s in syms if s not in codes_map]
                if missing:
                    raise ValueError(
                        f"cftc_market_codes is missing entries for {missing} "
                        f"on strategy {type(strategy).__name__}"
                    )
                market_codes = [codes_map[s] for s in syms]
                df = self._fetch_feed(market_codes, feed)
                # Rename columns from market_code back to NET_SPEC name so the
                # strategy's generate_signals receives the panel with the
                # column names it expects (per its position_columns property).
                df = df.rename(columns={codes_map[s]: s for s in syms})
                informational_parts.append(df)
            else:
                informational_parts.append(self._fetch_feed(syms, feed))
        informational_df = (
            pd.concat(informational_parts, axis=1).sort_index()
            if len(informational_parts) > 1
            else informational_parts[0].sort_index()
        )

        # Align informational onto the tradable business-day index via an as-of
        # forward-fill — value-based ``ffill`` over the union index so quarterly
        # GDPC1 / monthly CPI / weekly CFTC observations + holiday NaN in daily
        # yield series are all skipped properly. See the 2026-05-22 amendment.
        union_index = tradable_df.index.union(informational_df.index)
        informational_aligned = (
            informational_df.reindex(union_index).ffill().reindex(tradable_df.index)
        )

        merged = pd.concat([tradable_df, informational_aligned], axis=1)
        merged = merged.loc[:, full_universe]

        # Trim leading warm-up rows; the value-based ffill above guarantees no
        # mid-panel or trailing gaps, so all incompleteness is leading.
        complete = merged.notna().all(axis=1)
        if not complete.any():
            raise ValueError(f"no rows where all of {full_universe} are simultaneously present")
        merged = merged.loc[complete.idxmax() :]

        merged = self._apply_anomaly_filter(merged, tradable_symbols)
        self._validate_feed_values(merged, informational_symbols)
        return merged

    def _fetch_feed(self, symbols: list[str], feed_name: str) -> pd.DataFrame:
        """Dispatch one fetch via ``FeedRegistry``, honouring ``strict_feed``.

        Replaces the pre-S2J hardcoded ``_yfinance_fetch`` / ``_fred_fetch``
        helpers: the feed name comes from ``_resolve_feed`` and the adapter
        from ``FeedRegistry.get(name)``. ``strict_feed=True`` re-raises any
        real-feed failure (missing package, unconfigured key, offline, network,
        empty result); ``strict_feed=False`` falls back to deterministic
        fixtures (CI/test-safe).

        ``FeedRegistry.get`` is resolved **outside** the strict_feed try: a
        missing adapter registration is a wiring bug (the router pointed at a
        feed nobody registered), not a real-feed failure, and must surface as
        a ``KeyError`` regardless of ``strict_feed`` rather than be silently
        masked by the fixture fallback. Review request on PR #22.
        """
        adapter = FeedRegistry.get(feed_name)
        try:
            df = adapter.fetch(
                symbols=symbols,
                start=datetime.fromisoformat(self.data_start),
                end=datetime.fromisoformat(self.out_of_sample_end),
            )
            if df.empty:
                raise RuntimeError(f"{feed_name!r} returned an empty DataFrame")
            return df
        except Exception:
            if self.strict_feed:
                raise
            from alphakit.data.fixtures.generator import generate_fixture_prices

            return generate_fixture_prices(
                symbols=symbols,
                start=self.data_start,
                end=self.out_of_sample_end,
            )

    @staticmethod
    def _validate_feed_values(panel: pd.DataFrame, informational: list[str]) -> None:
        """Fail loud on values the downstream pipeline cannot consume.

        Two distinct contracts, because tradable and informational columns are
        used differently downstream (see ``vectorbt_bridge.run``):

        * **Every** column must be finite. A NaN/inf would be read by the
          strategy as a non-finite signal (informational) or handed to the
          bridge as a non-finite close (tradable).
        * **Tradable** columns must additionally be strictly ``> 0``: the
          bridge computes ``shares = target_value / close`` for traded columns,
          so a zero or negative close is undefined.
        * **Informational** columns are *not* required to be positive. They are
          never traded — the bridge drops identically-zero-weight columns before
          ``from_orders`` — so raw FRED inputs that are legitimately zero (a
          recession probability) or negative (a real-yield level) are valid;
          they need only be finite. (This supersedes the 2026-05-16 amendment's
          blanket "every column strictly positive" rule, which assumed the
          bridge traded informational columns; it does not.)
        """
        informational_set = set(informational)
        nonfinite = [c for c in panel.columns if not np.isfinite(panel[c]).all()]
        if nonfinite:
            raise ValueError(f"non-finite values in feed columns: {nonfinite}")
        tradable = [c for c in panel.columns if c not in informational_set]
        nonpositive = [c for c in tradable if not (panel[c] > 0).all()]
        if nonpositive:
            raise ValueError(
                f"non-positive values in tradable feed columns {nonpositive}; the "
                "vectorbt bridge computes shares = value / close for traded "
                "columns and so requires every tradable column to be strictly "
                "positive"
            )

    def _apply_anomaly_filter(self, panel: pd.DataFrame, tradable_cols: list[str]) -> pd.DataFrame:
        """Drop rows with non-positive or NaN values in any tradable column.

        Off by default; opt-in via ``drop_nonpositive_tradable_bars=True``.
        Singleton historical anomalies that would otherwise violate the bridge
        ``order.price > 0`` invariant — e.g. the 2020-04-20 WTI -$37.63
        settlement, Thanksgiving NaN gaps in futures continuous contracts —
        are dropped here so the bridge sees only investable bars. Each
        mid-panel drop is logged with its classification ("missing data" /
        "negative price" / "mixed") and the dropped dates are surfaced via
        ``self.last_anomaly_filter`` for inclusion in the benchmark JSON
        (``run_single`` mirrors them into ``result["anomaly_filter"]``). See
        ``docs/known-data-anomalies.md``.

        The filter silently trims any **leading** invalid block (pre-inception
        warm-up for a tradable ticker) — that's the same warm-up the
        multi-feed path's existing leading-trim removes — and only logs
        **mid-panel** drops, so the audit trail stays signal-noise free.
        """
        if not self.drop_nonpositive_tradable_bars or not tradable_cols:
            self.last_anomaly_filter = {"enabled": False}
            return panel

        tradable = panel[tradable_cols]
        valid = (tradable.notna() & (tradable > 0)).all(axis=1)
        if not valid.any():
            self.last_anomaly_filter = {
                "enabled": True,
                "bars_dropped": 0,
                "dropped_dates": [],
            }
            raise ValueError(
                f"anomaly filter found no valid rows in tradable columns "
                f"{tradable_cols}; every bar has a non-positive or NaN tradable value"
            )

        first_valid = valid.idxmax()
        panel_post = panel.loc[first_valid:]
        valid_post = valid.loc[first_valid:]
        tradable_post = tradable.loc[first_valid:]

        dropped_idx = panel_post.index[~valid_post]
        dropped_dates_str: list[str] = []
        log_lines: list[str] = []
        for date_ts in dropped_idx:
            row = tradable_post.loc[date_ts]
            nan_cols = [c for c in tradable_cols if pd.isna(row[c])]
            neg_cols = [c for c in tradable_cols if not pd.isna(row[c]) and row[c] <= 0]
            if nan_cols and not neg_cols:
                classification = f"NaN in {', '.join(nan_cols)} (missing data)"
            elif neg_cols and not nan_cols:
                worst_col = min(neg_cols, key=lambda c: float(row[c]))
                classification = f"{float(row[worst_col]):.2f} in {worst_col} (negative price)"
            else:
                parts: list[str] = []
                if nan_cols:
                    parts.append(f"NaN in {', '.join(nan_cols)}")
                if neg_cols:
                    worst_col = min(neg_cols, key=lambda c: float(row[c]))
                    parts.append(f"{float(row[worst_col]):.2f} in {worst_col}")
                classification = " + ".join(parts) + " (mixed)"
            date_str = pd.Timestamp(date_ts).strftime("%Y-%m-%d")
            dropped_dates_str.append(date_str)
            log_lines.append(f"  {date_str}: {classification}")

        if log_lines:
            _logger.warning(
                "Dropped %d tradable-anomaly bar(s):\n%s",
                len(log_lines),
                "\n".join(log_lines),
            )

        self.last_anomaly_filter = {
            "enabled": True,
            "bars_dropped": len(dropped_dates_str),
            "dropped_dates": dropped_dates_str,
        }
        return cast(pd.DataFrame, panel_post.loc[valid_post])
