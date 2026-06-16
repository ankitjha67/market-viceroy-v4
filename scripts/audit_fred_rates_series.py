"""S2K-2 feasibility probe — FRED series coverage audit for rates strategies.

Run locally with ``FRED_API_KEY`` in env (Windows side; key NEVER lands in
this repo or any sandbox session) to verify continuous 2005-2025 coverage
of the candidate series identified in the S2K-2 audit report.

Usage::

    uv run --with fredapi python scripts/audit_fred_rates_series.py

Output: per-series coverage table (start, end, gaps, n_obs, value range,
went_negative) + ``fred.search()`` results for the swap-rate hunt + verdict
per strategy.

The probe is read-only — no benchmark files are touched. Output goes to
stdout so it can be pasted back into the session for the build/no-build
decision (S2K-2 build phase or honest deferral).

Secondary probe (2026-05-31) — primary probe at 954de57 returned:

* swap_spread_mean_rev: ``ICERATES1100USD10Y`` does not exist on FRED.
  Need to hunt the actual ID via ``fred.search()`` or accept the
  defensible "no continuous swap rate post-2016" finding.
* global_inflation_momentum: ``CPALTT01{DE,JP}M657N`` returned values
  that look like rate-of-change (negatives), not LEVEL. OECD-MEI
  suffix convention needs verification — try ``M659N`` and the
  BIS-OECD ``DEUCPIALLMINMEI`` / ``JPNCPIALLMINMEI`` naming.
* CPI Japan probe hit rate-limit — sleep 1.5s between FRED calls
  (FRED publishes 120 req/min; we stay well under that).

Series under audit (UPDATED for secondary probe):

* **swap_spread_mean_rev** — needs continuous 10Y USD swap rate 2005-2025
  - DSWP10: legacy H.15 10Y swap rate (confirmed discontinued 2016)
  - DGS10: 10Y Treasury constant maturity (Treasury leg, control)
  - Plus ``fred.search()`` for swap-rate replacement candidates.

* **global_inflation_momentum** — needs CPI level + bond-yield-proxy
  for >=2 countries (US/Germany/Japan minimum)
  - CPIAUCSL (US, monthly, control)
  - CPALTT01DEM659N, CPALTT01DEM657N: rival OECD-MEI suffixes for DE
  - CPALTT01JPM659N, CPALTT01JPM657N: rival OECD-MEI suffixes for JP
  - DEUCPIALLMINMEI / JPNCPIALLMINMEI: BIS-OECD alternative naming
  - IRLTLT01{US,DE,JP}M156N: 10Y yields (US/DE/JP, confirmed continuous)
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

# Audit window — matches the S2K-2 in-scope backtest period.
AUDIT_START = datetime(2005, 1, 1)
AUDIT_END = datetime(2025, 12, 31)

# Acceptable gap tolerance (in days). Monthly series legitimately have
# 30-31 day gaps between observations — anything beyond that is suspect.
MAX_GAP_DAYS_DAILY = 14  # 2 calendar weeks: allow holiday spans + odd Fed pauses
MAX_GAP_DAYS_MONTHLY = 45  # ~1.5 months: allows for delayed releases

# Sleep between FRED calls so we don't trip the rate limiter mid-probe.
# FRED publishes 120 req/min = 1 req/0.5s; 1.5s gives ample headroom.
SLEEP_BETWEEN_CALLS_SEC = 1.5

# Free-text searches that should be exhausted before declaring "no
# continuous swap rate exists post-2016". Run after the per-series probes
# so the user sees both the negative evidence (per-ID FETCH_FAILED) and
# the positive evidence (what FRED *does* have under these queries).
SEARCH_QUERIES = [
    "10-year swap rate USD",
    "ICE swap rate",
    "USD interest rate swap",
    "SOFR swap rate 10",
]


@dataclass(frozen=True)
class SeriesProbe:
    series_id: str
    description: str
    expected_freq: str  # "daily" | "monthly"
    strategy: str
    notes: str = ""


CANDIDATES: list[SeriesProbe] = [
    # ---- swap_spread_mean_rev ----
    SeriesProbe(
        series_id="DSWP10",
        description="10-Year Swap Rate (H.15, LEGACY) [re-probe for record]",
        expected_freq="daily",
        strategy="swap_spread_mean_rev",
        notes="Confirmed DISCONTINUED ~2016-10. Re-included for archival completeness.",
    ),
    SeriesProbe(
        series_id="DGS10",
        description="10Y Treasury Constant Maturity (control)",
        expected_freq="daily",
        strategy="swap_spread_mean_rev",
        notes="Continuous since 1962 — control series for sanity-check.",
    ),
    # ---- global_inflation_momentum (US control) ----
    SeriesProbe(
        series_id="CPIAUCSL",
        description="CPI All Urban Consumers (US, SA, LEVEL, control)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Continuous since 1947; control series. Range will be ~[180, 320].",
    ),
    # ---- global_inflation_momentum (Germany CPI alternatives) ----
    SeriesProbe(
        series_id="CPALTT01DEM659N",
        description="CPI All Items, Germany — suffix M659N candidate",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes=(
            "Secondary probe — M657N returned negative values (rate-of-change). "
            "M659N is the OECD-MEI sibling. Verify range ~[80, 130] to confirm LEVEL."
        ),
    ),
    SeriesProbe(
        series_id="CPALTT01DEM657N",
        description="CPI All Items, Germany — suffix M657N (re-probe for record)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Primary probe showed negatives (rate-of-change, not LEVEL). Logged for record.",
    ),
    SeriesProbe(
        series_id="DEUCPIALLMINMEI",
        description="CPI All Items, Germany — BIS-OECD alternative naming",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Backup naming if both M657N and M659N fail to give a LEVEL.",
    ),
    # ---- global_inflation_momentum (Japan CPI alternatives) ----
    SeriesProbe(
        series_id="CPALTT01JPM659N",
        description="CPI All Items, Japan — suffix M659N candidate",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Secondary probe — same suffix-convention hypothesis as DE.",
    ),
    SeriesProbe(
        series_id="CPALTT01JPM657N",
        description="CPI All Items, Japan — suffix M657N (re-probe; primary hit rate-limit)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Primary probe rate-limited. Sleep window between calls should resolve.",
    ),
    SeriesProbe(
        series_id="JPNCPIALLMINMEI",
        description="CPI All Items, Japan — BIS-OECD alternative naming",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Backup naming if M657N / M659N both fail.",
    ),
    # ---- global_inflation_momentum (bond yields — known clean from primary probe,
    # re-included so the secondary-probe output is self-contained) ----
    SeriesProbe(
        series_id="IRLTLT01USM156N",
        description="10Y Long-Term Government Bond Yield (US, OECD/IMF)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Primary probe: clean continuous coverage. Re-probed for record.",
    ),
    SeriesProbe(
        series_id="IRLTLT01DEM156N",
        description="10Y Long-Term Government Bond Yield (Germany)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes=(
            "Primary probe: continuous, went negative 2015-2022 — confirms "
            "duration-approximation engineering is required."
        ),
    ),
    SeriesProbe(
        series_id="IRLTLT01JPM156N",
        description="10Y Long-Term Government Bond Yield (Japan)",
        expected_freq="monthly",
        strategy="global_inflation_momentum",
        notes="Primary probe: continuous, went negative 2016-2022. Same conclusion as DE.",
    ),
]


def probe_one(fred: object, probe: SeriesProbe) -> dict[str, object]:
    """Fetch ``probe.series_id``; return coverage summary dict."""
    try:
        series = fred.get_series(probe.series_id)  # type: ignore[attr-defined]
    except Exception as exc:
        return {
            "series_id": probe.series_id,
            "status": f"FETCH_FAILED: {type(exc).__name__}: {exc}",
        }

    series = series.sort_index().dropna()
    if series.empty:
        return {
            "series_id": probe.series_id,
            "status": "EMPTY_RESPONSE",
        }

    start, end = series.index[0], series.index[-1]
    covers_audit_window = start <= pd.Timestamp(AUDIT_START) and end >= pd.Timestamp(AUDIT_END)

    # Detect gaps within the audit window.
    in_window = series.loc[pd.Timestamp(AUDIT_START) : pd.Timestamp(AUDIT_END)]
    gaps_days: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []
    if len(in_window) >= 2:
        diffs = in_window.index.to_series().diff().dt.days.dropna()
        max_gap = MAX_GAP_DAYS_DAILY if probe.expected_freq == "daily" else MAX_GAP_DAYS_MONTHLY
        for end_ts, gap in diffs.items():
            if gap > max_gap:
                end_ts_pd = pd.Timestamp(end_ts)
                idx = in_window.index.get_loc(end_ts_pd)
                if isinstance(idx, int) and idx > 0:
                    start_ts = in_window.index[idx - 1]
                    gaps_days.append((start_ts, end_ts_pd, int(gap)))

    finite_min = float(series.min()) if not series.isna().all() else float("nan")
    finite_max = float(series.max()) if not series.isna().all() else float("nan")

    # Crude LEVEL-vs-rate-of-change classifier: a true LEVEL series for
    # CPI sits in roughly [50, 350] with min/max ratio > 1.2; a rate-of-
    # change series sits in [-5, 15] or thereabouts and goes negative
    # somewhere. The ``looks_like_level`` flag surfaces the classification
    # so we don't need to eyeball the printed range.
    looks_like_level = finite_min >= 0.0 and finite_max > 50.0

    return {
        "series_id": probe.series_id,
        "status": "OK",
        "start": str(start.date()),
        "end": str(end.date()),
        "n_obs": len(series),
        "covers_2005_2025": covers_audit_window,
        "min": finite_min,
        "max": finite_max,
        "went_negative": bool(finite_min < 0.0),
        "looks_like_level": bool(looks_like_level),
        "n_gaps": len(gaps_days),
        "gaps": [f"{s.date()} -> {e.date()} ({g}d)" for s, e, g in gaps_days[:5]],
    }


def search_fred(fred: object, query: str, limit: int = 10) -> list[dict[str, object]]:
    """Return the top-N FRED search hits for ``query`` (id, title, dates)."""
    try:
        df = fred.search(query)  # type: ignore[attr-defined]
    except Exception as exc:
        return [{"error": f"{type(exc).__name__}: {exc}"}]

    if df is None or len(df) == 0:
        return []

    df = df.head(limit)
    cols = [
        c
        for c in ("id", "title", "frequency", "observation_start", "observation_end")
        if c in df.columns
    ]
    records = df[cols].to_dict(orient="records")
    return [dict(r) for r in records]


def main() -> int:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("ERROR: FRED_API_KEY not set in env.", file=sys.stderr)
        return 2

    try:
        from fredapi import Fred
    except ImportError:
        print(
            "ERROR: fredapi not installed. Run with: "
            "uv run --with fredapi python scripts/audit_fred_rates_series.py",
            file=sys.stderr,
        )
        return 2

    fred = Fred(api_key=api_key)

    by_strategy: dict[str, list[tuple[SeriesProbe, dict[str, object]]]] = {}
    for probe in CANDIDATES:
        result = probe_one(fred, probe)
        by_strategy.setdefault(probe.strategy, []).append((probe, result))
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    for strategy, rows in by_strategy.items():
        print(f"\n=== {strategy} ===")
        for probe, r in rows:
            print(f"  [{probe.series_id}] {probe.description}")
            print(f"    notes: {probe.notes}")
            if r.get("status") != "OK":
                print(f"    STATUS: {r.get('status')}")
                continue
            print(
                f"    coverage: {r['start']} -> {r['end']}  "
                f"(n={r['n_obs']}, covers 2005-2025: {r['covers_2005_2025']})"
            )
            min_v = float(r["min"])  # type: ignore[arg-type]
            max_v = float(r["max"])  # type: ignore[arg-type]
            print(
                f"    range: [{min_v:.4f}, {max_v:.4f}]  "
                f"(went negative: {r['went_negative']}, looks_like_level: {r['looks_like_level']})"
            )
            if r["n_gaps"]:
                print(f"    gaps ({r['n_gaps']} found, first 5 shown):")
                gaps_list = r["gaps"]
                assert isinstance(gaps_list, list)
                for g in gaps_list:
                    print(f"      {g}")
            else:
                print("    gaps: none (within tolerance)")

    print("\n=== FRED search results (for swap-rate hunt) ===")
    for query in SEARCH_QUERIES:
        print(f"\n  query: {query!r}")
        hits = search_fred(fred, query, limit=10)
        if not hits:
            print("    no hits")
            continue
        for h in hits:
            if "error" in h:
                print(f"    ERROR: {h['error']}")
                continue
            print(
                f"    [{h.get('id')}] {h.get('title')}  "
                f"(freq={h.get('frequency')}, "
                f"{h.get('observation_start')} -> {h.get('observation_end')})"
            )
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
