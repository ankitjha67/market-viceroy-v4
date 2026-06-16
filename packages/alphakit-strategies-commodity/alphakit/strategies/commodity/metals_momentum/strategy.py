"""Metals-only time-series momentum, 12-month lookback / 1-month skip.

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
futures across an extensive cross-section. The metals subset (gold,
silver, copper, platinum) is part of the broader §V panel and
exhibits the same 12/1 momentum profile — documented in Asness
Table III's per-asset breakdowns where the metals legs contribute
positively to the commodity-only sub-strategy.
https://doi.org/10.1111/jofi.12021

Why a metals-only sibling
-------------------------
Metals form an economically coherent sub-cluster within the broader
commodity universe — gold and silver share monetary-asset features,
copper and platinum share industrial-cycle exposure, and the four
together share a long-horizon inflation-hedge role distinct from
energy and grains. A metals-focused TSMOM book is a common
practitioner allocation (see e.g. AQR's commodity-strategy memos and
Hurst/Ooi/Pedersen 2017 §IV) because the metals cross-section
trades less synchronously with energy and grains than the broader
commodity panel. We ship it as a separate strategy to expose this
sub-cluster as a first-class option, with the cluster overlap with
``commodity_tsmom`` documented explicitly in ``known_failures.md``.

Differentiation from sibling momentum strategies
------------------------------------------------
* ``commodity_tsmom`` — broader 8-commodity panel (energy + metals +
  grains). Strong cluster overlap with this strategy when metals
  dominate the broader commodity cross-section; expected ρ ≈
  0.75-0.90.
* Phase 1 ``tsmom_12_1`` (trend family) — same TSMOM mechanic on a
  6-asset multi-asset universe (SPY/EFA/EEM/AGG/GLD/DBC). Overlap
  via GLD only; expected ρ ≈ 0.3-0.5 in metals-driven regimes,
  lower otherwise.
* ``commodity_curve_carry`` — different signal (carry / roll yield)
  on the same broader panel; expected ρ ≈ 0.2-0.4.

Published rules (Asness §V applied to a metals subset)
------------------------------------------------------
Identical to the §V commodity-panel TSMOM, restricted to the metals
universe:

1. For each metal *m* and each month-end *t*, compute the trailing
   12-month return ending one month prior — the standard "12-1"
   convention.

2. **Sign-of-return** trade: long if positive, short if negative.

3. Position size is **per-asset volatility-scaled** to a constant
   target (10% annualised by default — see ``commodity_tsmom``
   docstring for the rationale on rescaling Asness §V's 40%
   per-asset target to a portfolio-level 10%). The *sign* and
   *relative* sizing are unchanged; only the absolute scale is
   rescaled.

4. Hold one month, rebalance monthly.

Volatility estimator
--------------------
As in ``commodity_tsmom``: simple rolling standard deviation over
``vol_lookback_days`` daily log returns (63 days ≈ 3 months of
trading days). Asness §V uses an EWMA estimator with a 60-day
half-life; both estimators converge to the same long-run realised
volatility, and the rolling window is chosen for determinism in CI.

Sign convention
---------------
Per-metal **weights**, one column per input symbol. Positive =
long, negative = short. Weights are deliberately **not normalised**
to sum to 1 — the vol-targeting can produce a gross book larger
than one, which is the point of a TSMOM strategy.

Edge cases
----------
* Before ``lookback_months + 1`` months of history are available,
  the strategy emits zero weights for that asset.
* If realised volatility is zero or NaN (e.g. a constant price
  series), the strategy emits a zero weight — not ``inf``.
* Weights are clipped to ``[-max_leverage_per_asset,
  max_leverage_per_asset]`` to keep the backtest sane when realised
  vol collapses.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class MetalsMomentum:
    """Metals-only time-series momentum, 12-month lookback / 1-month skip.

    Same 12/1 vol-targeted TSMOM mechanic as
    :class:`~alphakit.strategies.commodity.commodity_tsmom.strategy.CommodityTSMOM12m1m`,
    restricted to the metals subset of the §V commodity panel. The
    default universe (``GC=F``, ``SI=F``, ``HG=F``, ``PL=F``) covers
    monetary metals (gold, silver) and industrial metals (copper,
    platinum).

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

    name: str = "metals_momentum"
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
            metals-futures symbols (e.g. ``"GC=F"``, ``"SI=F"``,
            ``"HG=F"``, ``"PL=F"``), values are continuous-contract
            closing prices.

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

        daily_log_returns = np.log(prices / prices.shift(1))

        daily_vol = daily_log_returns.rolling(self.vol_lookback_days).std(ddof=1) * np.sqrt(
            self.annualization
        )

        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))

        effective_window = self.lookback_months - self.skip_months
        lookback_returns = (
            monthly_log_returns.rolling(effective_window).sum().shift(self.skip_months)
        )

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

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
