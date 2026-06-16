"""Soybean-crush-spread mean-reversion trade.

Implementation notes
====================

Foundational paper
------------------
Working, H. (1949). *The theory of price of storage*. American
Economic Review, 39(6), 1254–1262.

Working (1949) is the canonical exposition of the **theory of
storage**: storable-commodity prices are tied to processing /
storage costs through a no-arbitrage relationship. The soybean-
crush spread is a direct application — the spread is bounded
above by the marginal cost of processing soybeans into meal+oil
and bounded below by the cost of storing soybeans as raw input.

Primary methodology
-------------------
Simon, D. P. (1999).
*The soybean crush spread: Empirical evidence and trading strategies*.
Journal of Futures Markets, 19(3), 271–289.
https://doi.org/10.1002/(SICI)1096-9934(199905)19:3<271::AID-FUT2>3.0.CO;2-S

Simon (1999) documents the soybean crush spread as a mean-
reverting risk-arbitrage trade analogous to the petroleum crack
spread. The spread represents the **gross processing margin**
earned by soybean crushers — long the crush bets the margin
widens (good for crushers); short the crush bets the margin
compresses.

The 1:1.5:0.8 ratio
-------------------
The simplified bushel-equivalent ratio for the soybean crush is
**1 bushel of soybeans → 1.5 units of meal-equivalent + 0.8 units
of oil-equivalent** (the actual CBOT board-crush conversion is
slightly more complex due to unit differences; this is the
textbook simplification used in Simon 1999 §II)::

    crush_spread(t) = 1.5 * ZM(t) + 0.8 * ZL(t) - 1.0 * ZS(t)

A positive crush spread means processing is profitable;
negative crush means processors lose money (rare but happens
during severe oversupply or processing-margin compression
episodes — e.g. 2014 H2 record bean harvest).

Mean-reversion signal
---------------------
For each trading day *t*:

1. Compute the 1:1.5:0.8 crush spread.
2. Compute the rolling z-score over a ``zscore_lookback_days``
   window (default 252 ≈ 1 year).
3. **Long crush** when z < ``-entry_threshold`` (margin
   compressed below historical norm).
4. **Short crush** when z > ``+entry_threshold`` (margin too
   wide).
5. **Exit** when |z| < ``exit_threshold``.

Output is a 3-column DataFrame keyed on ``soybean_symbol``,
``meal_symbol``, ``oil_symbol``. Weights are normalised so the
gross book is 1:

* Long crush:  ZS = -0.303, ZM = +0.455, ZL = +0.242
* Short crush: ZS = +0.303, ZM = -0.455, ZL = -0.242
* Flat:        all zeros

The relative sizing 0.303 : 0.455 : 0.242 = 1 : 1.5 : 0.8
preserves the canonical bushel-equivalent ratio.

Why mean-reversion (not trend)
------------------------------
The crush spread is structurally mean-reverting because:

* Crushers *physically arbitrage* the spread: when the margin is
  too high, crushers ramp up processing → product supply
  increases → product prices fall → margin compresses.
* When the margin is negative, crushers cut runs → product
  supply tightens → prices rise → margin recovers.
* Storage costs and the perishability of crushed products bound
  the dispersion.

Simon (1999) Table 4 reports half-lives of **6-12 weeks** for the
crush spread mean reversion across the 1985-1995 sample.

Sign convention
---------------
Per-leg weight in roughly ``[-0.5, +0.5]``. Multi-leg discrete
signal: the 1:1.5:0.8 ratio is hardcoded; the only thing the
strategy decides is whether to be long, short, or flat.

Edge cases
----------
* Pre-warmup (insufficient history for z-score) → flat.
* Non-positive prices → ``ValueError``.
* Missing input columns → ``KeyError``.
"""

from __future__ import annotations

import pandas as pd

