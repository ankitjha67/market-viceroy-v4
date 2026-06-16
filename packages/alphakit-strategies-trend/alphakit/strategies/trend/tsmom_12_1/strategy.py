"""Time-series momentum, 12-month lookback / 1-month skip.

Implementation notes
====================

Paper
-----
Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012).
*Time series momentum*. Journal of Financial Economics, 104(2), 228–250.
https://doi.org/10.1016/j.jfineco.2011.11.003

Published rules
---------------
For each asset and each month *t*:

1. Compute the asset's return over the past 12 months, skipping the
   most recent month. I.e. the signal is built from the return over
   months ``[t-12, t-1)``. Skipping the most recent month sidesteps
   short-term reversal effects documented in Jegadeesh (1990).

2. The **sign** of that lookback return determines whether to be long
   (positive past return) or short (negative past return).

3. Position size is **volatility-scaled** so that every asset contributes
   roughly the same amount of risk. The target volatility in MOP (2012)
   is 40% annualised *per asset*, but that assumes a gross-leverage
   budget; practitioners typically rescale to a portfolio-level target
   (e.g. 10%). We expose ``vol_target_annual`` so the user can pick.

4. Positions are held for one month and rebalanced monthly.

Volatility estimator
--------------------
The original paper uses an exponentially-weighted-moving-average (EWMA)
estimator with a 60-day half-life. This implementation uses a simple
rolling standard deviation over ``vol_lookback_days`` daily log-returns
by default (63 days ≈ 3 months of trading days). Both converge to the
same long-run estimate; the rolling window is chosen here for
*reproducibility* — the weights you get with the default parameters are
deterministic functions of the input prices.

Sign convention
---------------
We return **weights** (not signals): a positive value is a long
position, a negative value is a short. ``NaN`` is treated as zero by
the engine bridges. Weights are deliberately **not normalised** to sum
to 1 — vol targeting can produce a gross book larger than one, which
is the entire point of the strategy.

Edge cases
----------
* Before ``lookback_months + skip_months + 1`` months of history are
  available, the strategy emits zero weights for that asset.
* If realised volatility is zero or NaN (e.g. a constant price series),
  the strategy emits a zero weight — not ``inf``.
* Weights are clipped to ``[-max_leverage_per_asset, max_leverage_per_asset]``
  to keep the backtest sane when realised vol collapses towards zero.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class TimeSeriesMomentum12m1m:
    """Time-series momentum with 12-month lookback and 1-month skip.

    Parameters
    ----------
    lookback_months
        Total months of history to sample (inclusive of the skipped window).
        Defaults to ``12`` per the original paper.
    skip_months
        Number of most-recent months to *skip* when computing the lookback
        return (the "12-1" convention). Defaults to ``1``.
    vol_target_annual
        Per-asset annualised volatility target used for position sizing.
        Defaults to ``0.10`` (10%).
    vol_lookback_days
        Window for the rolling realised-vol estimator. Defaults to
        ``63`` trading days (~3 months).
    annualization
        Periods per year used to annualise daily vol. ``252`` for daily
        bars (default), ``52`` for weekly, ``12`` for monthly.
    max_leverage_per_asset
        Safety cap on the gross per-asset weight. Defaults to ``3.0`` so
        that a collapse in realised vol cannot send weights to infinity.
    """

    # Instance-level metadata declared as class defaults. Tuples are
    # immutable so this is a safe default (ruff RUF012 only flags
    # mutable defaults like list/dict/set). The runtime Protocol check
    # in StrategyProtocol still sees these as instance attributes.
    name: str = "tsmom_12_1"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity")
    paper_doi: str = "10.1016/j.jfineco.2011.11.003"
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

    # ------------------------------------------------------------------
    # StrategyProtocol.generate_signals
    # ------------------------------------------------------------------
    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a target-weights DataFrame for ``prices``.

        Parameters
        ----------
        prices
            DataFrame indexed by (ideally daily) timestamps, columns are
            instrument symbols, values are adjusted close prices.

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. Weights change only at
            month-ends (everything in between is forward-filled) and are
            zero where insufficient history exists.
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

        # 2. Rolling realised vol, annualised. This is still on the daily
        #    grid; we'll resample to month-end in step 5.
        daily_vol = daily_log_returns.rolling(self.vol_lookback_days).std(ddof=1) * np.sqrt(
            self.annualization
        )

        # 3. Month-end prices → monthly log returns.
        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))

        # 4. Lookback return: sum of log returns over months
        #    [t - lookback_months, t - skip_months).
        effective_window = self.lookback_months - self.skip_months
        lookback_returns = (
            monthly_log_returns.rolling(effective_window).sum().shift(self.skip_months)
        )

        # 5. Direction + vol scaling, both evaluated at month-ends.
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

        # 6. Forward-fill to the full daily index and zero-fill any remaining
        #    leading NaNs (the warm-up window). Cast is needed because
        #    pandas-stubs declares the ffill/fillna chain as returning Any.
        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
