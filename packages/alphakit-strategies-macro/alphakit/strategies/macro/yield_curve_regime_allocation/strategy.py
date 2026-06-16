"""Yield-curve-slope 3-cell regime allocation (Estrella-Hardouvelis 1991 / Ang-Piazzesi-Wei 2006).

Third strategy in the macro family's regime-state group
(Commits 8-12). Inherits the informational-column + publication-
lag pattern; computes the yield-curve slope *internally* from two
raw yield-level columns so the (possibly negative) spread never
passes through the vectorbt bridge.

Implementation notes
====================

Foundational paper
------------------
Estrella, A. & Hardouvelis, G. A. (1991).
*The Term Structure as a Predictor of Real Economic Activity*.
Journal of Finance 46(2), 555-576.
https://doi.org/10.1111/j.1540-6261.1991.tb03775.x

Estrella & Hardouvelis (1991) is the seminal reference for the
**yield-curve slope as a leading indicator of economic activity**.
The paper documents that a steeper Treasury yield curve forecasts
stronger real GDP growth, consumption, and investment 1-4 quarters
ahead, and that a *flat or inverted* curve forecasts recessions.
The original spread is the 10-year minus 3-month Treasury yield;
this implementation uses the 10-year minus 2-year slope (see "Why
DGS2" below) which is ~0.9-correlated with the 10y-3m measure and
carries the same economic content.

Primary methodology
-------------------
Ang, A., Piazzesi, M. & Wei, M. (2006).
*What Does the Yield Curve Tell Us about GDP Growth?*. Journal of
Econometrics 131(1-2), 359-403.
https://doi.org/10.1016/j.jfineco.2005.05.005

Ang, Piazzesi & Wei (2006) provide the modern term-structure
modelling framework for the yield-curve-to-growth relationship.
They show that the *slope* of the term structure (the long-minus-
short spread) is the single most informative yield-curve summary
statistic for forecasting GDP growth, dominating the level and
curvature factors. The 3-cell regime taxonomy (steep / flat /
inverted) is the discrete implementation of the APW slope signal.

Why two papers
--------------
Estrella-Hardouvelis (1991) is the *foundational* result — the
yield-curve slope predicts real activity and recessions. Ang-
Piazzesi-Wei (2006) is the *modern methodology* — the slope is the
dominant yield-curve summary statistic for GDP forecasting. Both
are cited so the audit trail covers the foundational finding (EH
1991) and the modern term-structure framework (APW 2006).

Informational-column pattern + internal spread computation
----------------------------------------------------------
Inherits the informational-column pattern (Session 2D §2D
sub-section 3). This strategy reads **two** raw yield-level
informational columns and computes the slope internally:

* ``DGS10``: 10-year Treasury constant-maturity yield (%).
* ``DGS2``: 2-year Treasury constant-maturity yield (%).

The yield-curve slope is ``slope = DGS10 - DGS2``, computed
*inside* ``generate_signals``. The slope **goes negative on
inversion** — which is exactly the recession-warning regime the
strategy cares about — so the slope itself can never be an
informational column passed through the bridge (the vectorbt
bridge rejects non-positive ``close`` prices; see
``docs/phase-2-amendments.md`` "Session 2G: informational columns
must be positive-valued"). The two raw yield *levels* are
strictly positive, so they pass through cleanly; the (possibly
negative) slope is derived internally and never reaches the
bridge.

Both informational columns carry **weight = 0.0** in the output;
only the three tradable ETF columns (SPY, TLT, GLD) carry the
regime-conditional allocation.

Why DGS2 (2-year) instead of DGS3MO (3-month)
---------------------------------------------
Estrella-Hardouvelis (1991) originally uses the 10-year minus
3-month spread, and the Cleveland Fed recession-probability model
(consumed by Commit 8's ``recession_probability_rotation``) uses
the same 10y-3m spread. The natural short leg would therefore be
``DGS3MO``. However, ``DGS3MO`` prints exactly ``0.0`` on several
zero-interest-rate-policy days (2011, 2020-2021), which would trip
the bridge's ``order.price > 0`` assertion even though the column
is informational.

``DGS2`` (2-year) is used instead: the 2-year yield always carries
a term premium and stays strictly positive even at the ZIRP lower
bound. The 2s10s slope is ~0.9-correlated with the 10y-3m measure
and carries the same economic content, so the cross-strategy
cluster prediction with ``recession_probability_rotation``
(ρ ≈ 0.50-0.70 — both signals are yield-curve-slope-driven) holds.

Publication-lag handling
------------------------
Inherits the publication-lag discipline. The yield columns are
lagged by ``yield_lag_months`` (default 1) before the slope is
computed. Treasury yields are published daily with negligible
lag, but the 1-month lag is applied for parity with the other
Session 2G regime-state strategies (and to model the conservative
month-end-rebalance information set).

3-cell regime classification
----------------------------
For each month-end, after the lag:

* **Steep** (``slope >= steep_threshold``, default 1.0% / 100 bps):
  strongly upward-sloping curve forecasts strong growth → risk-on
  equity allocation.
* **Flat** (``flat_threshold <= slope < steep_threshold``, default
  flat_threshold 0.0): neutral curve → balanced allocation.
* **Inverted** (``slope < flat_threshold``, default 0.0): inverted
  curve forecasts recession → defensive allocation.

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``recession_probability_rotation``**
  (Commit 8) — closest cluster sibling. The Cleveland Fed
  recession-probability model uses the yield-curve slope (10y-3m)
  as its primary input, so this strategy's slope signal and
  Commit 8's recession-probability signal are driven by
  overlapping information. Expected ρ ≈ **0.50-0.70** — the
  highest within the regime-state group.
* **Phase 2 Session 2G ``growth_inflation_regime_rotation``**
  (Commit 9) — CPI + GDP signal, 4-cell. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``fed_policy_tilt``** (Commit 11) — fed
  funds rate signal. The short end of the curve (2-year) is
  closely tied to fed-funds expectations, so there is some signal
  overlap. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``inflation_regime_allocation``** (Commit 12)
  — CPI YoY signal. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) —
  static allocation. Expected ρ ≈ 0.30-0.50.

Cluster expectations are documented in ``known_failures.md``.

Universe (3 tradable ETFs + 2 informational FRED yield series)
--------------------------------------------------------------
* **Tradable:**
  - ``SPY``: US large-cap equity (steep-curve / pro-cyclical leg)
  - ``TLT``: 20+ year Treasuries (inverted-curve / defensive leg)
  - ``GLD``: Physical gold ETF (defensive inflation hedge)
* **Informational (FRED, zero-weight in output, strictly positive):**
  - ``DGS10``: 10-year Treasury yield (%)
  - ``DGS2``: 2-year Treasury yield (%)

Published rules (EH 1991 / APW 2006, 3-asset implementation)
------------------------------------------------------------
For each month-end *t*:

1. Read the two yield columns, apply ``yield_lag_months`` shift.
2. Compute the slope ``= DGS10 - DGS2`` on the lagged series.
3. Classify the regime:
   * ``slope >= steep_threshold`` → steep.
   * ``flat_threshold <= slope < steep_threshold`` → flat.
   * ``slope < flat_threshold`` → inverted.
4. Map the regime to its configured allocation:

   | Regime | Default (SPY/TLT/GLD) |
   |---|---|
   | steep | (0.70, 0.30, 0.00) |
   | flat | (0.40, 0.40, 0.20) |
   | inverted | (0.00, 0.60, 0.40) |

5. Emit weights at month-end; forward-fill daily. Both yield
   columns carry ``weight = 0.0``.

Sign convention
---------------
Long-only. Each regime's weights sum to 1.0 across the 3 tradable
ETFs; both informational columns always carry 0.0. Strategy emits
zero weights everywhere during warm-up (before
``yield_lag_months + 1`` months of yield history are available).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention".

Edge cases
----------
* Warm-up: requires ``yield_lag_months + 1`` months of yield
  history; before that, weights are zero everywhere.
* Missing required columns: ``KeyError`` listing the missing
  symbols.
* Non-positive ETF prices: ``ValueError``. Yield columns are not
  positivity-checked by the strategy, but the bridge requires
  them positive (DGS10 and DGS2 are strictly positive by
  construction — see "Why DGS2").
* NaN in either yield column after lag: rows emit zero weights
  (treated as warm-up).
* Constructor validates each regime-weight tuple sums to 1.0 with
  non-negative entries, and that ``flat_threshold <
  steep_threshold``.
"""

