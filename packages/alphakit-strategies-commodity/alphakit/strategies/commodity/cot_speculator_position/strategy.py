"""Contrarian COT speculator-positioning trade on commodity futures.

Implementation notes
====================

Foundational paper
------------------
Bessembinder, H. (1992).
*Systematic risk, hedging pressure, and risk premiums in futures markets*.
Review of Financial Studies, 5(4), 637–667.
https://doi.org/10.1093/rfs/5.4.637

Bessembinder (1992) decomposes the futures-curve risk premium into
hedging-pressure and macro-risk components. The empirical result:
**commercial hedgers earn a discount on their hedge sales /
purchases, and speculators earn the corresponding premium for
taking the other side.** Equivalently — when speculators crowd
into one direction, the premium they earn is competed away and
expected forward returns are negative.

Primary methodology
-------------------
de Roon, F. A., Nijman, T. E. & Veld, C. (2000).
*Hedging pressure effects in futures markets*.
Journal of Finance, 55(3), 1437–1456.
https://doi.org/10.1111/0022-1082.00253

de Roon-Nijman-Veld (2000) directly test the hedging-pressure
hypothesis on the CFTC Commitments of Traders (COT) data and find
that **non-commercial (speculator) net positioning predicts futures
returns with the wrong sign** — i.e. extreme speculator long
positioning forecasts negative returns; extreme speculator short
positioning forecasts positive returns. This is the contrarian COT
signal.

The strategy
------------
For each commodity *c* with a paired COT positioning column:

1. Compute the **historical percentile** of the
   net-speculator-position (long minus short, normalised by open
   interest) over a rolling ``percentile_lookback_weeks`` window
   (default 156 weeks ≈ 3 years).
2. When percentile > ``extreme_long_threshold`` (default 90 →
   speculators in the top decile of their long history) → **short**
   the front contract.
3. When percentile < ``extreme_short_threshold`` (default 10 →
   speculators in the bottom decile / extreme short) → **long**
   the front contract.
4. Otherwise → flat.

Friday-for-Tuesday COT lag
--------------------------
**Critical**: CFTC publishes the Commitments of Traders report
**every Friday at 15:30 ET**, covering positions held as of **the
prior Tuesday close**. The strategy *must* respect this Tuesday-
to-Friday publication lag — if today is Wednesday, the most recent
COT data we may legitimately use is the prior Friday's report
(which covers the Tuesday before that — six days earlier).

This implementation enforces the lag by **shifting the COT-derived
signal forward by ``cot_lag_days`` trading days** (default 3 ≈ a
Tuesday-to-Friday gap with a 1-day buffer for execution lag) before
applying the rule. Users running on real CFTC data should align
their ingestion to publish-Friday and pre-lag the data so the
synthetic shift here matches the live timeline.

A failure to apply the lag in backtests produces ~3-5% spurious
annualised excess returns from forward-looking bias on the
positioning data — the most common error in COT-strategy
research.

Input convention
----------------
The strategy expects a single DataFrame with **paired columns**
per commodity: a price column (e.g. ``"CL=F"``) and a positioning
column (e.g. ``"CL=F_NET_SPEC"``). The constructor parameter
``front_to_position_map`` defines the pairing.

Output is a DataFrame with one column per **traded front symbol**
(the keys of ``front_to_position_map``). Position columns are
consumed for the signal but not traded.

The positioning column can be either the **non-commercial long
fraction of open interest** (range ``(0, 1]``):

    long_fraction(t) = non_commercial_long(t) / open_interest(t)

or the raw **net** non-commercial position (range ``[-1, +1]``,
signed; negative values when speculators are net short). Either
form works: the trading rule is the rolling-percentile rank of the
positioning series, which is invariant to monotonic
transformations. Real CFTC ``*_NET_SPEC`` feeds typically come as
the signed net form, which is now accepted directly — no
shift-to-positive workaround required.

Input contract (post Session 2I 2026-05-22 amendment + Session 2J
bridge zero-weight drop): front-month price columns must be
**finite and strictly positive** (they are traded), and positioning
columns must be **finite** (they are informational — declared via
``required_symbols`` and dropped by the bridge before
``from_orders``, so the bridge no longer requires them positive).

Sign convention
---------------
Output values are in ``{-1.0, 0.0, +1.0}`` per traded leg. Multi-
asset legs are independently sized; the book is **not**
cross-sectionally normalised — a portfolio overlay can scale to
target gross/net.

Edge cases
----------
* Before ``percentile_lookback_weeks * 5`` trading days of history,
  the percentile is undefined and the signal is zero.
* Constant positioning (no historical variation) → percentile
  undefined → zero signal.
* Front-month price columns: ``NaN`` / ``inf`` or non-positive
  values → ``ValueError`` (these are traded closes the bridge
  needs to value the portfolio).
* Positioning columns: ``NaN`` / ``inf`` → ``ValueError``; negative
  values are valid (signed ``NET_SPEC``).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

_DEFAULT_FRONT_TO_POSITION_MAP: dict[str, str] = {
    "CL=F": "CL=F_NET_SPEC",
    "NG=F": "NG=F_NET_SPEC",
    "GC=F": "GC=F_NET_SPEC",
    "ZC=F": "ZC=F_NET_SPEC",
}

# CFTC market codes for the default 4-commodity panel, verified empirically
# against the 2024 ``deacot2024.zip`` ``annual.txt`` (S2K-1, 2026-MM-DD).
#
# The kickoff defaults (067411 for WTI, 023655 for NG) were both wrong-exchange
# variants — 067411 is ICE Europe WTI (not NYMEX), and 023655 is the NYMEX
# E-mini Natural Gas (not the standard Henry Hub contract). The corrected
# codes below match the contracts yfinance tracks via ``CL=F`` / ``NG=F``
# (NYMEX physical Light Sweet Crude and NYMEX Henry Hub Natural Gas). See
# ``docs/sessions/2k-closeout.md`` §8 for the empirical-verification lesson.
#
# Consumed by ``BenchmarkRunner._fetch_prices``: when an informational
# ``*_NET_SPEC`` symbol routes to the ``"cftc-cot-wide"`` adapter, the runner
# translates the NET_SPEC name to its market code via this map before fetch,
# and renames the returned columns back to NET_SPEC names after fetch.
_DEFAULT_CFTC_MARKET_CODES: dict[str, str] = {
    "CL=F_NET_SPEC": "067651",  # NYMEX WTI Light Sweet Crude — PHYSICAL
    "NG=F_NET_SPEC": "03565B",  # NYMEX Henry Hub Natural Gas (standard)
    "GC=F_NET_SPEC": "088691",  # COMEX Gold
    "ZC=F_NET_SPEC": "002602",  # CBOT Corn
}


class COTSpeculatorPosition:
    """Contrarian COT speculator-positioning trade.

    Long when speculators are extreme-short (bottom decile of their
    rolling positioning history); short when speculators are
    extreme-long (top decile); flat otherwise. Per de Roon-Nijman-
    Veld (2000) hedging-pressure effects on the CFTC COT data.

    Parameters
    ----------
    front_to_position_map
        Mapping ``{front_symbol: position_column}``. Defaults to a
        4-commodity panel: CL, NG, GC, ZC. The position column
        should contain net-speculator-position normalised by open
        interest.
    percentile_lookback_weeks
        Rolling window for computing the historical percentile of
        the positioning series. Defaults to ``156`` weeks (3 years).
    extreme_long_threshold
        Percentile (0-100) above which speculators are considered
        extreme-long → short the asset. Defaults to ``90``.
    extreme_short_threshold
        Percentile below which speculators are considered
        extreme-short → long the asset. Defaults to ``10``.
    cot_lag_days
        Trading-day lag applied to the positioning signal to respect
        the CFTC Friday-for-Tuesday publication delay. Defaults to
        ``3`` (Tue close → Fri publication + 1-day execution
        buffer).
    """

    name: str = "cot_speculator_position"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1111/0022-1082.00253"  # de Roon-Nijman-Veld 2000
    rebalance_frequency: str = "weekly"

    def __init__(
        self,
        *,
        front_to_position_map: Mapping[str, str] | None = None,
        cftc_market_codes: Mapping[str, str] | None = None,
        percentile_lookback_weeks: int = 156,
        extreme_long_threshold: float = 90.0,
        extreme_short_threshold: float = 10.0,
        cot_lag_days: int = 3,
    ) -> None:
        if front_to_position_map is None:
            front_to_position_map = _DEFAULT_FRONT_TO_POSITION_MAP
        if not front_to_position_map:
            raise ValueError("front_to_position_map must be non-empty")
        for front, pos in front_to_position_map.items():
            if not front or not pos:
                raise ValueError(
                    f"front_to_position_map entries must be non-empty strings; "
                    f"got {front!r}: {pos!r}"
                )
            if front == pos:
                raise ValueError(
                    f"front_to_position_map entry maps {front!r} to itself; "
                    f"front and position columns must differ"
                )
        if cftc_market_codes is None:
            cftc_market_codes = _DEFAULT_CFTC_MARKET_CODES
        if percentile_lookback_weeks < 4:
            raise ValueError(
                f"percentile_lookback_weeks must be >= 4, got {percentile_lookback_weeks}"
            )
        if not (50.0 < extreme_long_threshold <= 100.0):
            raise ValueError(
                f"extreme_long_threshold must be in (50, 100], got {extreme_long_threshold}"
            )
        if not (0.0 <= extreme_short_threshold < 50.0):
            raise ValueError(
                f"extreme_short_threshold must be in [0, 50), got {extreme_short_threshold}"
            )
        if cot_lag_days < 0:
            raise ValueError(f"cot_lag_days must be non-negative, got {cot_lag_days}")

        self.front_to_position_map = dict(front_to_position_map)
        # ``cftc_market_codes`` is consumed by the multi-feed runner's
        # ``_fetch_prices`` when dispatching ``*_NET_SPEC`` informational
        # symbols to the ``"cftc-cot-wide"`` adapter; the runner translates
        # NET_SPEC names → market codes before fetch and renames returned
        # columns back after fetch. See ``alphakit.bench.runner._fetch_prices``
        # and ``alphakit.data.positioning.cftc_cot_wide_adapter`` (S2K-1).
        self.cftc_market_codes = dict(cftc_market_codes)
        self.percentile_lookback_weeks = percentile_lookback_weeks
        self.extreme_long_threshold = extreme_long_threshold
        self.extreme_short_threshold = extreme_short_threshold
        self.cot_lag_days = cot_lag_days

    @property
    def front_symbols(self) -> list[str]:
        return list(self.front_to_position_map.keys())

    @property
    def position_columns(self) -> list[str]:
        return list(self.front_to_position_map.values())

    # Session 2G informational-column-pattern aliases. The runner's
    # ``_informational_columns`` (and the S2J feed router) read these to
    # split tradable futures (yfinance-futures) from informational CFTC
    # positioning columns (cftc-cot) — see ``BenchmarkRunner._fetch_prices``.
    @property
    def tradable_symbols(self) -> tuple[str, ...]:
        return tuple(self.front_to_position_map.keys())

    @property
    def required_symbols(self) -> tuple[str, ...]:
        return (*self.front_to_position_map.keys(), *self.front_to_position_map.values())

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a contrarian COT signal DataFrame.

        Parameters
        ----------
        prices
            DataFrame with both price columns (the keys of
            ``front_to_position_map``) and positioning columns (the
            values). Index is daily. Price columns are
            continuous-contract closing prices; positioning columns
            are net-speculator-position normalised by open interest.

        Returns
        -------
        weights
            DataFrame indexed like ``prices``, columns are the front
            symbols (traded legs), values in ``{-1.0, 0.0, +1.0}``.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=self.front_symbols, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        required = set(self.front_symbols) | set(self.position_columns)
        missing = required - set(prices.columns)
        if missing:
            raise KeyError(
                f"prices is missing required columns: {sorted(missing)}; "
                f"got columns={list(prices.columns)}"
            )
        # Front-month futures (tradable) must be finite AND strictly positive —
        # they are priced and traded. CFTC positioning columns are
        # *informational* (carry weight 0 in the output, per the Session 2G
        # pattern and the bridge's zero-weight-column drop) and are
        # legitimately signed: NET_SPEC is the net non-commercial position
        # scaled by open interest and can be negative when speculators are net
        # short. Per the 2026-05-22 amendment, informational columns require
        # only finite values, not positivity. (Finiteness is checked *before*
        # the positivity comparison because ``NaN <= 0`` is False, so the
        # positivity check alone would let non-finite tradable prices through —
        # review request on PR #22.)
        if not np.isfinite(prices[self.front_symbols].to_numpy()).all():
            raise ValueError("front-month price columns must be finite")
        if (prices[self.front_symbols] <= 0).any().any():
            raise ValueError("front-month price columns must be strictly positive")
        if not np.isfinite(prices[self.position_columns].to_numpy()).all():
            raise ValueError("positioning columns must be finite")

        # 1. Apply the Friday-for-Tuesday COT lag to the positioning
        # series before computing the signal.
        positions = prices[self.position_columns].shift(self.cot_lag_days)

        # 2. Rolling percentile per commodity over the lookback window
        # (in trading days; weekly lookback × 5 trading days).
        lookback_days = self.percentile_lookback_weeks * 5
        weights = pd.DataFrame(0.0, index=prices.index, columns=self.front_symbols)

        for front, pos_col in self.front_to_position_map.items():
            series = positions[pos_col]
            # Rolling percentile rank: where in the historical
            # distribution is the current observation? rank(pct=True)
            # within the rolling window.
            rolling_rank = series.rolling(lookback_days, min_periods=lookback_days).apply(
                lambda window: 100.0 * (window.rank(pct=True).iloc[-1]),
                raw=False,
            )
            # Contrarian rule:
            #   percentile > 90 → speculators extreme long → SHORT
            #   percentile < 10 → speculators extreme short → LONG
            short_mask = rolling_rank > self.extreme_long_threshold
            long_mask = rolling_rank < self.extreme_short_threshold

            col = pd.Series(0.0, index=prices.index)
            col[short_mask & np.isfinite(rolling_rank)] = -1.0
            col[long_mask & np.isfinite(rolling_rank)] = +1.0
            weights[front] = col

        return weights
