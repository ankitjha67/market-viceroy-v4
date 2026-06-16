"""Inflation-regime 3-cell allocation (Neville et al. 2021 / Erb-Harvey 2006).

Fifth and final strategy in the macro family's regime-state group
(Commits 8-12). Inherits the informational-column + publication-lag
pattern; classifies each month into low / moderate / high inflation
based on the CPI YoY rate computed internally from the CPIAUCSL index.

Implementation notes
====================

Foundational paper
------------------
Neville, H., Draaisma, T., Funnell, B., Harvey, C. R. & Van Hemert, O.
(2021). *The Best Strategies for Inflationary Times*. Journal of
Portfolio Management Quantitative Special Issue.
DOI: https://doi.org/10.3905/jpm.2021.1.290

Neville et al. (2021) analyse multi-asset performance across the full
range of inflationary environments using a 95-year dataset spanning 4
developed markets (US, UK, Japan, Germany). The foundational result:

* **Low inflation** (disinflation, <2% YoY): equities and nominal
  bonds deliver the highest risk-adjusted returns. Gold is neutral.
  Commodities underperform (real rates are high or rising).
* **Moderate inflation** (2-4% YoY): equities retain positive real
  returns. Nominal bonds underperform in real terms. Real assets
  (gold, commodities) begin to outperform.
* **High inflation** (>4% YoY): equities lose in real terms. Nominal
  bonds destroy real value. Gold and commodities substantially
  outperform in real terms — commodities most dramatically.

The 3-cell taxonomy (low / moderate / high) maps directly to the
paper's identified inflation regime breakpoints (their headline result
is the discontinuity in asset returns above the ~4% CPI threshold).

Primary methodology
-------------------
Erb, C. B. & Harvey, C. R. (2006). *The Strategic and Tactical Value
of Commodity Futures*. Financial Analysts Journal 62(2), 69-97.
DOI: https://doi.org/10.2469/faj.v62.n2.4080

Erb & Harvey (2006) document that commodity futures (as a proxy for
physical commodity exposure) provide both strategic diversification
*and* tactical inflation-hedging benefits. Their core tactical finding:
commodity returns are positively related to the inflation level — the
higher the inflation, the stronger the commodity outperformance. The
paper provides the empirical basis for allocating to DBC (commodities)
in the high-inflation cell.

Why two papers
--------------
Neville et al. (2021) is the *foundational* study of multi-asset
inflation-regime performance — the 95-year, 4-country dataset confirms
the 3-cell taxonomy and the equity/bond/gold/commodity ranking within
each cell. Erb & Harvey (2006) is the *primary methodology* for the
commodity allocation decision in the high-inflation cell, with
the specific tactical timing argument (commodity return correlates
with inflation level, not just direction) that justifies DBC in the
3-cell rotation.

Informational-column pattern + internal YoY computation
--------------------------------------------------------
Inherits the informational-column pattern (Session 2D §2D sub-section
3). The strategy reads ONE FRED informational column:

* ``CPIAUCSL``: CPI All Urban Consumers, All Items (seasonally
  adjusted). This is an **index** series (level), not a rate. It
  is always strictly positive (base value ~1.0, current ~300+).

The CPI YoY rate is computed **internally** after the publication lag
is applied:

  ``cpi_yoy = cpiaucsl_lagged.pct_change(12) * 100``

Computing YoY first and then applying the lag would mix real-time and
revised vintage data — the lag must be applied first (see
``known_failures.md``).

The bridge sees only the raw CPI index (strictly positive); the
(possibly negative in rare deflation) YoY rate is a transient
local variable that never reaches the bridge.

3-cell regime classification
-----------------------------
For each month-end *t*, after the lag and YoY computation:

* **Low inflation** (``cpi_yoy < low_threshold``, default 2.0%):
  disinflationary / low-inflation environment → equity-heavy.
* **Moderate inflation** (``low_threshold <= cpi_yoy < high_threshold``,
  default 2.0-4.0%): balanced with real-asset tilt.
* **High inflation** (``cpi_yoy >= high_threshold``, default 4.0%):
  commodity and gold-heavy, minimal equity/bonds.

| Regime | Default (SPY/TLT/GLD/DBC) |
|---|---|
| low       | (0.60, 0.30, 0.05, 0.05) |
| moderate  | (0.40, 0.20, 0.20, 0.20) |
| high      | (0.05, 0.05, 0.45, 0.45) |

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``growth_inflation_regime_rotation``**
  (Commit 9) — overlapping CPI dimension. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``recession_probability_rotation``**
  (Commit 8) — overlapping macro factor. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G ``yield_curve_regime_allocation``**
  (Commit 10) — yield-curve slope. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G ``fed_policy_tilt``** (Commit 11) —
  Fed funds rate signal. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) —
  static allocation. Expected ρ ≈ 0.40-0.60 (see below).

Permanent-portfolio cluster note
---------------------------------
The static permanent_portfolio holds 25% SPY / 25% TLT / 25% GLD /
25% DBC. This inflation_regime_allocation strategy holds 3 different
allocations across the 4-asset universe. In moderate inflation (SPY
40% / TLT 20% / GLD 20% / DBC 20%) the weights are somewhat
different from PP. In high inflation (SPY 5% / TLT 5% / GLD 45% /
DBC 45%), the strategy is GLD+DBC heavy — very different from PP.
The expected ρ ≈ 0.40-0.60 arises because both strategies hold GLD
and DBC and both hold some SPY and TLT — correlation from the common
assets, not the common weights.

Universe (4 tradable ETFs + 1 informational FRED series)
---------------------------------------------------------
* **Tradable:**
  - ``SPY``: US large-cap equity (low-inflation / pro-cyclical leg)
  - ``TLT``: 20+ year Treasuries (low-inflation / bond leg)
  - ``GLD``: Physical gold ETF (high-inflation hedge)
  - ``DBC``: DB Commodity Index ETF (high-inflation commodity leg)
* **Informational (FRED, zero-weight in output, strictly positive):**
  - ``CPIAUCSL``: CPI All Urban Consumers SA index (level, always > 0)

Published rules (Neville et al. 2021 / Erb-Harvey 2006, 4-asset)
-----------------------------------------------------------------
For each month-end *t*:

1. Read CPIAUCSL, apply ``cpi_lag_months`` shift.
2. Compute ``cpi_yoy = cpiaucsl_lagged.pct_change(12) * 100``.
3. Classify:
   * ``cpi_yoy < low_threshold`` → low.
   * ``low_threshold <= cpi_yoy < high_threshold`` → moderate.
   * ``cpi_yoy >= high_threshold`` → high.
4. Map the regime to its configured allocation.
5. Emit weights at month-end; forward-fill daily. CPIAUCSL carries
   ``weight = 0.0``.

Sign convention
---------------
Long-only. Each regime's weights sum to 1.0 across the 4 tradable
ETFs; the informational column always carries 0.0. Strategy emits
zero weights everywhere during warm-up (before
``cpi_lag_months + 12`` months of CPIAUCSL history are available for
the YoY computation).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention".

Edge cases
----------
* Warm-up: requires ``cpi_lag_months + 12`` months of CPIAUCSL
  history for the pct_change(12) YoY computation; before that,
  weights are zero everywhere.
* Missing required columns: ``KeyError`` listing the missing symbols.
* Non-positive ETF prices: ``ValueError``.
* NaN in CPIAUCSL after lag: rows emit zero weights.
* Constructor validates each regime-weight tuple sums to 1.0 with
  non-negative entries, and that ``low_threshold < high_threshold``.
"""