# Canonical 1:1.5:0.8 soybean-crush ratio (bushel-equivalent).
# Normalised so |w_ZS| + |w_ZM| + |w_ZL| = 1.
_TOTAL: float = 1.0 + 1.5 + 0.8  # 3.3
_CRUSH_RATIO_SOYBEAN: float = 1.0 / _TOTAL  # 0.303
_CRUSH_RATIO_MEAL: float = 1.5 / _TOTAL  # 0.455
_CRUSH_RATIO_OIL: float = 0.8 / _TOTAL  # 0.242


class CrushSpread:
    """Soybean-crush-spread mean-reversion trade.

    Long the crush (long meal+oil, short soybeans) when the rolling
    z-score is below ``-entry_threshold``; short the crush when
    z > ``+entry_threshold``; flat when ``|z| < exit_threshold``.

    Parameters
    ----------
    soybean_symbol
        Column name for the soybean leg. Defaults to ``"ZS=F"``.
    meal_symbol
        Column name for the soybean-meal leg. Defaults to ``"ZM=F"``.
    oil_symbol
        Column name for the soybean-oil leg. Defaults to ``"ZL=F"``.
    zscore_lookback_days
        Rolling window for the spread mean and standard deviation.
        Defaults to ``252`` trading days.
    entry_threshold
        |z| above which to enter a position. Defaults to ``2.0``.
    exit_threshold
        |z| below which to exit / stay flat. Defaults to ``0.5``.
    """

    name: str = "crush_spread"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1002/(SICI)1096-9934(199905)19:3<271::AID-FUT2>3.0.CO;2-S"
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        soybean_symbol: str = "ZS=F",
        meal_symbol: str = "ZM=F",
        oil_symbol: str = "ZL=F",
        zscore_lookback_days: int = 252,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
    ) -> None:
        for label, sym in (
            ("soybean_symbol", soybean_symbol),
            ("meal_symbol", meal_symbol),
            ("oil_symbol", oil_symbol),
        ):
            if not sym:
                raise ValueError(f"{label} must be a non-empty string")
        if len({soybean_symbol, meal_symbol, oil_symbol}) != 3:
            raise ValueError(
                "soybean_symbol, meal_symbol, oil_symbol must all differ; "
                f"got {soybean_symbol!r}, {meal_symbol!r}, {oil_symbol!r}"
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

        self.soybean_symbol = soybean_symbol
        self.meal_symbol = meal_symbol
        self.oil_symbol = oil_symbol
        self.zscore_lookback_days = zscore_lookback_days
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    @property
    def front_symbols(self) -> list[str]:
        return [self.soybean_symbol, self.meal_symbol, self.oil_symbol]

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a 3-leg crush-spread weights DataFrame."""
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

        zs = prices[self.soybean_symbol]
        zm = prices[self.meal_symbol]
        zl = prices[self.oil_symbol]

        # 1. 1:1.5:0.8 crush spread.
        crush = 1.5 * zm + 0.8 * zl - 1.0 * zs

        # 2. Rolling z-score.
        rolling_mean = crush.rolling(self.zscore_lookback_days).mean()
        rolling_std = crush.rolling(self.zscore_lookback_days).std(ddof=1)
        zscore = (crush - rolling_mean) / rolling_std

        # 3. Mean-reversion signal with hysteresis.
        long_entry = zscore < -self.entry_threshold
        short_entry = zscore > self.entry_threshold
        flat_zone = zscore.abs() < self.exit_threshold

        state = pd.Series(0.0, index=prices.index)
        state[long_entry] = 1.0
        state[short_entry] = -1.0
        state[flat_zone] = 0.0
        state_mask = long_entry | short_entry | flat_zone
        state_signal = state.where(state_mask).ffill().fillna(0.0)

        # 4. Apply the 1:1.5:0.8 ratio.
        weights = pd.DataFrame(0.0, index=prices.index, columns=self.front_symbols)
        weights[self.soybean_symbol] = -state_signal * _CRUSH_RATIO_SOYBEAN
        weights[self.meal_symbol] = state_signal * _CRUSH_RATIO_MEAL
        weights[self.oil_symbol] = state_signal * _CRUSH_RATIO_OIL
        return weights
