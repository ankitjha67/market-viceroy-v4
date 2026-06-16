"""Global inflation momentum, bond tilt (Ilmanen/Maloney/Ross 2014).

Implementation notes
====================

Foundational paper / book
-------------------------
Ilmanen, A. (2011). *Expected Returns: An Investor's Guide to
Harvesting Market Rewards*. Wiley. Chapter 12 covers cross-country
macro-sensitivity factors including inflation momentum.

Primary methodology
-------------------
Ilmanen, A., Maloney, T. & Ross, A. (2014). *Exploring
Macroeconomic Sensitivities: How Investments Respond to Different
Economic Environments*. Journal of Portfolio Management, 40(3),
87–99.
https://doi.org/10.3905/jpm.2014.40.3.087

IMR (2014) decompose asset returns by macroeconomic regime and
document that *rising inflation* environments are negative for bond
returns across countries. The paper derives a tradeable signal:
country-level inflation momentum predicts country-level bond
returns negatively. Countries with rising inflation see their bonds
underperform; countries with falling inflation see their bonds
outperform.

Why two papers
--------------
Ilmanen (2011) is the textbook *foundational* synthesis of macro
factor investing including inflation regimes. IMR (2014) is the
explicit *expected-return* paper that operationalises the inflation-
momentum-→-bond-return signal. The synthesis is the cross-country
ranking implemented here.

Differentiation from sibling strategies
---------------------------------------
* `breakeven_inflation_rotation` — single-country (US-only) rotation
  between TIPS and nominal Treasury based on breakeven *level*.
  Different signal type (level vs momentum), different country
  scope (US-only vs G10).
* `real_yield_momentum` — TIPS-derived bond momentum on US real
  yields. Single-country, momentum mechanic on bond price (not
  inflation).
* `g10_bond_carry` — cross-country bond carry on yield levels.
  Same country scope but different signal (carry, not inflation
  momentum).

Algorithm
---------
The strategy expects a multi-column ``prices`` DataFrame with
**paired columns**: each country provides one ``CPI_<country>``
column (a CPI-level proxy series) and one ``BOND_<country>`` column
(a country bond-price proxy). Country labels must match exactly:
e.g. ``CPI_US`` pairs with ``BOND_US``.

For each month-end:

1. **Inflation momentum** per country = trailing 12-month log
   change in the CPI level proxy.
2. **Cross-sectional rank** of inflation momentum across
   countries.
3. **Bond weights:** dollar-neutral on the BOND_ columns. Long
   the bond of the country with the *lowest* inflation momentum
   (falling inflation → bonds rally), short the bond of the
   country with the *highest* inflation momentum (rising
   inflation → bonds fall). Sign is therefore *negative*
   demeaned-rank.
4. CPI_ columns receive zero weight (informational only).
5. Forward-fill monthly weights to daily.

Edge cases
----------
* Before ``cpi_lookback_months`` months are available, weights are
  zero.
* Columns not following the ``CPI_/BOND_`` convention raise
  ``ValueError``.
* Mismatched pairing (e.g. ``CPI_US`` without a ``BOND_US``) raises
  ``ValueError``.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class GlobalInflationMomentum:
    """Cross-country inflation-momentum-driven bond tilt (Ilmanen/Maloney/Ross 2014).

    Parameters
    ----------
    cpi_lookback_months
        Trailing window (in months) for the inflation momentum
        signal (default ``12``).
    """

    name: str = "global_inflation_momentum"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.3905/jpm.2014.40.3.087"  # Ilmanen/Maloney/Ross 2014
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        cpi_lookback_months: int = 12,
    ) -> None:
        if cpi_lookback_months <= 0:
            raise ValueError(f"cpi_lookback_months must be positive, got {cpi_lookback_months}")
        self.cpi_lookback_months = cpi_lookback_months

    @staticmethod
    def _split_columns(columns: pd.Index) -> tuple[list[str], list[str], list[str]]:
        """Split column names into (cpi_cols, bond_cols, country_labels).

        Validates that every CPI_X has a matching BOND_X and vice versa.
        """
        cpi_cols: list[str] = []
        bond_cols: list[str] = []
        countries: list[str] = []
        cpi_labels: set[str] = set()
        bond_labels: set[str] = set()
        for col in columns:
            if not isinstance(col, str):
                raise ValueError(f"all column names must be strings, got {col!r}")
            if col.startswith("CPI_"):
                cpi_labels.add(col[len("CPI_") :])
            elif col.startswith("BOND_"):
                bond_labels.add(col[len("BOND_") :])
            else:
                raise ValueError(
                    f"columns must use 'CPI_<country>' or 'BOND_<country>' "
                    f"naming convention; got {col!r}"
                )
        unmatched_cpi = cpi_labels - bond_labels
        unmatched_bond = bond_labels - cpi_labels
        if unmatched_cpi:
            raise ValueError(
                f"CPI columns missing matching BOND counterpart: {sorted(unmatched_cpi)}"
            )
        if unmatched_bond:
            raise ValueError(
                f"BOND columns missing matching CPI counterpart: {sorted(unmatched_bond)}"
            )
        for label in sorted(cpi_labels):
            cpi_cols.append(f"CPI_{label}")
            bond_cols.append(f"BOND_{label}")
            countries.append(label)
        return cpi_cols, bond_cols, countries

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return inflation-momentum-driven bond weights aligned to ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain paired
            ``CPI_<country>`` and ``BOND_<country>`` columns; every CPI
            column must have a matching BOND column with the same
            country suffix.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        cpi_cols, bond_cols, countries = self._split_columns(prices.columns)
        if len(countries) < 2:
            raise ValueError(
                f"global inflation momentum requires >= 2 countries, got {len(countries)}"
            )

        cpi_panel = prices[cpi_cols]
        month_end_cpi = cpi_panel.resample("ME").last()
        inflation_momentum = np.log(month_end_cpi / month_end_cpi.shift(self.cpi_lookback_months))
        inflation_momentum.columns = countries

        ranks = inflation_momentum.rank(axis=1, method="average", ascending=True)
        n = float(len(countries))
        demeaned_rank = ranks - (n + 1.0) / 2.0
        normaliser = demeaned_rank.abs().sum(axis=1).replace(0.0, np.nan)
        country_weights = -demeaned_rank.div(normaliser, axis=0)

        country_weights.columns = bond_cols
        weights = pd.DataFrame(0.0, index=country_weights.index, columns=prices.columns)
        for col in bond_cols:
            weights[col] = country_weights[col]

        daily_weights = weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
