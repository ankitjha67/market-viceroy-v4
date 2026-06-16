"""Cross-asset GTAA time-series momentum on a multi-asset ETF panel.

Implementation notes
====================

Foundational paper
------------------
Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017).
*A Century of Evidence on Trend-Following Investing*. Journal of
Portfolio Management 44(1), 15-29.
https://doi.org/10.3905/jpm.2017.44.1.015

HOP (2017) extends the time-series-momentum result of MOP (2012) and
AMP (2013) out to 1880 across 67 markets and four asset classes
(equity indices, government bonds, commodities, currencies). The
century-long out-of-sample evidence confirms that the 12/1 TSMOM
mechanic earns a positive risk premium across regimes — including
the regimes outside the standard 1985–2010 sample windows used in
the seminal papers.

Primary methodology
-------------------
Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013).
*Value and Momentum Everywhere*. Journal of Finance 68(3), 929-985.
Section V applies the 12/1 time-series-momentum rule across four
asset classes (equity index futures, government bonds, currencies,
commodities) and documents a diversified-cross-asset Sharpe
substantially higher than any single-asset-class application of
the same rule.
https://doi.org/10.1111/jofi.12021

Why two papers
--------------
AMP (2013) §V is the *implementation anchor*: it specifies the
cross-asset universe and combination logic. HOP (2017) is the
*long-horizon validation*: 130 years of out-of-sample evidence
confirms that the 12/1 cross-asset book holds up beyond the AMP
in-sample window. Where AMP documents the Sharpe on 1972–2009,
HOP confirms it on 1880–2013 and decomposes the contribution by
asset class. Both are cited so the audit trail covers both the
implementation rule and the long-run robustness evidence.

Differentiation from sibling Phase 1 and Phase 2 strategies
-----------------------------------------------------------
* **Phase 1 ``tsmom_12_1`` (trend family)** — same 12/1 TSMOM
  mechanic on a 6-ETF universe ``(SPY, EFA, EEM, AGG, GLD, DBC)``
  cited on Moskowitz/Ooi/Pedersen 2012 as the primary anchor. This
  strategy differs in three load-bearing ways:
    1. **Universe breadth.** This strategy uses 9 ETFs spanning four
       asset super-classes (equity / bonds / commodities / real
       estate), explicitly adding ``TLT`` (long Treasuries),
       ``HYG`` (high-yield credit), and ``VNQ`` (US REITs) that
       are absent from the Phase 1 trend universe. The 9-ETF panel
       includes duration risk, credit risk, and real-asset
       cyclicality that the 6-ETF Phase 1 panel does not.
    2. **Citation anchor.** AMP 2013 §V (the cross-asset case
       study) rather than MOP 2012 (the foundational
       time-series-momentum paper). HOP 2017 is the long-horizon
       extension that the Phase 1 strategy does not cite.
    3. **Framing.** This is a *GTAA* (global tactical asset
       allocation) strategy positioned in the macro family,
       distinct from the *trend-following* framing of Phase 1
       ``tsmom_12_1``. Same mechanic, different cluster identity.
* **Phase 1 ``dual_momentum_gem`` (trend family)** — Antonacci's
  3-asset absolute + relative momentum on US equity / Intl equity
  / bonds. Same overall asset-allocation theme but discrete
  100%-allocation switching versus continuous vol-scaled weights.
  Expected ρ ≈ 0.30–0.50 (correlated direction but different
  weighting philosophy).
* **Phase 2 ``commodity_tsmom`` (commodity family)** — same TSMOM
  mechanic but commodity-only universe ``(CL, NG, GC, SI, HG, ZC,
  ZS, ZW)``. Different asset class; expected ρ ≈ 0.30–0.50 when
  commodities dominate the cross-asset trend signal and lower
  otherwise.
* **Phase 2 ``bond_tsmom_12_1`` (rates family)** — single-asset
  10Y treasury TSMOM. Different universe and shape; expected ρ ≈
  0.20–0.40 (the TLT leg of this strategy partially overlaps).
* **Within Session 2G:** ``permanent_portfolio`` (Commit 2) is a
  static-weight allocator on the same broad-asset theme. Expected
  ρ ≈ 0.40–0.60 in trending regimes (when GTAA momentum aligns
  with permanent-portfolio constituents) and lower in mean-
  reverting regimes.

Cluster expectations are documented in ``known_failures.md``.

Published rules (AMP §V applied to a cross-asset ETF panel)
-----------------------------------------------------------
For each asset *a* and each month-end *t*:

1. Compute the asset's return over the 12 months *ending one month
   prior* — months ``[t-12, t-1)``. Skip the most recent month per
   the 12/1 convention (sidesteps short-term reversal).
2. **Sign-of-return trade.** Long if positive, short if negative.
3. **Per-asset volatility scaling** to a constant target (10%
   annualised by default). Position size for asset *a* at month
   *t*::

       weight_a(t) = sign(lookback_return_a) × (vol_target / realised_vol_a)

4. Hold one month, rebalance monthly.

Volatility estimator
--------------------
AMP §V uses an EWMA estimator with a 60-day half-life. This
implementation uses a simple rolling standard deviation over
``vol_lookback_days`` daily log returns (63 days ≈ 3 months) — the
same estimator used by Phase 2 sibling strategies (``bond_tsmom_12_1``,
``commodity_tsmom``, ``metals_momentum``) for consistency across the
family. Both estimators converge to the same long-run realised
volatility; the rolling window is chosen for determinism in CI.

Sign convention
---------------
Per-asset weights on a multi-column DataFrame (one column per input
symbol). Positive = long, negative = short. NaN is treated as zero
by the bridge. Weights are deliberately **not** normalised to sum
to 1 — the vol-scaling can produce a gross book larger than one,
which is the point of a TSMOM strategy. The cross-asset universe
typically produces a gross book in the 1.5–3× range with all 9 ETFs
contributing.

Rebalance cadence
-----------------
Monthly target signal. The vectorbt bridge applies
``SizeType.TargetPercent`` semantics, producing daily drift-
correction trades on top of the monthly signal — see Session 2G
amendment "alphakit-wide rebalance-cadence convention" in
``docs/phase-2-amendments.md`` for the project-wide framing. The
``rebalance_frequency`` attribute documents the *signal cadence*,
not the bridge-event cadence.

Edge cases
----------
* Before ``lookback_months + 1`` months of history are available,
  the strategy emits zero weights for that asset.
* If realised volatility is zero or NaN (constant-price series),
  the strategy emits zero — never ``inf`` — for that asset.
* Weights are clipped to ``[-max_leverage_per_asset,
  max_leverage_per_asset]`` to bound the backtest when realised
  vol collapses.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class GtaaCrossAssetMomentum:
    """Cross-asset GTAA time-series momentum, 12-month lookback / 1-month skip.

    Parameters
    ----------
    lookback_months
        Total months of history to sample (inclusive of the skipped
        window). Defaults to ``12`` per AMP §V.
    skip_months
        Number of most-recent months to *skip* when computing the
        lookback return (the "12-1" convention). Defaults to ``1``.
    vol_target_annual
        Per-asset annualised volatility target used for position
        sizing. Defaults to ``0.10`` (10%).
    vol_lookback_days
        Window for the rolling realised-vol estimator. Defaults to
        ``63`` trading days (~3 months).
    annualization
        Periods per year used to annualise daily vol. ``252`` for
        daily bars (default).
    max_leverage_per_asset
        Safety cap on the gross per-asset weight. Defaults to ``3.0``
        so a collapse in realised volatility cannot push weights to
        infinity.
    """

    name: str = "gtaa_cross_asset_momentum"
    family: str = "macro"
    asset_classes: tuple[str, ...] = ("equity", "bonds", "commodities", "real_estate")
    paper_doi: str = "10.1111/jofi.12021"  # Asness/Moskowitz/Pedersen 2013 §V
    rebalance_frequency: str = "monthly"

    def __init__(
        self,
        *,
        lookback_months: int = 12,
        skip_months: int = 1,
        vol_target_annual: float = 0.10,
        vol_lookback_days: int = 63,
        annualization: int = 252,
        max_leverage_per_asset: float = 3.0,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= lookback_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < lookback_months ({lookback_months})"
            )
        if vol_target_annual <= 0:
            raise ValueError(f"vol_target_annual must be positive, got {vol_target_annual}")
        if vol_lookback_days < 2:
            raise ValueError(f"vol_lookback_days must be >= 2, got {vol_lookback_days}")
        if annualization <= 0:
            raise ValueError(f"annualization must be positive, got {annualization}")
        if max_leverage_per_asset <= 0:
            raise ValueError(
                f"max_leverage_per_asset must be positive, got {max_leverage_per_asset}"
            )

        self.lookback_months = lookback_months
        self.skip_months = skip_months
        self.vol_target_annual = vol_target_annual
        self.vol_lookback_days = vol_lookback_days
        self.annualization = annualization
        self.max_leverage_per_asset = max_leverage_per_asset

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a target-weights DataFrame for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by daily timestamps, columns are
            multi-asset ETF tickers spanning the cross-asset GTAA
            universe (default: SPY / EFA / EEM / AGG / TLT / HYG /
            GLD / DBC / VNQ). Values are continuous closing prices.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. Weights change only at
            month-ends (forward-filled daily) and are zero where
            insufficient history exists.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        # 1. Daily log returns (used for the vol estimator).
        daily_log_returns = np.log(prices / prices.shift(1))

        # 2. Rolling realised vol, annualised.
        daily_vol = daily_log_returns.rolling(self.vol_lookback_days).std(ddof=1) * np.sqrt(
            self.annualization
        )

        # 3. Month-end prices → monthly log returns.
        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))

        # 4. Lookback return over months [t-lookback_months, t-skip_months).
        effective_window = self.lookback_months - self.skip_months
        lookback_returns = (
            monthly_log_returns.rolling(effective_window).sum().shift(self.skip_months)
        )

        # 5. Sign × vol scaling, evaluated at month-ends.
        direction = np.sign(lookback_returns)
        monthly_vol = daily_vol.resample("ME").last()
        with np.errstate(divide="ignore", invalid="ignore"):
            vol_scalar = self.vol_target_annual / monthly_vol
        vol_scalar = vol_scalar.replace([np.inf, -np.inf], np.nan)

        monthly_weights = direction * vol_scalar
        monthly_weights = monthly_weights.clip(
            lower=-self.max_leverage_per_asset,
            upper=self.max_leverage_per_asset,
        )

        # 6. Forward-fill to the daily index and zero-fill warm-up NaNs.
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
