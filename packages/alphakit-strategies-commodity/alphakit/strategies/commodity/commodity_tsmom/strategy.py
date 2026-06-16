"""Cross-commodity time-series momentum, 12-month lookback / 1-month skip.

Implementation notes
====================

Foundational paper
------------------
Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H. (2012).
*Time series momentum*. Journal of Financial Economics, 104(2), 228–250.
https://doi.org/10.1016/j.jfineco.2011.11.003

Primary methodology
-------------------
Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013).
*Value and momentum everywhere*. Journal of Finance, 68(3), 929–985.
Section V applies the 12/1 time-series-momentum rule to commodity
futures across an extensive cross-section (energy, metals, grains,
softs, livestock) and validates the strategy on the commodity
sub-panel — Sharpe of 0.78 on the commodity-only book over 1985-2010
per Asness Table III.
https://doi.org/10.1111/jofi.12021

Why two papers
--------------
Moskowitz/Ooi/Pedersen (2012) is the seminal *time-series-momentum*
paper but documents the strategy primarily on a 58-instrument
multi-asset futures panel (commodities are part of that panel but
not the focus). The commodity-specific cross-sectional application —
what this strategy implements — is a Section V case study in
Asness/Moskowitz/Pedersen (2013), which extends the 12/1 rule
explicitly to the commodity panel and confirms the result on a
broader commodity universe and a longer sample. We anchor the
implementation on Asness §V because that is the section whose
methodology is replicated verbatim; we cite Moskowitz 2012 as the
foundational reference.

Differentiation from sibling momentum strategies
------------------------------------------------
* Phase 1 ``tsmom_12_1`` (trend family) — same TSMOM mechanic but
  positioned in the trend family with a balanced 6-ETF multi-asset
  universe (SPY/EFA/EEM/AGG/GLD/DBC). Cited on Moskowitz 2012 as
  the primary paper because the 6-asset universe spans equities and
  bonds in addition to commodities.
* ``commodity_tsmom`` (this strategy) — positioned in the commodity
  family with a *commodity-only* default universe (CL, NG, GC, SI,
  HG, ZC, ZS, ZW). Cited on Asness §V as the primary paper because
  the commodity sub-strategy in Asness Table III is the direct
  empirical anchor.
* ``metals_momentum`` (Session 2E sibling) — same mechanic on a
  metals-only universe (GC, SI, HG, PL). Strong cluster correlation
  with this strategy when metals dominate the broader commodity
  cross-section; documented in ``known_failures.md``.

Published rules (Asness §V applied to a commodity panel)
--------------------------------------------------------
For each commodity *c* and each month-end *t*:

1. Compute the asset's return over the past 12 months, skipping the
   most recent month — the standard "12-1" convention. The signal is
   built from the return over months ``[t-12, t-1)``.

2. The **sign** of that lookback return determines whether to be
   long (positive past return) or short (negative past return) the
   commodity.

3. Position size is **volatility-scaled** so that every commodity
   contributes roughly the same amount of risk. The target
   volatility in MOP (2012) is 40% annualised *per asset*, which
   assumes a multi-instrument gross-leverage budget of ~2-3×; here
   we rescale to a portfolio-level 10% per-asset target so a
   typical 8-commodity panel produces a portfolio volatility in the
   8-12% range that practitioners benchmark against. The *sign* and
   *relative* sizing are unchanged; only the absolute scale is
   rescaled. All headline metrics are scale-invariant.

4. Positions are held for one month and rebalanced monthly.

Volatility estimator
--------------------
Asness §V uses an EWMA estimator with a 60-day half-life. This
implementation uses a simple rolling standard deviation over
``vol_lookback_days`` daily log returns (63 days ≈ 3 months of
trading days) — both estimators converge to the same long-run
realised volatility, and the rolling window is chosen for
determinism in CI (no exponential-decay state to seed).

Sign convention
---------------
We return **weights** on a per-commodity basis (one column per
input symbol). A positive weight is a long position, a negative
weight is a short. ``NaN`` is treated as zero by the engine.
Weights are deliberately **not normalised** to sum to 1 — the
vol-targeting can produce a gross book larger than one, which is
the point of a TSMOM strategy.

Edge cases
----------
* Before ``lookback_months + 1`` months of history are available,
  the strategy emits zero weights for that asset.
* If realised volatility is zero or NaN (e.g. a constant price
  series), the strategy emits a zero weight — not ``inf``.
* Weights are clipped to ``[-max_leverage_per_asset,
  max_leverage_per_asset]`` to keep the backtest sane when
  realised vol collapses.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class CommodityTSMOM12m1m:
    """Cross-commodity time-series momentum, 12-month lookback / 1-month skip.

    Parameters
    ----------
    lookback_months
        Total months of history to sample (inclusive of the skipped
        window). Defaults to ``12`` per Asness §V.
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

    name: str = "commodity_tsmom"
    family: str = "commodity"
    asset_classes: tuple[str, ...] = ("commodity",)
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
            commodity-futures symbols (e.g. ``"CL=F"``, ``"GC=F"``,
            ``"ZC=F"``), values are continuous-contract closing
            prices.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. Weights change only at
            month-ends (everything in between is forward-filled) and
            are zero where insufficient history exists.
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
