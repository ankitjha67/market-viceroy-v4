"""3-2-1 crack-spread mean-reversion trade.

Implementation notes
====================

Foundational paper
------------------
Geman, H. (2005). *Commodities and commodity derivatives:
Modeling and pricing for agriculturals, metals and energy*.
Wiley. Chapter 7 covers energy-product spread trading and
documents the canonical 3-2-1 refining-margin convention used by
US refiners.

Primary methodology
-------------------
Girma, P. B. & Paulson, A. S. (1999).
*Risk arbitrage opportunities in petroleum futures spreads*.
Journal of Futures Markets, 19(8), 931–955.
https://doi.org/10.1002/(SICI)1096-9934(199912)19:8<931::AID-FUT5>3.0.CO;2-L

Girma-Paulson (1999) documents the **crack spread** as a
mean-reverting trade between crude oil and refined products. The
spread represents the **gross refining margin** earned by
refiners — long the crack means betting that the refining margin
will widen (good for refiners); short the crack bets that the
margin will compress.

The 3-2-1 ratio
---------------
The canonical US refining ratio is **3 barrels of crude in → 2
barrels of gasoline + 1 barrel of heating oil out**. This reflects
the typical product yield of a US Gulf Coast refinery::

    crack_spread(t) = 2 * RB(t) + 1 * HO(t) - 3 * CL(t)

per barrel-equivalent. A positive crack spread means refining is
profitable (products worth more than crude); a negative crack
means refining loses money (rare but happened in 2008 H2 and
2020 H1).

Mean-reversion signal
---------------------
For each trading day *t*:

1. Compute the 3-2-1 crack spread.
2. Compute the rolling z-score over a ``zscore_lookback_days``
   window (default 252 ≈ 1 year).
3. **Long crack** when z < ``-entry_threshold`` (margin
   compressed below historical norm — bet on widening).
4. **Short crack** when z > ``+entry_threshold`` (margin too
   wide — bet on compression).
5. **Exit** when |z| < ``exit_threshold``.

Output is a 3-column DataFrame keyed on ``crude_symbol``,
``gasoline_symbol``, ``heating_oil_symbol``. Weights are normalised
so the gross book (sum of |w|) is 1:

* Long crack:  CL = -0.5, RB = +0.333, HO = +0.167
* Short crack: CL = +0.5, RB = -0.333, HO = -0.167
* Flat:        CL = 0,    RB = 0,      HO = 0

The relative sizing 0.5 : 0.333 : 0.167 = 3 : 2 : 1 preserves the
canonical refining ratio.

Why mean-reversion (not trend)
------------------------------
The crack spread is structurally mean-reverting because:

* Refiners *physically arbitrage* the spread: when the margin is
  too high, refiners ramp up production → product supply increases
  → product prices fall → margin compresses.
* When the margin is negative, refiners cut runs or shut down →
  product supply tightens → prices rise → margin recovers.
* Storage costs and product-grade specs prevent the margin from
  drifting indefinitely.

Girma-Paulson (1999) Table III reports half-lives of 8-14 weeks
for the 3-2-1 crack mean reversion across the 1986-1996 sample.
The strategy default `zscore_lookback_days = 252` (1 year)
captures roughly 5 half-lives of dynamics — sufficient to estimate
a stable mean.

Sign convention
---------------
Per-leg weight in ``[-0.5, +0.5]``. Multi-leg discrete signal: the
3-2-1 ratio is hardcoded; the only thing the strategy decides is
whether the trade is long, short, or flat.

Edge cases
----------
* Pre-warmup (insufficient history for z-score) → flat.
* Non-positive prices → ``ValueError``.
* Missing input columns → ``KeyError``.
"""

from __future__ import annotations

import pandas as pd

# Canonical 3-2-1 refining ratio: 3 crude in, 2 gasoline + 1 heating oil out.
# Normalised so |w_CL| + |w_RB| + |w_HO| = 1.
_CRACK_RATIO_CRUDE: float = 3.0 / 6.0  # 0.500
_CRACK_RATIO_GASOLINE: float = 2.0 / 6.0  # 0.333
_CRACK_RATIO_HEATING_OIL: float = 1.0 / 6.0  # 0.167


