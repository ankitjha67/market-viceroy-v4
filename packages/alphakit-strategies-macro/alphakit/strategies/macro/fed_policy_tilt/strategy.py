"""Federal-policy-tilt 2-cell regime allocation (Conover et al. 2008 / Jensen-Mercer-Johnson 1996).

Fourth strategy in the macro family's regime-state group
(Commits 8-12). Inherits the informational-column + publication-
lag pattern; classifies each month as Fed-tightening or Fed-easing
by comparing the current FEDFUNDS rate to its N-month-ago level.

Implementation notes
====================

Foundational paper
------------------
Conover, C. M., Jensen, G. R., Johnson, R. R. & Mercer, J. M. (2008).
*Sector Rotation and Monetary Conditions*.
Journal of Investing 17(2), 34-46.
https://doi.org/10.3905/joi.2008.17.4.61

Conover et al. (2008) extend Jensen-Mercer-Johnson (1996) from
individual equity categories to multi-asset sector rotation. The paper
demonstrates that a 2-cell Fed tightening/easing classification —
derived from the direction of the federal funds rate — produces
economically significant differences in asset-class returns. The
foundational result: equity returns are substantially higher in
easing environments; bond and gold returns are superior in tightening
environments.

Primary methodology
-------------------
Jensen, G. R., Mercer, J. M. & Johnson, R. R. (1996).
*Business Conditions, Monetary Policy, and Expected Security Returns*.
Journal of Financial Economics 40(2), 213-237.
https://doi.org/10.1016/0304-405X(96)00875-X

Jensen, Mercer & Johnson (1996) provide the rigorous asset-pricing
framework: monetary policy (tightening vs. easing) shifts the
investment opportunity set, systematically altering expected returns
across asset classes. Their 2-cell taxonomy (initiated/expansive
monetary conditions) maps directly to the strategy's tightening/easing
classification. The paper uses discount-rate changes; this
implementation uses the monthly FEDFUNDS rate direction as the
continuous signal analogue.

Why two papers
--------------
Jensen-Mercer-Johnson (1996) is the *foundational* academic result —
monetary policy tilt shifts the asset-class opportunity set. Conover
et al. (2008) is the *direct implementation methodology* for the
multi-asset version: sector/asset rotation driven by the Fed funds rate
direction, with the specific asset classes (equity, bonds, gold) and
2-cell taxonomy used here.

Informational-column pattern
----------------------------
Inherits the informational-column pattern (Session 2D §2D sub-section
3). The strategy reads one FRED informational column:

* ``FEDFUNDS``: effective federal funds rate (%, monthly averages).

The FEDFUNDS rate level is strictly positive in virtually all
historical periods. The only exception is the 2010-2015 ZIRP period
when the rate printed near (but not exactly) 0 — FEDFUNDS never prints
exactly 0.0 because it is an averages series (typical ZIRP readings:
0.07%, 0.09%, etc.). This is different from DGS3MO (which prints
exactly 0.0 on several ZIRP days). FEDFUNDS satisfies the bridge-
positivity constraint naturally.

The tightening/easing regime is computed internally by comparing the
current (lagged) rate to the rate ``lookback_months`` periods ago:
* ``delta > 0`` → tightening
* ``delta <= 0`` → easing

Both cases are handled as valid regimes; ``delta == 0`` (rate
unchanged) is classified as easing (no tightening).

Publication-lag handling
------------------------
The FEDFUNDS column is lagged by ``fed_lag_months`` (default 1) before
the direction is computed. The Fed publishes the monthly FEDFUNDS
average with a short lag (~2 weeks), so the 1-month lag is conservative
but consistent with the group convention.

2-cell regime classification
-----------------------------
For each month-end, after the lag:

* **Tightening** (``delta > 0``, rate rising over the trailing
  ``lookback_months``): pro-cyclical environment → equities-biased.
  *Wait* — Conover et al. (2008) and JMJ (1996) find that easing is
  *equity-positive* and tightening is *bond/gold-positive*. The
  strategy therefore uses the counterintuitive assignment:

  | Regime | Default (SPY/TLT/GLD) |
  |---|---|
  | easing     | (0.70, 0.20, 0.10) |
  | tightening | (0.20, 0.60, 0.20) |

  This matches the empirical finding: equities outperform in easing;
  bonds and gold outperform in tightening. The equity-heavy assignment
  is easing, not tightening.

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``recession_probability_rotation``** (Commit 8)
  — overlapping macro factor: the Cleveland Fed recession-probability
  model includes the FEDFUNDS rate as an input. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``yield_curve_regime_allocation``** (Commit 10)
  — the 2-year yield (DGS2) tracks fed-funds expectations, so there is
  signal overlap on the short end. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``growth_inflation_regime_rotation``** (Commit 9)
  — overlapping macro-state factor. Expected ρ ≈ 0.40-0.60.
* **Phase 2 Session 2G ``inflation_regime_allocation``** (Commit 12)
  — CPI YoY signal. Expected ρ ≈ 0.30-0.50.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) — static
  allocation. Expected ρ ≈ 0.20-0.40.

Cluster expectations are documented in ``known_failures.md``.

Universe (3 tradable ETFs + 1 informational FRED rate series)
--------------------------------------------------------------
* **Tradable:**
  - ``SPY``: US large-cap equity (easing / pro-cyclical leg)
  - ``TLT``: 20+ year Treasuries (tightening / defensive bond leg)
  - ``GLD``: Physical gold ETF (tightening / inflation-hedge leg)
* **Informational (FRED, zero-weight in output, strictly positive):**
  - ``FEDFUNDS``: effective federal funds rate (%)

Published rules (Conover et al. 2008 / JMJ 1996, 3-asset)
-----------------------------------------------------------
For each month-end *t*:

1. Read FEDFUNDS, apply ``fed_lag_months`` shift.
2. Compute the rate delta: ``current_rate - rate[lookback_months ago]``.
3. Classify:
   * ``delta > 0`` → tightening.
   * ``delta <= 0`` → easing (unchanged or falling rate).
4. Map the regime to its configured allocation.
5. Emit weights at month-end; forward-fill daily. FEDFUNDS column
   carries ``weight = 0.0``.

Sign convention
---------------
Long-only. Each regime's weights sum to 1.0 across the 3 tradable
ETFs; the informational column always carries 0.0. Strategy emits
zero weights everywhere during warm-up (before
``fed_lag_months + lookback_months`` months of FEDFUNDS history are
available).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention".

Edge cases
----------
* Warm-up: requires ``fed_lag_months + lookback_months`` months of
  FEDFUNDS history; before that, weights are zero everywhere.
* Missing required columns: ``KeyError`` listing the missing symbols.
* Non-positive ETF prices: ``ValueError``.
* NaN in FEDFUNDS column after lag: rows emit zero weights.
* Constructor validates each regime-weight tuple sums to 1.0 with
  non-negative entries.
"""

