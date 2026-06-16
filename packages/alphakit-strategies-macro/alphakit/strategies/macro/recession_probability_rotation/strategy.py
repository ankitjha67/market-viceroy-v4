"""Recession-probability-driven asset rotation across equity / bonds / gold.

First strategy in the macro family's regime-state group
(Commits 8-12). Introduces the *informational-column pattern* per
Session 2D's signal-contract amendment
(``docs/phase-2-amendments.md`` §2D sub-section 3): the strategy
takes one or more **informational** columns alongside the tradable
asset price columns. Informational columns drive the regime
classification but carry **zero weight** in the output — they
inform but do not trade.

This is the first consumer of the regime-state primitive and the
gate-3 review checkpoint for the pattern. Commits 9-12 follow the
same convention.

Implementation notes
====================

Foundational paper
------------------
Estrella, A. & Mishkin, F. S. (1998).
*Predicting U.S. Recessions: Financial Variables as Leading
Indicators*. Review of Economics and Statistics 80(1), 45-61.
https://doi.org/10.1162/003465398557320

Estrella & Mishkin (1998) is the seminal reference for the
**recession-probability** family of models. The paper estimates
probit models linking the slope of the Treasury yield curve and
other financial variables to subsequent NBER-dated recessions,
producing a continuous recession-probability output that the
Federal Reserve Bank of Cleveland publishes in real time as
the FRED series ``RECPROUSM156N`` (also known as the
*Cleveland Fed recession probability*).

The 30% probability threshold is the canonical signal level in
the paper: when the predicted recession probability exceeds 30%
in any month, the model strongly anticipates an NBER-dated
recession within the next 12 months. The threshold is robust
across the 1959-1998 in-sample window and has held up in real-
time forecasting since.

Primary methodology
-------------------
Wright, J. H. (2006). *The Yield Curve and Predicting
Recessions*. Federal Reserve Board FEDS Working Paper 2006-07.
https://www.federalreserve.gov/pubs/feds/2006/200607/200607pap.pdf

Wright (2006) extends the Estrella-Mishkin framework with a
more sophisticated probit specification including the fed funds
rate alongside the term spread. The Wright (2006) model is the
specification currently used by the Cleveland Fed to generate
the ``RECPROUSM156N`` series — strategy code reads the FRED
series directly rather than re-estimating the model, so this
strategy effectively *implements* Wright (2006) by reading the
Cleveland Fed's published output.

Wright (2006) does not have a DOI (it is a Federal Reserve Board
working paper); cited by URL above. The ``paper_doi`` class
attribute points to the Estrella-Mishkin 1998 DOI as the
foundational anchor.

Why two papers
--------------
Estrella-Mishkin (1998) provides the *foundational model* — the
probit-on-financial-variables recession-probability framework
that established the canonical 30% threshold. Wright (2006)
provides the *production specification* — the model currently
estimated by the Cleveland Fed to generate ``RECPROUSM156N``.
Both are cited so the audit trail covers the foundational paper
(EM 1998) and the contemporary model (Wright 2006) that the
strategy actually consumes via FRED.

Informational-column pattern (Session 2D §2D sub-section 3)
-----------------------------------------------------------
This strategy is the *first consumer* of the informational-column
pattern. The convention (documented in ``docs/phase-2-amendments.md``
Session 2D "signal-contract clarifications" §3) is:

* Input ``prices`` DataFrame contains both **tradable** ETF
  price columns (SPY, TLT, GLD) AND **informational** columns
  (the FRED recession-probability series ``RECPROUSM156N``).
* Output ``weights`` DataFrame contains the same columns. The
  tradable columns carry the regime-conditional allocation
  weights; the informational columns carry **weight = 0.0** at
  every bar.
* The vectorbt bridge dispatches ``SizeType.TargetPercent`` across
  all columns; a zero-weight column is a no-op (no orders, no
  drift correction) so the informational column passes through
  cleanly.

The pattern is required because some Phase 2 strategies need
exogenous signals (FRED macro variables, CFTC positioning) that
cannot be modelled as additional tradable assets. Threading the
signal through the input DataFrame as a zero-weight column
preserves the StrategyProtocol's ``generate_signals(prices) →
weights`` shape contract without requiring constructor-side
state.

Publication-lag handling (load-bearing for FRED-driven regimes)
---------------------------------------------------------------
FRED's ``RECPROUSM156N`` series is published with a **one-month
reporting lag**: the recession-probability estimate for month *N*
is published in month *N+1* (typically mid-month or end-of-month
depending on data-release cadence). A naïve strategy that reads
``RECPROUSM156N[month_end_N]`` when emitting weights for month-end
*N* would be using future information.

The fix is to **shift the informational column by
``lag_months``** (default 1) before reading it:

    recession_prob_lagged = prices["RECPROUSM156N"].shift(lag_months)

After the shift, ``recession_prob_lagged[month_end_N]`` contains
the value that was last *published* before month-end *N* — i.e.
the recession probability for month *N-1*. This matches what a
real-time investor would have seen at month-end *N*.

The lag is configurable via the ``lag_months`` constructor
parameter for users with data sources that have different
publication cadences (e.g. a real-time Cleveland Fed feed with
weekly updates might use ``lag_months=0``).

Failure to apply the lag is the most common foot-gun in FRED-
driven regime strategies. ``known_failures.md`` item 2 documents
this explicitly.

Threshold-based regime classification (Estrella-Mishkin 1998)
-------------------------------------------------------------
Two-cell regime taxonomy:

* **Risk-on (low recession probability):** ``recession_prob <
  recession_threshold`` (default 0.30). The economy is not
  imminently entering recession; the strategy holds a pro-cyclical
  allocation (default 60% SPY / 40% TLT — standard 60/40).
* **Risk-off (high recession probability):** ``recession_prob >=
  recession_threshold``. The economy is anticipated to enter
  recession; the strategy rotates to a defensive allocation
  (default 0% SPY / 60% TLT / 40% GLD — long-duration Treasuries
  plus gold).

Both allocation modes are parameterised in the constructor; the
defaults follow the Estrella-Mishkin (1998) "above-threshold ⇒
defensive" prescription without specifying exact weights (which
the paper does not provide — it predicts recession occurrence,
not optimal asset allocation).

Differentiation from sibling strategies
---------------------------------------
* **Phase 2 Session 2G ``growth_inflation_regime_rotation``**
  (Commit 9) — uses CPI and GDP series for a 4-cell regime
  taxonomy. Same informational-column pattern; different
  regime variables and finer taxonomy. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G ``yield_curve_regime_allocation``**
  (Commit 10) — uses the yield-curve slope (T10Y3M) which is
  one of the inputs to the Cleveland Fed's recession-probability
  model. Highly correlated signal source; expected ρ ≈
  **0.50–0.70** (closest within the regime-state group).
* **Phase 2 Session 2G ``fed_policy_tilt``** (Commit 11) — uses
  fed funds rate changes. Different signal, similar pro-cyclical
  /defensive rotation mechanic. Expected ρ ≈ 0.40–0.60.
* **Phase 2 Session 2G ``inflation_regime_allocation``** (Commit 12)
  — CPI YoY regimes. Different signal, different asset rotation.
  Expected ρ ≈ 0.30–0.50.
* **Phase 2 Session 2G ``permanent_portfolio``** (Commit 2) —
  static allocation; this strategy is dynamic. Expected ρ ≈
  0.30–0.50.
* **Phase 2 Session 2G ``risk_parity_erc_3asset``** (Commit 5)
  — different mechanic (covariance vs regime). Expected ρ ≈
  0.30–0.50.

Cluster expectations are documented in ``known_failures.md``.

Universe (3 tradable ETFs + 1 informational FRED series)
--------------------------------------------------------
* **Tradable:**
  - ``SPY``: US large-cap equity (pro-cyclical leg)
  - ``TLT``: 20+ year Treasuries (defensive duration leg)
  - ``GLD``: Physical gold ETF (defensive inflation-hedge leg)
* **Informational (FRED, zero-weight in output):**
  - ``RECPROUSM156N``: Cleveland Fed recession probability,
    monthly. Strategy applies a ``lag_months`` shift before
    reading to avoid forward-looking bias.

Model versioning
----------------
The Cleveland Fed periodically revises the underlying probit
model. The Sharpe estimates in ``paper.md`` and
``benchmark_results.json`` are conditional on the *current* model
version (as of the validation cutoff). Future model revisions
would require revalidation; this is documented in
``known_failures.md`` item 4.

Published rules (EM 1998 / Wright 2006, 3-asset implementation)
---------------------------------------------------------------
For each month-end *t*:

1. Read the recession-probability column from ``prices``, applied
   with a ``lag_months`` shift (default 1) to model the FRED
   publication lag.
2. Compare the lagged probability against ``recession_threshold``:

   * If ``recession_prob_lagged(t) < recession_threshold``:
     **risk-on**.
   * Else: **risk-off**.

3. Allocate per the configured regime weights:

   * Risk-on: ``(equity_weight_risk_on, bonds_weight_risk_on,
     gold_weight_risk_on)``. Default ``(0.60, 0.40, 0.00)``.
   * Risk-off: ``(equity_weight_risk_off, bonds_weight_risk_off,
     gold_weight_risk_off)``. Default ``(0.00, 0.60, 0.40)``.

4. Emit weights at month-end; forward-fill daily until the next
   rebalance. The informational column ``RECPROUSM156N`` carries
   ``weight = 0.0`` at every bar.

Sign convention
---------------
Long-only. Each regime's weights sum to 1.0 across the 3 tradable
ETFs; the informational column always carries 0.0. Strategy emits
zero weights on all 4 columns during warm-up (before
``lag_months + 1`` months of FRED history are available).

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md`` for the project-wide framing.

Edge cases
----------
* Warm-up: requires ``lag_months + 1`` months of history per ETF
  AND per informational column. Before that, weights are zero
  everywhere (bridge holds 100% cash).
* Missing required columns (any of 3 tradable + 1 informational):
  ``KeyError`` listing the missing symbols.
* Non-positive ETF prices: ``ValueError``. The informational
  column is *not* checked for positivity — FRED probability values
  are in [0, 1] but may be 0.0 (no historical recession period
  detected).
* NaN in the informational column: rows where the lagged probability
  is NaN emit zero weights on all columns (treated as warm-up).
* Constructor validates that the risk-on and risk-off weight
  tuples each sum to 1.0 within tolerance.
"""

