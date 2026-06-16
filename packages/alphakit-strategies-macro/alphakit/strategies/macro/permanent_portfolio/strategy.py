"""Permanent Portfolio — static 25/25/25/25 allocation across equity, bonds, gold, cash.

Implementation notes
====================

Foundational paper
------------------
Browne, H. (1987). *Why the Best-Laid Investment Plans Usually Go
Wrong: And How You Can Find Safety and Profit in an Uncertain World*.
Quill / William Morrow. ISBN 0-688-06778-6.

Browne's original "Permanent Portfolio" thesis: split the portfolio
equally across four assets that respond differently to the four major
economic regimes — equities for prosperity, long bonds for deflation,
gold for inflation, and cash for tight money / recession. The
construction was first formally proposed in *Fail-Safe Investing*
(Browne 1981) and refined in the 1987 follow-up cited above; the
1987 book is the canonical, widely-cited reference and is the
source whose 25/25/25/25 split this implementation replicates
verbatim.

Primary methodology
-------------------
Estrada, J. (2018). *From Failure to Success: Replacing the Failure
Rate*. SSRN Working Paper 3168697.
https://doi.org/10.2139/ssrn.3168697

Estrada (2018) provides the formal out-of-sample replication of the
Permanent Portfolio with rigorous failure-rate / Sharpe analysis
over 1972–2016. Table 1 of Estrada reports a Sharpe of approximately
0.5 for the 25/25/25/25 US portfolio over the full sample, with
materially lower drawdowns than equity-only or 60/40 benchmarks
across the four major regime stresses (1973–74 inflation, 1980–82
disinflation, 2000–02 dotcom bust, 2008 GFC). We anchor the
implementation on Estrada because that paper provides the
peer-reviewable empirical evidence — Browne's book is the original
construction but does not provide the regression-tested out-of-
sample numbers.

Why two papers
--------------
Browne 1987 specifies the *construction* — the four asset classes
and the equal-weight rule — but is a popular-press investment book
without formal back-testing methodology. Estrada 2018 provides the
academic *empirical anchor* with explicit Sharpe / failure-rate
tables on US data 1972–2016 plus international robustness checks on
10 developed-market equity / bond / gold panels. Strategy code
replicates Browne's construction; ``benchmark_results.json`` is
calibrated to Estrada's reported Sharpe range.

Differentiation from sibling Phase 2 and Phase 1 strategies
-----------------------------------------------------------
* **No direct Phase 1 sibling.** Phase 1 trend/meanrev/carry/value/
  volatility strategies are all single-asset or cross-sectional
  factor signals. A *static-weight multi-asset allocation* is a new
  shape introduced in the macro family. The closest Phase 1 analogs
  are ``dual_momentum_gem`` (trend) which uses a 3-asset universe
  but rotates *dynamically* on momentum, and ``vol_targeting``
  (volatility) which is per-asset, not portfolio-level.
* **Within Session 2G:** ``gtaa_cross_asset_momentum`` (Commit 3,
  AMP 2013) trades 12/1 momentum on a similar multi-asset ETF
  universe but with *dynamic* sign-and-vol weights; this strategy
  is its static-weight counterpoint. ``risk_parity_erc_3asset``
  (Commit 5) is the closest multi-asset sibling but uses
  covariance-based equal-risk-contribution weights (which adapt
  monthly to the realised covariance) rather than fixed 25/25/25/25.

Cluster expectations are documented in ``known_failures.md``.

Published rules (Browne 1987, replicated verbatim)
--------------------------------------------------
For each rebalance date *t*:

1. Target weights are constant: 25% equity, 25% long bonds, 25% gold,
   25% cash. The four legs by default map to ``"SPY"`` (US large-cap
   equity), ``"TLT"`` (20+ year Treasuries), ``"GLD"`` (physical
   gold), and ``"SHY"`` (1–3 year Treasuries as a cash proxy).
2. The strategy emits the 25/25/25/25 target weights on each
   month-end bar, forward-filled to every intermediate bar (the
   AlphaKit-wide signal convention established in Phase 1
   ``dual_momentum_gem`` and applied uniformly across Sessions 2D /
   2E / 2F / 2G). The vectorbt bridge applies
   ``SizeType.TargetPercent`` semantics: on each daily bar it
   re-marks the portfolio to target by issuing small drift-correction
   trades — **not** a single discrete monthly rebalance event. The
   economic exposure matches a true monthly rebalance to within a
   small friction cost; only the trade-event distribution differs
   (~63 small drift-correction events per asset per year instead of
   ~12 discrete monthly rebalances). See ``known_failures.md`` item 4
   for the bridge-cadence discussion and ``docs/phase-2-amendments.md``
   for the project-wide convention amendment.
3. No regime state, no momentum signal, no covariance estimation.
   This is the simplest allocator in the macro family — its role
   is to establish the family pattern (multi-asset target weights,
   monthly signal cadence, vectorbt-bridge integration) before the
   architecturally novel strategies layer on top.

Sign convention
---------------
All weights are non-negative (long-only). Weights sum to exactly
1.0 at every rebalance bar (no leverage, no cash drag — the
``SHY`` leg models cash explicitly).

Edge cases
----------
* Required input columns: SPY, TLT, GLD, SHY by default (overridable
  via ``__init__`` parameters). Missing any of the four raises
  ``KeyError`` with the missing symbol.
* Non-positive prices raise ``ValueError`` — the bridge cannot price
  a zero or negative equity series.
* Warm-up: there is none. The first available rebalance date
  immediately gets 25/25/25/25. There is no lookback window.
* Empty input: returns an empty DataFrame with the four required
  columns and zero rows.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class PermanentPortfolio:
    """Static 25/25/25/25 allocation across equity, bonds, gold, cash.

    Parameters
    ----------
    equity_symbol
        Symbol for the equity leg. Defaults to ``"SPY"`` (US
        large-cap).
    bonds_symbol
        Symbol for the long-bonds leg. Defaults to ``"TLT"`` (20+
        year Treasuries).
    gold_symbol
        Symbol for the gold leg. Defaults to ``"GLD"`` (physical
        gold ETF).
    cash_symbol
        Symbol for the cash / short-Treasury leg. Defaults to
        ``"SHY"`` (1–3 year Treasuries as a cash proxy — Browne's
        original construction holds T-bills, but the AlphaKit
        substrate is daily ETF prices and SHY is the cleanest
        cash-equivalent on yfinance).
    target_weights
        Per-leg target weights in the order ``(equity, bonds, gold,
        cash)``. Defaults to ``(0.25, 0.25, 0.25, 0.25)``. Must be
        positive and sum to 1.0 within a 1e-9 tolerance.
    """

    name: str = "permanent_portfolio"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "gold", "cash")
    paper_doi: str = "10.2139/ssrn.3168697"  # Estrada 2018
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        equity_symbol: str = "SPY",
        bonds_symbol: str = "TLT",
        gold_symbol: str = "GLD",
        cash_symbol: str = "SHY",
        target_weights: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25),
    ) -> None:
        for label, sym in (
            ("equity_symbol", equity_symbol),
            ("bonds_symbol", bonds_symbol),
            ("gold_symbol", gold_symbol),
            ("cash_symbol", cash_symbol),
        ):
            if not isinstance(sym, str) or not sym:
                raise ValueError(f"{label} must be a non-empty string, got {sym!r}")

        symbols = (equity_symbol, bonds_symbol, gold_symbol, cash_symbol)
        if len(set(symbols)) != 4:
            raise ValueError(
                f"equity / bonds / gold / cash symbols must be distinct; got {symbols}"
            )

        if len(target_weights) != 4:
            raise ValueError(
                f"target_weights must have exactly 4 entries (equity, bonds, gold, cash); "
                f"got {target_weights}"
            )
        if any(w <= 0 for w in target_weights):
            raise ValueError(f"target_weights must all be positive; got {target_weights}")
        weight_sum = float(sum(target_weights))
        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                f"target_weights must sum to 1.0 within 1e-9 tolerance; got sum={weight_sum}"
            )

        self.equity_symbol = equity_symbol
        self.bonds_symbol = bonds_symbol
        self.gold_symbol = gold_symbol
        self.cash_symbol = cash_symbol
        self.target_weights = target_weights

    @property
    def required_symbols(self) -> tuple[str, str, str, str]:
        """The four input columns the strategy requires."""
        return (self.equity_symbol, self.bonds_symbol, self.gold_symbol, self.cash_symbol)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a target-weights DataFrame for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps. Must contain the
            four columns named by ``equity_symbol`` / ``bonds_symbol``
            / ``gold_symbol`` / ``cash_symbol`` (SPY/TLT/GLD/SHY by
            default). Additional columns are ignored. Values must
            be strictly positive (closing prices).

        Returns
        -------
        weights
            DataFrame aligned to ``prices`` with one column per
            required symbol. Weights change only at month-ends
            (everything in between is forward-filled) and equal the
            configured ``target_weights`` from the first available
            month-end onward.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")

        missing = [s for s in self.required_symbols if s not in prices.columns]
        if missing:
            raise KeyError(
                f"prices is missing required columns for permanent_portfolio: {missing}. "
                f"Required: {list(self.required_symbols)}; got: {list(prices.columns)}"
            )

        leg_prices = prices.loc[:, list(self.required_symbols)]

        if leg_prices.empty:
            return pd.DataFrame(
                index=prices.index,
                columns=list(self.required_symbols),
                dtype=float,
            )

        if not isinstance(leg_prices.index, pd.DatetimeIndex):
            raise TypeError(
                f"prices must have a DatetimeIndex, got {type(leg_prices.index).__name__}"
            )
        if (leg_prices <= 0).any().any():
            raise ValueError("prices must be strictly positive for all four legs")

        # Month-end rebalance bars. The strategy emits target weights on
        # every month-end and forward-fills daily in between (the bridge
        # treats forward-filled weights as "hold prior position").
        month_end_mask = (
            leg_prices.index.to_series().groupby(leg_prices.index.to_period("M")).transform("max")
            == leg_prices.index.to_series()
        )

        weights = pd.DataFrame(
            np.zeros(leg_prices.shape, dtype=float),
            index=leg_prices.index,
            columns=list(self.required_symbols),
        )
        # Assign the constant target on every month-end bar.
        target = np.asarray(self.target_weights, dtype=float)
        weights.loc[month_end_mask, :] = target

        # Forward-fill so weights persist between rebalance bars; bars
        # before the first month-end remain zero (no warm-up).
        weights = weights.where(month_end_mask).ffill().fillna(0.0)
        return cast(pd.DataFrame, weights)