from __future__ import annotations

from typing import ClassVar, cast

import pandas as pd

# Regime-weight tuple type: (SPY, TLT, GLD).
_RegimeWeights = tuple[float, float, float]


class FedPolicyTilt:
    """Federal-policy-tilt 2-cell regime allocation (Conover et al. 2008 / JMJ 1996).

    Parameters
    ----------
    equity_symbol
        Symbol for the pro-cyclical equity leg. Defaults to ``"SPY"``.
    bonds_symbol
        Symbol for the defensive long-duration bonds leg. Defaults
        to ``"TLT"``.
    gold_symbol
        Symbol for the inflation-hedge leg. Defaults to ``"GLD"``.
    fed_column
        FRED federal funds rate column. Defaults to ``"FEDFUNDS"``.
    lookback_months
        Number of months over which the FEDFUNDS rate direction is
        measured (``current - rate[lookback_months ago]``). Defaults
        to ``3`` (3-month rolling direction).
    fed_lag_months
        Publication-lag shift applied to the FEDFUNDS column before
        computing the regime. Defaults to ``1``.
    regime_weights
        Mapping from regime to (SPY, TLT, GLD) weights. Keys must
        be exactly ``{"easing", "tightening"}``. Each tuple must sum
        to 1.0 with non-negative entries.
    """

    name: str = "fed_policy_tilt"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold")
    paper_doi: str = "10.1016/0304-405X(96)00875-X"  # Jensen-Mercer-Johnson 1996
    rebalance_frequency: str = "monthly"

    _DEFAULT_REGIME_WEIGHTS: ClassVar[dict[str, _RegimeWeights]] = {
        # (SPY, TLT, GLD) — easing is equity-positive (JMJ 1996 / Conover 2008)
        "easing": (0.70, 0.20, 0.10),
        "tightening": (0.20, 0.60, 0.20),
    }

    _REGIME_KEYS: ClassVar[frozenset[str]] = frozenset({"easing", "tightening"})

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        fed_column: str = "FEDFUNDS",
        lookback_months: int = 3,
        fed_lag_months: int = 1,
        regime_weights: dict[str, _RegimeWeights] | None = None,
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("fed_column", fed_column),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")

        tradable = (equity_symbol, bonds_symbol, gold_symbol)
        if len(set(tradable)) != 3:
            raise ValueError(f"equity / bonds / gold symbols must be distinct; got {tradable}")
        if fed_column in set(tradable):
            raise ValueError(
                f"fed_column ({fed_column!r}) must not overlap with tradable symbols {tradable}"
            )

        if lookback_months < 1:
            raise ValueError(f"lookback_months must be >= 1; got {lookback_months}")
        if fed_lag_months < 0:
            raise ValueError(f"fed_lag_months must be non-negative; got {fed_lag_months}")

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
        self.fed_column = fed_column
        self.lookback_months = lookback_months
        self.fed_lag_months = fed_lag_months
        self.regime_weights = dict(weights)

    @property
    def tradable_symbols(self) -> tuple[str, str, str]:
        """The three tradable ETF columns (equity, bonds, gold)."""
        return (self.equity_symbol, self.bonds_symbol, self.gold_symbol)

    @property
    def required_symbols(self) -> tuple[str, ...]:
        """The four required columns: 3 tradable ETFs + 1 informational FEDFUNDS."""
        return (*self.tradable_symbols, self.fed_column)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return 2-cell Fed-policy-tilt regime weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            three tradable ETF columns AND the FEDFUNDS informational
            column. ETF columns must be strictly positive.

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. The three tradable columns carry the
            regime-conditional allocation; FEDFUNDS carries
            **weight = 0.0** at every bar.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for fed_policy_tilt: "
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

        # Apply publication lag to FEDFUNDS, then compute direction.
        fed_lagged = month_end_all[self.fed_column].shift(self.fed_lag_months)
        # Delta: current rate vs. rate lookback_months ago (on lagged series).
        fed_delta = fed_lagged - fed_lagged.shift(self.lookback_months)

        tightening = fed_delta > 0
        easing = fed_delta <= 0
        valid = fed_delta.notna()

        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_all.index,
            columns=list(self.required_symbols),
        )

        regime_masks = {
            "tightening": tightening & valid,
            "easing": easing & valid,
        }
        for regime, mask in regime_masks.items():
            if not mask.any():
                continue
            w = self.regime_weights[regime]
            monthly_weights.loc[mask, self.equity_symbol] = w[0]
            monthly_weights.loc[mask, self.bonds_symbol] = w[1]
            monthly_weights.loc[mask, self.gold_symbol] = w[2]

        daily_weights = monthly_weights.reindex(all_cols.index).ffill().fillna(0.0)
        # Defensive: ensure the FEDFUNDS informational column is exactly 0.0.
        daily_weights[self.fed_column] = 0.0
        return cast(pd.DataFrame, daily_weights)
