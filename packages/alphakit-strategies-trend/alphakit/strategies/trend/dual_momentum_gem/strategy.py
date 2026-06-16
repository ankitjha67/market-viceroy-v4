"""Global Equities Momentum (Antonacci 2014).

Paper / book
------------
Antonacci, G. (2014). *Dual Momentum Investing: An Innovative Strategy
for Higher Returns with Lower Risk*. McGraw-Hill. ISBN 978-0071849449.
Working-paper version: *Risk Premia Harvesting Through Dual Momentum*.
SSRN 2042750. https://doi.org/10.2139/ssrn.2042750

Rules
-----
At every month-end:

1. **Absolute momentum.** Compare the US-equity 12-month total return
   against the risk-free (short-Treasury) 12-month total return. If
   the US equity return is *below* the risk-free return, be **100%
   bonds** — the momentum tide is out and you sit in safe assets.
2. **Relative momentum.** If US equity passes the absolute-momentum
   filter, compare it against International equity over the same
   12-month window. Long whichever is higher, 100% of the portfolio.

The strategy therefore *always* holds exactly one of three assets
(US equity, International equity, bonds) at 100% weight. It is
arguably the simplest respectable tactical-allocation rule in
published finance, and its multi-decade Sharpe / drawdown profile
has held up well in out-of-sample tests.

Edge cases
----------
* Warm-up (first 12 months of data): zero weights.
* If any of the four symbols is missing at a given month-end (NaN
  price), we flat the portfolio for that month rather than guess.
"""

from __future__ import annotations

from typing import cast

import pandas as pd


class DualMomentumGEM:
    """Global Equities Momentum (Antonacci 2014).

    Parameters
    ----------
    us_equity
        Symbol for the US-equity leg. Defaults to ``"SPY"``.
    intl_equity
        Symbol for the International-equity leg. Defaults to ``"VEU"``.
    bonds
        Symbol for the bond leg. Defaults to ``"AGG"``.
    risk_free
        Symbol for the risk-free (short-Treasury) leg used in the
        absolute-momentum check. Defaults to ``"SHY"``.
    lookback_months
        Lookback window for both absolute and relative momentum.
        Defaults to ``12``.
    """

    name: str = "dual_momentum_gem"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "bond", "etf")
    paper_doi: str = "10.2139/ssrn.2042750"
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        us_equity: str = "SPY",
        intl_equity: str = "VEU",
        bonds: str = "AGG",
        risk_free: str = "SHY",
        lookback_months: int = 12,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        seen = {us_equity, intl_equity, bonds, risk_free}
        if len(seen) != 4:
            raise ValueError(
                f"us_equity, intl_equity, bonds, risk_free must be distinct; "
                f"got {(us_equity, intl_equity, bonds, risk_free)}"
            )
        self.us_equity = us_equity
        self.intl_equity = intl_equity
        self.bonds = bonds
        self.risk_free = risk_free
        self.lookback_months = lookback_months

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        required = {self.us_equity, self.intl_equity, self.bonds, self.risk_free}
        missing = required - set(prices.columns)
        if missing:
            raise ValueError(
                f"prices is missing required symbols: {sorted(missing)}; "
                f"available: {sorted(prices.columns)}"
            )

        monthly = prices.resample("ME").last()
        lookback_returns = monthly.pct_change(self.lookback_months)

        us = lookback_returns[self.us_equity]
        intl = lookback_returns[self.intl_equity]
        rf = lookback_returns[self.risk_free]

        # Warm-up mask: every leg must be observable.
        valid = (
            lookback_returns[[self.us_equity, self.intl_equity, self.risk_free]].notna().all(axis=1)
        )

        absmom_pass = us > rf
        pick_us = absmom_pass & (us >= intl) & valid
        pick_intl = absmom_pass & (us < intl) & valid
        pick_bonds = (~absmom_pass) & valid

        monthly_weights = pd.DataFrame(0.0, index=monthly.index, columns=prices.columns)
        monthly_weights.loc[pick_us, self.us_equity] = 1.0
        monthly_weights.loc[pick_intl, self.intl_equity] = 1.0
        monthly_weights.loc[pick_bonds, self.bonds] = 1.0

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
