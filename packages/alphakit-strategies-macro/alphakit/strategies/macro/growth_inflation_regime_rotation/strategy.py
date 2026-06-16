"""Growth × inflation 4-cell macro regime rotation (Ilmanen-Maloney-Ross 2014).

Second strategy in the macro family's regime-state group
(Commits 8-12). Inherits the informational-column pattern and
publication-lag-handling discipline established by Commit 8's
``recession_probability_rotation``, extended to **two**
informational columns (CPI + GDP) and a **4-cell** regime
taxonomy.

Implementation notes
====================

Primary methodology (sole anchor)
---------------------------------
Ilmanen, A., Maloney, T. & Ross, A. (2014).
*Exploring Macroeconomic Sensitivities: How Investments Respond
to Different Economic Environments*. Journal of Portfolio
Management 40(3), 87-99.
https://doi.org/10.3905/jpm.2014.40.3.087

IMR (2014) is the canonical academic reference for the
**growth × inflation 4-cell macro-regime taxonomy**. The paper
decomposes the macroeconomic environment into four cells defined
by the cross of *growth* (rising vs falling relative to trend) and
*inflation* (rising vs falling relative to trend), and documents
the empirical asset-class sensitivities in each cell:

* **Rising growth + rising inflation** ("overheating"): equities
  and commodities outperform; bonds underperform.
* **Rising growth + falling inflation** ("goldilocks"): equities
  and bonds both outperform — the best regime for a balanced
  stock/bond book.
* **Falling growth + rising inflation** ("stagflation"): real
  assets (gold, commodities) outperform; equities and bonds both
  struggle.
* **Falling growth + falling inflation** ("deflation /
  recession"): long-duration bonds outperform; equities and
  commodities underperform.

IMR (2014) is cited as a **sole anchor** (single-paper citation
pattern, matching the Session 2F precedent of ``calendar_spread_atm``
citing Goyal/Saretto 2009). The 4-cell construction is a
well-established framework in the academic literature; IMR 2014
provides both the taxonomy and the empirical asset-class
sensitivities that drive the regime-conditional allocation. No
separate foundational paper is needed — IMR specifies both the
*what* (the 4-cell taxonomy) and the *how much* (the empirical
sensitivities).

Informational-column pattern (Session 2D §2D sub-section 3)
-----------------------------------------------------------
Inherits the pattern established by Commit 8. Two informational
columns this time:

* ``CPIAUCSL``: CPI All Urban Consumers (index level). The
  strategy computes year-over-year inflation internally
  (``pct_change(12 months) × 100``) — the input is the raw FRED
  index, not a pre-computed rate.
* ``GDPC1``: Real Gross Domestic Product (chained-dollar *level*,
  quarterly, always positive). The strategy computes year-over-
  year growth internally (``pct_change(12 months) × 100``) — same
  treatment as CPI.

Both informational columns carry **weight = 0.0** in the output;
only the four tradable ETF columns (SPY, TLT, GLD, DBC) carry
the regime-conditional allocation.

Why GDPC1 (level) instead of A191RL1Q225SBEA (growth rate)
---------------------------------------------------------
The Session 2G plan originally specified the GDP *growth rate*
series ``A191RL1Q225SBEA``. That series goes **negative** in
recessions (e.g. -3% annualised in 2020 Q2). The vectorbt bridge
treats every input column — including informational columns — as
a ``close`` price and **rejects non-positive prices**
(``order.price must be finite and greater than 0``), even for
zero-weight columns. A negative-valued informational column
therefore breaks the bridge.

The fix is to consume the GDP *level* series ``GDPC1`` (always
positive) and compute the YoY growth rate internally — exactly
parallel to the CPI index → YoY treatment. This sidesteps the
bridge-positivity constraint and makes the two informational
columns symmetric (both index/level → YoY internally). The
architectural constraint — *informational columns passed through
the vectorbt bridge must be positive-valued* — is documented in
``known_failures.md`` and applies to all FRED-driven regime
strategies (FEDFUNDS and CPIAUCSL are naturally positive; only
the GDP growth-rate series needed the level-vs-rate switch).

Publication-lag handling (two separate lags)
--------------------------------------------
Inherits the publication-lag discipline established by Commit 8,
extended to two separately-lagged columns:

* **CPI lag** (``cpi_lag_months``, default 1): CPI is released
  ~mid-month for the *prior* month, so a 1-month lag models the
  real-time availability.
* **GDP lag** (``gdp_lag_months``, default 1): GDP is released
  quarterly with an ~1-month lag after quarter-end, with
  subsequent revisions 2-3 months out. The default 1-month lag
  models the advance-estimate availability; users wanting to
  model the final-revision availability should set
  ``gdp_lag_months=3``. The quarterly cadence means the GDP
  *level* value forward-fills within each quarter when resampled
  to month-end; the YoY growth is then computed on the lagged
  forward-filled level.

Failure to apply the lag is the load-bearing foot-gun documented
in ``recession_probability_rotation/known_failures.md`` item 2.
This strategy applies the lag to **both** informational columns
separately — verified by
``tests/test_unit.py::test_publication_lag_applied_to_both_columns``.

4-cell regime classification
----------------------------
For each month-end, after applying the lags:

* **Growth state:** ``rising`` if the lagged GDP growth rate
  exceeds ``growth_threshold`` (default 2.0% annualised), else
  ``falling``.
* **Inflation state:** ``rising`` if the lagged CPI YoY exceeds
  ``inflation_threshold`` (default 2.5%), else ``falling``.

The cross produces the 4-cell regime, each mapped to a
configured asset allocation (defaults follow IMR 2014's documented
sensitivities — see ``regime_weights`` parameter).

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``recession_probability_rotation``**
  (Commit 8) — single informational column (recession probability),
  2-cell regime. This strategy uses two informational columns
  (CPI + GDP) and a finer 4-cell taxonomy. Expected ρ ≈
  **0.40–0.60** (overlapping macro-state common factor; the
  falling-growth cells of this strategy correlate with the
  high-recession-probability regime of Commit 8).
* **Phase 2 Session 2G ``yield_curve_regime_allocation``**
  (Commit 10) — yield-curve slope signal, 3-cell. Expected ρ ≈
  0.40–0.60.
* **Phase 2 Session 2G ``fed_policy_tilt``** (Commit 11) — fed
  funds rate signal, 2-cell. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G ``inflation_regime_allocation``** (Commit 12)
  — CPI-only 3-cell. This strategy's inflation dimension overlaps
  with Commit 12's signal. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30–0.50.

Cluster expectations are documented in ``known_failures.md``.

Universe (4 tradable ETFs + 2 informational FRED series)
--------------------------------------------------------
* **Tradable:**
  - ``SPY``: US large-cap equity
  - ``TLT``: 20+ year Treasuries
  - ``GLD``: Physical gold ETF
  - ``DBC``: Broad commodities (Invesco DB)
* **Informational (FRED, zero-weight in output):**
  - ``CPIAUCSL``: CPI index → YoY inflation computed internally
  - ``GDPC1``: Real GDP level → YoY growth computed internally

Published rules (IMR 2014, 4-asset implementation)
--------------------------------------------------
For each month-end *t*:

1. Read CPI index column, apply ``cpi_lag_months`` shift, compute
   YoY inflation = ``pct_change(12) × 100`` on the lagged series.
2. Read GDP level column, apply ``gdp_lag_months`` shift, compute
   YoY growth = ``pct_change(12) × 100`` on the lagged series.
3. Classify the growth state (rising/falling vs
   ``growth_threshold``) and the inflation state (rising/falling
   vs ``inflation_threshold``).
4. Map the (growth, inflation) cell to its configured allocation:

   | Growth | Inflation | Default allocation (SPY/TLT/GLD/DBC) |
   |---|---|---|
   | rising | rising  | (0.40, 0.00, 0.20, 0.40) overheating |
   | rising | falling | (0.60, 0.40, 0.00, 0.00) goldilocks |
   | falling| rising  | (0.00, 0.20, 0.40, 0.40) stagflation |
   | falling| falling | (0.15, 0.70, 0.15, 0.00) deflation |

5. Emit weights at month-end; forward-fill daily until the next
   rebalance. Both informational columns carry ``weight = 0.0``.

Sign convention
---------------
Long-only. Each regime's weights sum to 1.0 across the 4 tradable
ETFs; the two informational columns always carry 0.0. Strategy
emits zero weights everywhere during warm-up: both CPI YoY and
GDP YoY need 12 months of history plus their respective lags, so
warm-up is ``max(cpi_lag_months, gdp_lag_months) + 12`` months.

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md``.

Edge cases
----------
* Warm-up: both CPI YoY and GDP YoY need 12 months of history
  plus their respective lags; before that, weights are zero
  everywhere.
* Missing required columns: ``KeyError`` listing the missing
  symbols.
* Non-positive ETF prices: ``ValueError``. Informational columns
  (CPI index, GDP level) are both positive by construction; the
  strategy does not positivity-check them, but the vectorbt bridge
  requires them to be positive (see "Why GDPC1" above and
  ``known_failures.md``).
* NaN in either informational column after lag: rows emit zero
  weights (treated as warm-up).
* Constructor validates each of the 4 regime-weight tuples sums
  to 1.0 with non-negative entries.
"""

