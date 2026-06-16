"""Calendar-based seasonal trade on US grain futures.

Implementation notes
====================

Foundational paper
------------------
Fama, E. F. & French, K. R. (1987).
*Commodity futures prices: Some evidence on forecast power,
premiums, and the theory of storage*.
Journal of Business, 60(1), 55–73.
https://doi.org/10.1086/296385

Fama-French (1987) documents that storable-commodity futures
prices exhibit predictable seasonality driven by the **theory of
storage**: prices peak when stocks are at their seasonal low
(immediately before harvest) and trough when stocks are at their
seasonal high (immediately after harvest). The premium-discount
cycle is the cost of holding storage through the agricultural
year.

Primary methodology
-------------------
Sørensen, C. (2002).
*Modeling seasonality in agricultural commodity futures*.
Journal of Futures Markets, 22(5), 393–426.
https://doi.org/10.1002/fut.10017

Sørensen (2002) fits a state-space model with explicit calendar-
seasonal terms to corn, soybean, and wheat futures over 1972-2000
and finds:

* **Corn (ZC)**: prices typically peak May-June (planting weather
  uncertainty premium), trough September-October (US harvest).
  Annualised seasonal amplitude ~10-15%.
* **Soybeans (ZS)**: peak May-July (planting + early-summer weather
  premium), trough October-November (US harvest). Amplitude
  ~8-12%.
* **Wheat (ZW)**: peak February-April (winter-wheat weather
  uncertainty), trough July-August (winter-wheat harvest in the
  US Plains). Amplitude ~6-10%.

The strategy
------------
For each grain *g* at each month-end *t*:

1. Look up the calendar month of *t*.
2. **Long** if month is in the commodity-specific peak window
   (high-stock-uncertainty premium).
3. **Short** if month is in the commodity-specific trough window
   (post-harvest stock release).
4. **Flat** otherwise.

The seasonal calendar is hardcoded per the Sørensen (2002) Section
III findings:

* ZC long Apr-Jun, short Sep-Nov
* ZS long May-Jul, short Oct-Dec
* ZW long Feb-Apr, short Jul-Aug

Sign convention
---------------
Per-leg discrete signal in ``{−1.0, 0.0, +1.0}``. Output columns
match the input universe (``front_symbols`` constructor param).

Why a fixed calendar rule
-------------------------
The seasonal pattern has been remarkably stable across the
1972-2000 sample (Sørensen Table II) and replications through 2014
(Pukthuanthong & Roll, 2017): the planting-harvest cycle on US
grains is set by the agricultural year, not the macro cycle, so
the seasonality persists across regimes.

The strategy deliberately uses a **fixed calendar rule** rather
than a learned-from-data signal because:

1. The economic content (storage theory) is well-understood and
   stable.
2. A learned signal on a 30-50 year sample has 30-50 in-sample
   data points per month — over-fitting risk is high.
3. A fixed rule is transparent and falsifiable — if the
   seasonality breaks down (e.g. due to climate change shifting
   the harvest calendar), the failure is visible and the rule
   can be updated explicitly rather than absorbed into a model.

Edge cases
----------
* Empty input → empty output.
* Non-positive prices → ``ValueError``.
* Missing input columns → ``KeyError``.
* Universe parameter restricts which legs are traded; unknown
  symbols (no calendar entry) → ``ValueError`` at construction
  time.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

# Sørensen (2002) §III seasonal calendar, by US-grain symbol.
# Months are 1-indexed (1 = January). Peak = long, Trough = short.
_SEASONAL_CALENDAR: dict[str, dict[str, set[int]]] = {
    "ZC=F": {"long": {4, 5, 6}, "short": {9, 10, 11}},  # Corn
    "ZS=F": {"long": {5, 6, 7}, "short": {10, 11, 12}},  # Soybeans
    "ZW=F": {"long": {2, 3, 4}, "short": {7, 8}},  # Wheat
}

_DEFAULT_UNIVERSE: tuple[str, ...] = ("ZC=F", "ZS=F", "ZW=F")


class GrainSeasonality:
    """Calendar-based seasonal trade on US grain futures.

    Long the planting-uncertainty months and short the harvest
    months per Sørensen (2002) §III. Per-leg discrete signal.

    Parameters
    ----------
    universe
        Iterable of grain symbols to trade. Each symbol must have a
        seasonal-calendar entry. Defaults to ``("ZC=F", "ZS=F",
        "ZW=F")``.
    """

    name: str = "grain_seasonality"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
    paper_doi: str = "10.1002/fut.10017"  # Sørensen 2002
    rebalance_frequency: str = "monthly"

    def __init__(self, *, universe: Iterable[str] | None = None) -> None:
        if universe is None:
            symbols: tuple[str, ...] = _DEFAULT_UNIVERSE
        else:
            symbols = tuple(universe)
        if not symbols:
            raise ValueError("universe must be non-empty")
        for sym in symbols:
            if not sym:
                raise ValueError("universe entries must be non-empty strings")
            if sym not in _SEASONAL_CALENDAR:
                known = sorted(_SEASONAL_CALENDAR.keys())
                raise ValueError(f"no seasonal calendar entry for {sym!r}; known symbols: {known}")
        self.universe: tuple[str, ...] = symbols

    @property
    def front_symbols(self) -> list[str]:
        return list(self.universe)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a calendar-seasonal signal DataFrame.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, columns include
            (at least) the symbols in ``self.universe``. Values are
            grain-futures continuous-contract closing prices.

        Returns
        -------
        signal
            DataFrame indexed like ``prices``, columns are the
            traded universe, values in ``{-1.0, 0.0, +1.0}``.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=self.front_symbols, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        missing = set(self.universe) - set(prices.columns)
        if missing:
            raise KeyError(
                f"prices is missing required columns: {sorted(missing)}; "
                f"got columns={list(prices.columns)}"
            )
        if (prices[list(self.universe)] <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        months = prices.index.month
        signal = pd.DataFrame(0.0, index=prices.index, columns=self.front_symbols)
        for sym in self.universe:
            cal = _SEASONAL_CALENDAR[sym]
            long_mask = months.isin(cal["long"])
            short_mask = months.isin(cal["short"])
            signal.loc[long_mask, sym] = 1.0
            signal.loc[short_mask, sym] = -1.0
        return signal