from __future__ import annotations

from typing import ClassVar, cast

import pandas as pd

# Regime-weight tuple type: (SPY, TLT, GLD, DBC).
_RegimeWeights = tuple[float, float, float, float]


class InflationRegimeAllocation:
    """Inflation-regime 3-cell allocation (Neville et al. 2021 / Erb-Harvey 2006).

    Parameters
    ----------
    equity_symbol
        US equity ETF symbol. Defaults to ``"SPY"``.
    bonds_symbol
        Long-duration Treasury ETF symbol. Defaults to ``"TLT"``.
    gold_symbol
        Gold ETF symbol. Defaults to ``"GLD"``.
    commodities_symbol
        Broad commodity ETF symbol. Defaults to ``"DBC"``.
    cpi_column
        FRED CPI index column (level series, always positive). Defaults
        to ``"CPIAUCSL"``.
    low_threshold
        CPI YoY (%) below which the regime is "low inflation". Defaults
        to ``2.0``.
    high_threshold
        CPI YoY (%) at or above which the regime is "high inflation".
        Defaults to ``4.0``. Must be > ``low_threshold``.
    cpi_lag_months
        Publication-lag shift applied to CPIAUCSL before computing YoY.
        Defaults to ``1``.
    regime_weights
        Mapping from regime to (SPY, TLT, GLD, DBC) weights. Keys must
        be exactly ``{"low", "moderate", "high"}``. Each tuple must sum
        to 1.0 with non-negative entries.
    """

    name: str = "inflation_regime_allocation"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold", "commodities")
    paper_doi: str = "10.2469/faj.v62.n2.4080"  # Erb-Harvey 2006 primary
    rebalance_frequency: str = "monthly"

    _DEFAULT_REGIME_WEIGHTS: ClassVar[dict[str, _RegimeWeights]] = {
        # (SPY, TLT, GLD, DBC) — Neville et al. 2021 inflation-regime mapping.
        "low": (0.60, 0.30, 0.05, 0.05),  # equity+bonds in low inflation
        "moderate": (0.40, 0.20, 0.20, 0.20),  # balanced with real-asset tilt
        "high": (0.05, 0.05, 0.45, 0.45),  # gold+commodities in high inflation
    }

    _REGIME_KEYS: ClassVar[frozenset[str]] = frozenset({"low", "moderate", "high"})

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        commodities_symbol: str = "DBC",
        cpi_column: str = "CPIAUCSL",
        low_threshold: float = 2.0,
        high_threshold: float = 4.0,
        cpi_lag_months: int = 1,
        regime_weights: dict[str, _RegimeWeights] | None = None,
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("commodities_symbol", commodities_symbol),
            ("cpi_column", cpi_column),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")

        tradable = (equity_symbol, bonds_symbol, gold_symbol, commodities_symbol)
        if len(set(tradable)) != 4:
            raise ValueError(
                f"equity / bonds / gold / commodities symbols must be distinct; got {tradable}"
            )
        if cpi_column in set(tradable):
            raise ValueError(
                f"cpi_column ({cpi_column!r}) must not overlap with tradable symbols {tradable}"
            )

        if low_threshold >= high_threshold:
            raise ValueError(
                f"low_threshold ({low_threshold}) must be < high_threshold ({high_threshold})"
            )
        if cpi_lag_months < 0:
            raise ValueError(f"cpi_lag_months must be non-negative; got {cpi_lag_months}")

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
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.cpi_lag_months = cpi_lag_months
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
        """The five required columns: 4 tradable ETFs + 1 informational CPIAUCSL."""
        return (*self.tradable_symbols, self.cpi_column)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return 3-cell inflation-regime weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            four tradable ETF columns AND the CPIAUCSL informational
            column. ETF columns must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. The four tradable columns carry the
            regime-conditional allocation; CPIAUCSL carries
            **weight = 0.0** at every bar.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for inflation_regime_allocation: "
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

        # Apply publication lag to CPIAUCSL FIRST, then compute YoY.
        # Critical: lag before YoY (not after) to avoid lookahead bias.
        cpi_lagged = month_end_all[self.cpi_column].shift(self.cpi_lag_months)
        cpi_yoy = cpi_lagged.pct_change(12) * 100  # YoY percent change

        low = cpi_yoy < self.low_threshold
        moderate = (cpi_yoy >= self.low_threshold) & (cpi_yoy < self.high_threshold)
        high = cpi_yoy >= self.high_threshold
        valid = cpi_yoy.notna()

        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_all.index,
            columns=list(self.required_symbols),
        )

        regime_masks = {
            "low": low & valid,
            "moderate": moderate & valid,
            "high": high & valid,
        }
        for regime, mask in regime_masks.items():
            if not mask.any():
                continue
            w = self.regime_weights[regime]
            monthly_weights.loc[mask, self.equity_symbol] = w[0]
            monthly_weights.loc[mask, self.bonds_symbol] = w[1]
            monthly_weights.loc[mask, self.gold_symbol] = w[2]
            monthly_weights.loc[mask, self.commodities_symbol] = w[3]

        daily_weights = monthly_weights.reindex(all_cols.index).ffill().fillna(0.0)
        # Defensive: ensure the CPI informational column is exactly 0.0.
        daily_weights[self.cpi_column] = 0.0
        return cast(pd.DataFrame, daily_weights)