from __future__ import annotations

from typing import ClassVar, cast

import pandas as pd

# Regime-weight tuple type: (SPY, TLT, GLD).
_RegimeWeights = tuple[float, float, float]


class YieldCurveRegimeAllocation:
    """Yield-curve-slope 3-cell regime allocation (EH 1991 / APW 2006).

    Parameters
    ----------
    equity_symbol
        Symbol for the pro-cyclical equity leg. Defaults to ``"SPY"``.
    bonds_symbol
        Symbol for the defensive long-duration bonds leg. Defaults
        to ``"TLT"``.
    gold_symbol
        Symbol for the defensive inflation-hedge leg. Defaults to
        ``"GLD"``.
    long_yield_column
        FRED long-end yield column. Defaults to ``"DGS10"``
        (10-year Treasury constant-maturity yield).
    short_yield_column
        FRED short-end yield column. Defaults to ``"DGS2"``
        (2-year Treasury) — chosen over DGS3MO for bridge-
        positivity robustness (see module docstring "Why DGS2").
    steep_threshold
        Slope (%) at or above which the curve is classified
        "steep". Defaults to ``1.0`` (100 bps).
    flat_threshold
        Slope (%) at or above which (but below ``steep_threshold``)
        the curve is classified "flat"; below this it is
        "inverted". Defaults to ``0.0``. Must be < ``steep_threshold``.
    yield_lag_months
        Publication-lag shift applied to both yield columns.
        Defaults to ``1``.
    regime_weights
        Mapping from regime to (SPY, TLT, GLD) weights. Keys must
        be exactly ``{"steep", "flat", "inverted"}``. Each tuple
        must sum to 1.0 with non-negative entries.
    """

    name: str = "yield_curve_regime_allocation"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold")
    paper_doi: str = "10.1016/j.jfineco.2005.05.005"  # Ang-Piazzesi-Wei 2006
    rebalance_frequency: str = "monthly"

    _DEFAULT_REGIME_WEIGHTS: ClassVar[dict[str, _RegimeWeights]] = {
        # (SPY, TLT, GLD)
        "steep": (0.70, 0.30, 0.00),
        "flat": (0.40, 0.40, 0.20),
        "inverted": (0.00, 0.60, 0.40),
    }

    _REGIME_KEYS: ClassVar[frozenset[str]] = frozenset({"steep", "flat", "inverted"})

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        long_yield_column: str = "DGS10",
        short_yield_column: str = "DGS2",
        steep_threshold: float = 1.0,
        flat_threshold: float = 0.0,
        yield_lag_months: int = 1,
        regime_weights: dict[str, _RegimeWeights] | None = None,
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("long_yield_column", long_yield_column),
            ("short_yield_column", short_yield_column),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")

        tradable = (equity_symbol, bonds_symbol, gold_symbol)
        if len(set(tradable)) != 3:
            raise ValueError(f"equity / bonds / gold symbols must be distinct; got {tradable}")
        informational = (long_yield_column, short_yield_column)
        if len(set(informational)) != 2:
            raise ValueError(
                f"long_yield_column and short_yield_column must be distinct; got {informational}"
            )
        overlap = set(tradable) & set(informational)
        if overlap:
            raise ValueError(
                f"informational columns must not overlap with tradable symbols; "
                f"overlap = {sorted(overlap)}"
            )

        if flat_threshold >= steep_threshold:
            raise ValueError(
                f"flat_threshold ({flat_threshold}) must be < steep_threshold ({steep_threshold})"
            )
        if yield_lag_months < 0:
            raise ValueError(f"yield_lag_months must be non-negative; got {yield_lag_months}")

        weights = regime_weights if regime_weights is not None else self._DEFAULT_REGIME_WEIGHTS
        if set(weights.keys()) != self._REGIME_KEYS:
            raise ValueError(
                f"regime_weights keys must be exactly {sorted(self._REGIME_KEYS)}; "
                f"got {sorted(weights.keys())}"
            )
        for key, w in weights.items():
            if len(w) != 3:
                raise ValueError(
                    f"regime_weights[{key!r}] must have exactly 3 entries (SPY, TLT, GLD); got {w}"
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
        self.long_yield_column = long_yield_column
        self.short_yield_column = short_yield_column
        self.steep_threshold = steep_threshold
        self.flat_threshold = flat_threshold
        self.yield_lag_months = yield_lag_months
        self.regime_weights = dict(weights)

    @property
    def tradable_symbols(self) -> tuple[str, str, str]:
        """The three tradable ETF columns (equity, bonds, gold)."""
        return (self.equity_symbol, self.bonds_symbol, self.gold_symbol)

    @property
    def required_symbols(self) -> tuple[str, ...]:
        """The five required columns: 3 tradable ETFs + 2 informational yield series."""
        return (*self.tradable_symbols, self.long_yield_column, self.short_yield_column)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return 3-cell yield-curve regime weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            three tradable ETF columns AND the two yield-level
            informational columns (default: SPY / TLT / GLD /
            DGS10 / DGS2). ETF columns must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. The three tradable columns carry the
            regime-conditional allocation; the two yield columns
            carry **weight = 0.0** at every bar.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for yield_curve_regime_allocation: "
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
            raise ValueError("prices must be strictly positive for all three tradable ETF legs")

        # Resample to month-end.
        month_end_all = all_cols.resample("ME").last()

        # Lag both yield columns, then compute the slope internally.
        # The slope can go negative (inversion) — it never reaches the
        # bridge because only the positive raw yield columns are in
        # the input DataFrame; the slope is a transient local variable.
        long_lagged = month_end_all[self.long_yield_column].shift(self.yield_lag_months)
        short_lagged = month_end_all[self.short_yield_column].shift(self.yield_lag_months)
        slope = long_lagged - short_lagged

        steep = slope >= self.steep_threshold
        flat = (slope >= self.flat_threshold) & (slope < self.steep_threshold)
        inverted = slope < self.flat_threshold
        valid = slope.notna()

        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_all.index,
            columns=list(self.required_symbols),
        )

        regime_masks = {
            "steep": steep & valid,
            "flat": flat & valid,
            "inverted": inverted & valid,
        }
        for regime, mask in regime_masks.items():
            if not mask.any():
                continue
            w = self.regime_weights[regime]
            monthly_weights.loc[mask, self.equity_symbol] = w[0]
            monthly_weights.loc[mask, self.bonds_symbol] = w[1]
            monthly_weights.loc[mask, self.gold_symbol] = w[2]

        daily_weights = monthly_weights.reindex(all_cols.index).ffill().fillna(0.0)
        # Defensive: ensure both yield columns are exactly 0.0.
        daily_weights[self.long_yield_column] = 0.0
        daily_weights[self.short_yield_column] = 0.0
        return cast(pd.DataFrame, daily_weights)