class CrackSpread:
    """3-2-1 crack-spread mean-reversion trade.

    Long the crack (long products, short crude) when the rolling
    z-score is below ``-entry_threshold``; short the crack when
    z > ``+entry_threshold``; flat when ``|z| < exit_threshold``.

    Parameters
    ----------
    crude_symbol
        Column name for the crude-oil leg. Defaults to ``"CL=F"``.
    gasoline_symbol
        Column name for the gasoline leg. Defaults to ``"RB=F"``.
    heating_oil_symbol
        Column name for the heating-oil leg. Defaults to ``"HO=F"``.
    zscore_lookback_days
        Rolling window for the spread mean and standard deviation.
        Defaults to ``252`` trading days (~1 year).
    entry_threshold
        |z| above which to enter a position. Defaults to ``2.0``.
    exit_threshold
        |z| below which to exit / stay flat. Defaults to ``0.5``.
        Must be < ``entry_threshold``.
    """

    name: str = "crack_spread"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1002/(SICI)1096-9934(199912)19:8<931::AID-FUT5>3.0.CO;2-L"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        crude_symbol: str = "CL=F",
        gasoline_symbol: str = "RB=F",
        heating_oil_symbol: str = "HO=F",
        zscore_lookback_days: int = 252,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
    ) -> None:
        for label, sym in (
            ("crude_symbol", crude_symbol),
            ("gasoline_symbol", gasoline_symbol),
            ("heating_oil_symbol", heating_oil_symbol),
        ):
            if not sym:
                raise ValueError(f"{label} must be a non-empty string")
        if len({crude_symbol, gasoline_symbol, heating_oil_symbol}) != 3:
            raise ValueError(
                "crude_symbol, gasoline_symbol, heating_oil_symbol must all differ; "
                f"got {crude_symbol!r}, {gasoline_symbol!r}, {heating_oil_symbol!r}"
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

        self.crude_symbol = crude_symbol
        self.gasoline_symbol = gasoline_symbol
        self.heating_oil_symbol = heating_oil_symbol
        self.zscore_lookback_days = zscore_lookback_days
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    @property
    def front_symbols(self) -> list[str]:
        return [self.crude_symbol, self.gasoline_symbol, self.heating_oil_symbol]

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a 3-leg crack-spread weights DataFrame.

        Parameters
        ----------
        prices
            DataFrame with at least the columns ``crude_symbol``,
            ``gasoline_symbol``, and ``heating_oil_symbol``.

        Returns
        -------
        weights
            DataFrame indexed like ``prices``, 3 columns matching
            the leg symbols, values in
            ``{-0.5, -0.333, -0.167, 0.0, +0.167, +0.333, +0.5}``.
        """
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

        cl = prices[self.crude_symbol]
        rb = prices[self.gasoline_symbol]
        ho = prices[self.heating_oil_symbol]

        # 1. 3-2-1 crack spread per barrel.
        crack = 2.0 * rb + 1.0 * ho - 3.0 * cl

        # 2. Rolling z-score.
        rolling_mean = crack.rolling(self.zscore_lookback_days).mean()
        rolling_std = crack.rolling(self.zscore_lookback_days).std(ddof=1)
        zscore = (crack - rolling_mean) / rolling_std

        # 3. Mean-reversion signal: long crack when z < -entry,
        # short crack when z > +entry, with hysteresis at exit.
        long_entry = zscore < -self.entry_threshold
        short_entry = zscore > self.entry_threshold
        flat_zone = zscore.abs() < self.exit_threshold

        # State-machine: hold position until |z| < exit_threshold or
        # crosses into the opposite extreme. We approximate this by
        # extending the signal with forward-fill across the
        # in-position region.
        state = pd.Series(0.0, index=prices.index)
        state[long_entry] = 1.0
        state[short_entry] = -1.0
        state[flat_zone] = 0.0
        # NaN (pre-warmup or in the hysteresis band) → carry the
        # previous state. We mark non-set rows as NaN, ffill, then
        # fill leading NaN with 0.
        state_mask = long_entry | short_entry | flat_zone
        state_signal = state.where(state_mask).ffill().fillna(0.0)

        # 4. Apply the 3-2-1 ratio to each leg.
        weights = pd.DataFrame(0.0, index=prices.index, columns=self.front_symbols)
        weights[self.crude_symbol] = -state_signal * _CRACK_RATIO_CRUDE
        weights[self.gasoline_symbol] = state_signal * _CRACK_RATIO_GASOLINE
        weights[self.heating_oil_symbol] = state_signal * _CRACK_RATIO_HEATING_OIL
        return weights