from __future__ import annotations

from typing import cast

import pandas as pd


class RecessionProbabilityRotation:
    """Recession-probability-driven rotation across equity / bonds / gold.

    Parameters
    ----------
    equity_symbol
        Symbol for the pro-cyclical equity leg. Defaults to
        ``"SPY"`` (US large-cap).
    bonds_symbol
        Symbol for the defensive long-duration bonds leg. Defaults
        to ``"TLT"`` (20+ year Treasuries).
    gold_symbol
        Symbol for the defensive inflation-hedge leg. Defaults to
        ``"GLD"`` (physical gold ETF).
    recession_column
        Name of the FRED recession-probability column in the input
        DataFrame. Defaults to ``"RECPROUSM156N"`` (Cleveland Fed
        recession probability, monthly).
    recession_threshold
        Threshold above which the strategy classifies the regime as
        "risk-off". Defaults to ``0.30`` per Estrella-Mishkin 1998.
        Must be in ``(0, 1)``.
    lag_months
        Number of months to lag the recession-probability column
        before reading, to model the FRED publication lag. Defaults
        to ``1`` (the lagged value at month-end N is the recession
        probability for month N-1). Must be non-negative.
    risk_on_weights
        Allocation across (equity, bonds, gold) when the lagged
        recession probability is *below* the threshold. Defaults
        to ``(0.60, 0.40, 0.00)`` (standard 60/40). Must sum to
        1.0 within 1e-9 tolerance; all entries non-negative.
    risk_off_weights
        Allocation across (equity, bonds, gold) when the lagged
        recession probability is *at or above* the threshold.
        Defaults to ``(0.00, 0.60, 0.40)`` (long-duration Treasuries
        + gold). Must sum to 1.0 within 1e-9 tolerance; all
        entries non-negative.
    """

    name: str = "recession_probability_rotation"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold")
    paper_doi: str = "10.1162/003465398557320"  # Estrella & Mishkin 1998
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        recession_column: str = "RECPROUSM156N",
        recession_threshold: float = 0.30,
        lag_months: int = 1,
        risk_on_weights: tuple[float, float, float] = (0.60, 0.40, 0.00),
        risk_off_weights: tuple[float, float, float] = (0.00, 0.60, 0.40),
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("recession_column", recession_column),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")
        tradable = (equity_symbol, bonds_symbol, gold_symbol)
        if len(set(tradable)) != 3:
            raise ValueError(f"equity / bonds / gold symbols must be distinct; got {tradable}")
        if recession_column in tradable:
            raise ValueError(
                f"recession_column ({recession_column!r}) must not overlap with "
                f"tradable symbols {tradable}"
            )

        if not 0.0 < recession_threshold < 1.0:
            raise ValueError(f"recession_threshold must be in (0, 1); got {recession_threshold}")
        if lag_months < 0:
            raise ValueError(f"lag_months must be non-negative; got {lag_months}")

        for label, w in (
            ("risk_on_weights", risk_on_weights),
            ("risk_off_weights", risk_off_weights),
        ):
            if len(w) != 3:
                raise ValueError(
                    f"{label} must have exactly 3 entries (equity, bonds, gold); got {w}"
                )
            if any(x < 0 for x in w):
                raise ValueError(f"{label} entries must be non-negative; got {w}")
            if abs(sum(w) - 1.0) > 1e-9:
                raise ValueError(f"{label} must sum to 1.0 within 1e-9 tolerance; got sum={sum(w)}")

        self.equity_symbol = equity_symbol
        self.bonds_symbol = bonds_symbol
        self.gold_symbol = gold_symbol
        self.recession_column = recession_column
        self.recession_threshold = recession_threshold
        self.lag_months = lag_months
        self.risk_on_weights = risk_on_weights
        self.risk_off_weights = risk_off_weights

    @property
    def tradable_symbols(self) -> tuple[str, str, str]:
        """The three tradable ETF columns (equity, bonds, gold)."""
        return (self.equity_symbol, self.bonds_symbol, self.gold_symbol)

    @property
    def required_symbols(self) -> tuple[str, str, str, str]:
        """The four required columns: 3 tradable ETFs + 1 informational FRED series."""
        return (*self.tradable_symbols, self.recession_column)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return regime-conditional weights for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            three tradable ETF columns AND the recession-probability
            informational column (default: SPY / TLT / GLD /
            RECPROUSM156N). The ETF columns must be strictly
            positive; the recession-probability column must be in
            ``[0, 1]`` (values outside that range are accepted but
            documented as a model-version warning in
            ``known_failures.md``).

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. The three tradable columns carry the
            regime-conditional allocation; the recession-probability
            informational column carries **weight = 0.0** at every
            bar (per the Session 2D §2D sub-section 3 informational-
            column pattern).
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for recession_probability_rotation: "
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

        # Validate tradable ETF columns (must be strictly positive).
        tradable_cols = all_cols.loc[:, list(self.tradable_symbols)]
        if (tradable_cols <= 0).any().any():
            raise ValueError("prices must be strictly positive for all three tradable ETF legs")

        # Resample to month-end. Both the ETF panel and the FRED series
        # are reduced to their month-end values. The FRED series is
        # itself monthly so resampling to ME just picks the last
        # available value within each month.
        month_end_all = all_cols.resample("ME").last()

        # Apply publication-lag shift to the recession-probability column.
        # This is the load-bearing correctness mechanism — without it
        # the strategy uses future information.
        recession_lagged = month_end_all[self.recession_column].shift(self.lag_months)

        # Regime classification at each month-end.
        risk_on = recession_lagged < self.recession_threshold
        risk_off = recession_lagged >= self.recession_threshold
        warm_up = recession_lagged.isna()

        # Build monthly weights DataFrame.
        monthly_weights = pd.DataFrame(
            0.0,
            index=month_end_all.index,
            columns=list(self.required_symbols),
        )

        # Risk-on rows: pro-cyclical allocation.
        if risk_on.any():
            monthly_weights.loc[risk_on, self.equity_symbol] = self.risk_on_weights[0]
            monthly_weights.loc[risk_on, self.bonds_symbol] = self.risk_on_weights[1]
            monthly_weights.loc[risk_on, self.gold_symbol] = self.risk_on_weights[2]

        # Risk-off rows: defensive allocation.
        if risk_off.any():
            monthly_weights.loc[risk_off, self.equity_symbol] = self.risk_off_weights[0]
            monthly_weights.loc[risk_off, self.bonds_symbol] = self.risk_off_weights[1]
            monthly_weights.loc[risk_off, self.gold_symbol] = self.risk_off_weights[2]

        # Warm-up rows already zero (initialised to 0.0).
        # The informational column always carries 0.0 (initialised so and never set).
        _ = warm_up  # documents the third partition explicitly

        # Forward-fill to daily index and zero-fill warm-up NaNs.
        daily_weights = monthly_weights.reindex(all_cols.index).ffill().fillna(0.0)
        # Defensive: ensure the informational column is exactly 0.0 everywhere
        # (in case of any numerical drift through the ffill pipeline).
        daily_weights[self.recession_column] = 0.0
        return cast(pd.DataFrame, daily_weights)
