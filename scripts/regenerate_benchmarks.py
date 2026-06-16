#!/usr/bin/env python3
"""Session 2H/2I/2J benchmark regeneration.

Regenerates ``benchmark_results.json`` for the macro + rates + commodity
families on the canonical runner schema, stamping a ``data_source`` field
that records provenance:

* **Tier-1 (17)** — ETF-only universes (11 rates + 6 macro). Fetched from
  real yfinance prices under a retry budget; ``data_source="yfinance-real"``.
* **Tier-2 (5 macro, FRED-gated)** — require FRED informational columns.
  Two feeds, selected by ``--feed`` (default ``synthetic``):

  * ``--feed synthetic`` — regenerated through the runner using
    regime-exercising **synthetic panels** passed via
    ``run_single(prices=...)``; ``data_source="synthetic-fixture"``.
  * ``--feed real`` — regenerated against **real yfinance + FRED** data via
    the multi-feed ``BenchmarkRunner(strict_feed=True)`` (Session 2I): the
    tradable columns come from yfinance and the informational (FRED) columns
    from FRED, fail-loud on any feed failure; ``data_source="yfinance+fred-real"``.
    Requires ``FRED_API_KEY`` + the ``fredapi`` package.

* **Commodity (7, Session 2J)** — front-month futures (``=F``) via
  yfinance-futures, plus ``cot_speculator_position`` whose ``*_NET_SPEC``
  CFTC positioning columns route to the cftc-cot-wide adapter. Real-feed only
  (``--feed real`` required); 6 stamp ``data_source="yfinance-futures-real"``,
  ``cot_speculator_position`` stamps ``data_source="yfinance+cftc-real"``.
  Requires the ``yfinance`` package (CFTC is a public ZIP, no key). The 3
  second-month-blocked commodity strategies (``commodity_curve_carry``,
  ``ng_contango_short``, ``wti_backwardation_carry``) are **not** offered
  for real-feed regen — yfinance has no continuous second-month — and stay
  ``synthetic-fixture``; see the 2026-05-31 amendment for the constraint.

Real-feed modes require the relevant optional dependency:

    uv run --with yfinance --extra dev python scripts/regenerate_benchmarks.py all
    uv run --with fredapi --extra dev python \
        scripts/regenerate_benchmarks.py tier2 --feed real
    uv run --with yfinance --extra dev python \
        scripts/regenerate_benchmarks.py commodity --feed real

The script **fails loud** if a required real feed is unavailable (yfinance
missing for Tier-1 / commodity; ``FRED_API_KEY`` unset or ``fredapi`` missing
for Tier-2 ``--feed real``), rather than silently falling back to synthetic
fixtures (the trap in ``BenchmarkRunner._fetch_prices``).

Modes: ``smoke`` (3 single-ETF rates), ``tier1`` (17 real), ``tier2``
(5 macro), ``commodity`` (7 — 6 front-month + cot_speculator_position via
the Session 2K-1 cftc-cot-wide adapter, ``--feed real`` required), ``all``
(Tier-1 + Tier-2). ``--feed`` governs the Tier-2 + commodity paths.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from alphakit.bench import discovery  # noqa: E402
from alphakit.bench.runner import BenchmarkRunner  # noqa: E402
from alphakit.data.errors import FeedNotConfiguredError  # noqa: E402

# Tier-1: ETF-only universes, real-feed via yfinance. slug -> family.
TIER1: dict[str, str] = {
    "bond_tsmom_12_1": "rates",
    "curve_steepener_2s10s": "rates",
    "curve_flattener_2s10s": "rates",
    "curve_butterfly_2s5s10s": "rates",
    "bond_carry_rolldown": "rates",
    "duration_targeted_momentum": "rates",
    "breakeven_inflation_rotation": "rates",
    "real_yield_momentum": "rates",
    "yield_curve_pca_trade": "rates",
    "g10_bond_carry": "rates",
    "credit_spread_momentum": "rates",
    "permanent_portfolio": "macro",
    "gtaa_cross_asset_momentum": "macro",
    "vigilant_asset_allocation_5": "macro",
    "risk_parity_erc_3asset": "macro",
    "min_variance_gtaa": "macro",
    "max_diversification": "macro",
}

# The 3 simplest single-ETF rates strategies — run first as a viability gate.
SMOKE: list[str] = ["bond_tsmom_12_1", "real_yield_momentum", "credit_spread_momentum"]

# Tier-2: FRED-gated macro strategies, regenerated on synthetic panels.
TIER2: list[str] = [
    "recession_probability_rotation",
    "growth_inflation_regime_rotation",
    "yield_curve_regime_allocation",
    "fed_policy_tilt",
    "inflation_regime_allocation",
]

# Commodity tier (Session 2J + Session 2K-1): 6 front-month futures + 1
# mixed-feed (cot). Routed via the S2J per-role feed router (``=F`` →
# yfinance-futures; ``*_NET_SPEC`` → cftc-cot-wide for cot, per Session 2K-1).
# The 3 commodity strategies needing continuous second-month futures
# (``commodity_curve_carry``, ``ng_contango_short``, ``wti_backwardation_carry``)
# are NOT in this list — yfinance returns 404 for ``CL2=F`` / ``NG2=F`` /
# ``GC2=F``, so they remain synthetic-fixture pending a non-free second-month
# source (Phase 3). See the 2026-05-31 amendment.
#
# ``cot_speculator_position`` is back in this list as of Session 2K-1: the
# CFTC adapter column rename (S2J-2.8), the new ``CFTCCOTWideAdapter``
# (S2K-1), the ``cftc_market_codes`` mapping on the strategy (S2K-1), and the
# runner-side NET_SPEC→market-code translation (S2K-1) together resolve the
# three architectural layers documented in
# ``docs/known-data-anomalies.md`` → "Deferred to Session 2K".
COMMODITY: list[str] = [
    "commodity_tsmom",
    "crack_spread",
    "crush_spread",
    "grain_seasonality",
    "metals_momentum",
    "wti_brent_spread",
    "cot_speculator_position",
]

# ``_COMMODITY_MIXED`` records strategies whose real-feed data_source is
# ``yfinance+cftc-real`` rather than the pure ``yfinance-futures-real``.
# Session 2K-1 re-adds ``cot_speculator_position`` after the S2J-2.8 deferral.
_COMMODITY_MIXED: set[str] = {"cot_speculator_position"}

_DATA_START = "2005-01-01"
_IN_SAMPLE_END = "2019-12-31"
_OOS_END = "2025-12-31"

# Retry budget for real fetches (per spec): 3 retries, exp backoff.
_RETRY_DELAYS = [5, 30, 120]


def _require_yfinance() -> None:
    """Raise loudly if yfinance is unavailable (no silent fixture fallback)."""
    try:
        import yfinance  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "ERROR: real-feed regeneration requires yfinance, which is not "
            "importable. Re-run with the extra, e.g.:\n"
            "    uv run --with yfinance --extra dev python "
            "scripts/regenerate_benchmarks.py <mode>\n"
            f"(import error: {exc})"
        ) from exc


def _require_commodity_real() -> None:
    """Fail loud if Tier-commodity ``--feed real`` prerequisites are missing.

    Only yfinance is checked — the cftc-cot-wide adapter (Session 2K-1) uses
    ``requests`` for the CFTC ZIP download, which is also a yfinance transitive
    dependency, so once yfinance is importable ``requests`` is too. No FRED
    key is needed (commodity universe carries no FRED series); no EIA key is
    needed (no in-scope strategy consumes EIA). CFTC itself has no API key —
    the COT archive is a public ZIP download.
    """
    try:
        import yfinance  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "ERROR: commodity --feed real requires the yfinance package, which "
            "is not importable. Re-run with it, e.g.:\n"
            "    uv run --with yfinance --extra dev python "
            "scripts/regenerate_benchmarks.py commodity --feed real\n"
            f"(import error: {exc})"
        ) from exc


def _require_fred_real() -> None:
    """Fail loud if Tier-2 ``--feed real`` prerequisites are missing.

    Checks the key first (raising :class:`FeedNotConfiguredError` with an
    OS-specific setup message, matching the FRED adapter), then the package.
    Failing here — before any fetch — means the runner never silently
    substitutes fixtures for an unconfigured real feed.
    """
    if not os.environ.get("FRED_API_KEY"):
        raise FeedNotConfiguredError(
            "--feed real requires the FRED_API_KEY environment variable (not "
            "set). Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html, then set it:\n"
            "  Linux/macOS:  export FRED_API_KEY=your_key_here\n"
            "  Windows (PowerShell, persistent):  "
            "[Environment]::SetEnvironmentVariable('FRED_API_KEY','your_key_here','User')\n"
            "Then re-run:  uv run --with fredapi --extra dev python "
            "scripts/regenerate_benchmarks.py tier2 --feed real"
        )
    try:
        import fredapi  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "ERROR: --feed real requires the fredapi package, which is not "
            "importable. Re-run with it, e.g.:\n"
            "    uv run --with fredapi --extra dev python "
            "scripts/regenerate_benchmarks.py tier2 --feed real\n"
            f"(import error: {exc})"
        ) from exc


def _fetch_with_retry(universe: list[str]) -> pd.DataFrame:
    """Fetch real prices with the documented retry budget (5s/30s/120s)."""
    from alphakit.data.equities.yfinance_adapter import YFinanceAdapter

    adapter = YFinanceAdapter()
    start = dt.datetime.fromisoformat(_DATA_START)
    end = dt.datetime.fromisoformat(_OOS_END)
    last_exc: Exception | None = None
    for attempt in range(4):  # 1 initial + 3 retries
        try:
            df = adapter.fetch(symbols=universe, start=start, end=end)
            if df.empty:
                raise RuntimeError("adapter returned empty DataFrame")
            return df
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                delay = _RETRY_DELAYS[attempt]
                print(f"      fetch attempt {attempt + 1} failed ({exc}); retrying in {delay}s")
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Tier-2 synthetic panels (regime-exercising; mirror the Session 2G tests)
# ---------------------------------------------------------------------------


def _bdays() -> pd.DatetimeIndex:
    return pd.date_range(_DATA_START, _OOS_END, freq="B")


def _gbm(
    index: pd.DatetimeIndex, seed: int, mu: float = 0.0003, sigma: float = 0.011
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(mu, sigma, len(index))))


def _blocks(index: pd.DatetimeIndex, values: list[float], block_years: float = 2.0) -> np.ndarray:
    """Piecewise-constant series cycling through ``values`` in N-year blocks."""
    out = np.empty(len(index), dtype=float)
    block = round(block_years * 252)
    for i in range(0, len(index), block):
        out[i : i + block] = values[(i // block) % len(values)]
    return out


def _etfs(index: pd.DatetimeIndex, symbols: list[str], seed0: int = 10) -> dict[str, np.ndarray]:
    return {s: _gbm(index, seed0 + i) for i, s in enumerate(symbols)}


def _panel_recession_probability_rotation() -> pd.DataFrame:
    """RECPROUSM156N cycles 0.10 (risk-on) / 0.50 (risk-off) across the 0.30 threshold."""
    idx = _bdays()
    data = _etfs(idx, ["SPY", "TLT", "GLD"])
    data["RECPROUSM156N"] = _blocks(idx, [0.10, 0.50], block_years=2.5)
    return pd.DataFrame(data, index=idx)


def _panel_growth_inflation_regime_rotation() -> pd.DataFrame:
    """CPI alternates ~1.5%/4.5% YoY; GDP level alternates ~3%/1% growth — exercises 4 cells."""
    idx = _bdays()
    data = _etfs(idx, ["SPY", "TLT", "GLD", "DBC"])
    cpi_rate = _blocks(idx, [0.015, 0.045], block_years=3.0)
    data["CPIAUCSL"] = 250.0 * np.exp(np.cumsum(np.log1p((1 + cpi_rate) ** (1 / 252) - 1)))
    gdp_growth = _blocks(idx, [3.0, 1.0], block_years=2.0)
    data["GDPC1"] = 20000.0 * np.exp(np.cumsum(np.log1p((1 + gdp_growth / 100) ** (1 / 252) - 1)))
    return pd.DataFrame(data, index=idx)


def _panel_yield_curve_regime_allocation() -> pd.DataFrame:
    """2s10s slope cycles steep(+2.0)/flat(+0.4)/inverted(-0.5); DGS2 fixed at 1.0%."""
    idx = _bdays()
    data = _etfs(idx, ["SPY", "TLT", "GLD"])
    dgs2 = np.full(len(idx), 1.0)
    slope = _blocks(idx, [2.0, 0.4, -0.5], block_years=2.0)
    data["DGS10"] = np.maximum(dgs2 + slope, 0.05)
    data["DGS2"] = dgs2
    return pd.DataFrame(data, index=idx)


def _panel_fed_policy_tilt() -> pd.DataFrame:
    """FEDFUNDS cycles rising (tightening) / falling (easing); strictly positive."""
    idx = _bdays()
    data = _etfs(idx, ["SPY", "TLT", "GLD"])
    n = len(idx)
    half = n // 2
    fed = np.concatenate([np.linspace(0.5, 4.0, half), np.linspace(4.0, 0.5, n - half)])
    data["FEDFUNDS"] = np.maximum(fed, 0.07)
    return pd.DataFrame(data, index=idx)


def _panel_inflation_regime_allocation() -> pd.DataFrame:
    """CPI YoY cycles low(1%)/moderate(3%)/high(6%) — exercises all 3 cells."""
    idx = _bdays()
    data = _etfs(idx, ["SPY", "TLT", "GLD", "DBC"])
    cpi_rate = _blocks(idx, [0.01, 0.03, 0.06], block_years=3.0)
    data["CPIAUCSL"] = 250.0 * np.exp(np.cumsum(np.log1p((1 + cpi_rate) ** (1 / 252) - 1)))
    return pd.DataFrame(data, index=idx)


_TIER2_PANELS = {
    "recession_probability_rotation": _panel_recession_probability_rotation,
    "growth_inflation_regime_rotation": _panel_growth_inflation_regime_rotation,
    "yield_curve_regime_allocation": _panel_yield_curve_regime_allocation,
    "fed_policy_tilt": _panel_fed_policy_tilt,
    "inflation_regime_allocation": _panel_inflation_regime_allocation,
}


# ---------------------------------------------------------------------------
# Regeneration
# ---------------------------------------------------------------------------


def _runner() -> BenchmarkRunner:
    return BenchmarkRunner(
        commission_bps=5.0,
        data_start=_DATA_START,
        in_sample_end=_IN_SAMPLE_END,
        out_of_sample_end=_OOS_END,
    )


def _write(slug: str, family: str, result: dict[str, Any], data_source: str) -> None:
    result["data_source"] = data_source
    _runner().write_benchmark(slug, result, family=family)


def regen_tier1(slug: str) -> tuple[bool, str]:
    """Real-feed regen for one Tier-1 strategy. Returns (success, message)."""
    family = TIER1[slug]
    universe = list(discovery.load_config(family, slug)["universe"])
    try:
        prices = _fetch_with_retry(universe)
    except Exception as exc:
        return False, f"FETCH FAILED ({exc}); kept existing synthetic benchmark"
    result = _runner().run_single(slug, prices=prices, family=family)
    _write(slug, family, result, "yfinance-real")
    sharpe = result["metrics"]["sharpe"]
    return (
        True,
        f"yfinance-real OK  Sharpe={sharpe:+.4f}  ({prices.shape[0]} bars, {len(universe)} cols)",
    )


def regen_tier2(slug: str) -> tuple[bool, str]:
    """Synthetic-panel regen for one Tier-2 strategy. Returns (success, message)."""
    panel = _TIER2_PANELS[slug]()
    result = _runner().run_single(slug, prices=panel, family="macro")
    _write(slug, "macro", result, "synthetic-fixture")
    sharpe = result["metrics"]["sharpe"]
    return True, f"synthetic-fixture OK  Sharpe={sharpe:+.4f}  ({panel.shape[0]} bars)"


def regen_tier2_real(slug: str) -> tuple[bool, str]:
    """Real-feed (yfinance + FRED) regen for one Tier-2 strategy.

    Routes through ``BenchmarkRunner(strict_feed=True).run_single`` with **no**
    pre-loaded prices, so the runner's multi-feed ``_fetch_prices`` pulls the
    tradable columns from yfinance and the informational (FRED) columns from
    FRED, failing loud on any feed failure (no synthetic fallback). On a
    fetch/feed error we keep the existing benchmark and report the failure
    rather than writing partial or substituted data. Returns (success, message).
    """
    runner = BenchmarkRunner(
        commission_bps=5.0,
        data_start=_DATA_START,
        in_sample_end=_IN_SAMPLE_END,
        out_of_sample_end=_OOS_END,
        strict_feed=True,
    )
    try:
        result = runner.run_single(slug, family="macro")
    except Exception as exc:
        return False, f"FETCH FAILED ({exc}); kept existing benchmark"
    _write(slug, "macro", result, "yfinance+fred-real")
    sharpe = result["metrics"]["sharpe"]
    universe = result["universe"]
    return True, f"yfinance+fred-real OK  Sharpe={sharpe:+.4f}  ({len(universe)} cols)"


def regen_commodity_real(slug: str) -> tuple[bool, str]:
    """Real-feed (yfinance-futures + cftc-cot-wide) regen for one commodity strategy.

    Routes through ``BenchmarkRunner(strict_feed=True).run_single`` with no
    pre-loaded prices, so the runner's S2J per-role feed router dispatches
    tradable ``=F`` symbols to yfinance-futures and (for cot only)
    ``*_NET_SPEC`` informational columns to cftc-cot-wide. Fail-loud on any feed
    failure; the existing benchmark is kept on a fetch error. ``data_source``
    is ``yfinance+cftc-real`` when the strategy is in ``_COMMODITY_MIXED``
    (currently only ``cot_speculator_position``), else ``yfinance-futures-real``.

    ``drop_nonpositive_tradable_bars=True`` enables the S2J-2.6 anomaly filter
    so the runner drops singleton tradable-anomaly bars before the bridge sees
    them — e.g. the 2020-04-20 WTI -$37.63 settlement and Thanksgiving NaN
    gaps in futures continuous contracts. The filter records the dropped
    dates in ``result["anomaly_filter"]`` for audit. See
    ``docs/known-data-anomalies.md``.
    """
    runner = BenchmarkRunner(
        commission_bps=5.0,
        data_start=_DATA_START,
        in_sample_end=_IN_SAMPLE_END,
        out_of_sample_end=_OOS_END,
        strict_feed=True,
        drop_nonpositive_tradable_bars=True,
    )
    try:
        result = runner.run_single(slug, family="commodity")
    except Exception as exc:
        return False, f"FETCH FAILED ({exc}); kept existing benchmark"
    data_source = "yfinance+cftc-real" if slug in _COMMODITY_MIXED else "yfinance-futures-real"
    _write(slug, "commodity", result, data_source)
    sharpe = result["metrics"]["sharpe"]
    universe = result["universe"]
    dropped = result.get("anomaly_filter", {}).get("bars_dropped", 0)
    anomaly_suffix = f"  [{dropped} anomaly bar(s) dropped]" if dropped else ""
    return (
        True,
        f"{data_source} OK  Sharpe={sharpe:+.4f}  ({len(universe)} cols){anomaly_suffix}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Session 2H/2I/2J benchmark regeneration")
    parser.add_argument("mode", choices=["smoke", "tier1", "tier2", "commodity", "all"])
    parser.add_argument(
        "--feed",
        choices=["synthetic", "real"],
        default="synthetic",
        help="Tier-2 feed: 'synthetic' (default, regime-exercising panels) or "
        "'real' (yfinance + FRED via the multi-feed runner; needs FRED_API_KEY "
        "+ fredapi). 'commodity' mode requires --feed real (yfinance-futures + "
        "cftc-cot-wide via the S2J per-role router).",
    )
    args = parser.parse_args()

    if args.mode == "commodity" and args.feed != "real":
        raise SystemExit(
            "commodity mode requires --feed real (the 7 in-scope commodity "
            "strategies are regenerated from yfinance-futures + cftc-cot-wide). "
            "The 3 second-month-blocked commodity strategies "
            "(commodity_curve_carry, ng_contango_short, wti_backwardation_carry) "
            "remain synthetic-fixture per the 2026-05-31 amendment."
        )

    if args.mode in ("smoke", "tier1", "all"):
        _require_yfinance()
    if args.feed == "real" and args.mode in ("tier2", "all"):
        _require_fred_real()
    if args.mode == "commodity":
        _require_commodity_real()

    real_ok = 0
    real_fail: list[str] = []
    synth_ok = 0
    fred_ok = 0
    fred_fail: list[str] = []
    commodity_ok = 0
    commodity_fail: list[str] = []

    if args.mode == "smoke":
        slugs = SMOKE
    elif args.mode == "tier1":
        slugs = list(TIER1)
    elif args.mode in ("tier2", "commodity"):
        slugs = []
    else:
        slugs = list(TIER1)

    for slug in slugs:
        print(f"  [{TIER1[slug]:>8}] {slug:38s}", end=" ")
        ok, msg = regen_tier1(slug)
        print(msg)
        if ok:
            real_ok += 1
        else:
            real_fail.append(slug)

    if args.mode in ("tier2", "all"):
        for slug in TIER2:
            print(f"  [   macro] {slug:38s}", end=" ")
            if args.feed == "real":
                ok, msg = regen_tier2_real(slug)
                print(msg)
                if ok:
                    fred_ok += 1
                else:
                    fred_fail.append(slug)
            else:
                _, msg = regen_tier2(slug)
                print(msg)
                synth_ok += 1

    if args.mode == "commodity":
        for slug in COMMODITY:
            print(f"  [commodity] {slug:38s}", end=" ")
            ok, msg = regen_commodity_real(slug)
            print(msg)
            if ok:
                commodity_ok += 1
            else:
                commodity_fail.append(slug)

    print("=" * 70)
    print(f"real-feed (yfinance-real): {real_ok} ok, {len(real_fail)} failed")
    if real_fail:
        print(f"  failed (kept synthetic): {real_fail}")
    if synth_ok:
        print(f"tier-2 synthetic panels:   {synth_ok} regenerated")
    if fred_ok or fred_fail:
        print(f"tier-2 real (yfinance+fred): {fred_ok} ok, {len(fred_fail)} failed")
        if fred_fail:
            print(f"  failed (kept existing):  {fred_fail}")
    if commodity_ok or commodity_fail:
        print(
            f"commodity real (yfinance-futures + cftc-cot-wide): "
            f"{commodity_ok} ok, {len(commodity_fail)} failed"
        )
        if commodity_fail:
            print(f"  failed (kept existing):  {commodity_fail}")
    return 1 if ((args.mode == "smoke" and real_fail) or fred_fail or commodity_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