from __future__ import annotations

from typing import ClassVar, cast

import pandas as pd

# Regime-weight tuple type: (SPY, TLT, GLD, DBC).
_RegimeWeights = tuple[float, float, float, float]


class GrowthInflationRegimeRotation:
    """Growth × inflation 4-cell macro regime rotation (IMR 2014).

    Parameters
    ----------
    equity_symbol
        Symbol for the equity leg. Defaults to ``"SPY"``.
    bonds_symbol
        Symbol for the long-bonds leg. Defaults to ``"TLT"``.
    gold_symbol
        Symbol for the gold leg. Defaults to ``"GLD"``.
    commodities_symbol
        Symbol for the commodities leg. Defaults to ``"DBC"``.
    cpi_column
        FRED CPI index column name. Defaults to ``"CPIAUCSL"``.
        The strategy computes year-over-year inflation internally.
    gdp_column
        FRED GDP *level* column name. Defaults to ``"GDPC1"``
        (real GDP, chained dollars, always positive). The strategy
        computes YoY growth internally — see "Why GDPC1" in the
        module docstring for why the level series is used instead
        of the (negative-capable) growth-rate series.
    growth_threshold
        YoY real GDP growth (%) above which growth is classified
        "rising". Defaults to ``2.0``.
    inflation_threshold
        CPI YoY (%) above which inflation is classified "rising".
        Defaults to ``2.5``.
    cpi_lag_months
        Publication-lag shift for the CPI column. Defaults to ``1``.
    gdp_lag_months
        Publication-lag shift for the GDP column. Defaults to ``1``
        (advance estimate). Set to ``3`` for final-revision
        availability.
    regime_weights
        Mapping from regime cell to (SPY, TLT, GLD, DBC) weights.
        Keys must be exactly
        ``{"rising_rising", "rising_falling", "falling_rising",
        "falling_falling"}`` (growth_inflation). Each tuple must
        sum to 1.0 with non-negative entries. Defaults follow IMR
        2014's documented asset-class sensitivities.
    """

    name: str = "growth_inflation_regime_rotation"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold", "commodities")
    paper_doi: str = "10.3905/jpm.2014.40.3.087"  # Ilmanen-Maloney-Ross 2014
    rebalance_frequency: str = "monthly"

    _DEFAULT_REGIME_WEIGHTS: ClassVar[dict[str, _RegimeWeights]] = {
        # (SPY, TLT, GLD, DBC)
        "rising_rising": (0.40, 0.00, 0.20, 0.40),  # overheating
        "rising_falling": (0.60, 0.40, 0.00, 0.00),  # goldilocks
        "falling_rising": (0.00, 0.20, 0.40, 0.40),  # stagflation
        "falling_falling": (0.15, 0.70, 0.15, 0.00),  # deflation / recession
    }

    _REGIME_KEYS: ClassVar[frozenset[str]] = frozenset(
        {"rising_rising", "rising_falling", "falling_rising", "falling_falling"}
    )

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        commodities_symbol: str = "DBC",
        cpi_column: str = "CPIAUCSL",
        gdp_column: str = "GDPC1",
        growth_threshold: float = 2.0,
        inflation_threshold: float = 2.5,
        cpi_lag_months: int = 1,
        gdp_lag_months: int = 1,
        regime_weights: dict[str, _RegimeWeights] | None = None,
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("commodities_symbol", commodities_symbol),
            ("cpi_column", cpi_column),
            ("gdp_column", gdp_column),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")

        tradable = (equity_symbol, bonds_symbol, gold_symbol, commodities_symbol)
        if len(set(tradable)) != 4:
            raise ValueError(
                f"equity / bonds / gold / commodities symbols must be distinct; got {tradable}"
            )
        informational = (cpi_column, gdp_column)
        if len(set(informational)) != 2:
            raise ValueError(f"cpi_column and gdp_column must be distinct; got {informational}")
        overlap = set(tradable) & set(informational)
        if overlap:
            raise ValueError(
                f"informational columns must not overlap with tradable symbols; "
                f"overlap = {sorted(overlap)}"
            )

        if cpi_lag_months < 0:
            raise ValueError(f"cpi_lag_months must be non-negative; got {cpi_lag_months}")
        if gdp_lag_months < 0:
            raise ValueError(f"gdp_lag_months must be non-negative; got {gdp_lag_months}")

        weights = regime_weights if regime_weights is not None else self._DEFAULT_REGIME_WEIGHTS
        if set(weights.keys()) != self._REGIME_KEYS:
            raise ValueError(
                f"regime_weights keys must be exactly {sorted(self._REGIME_KEYS)}; "
                f"got {sorted(weights.keys())}"
            )
        for key, w in weights.items():
            if len(w) != 4:
                raise ValueError(
                    f"regime_weights[{key!r}] must have exactly 4 entries "
                    f"(SPY, TLT, GLD, DBC); got {w}"
                )
            if any(x < 0 for x in w):
                raise ValueError(f"regime_weights[{key!r}] entries must be non-negative; got {w}")
            if abs(sum(w) - 1.0) > 1e-9:
                raise ValueError(
                    f"regime_weights[{key!r}] must sum to 1.0 within 1e-9 tolerance; "
                    f"got sum={sum(w)}"
                )

        self.equity_symbol = equity_symbol
        self.bonds_symbol = bonds_symbol
        self.gold_symbol = gold_symbol
        self.commodities_symbol = commodities_symbol
        self.cpi_column = cpi_column
        self.gdp_column = gdp_column
        self.growth_threshold = growth_threshold
        self.inflation_threshold = inflation_threshold
        self.cpi_lag_months = cpi_lag_months
        self.gdp_lag_months = gdp_lag_months
        self.regime_weights = dict(weights)

    @property
    def tradable_symbols(self) -> tuple[str, str, str, str]:
        """The four tradable ETF columns (equity, bonds, gold, commodities)."""
        return (
            self.equity_symbol,
            self.bonds_symbol,
            self.gold_symbol,
            self.commodities_symbol,
        )

    @property
    def required_symbols(self) -> tuple[str, ...]:
        """The six required columns: 4 tradable ETFs + 2 informational FRED series."""
        return (*self.tradable_symbols, self.cpi_column, self.gdp_column)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return 4-cell regime-conditional weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            four tradable ETF columns AND the two informational FRED
            columns (default: SPY / TLT / GLD / DBC / CPIAUCSL /
            GDPC1). ETF columns must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. The four tradable columns carry the
            regime-conditional allocation; the two informational
            columns carry **weight = 0.0** at every bar.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for growth_inflation_regime_rotation: "
                f"{missing}. Required: {list(self.required_symbols)}; "
                f"got: {list(prices.columns)}"
            )

        all_cols = prices.loc[:, list(self.required_symbols)]

        if all_cols.empty:
            return pd.DataFrame(
                index=prices.index,
                columns=list(self.required_symbols),
                dtype=float,
            )

        if not isinstance(all_cols.index, pd.DatetimeIndex):
            raise TypeError(
                f"prices must have a DatetimeIndex, got {type(all_cols.index).__name__}"
            )

        tradable_cols = all_cols.loc[:, list(self.tradable_symbols)]
        if (tradable_cols <= 0).any().any():
            raise ValueError("prices must be strictly positive for all four tradable ETF legs")

        # Resample to month-end.
        month_end_all = all_cols.resample("ME").last()

        # Inflation: lag the CPI index, then compute YoY on the lagged series.
        cpi_lagged = month_end_all[self.cpi_column].shift(self.cpi_lag_months)
        cpi_yoy = cpi_lagged.pct_change(12) * 100.0

        # Growth: lag the GDP level, then compute YoY on the lagged series.
        gdp_lagged = month_end_all[self.gdp_column].shift(self.gdp_lag_months)
        gdp_yoy = gdp_lagged.pct_change(12) * 100.0

        # 4-cell regime classification.
        growth_rising = gdp_yoy > self.growth_threshold
        inflation_rising = cpi_yoy > self.inflation_threshold
        valid = gdp_yoy.notna() & cpi_yoy.notna()

        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_all.index,
            columns=list(self.required_symbols),
        )

        cell_masks = {
            "rising_rising": growth_rising & inflation_rising & valid,
            "rising_falling": growth_rising & ~inflation_rising & valid,
            "falling_rising": ~growth_rising & inflation_rising & valid,
            "falling_falling": ~growth_rising & ~inflation_rising & valid,
        }
        for cell, mask in cell_masks.items():
            if not mask.any():
                continue
            w = self.regime_weights[cell]
            monthly_weights.loc[mask, self.equity_symbol] = w[0]
            monthly_weights.loc[mask, self.bonds_symbol] = w[1]
            monthly_weights.loc[mask, self.gold_symbol] = w[2]
            monthly_weights.loc[mask, self.commodities_symbol] = w[3]

        daily_weights = monthly_weights.reindex(all_cols.index).ffill().fillna(0.0)
        # Defensive: ensure both informational columns are exactly 0.0.
        daily_weights[self.cpi_column] = 0.0
        daily_weights[self.gdp_column] = 0.0
        return cast(pd.DataFrame, daily_weights)
