"""WTI-Brent crude-oil pairs-trading spread.

Implementation notes
====================

Foundational paper
------------------
Gatev, E., Goetzmann, W. N. & Rouwenhorst, K. G. (2006).
*Pairs trading: Performance of a relative-value arbitrage rule*.
Review of Financial Studies, 19(3), 797–827.
https://doi.org/10.1093/rfs/hhj020

GGR (2006) establishes the pairs-trading methodology: identify
two assets with a stable historical price relationship, normalise
the spread, trade the mean reversion when the spread crosses a
threshold (typically 2σ from the historical mean), and exit when
the spread reverts.

Primary methodology
-------------------
Reboredo, J. C. (2011).
*How do crude oil prices co-move? A copula approach*.
Energy Economics, 33(5), 948–955.
https://doi.org/10.1016/j.eneco.2011.04.006

Reboredo (2011) documents the **WTI-Brent cointegration** and the
specific conditions under which the spread diverges:

* In normal times the two grades are cointegrated (long-run
  equilibrium relationship); the spread oscillates around a small
  premium reflecting transport and quality differentials.
* During *infrastructure* dislocations (Cushing-OK pipeline
  congestion 2011-2014, US export ban repeal 2015-2016), the
  spread can persist in disequilibrium for months.
* During *geopolitical* events (Brent supply shocks like 2014
  Libya, 2019 Saudi attacks, 2022 Russia sanctions), the spread
  can move quickly in either direction before re-establishing.

Cointegration analysis
----------------------
WTI and Brent are both light-sweet crude grades but priced at
different delivery points (WTI at Cushing, OK; Brent at North
Sea). The two prices are cointegrated under the Engle-Granger
test in normal periods, with the cointegration coefficient near
1.0 (i.e. the spread is approximately ``CL - BZ`` after a constant
mean shift representing the typical Brent premium for transport
+ quality).

The strategy does **not** explicitly run an Engle-Granger or
Johansen test in code — instead it relies on the published
cointegration result (Reboredo 2011 Table 2; Lin-Tamvakis 2010
JFM) and uses a rolling z-score of the simple ``CL - BZ`` spread
as the trading signal. The rolling lookback effectively re-
estimates the equilibrium mean as it shifts (e.g. through the
2011-2014 Cushing-glut regime), so the strategy adapts to slow
changes in the cointegration relationship without an explicit
re-test.

Pairs-trading signal
--------------------
For each trading day *t*:

1. Compute the spread ``CL(t) - BZ(t)``.
2. Compute the rolling z-score over a ``zscore_lookback_days``
   window (default 252 ≈ 1 year, vs GGR's 12-month formation
   period).
3. **Long spread** (long WTI, short Brent) when z < ``-entry_threshold``.
4. **Short spread** (short WTI, long Brent) when z > ``+entry_threshold``.
5. **Exit** when |z| < ``exit_threshold``.

Output is a 2-column DataFrame keyed on ``wti_symbol`` and
``brent_symbol``. Per-leg weights are ±0.5 to maintain a
dollar-neutral 1:1 pair:

* Long spread:  CL = +0.5, BZ = -0.5
* Short spread: CL = -0.5, BZ = +0.5
* Flat:         both zero

Sign convention
---------------
Per-leg weight in ``{-0.5, 0.0, +0.5}``. 1:1 dollar-neutral pair,
matching the GGR canonical form.

Edge cases
----------
* Pre-warmup → flat.
* Non-positive prices → ``ValueError``.
* Missing input columns → ``KeyError``.
"""

from __future__ import annotations

import pandas as pd


class WTIBrentSpread:
    """WTI-Brent crude-oil pairs-trading spread.

    Long the spread (long WTI, short Brent) when the rolling
    z-score is below ``-entry_threshold``; short the spread when
    z > ``+entry_threshold``; flat when ``|z| < exit_threshold``.

    Parameters
    ----------
    wti_symbol
        Column name for the WTI leg. Defaults to ``"CL=F"``.
    brent_symbol
        Column name for the Brent leg. Defaults to ``"BZ=F"``.
    zscore_lookback_days
        Rolling window for the spread mean and standard deviation.
        Defaults to ``252`` trading days.
    entry_threshold
        |z| above which to enter a position. Defaults to ``2.0``.
    exit_threshold
        |z| below which to exit / stay flat. Defaults to ``0.5``.
    """

    name: str = "wti_brent_spread"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1016/j.eneco.2011.04.006"  # Reboredo 2011
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        wti_symbol: str = "CL=F",
        brent_symbol: str = "BZ=F",
        zscore_lookback_days: int = 252,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
    ) -> None:
        if not wti_symbol:
            raise ValueError("wti_symbol must be a non-empty string")
        if not brent_symbol:
            raise ValueError("brent_symbol must be a non-empty string")
        if wti_symbol == brent_symbol:
            raise ValueError(
                f"wti_symbol and brent_symbol must differ; got {wti_symbol!r} for both"
            )
        if zscore_lookback_days < 30:
            raise ValueError(f"zscore_lookback_days must be >= 30, got {zscore_lookback_days}")
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be > 0, got {entry_threshold}")
        if exit_threshold < 0:
            raise ValueError(f"exit_threshold must be >= 0, got {exit_threshold}")
        if exit_threshold >= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be < entry_threshold ({entry_threshold})"
            )

        self.wti_symbol = wti_symbol
        self.brent_symbol = brent_symbol
        self.zscore_lookback_days = zscore_lookback_days
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    @property
    def front_symbols(self) -> list[str]:
        return [self.wti_symbol, self.brent_symbol]

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a 2-leg WTI-Brent pairs-trading weights DataFrame."""
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=self.front_symbols, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        missing = set(self.front_symbols) - set(prices.columns)
        if missing:
            raise KeyError(
                f"prices is missing required columns: {sorted(missing)}; "
                f"got columns={list(prices.columns)}"
            )
        if (prices[self.front_symbols] <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        cl = prices[self.wti_symbol]
        bz = prices[self.brent_symbol]

        # 1. Spread = CL - BZ
        spread = cl - bz

        # 2. Rolling z-score
        rolling_mean = spread.rolling(self.zscore_lookback_days).mean()
        rolling_std = spread.rolling(self.zscore_lookback_days).std(ddof=1)
        zscore = (spread - rolling_mean) / rolling_std

        # 3. Mean-reversion signal with hysteresis
        long_entry = zscore < -self.entry_threshold
        short_entry = zscore > self.entry_threshold
        flat_zone = zscore.abs() < self.exit_threshold

        state = pd.Series(0.0, index=prices.index)
        state[long_entry] = 1.0
        state[short_entry] = -1.0
        state[flat_zone] = 0.0
        state_mask = long_entry | short_entry | flat_zone
        state_signal = state.where(state_mask).ffill().fillna(0.0)

        # 4. 1:1 dollar-neutral pair (per-leg ±0.5)
        weights = pd.DataFrame(0.0, index=prices.index, columns=self.front_symbols)
        weights[self.wti_symbol] = state_signal * 0.5
        weights[self.brent_symbol] = -state_signal * 0.5
        return weights
