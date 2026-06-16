"""Time-series momentum with continuous, t-statistic-scaled signal.

Paper
-----
Hurst, B., Ooi, Y. H. & Pedersen, L. H. (2017).
*A Century of Evidence on Trend-Following Investing*.
AQR Capital Management. SSRN 2993026.
https://doi.org/10.2139/ssrn.2993026

What changes vs. ``tsmom_12_1``
-------------------------------
MOP (2012) used a *discrete* ``sign()`` of the lookback return; the
position is ±1 for every asset and all the interesting variation comes
from the vol-scalar. HOP (2017) extend this to a *continuous* signal
whose magnitude encodes the *strength* of the trend, not just its
direction. Concretely, we build a t-statistic-style z-score of the
lookback monthly returns:

    z_i,t = mean(monthly_returns_i, lookback window)
            / std (monthly_returns_i, lookback window)

and then saturate it through ``tanh`` to get a bounded, smooth signal:

    signal_i,t = tanh(signal_scale * z_i,t)      ∈ (-1, +1)

Finally we apply the MOP vol scalar on top:

    weight_i,t = signal_i,t * (vol_target / realised_vol_i,t)

Intuition: a strong, steady uptrend has a large positive z-score and
``tanh`` saturates at +1, so the weight equals the MOP target-vol
ratio. A weak or choppy uptrend has a small z-score (mean ≪ std), so
the weight is deliberately *smaller* than MOP would produce. This
damps the gross book during regime-change periods and is the main
reason HOP (2017) show better drawdown profiles than vanilla MOP on
decade-scale tests.

Why ``tanh``?
-------------
* Continuous, monotone, odd function — preserves the sign convention.
* Saturates smoothly at ±1 so vol-scaling alone (not the signal)
  determines the maximum gross exposure.
* One scalar hyper-parameter (``signal_scale``) controls the
  "aggressiveness" of the saturation without introducing regime breaks.

Other common smoothing choices include arctan and clipped linear; tanh
is the most common in the trend-following literature (see Levine &
Pedersen 2016, Baltas & Kosowski 2013).
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


class TimeSeriesMomentumVolScaled:
    """Time-series momentum with a continuous t-statistic signal.

    Parameters
    ----------
    lookback_months
        Total months of history to sample (inclusive of the skipped window).
        Defaults to ``12``.
    skip_months
        Number of most-recent months to *skip* when computing the lookback
        statistics. Defaults to ``1``.
    vol_target_annual
        Per-asset annualised vol target used for position sizing.
        Defaults to ``0.10``.
    vol_lookback_days
        Window for the rolling realised-vol estimator. Defaults to
        ``63`` trading days (~3 months).
    annualization
        Periods per year used to annualise daily vol. Defaults to ``252``.
    max_leverage_per_asset
        Safety cap on the gross per-asset weight. Defaults to ``3.0``.
    signal_scale
        Multiplicative scale on the z-score before ``tanh``. Values
        greater than 1 sharpen the saturation (more aggressive trend
        following); values less than 1 soften it. Defaults to ``1.0``.
    """

    name: str = "tsmom_volscaled"
    family: str = "trend"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity")
    paper_doi: str = "10.2139/ssrn.2993026"
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
        signal_scale: float = 1.0,
    ) -> None:
        if lookback_months <= 0:
            raise ValueError(f"lookback_months must be positive, got {lookback_months}")
        if skip_months < 0:
            raise ValueError(f"skip_months must be non-negative, got {skip_months}")
        if skip_months >= lookback_months:
            raise ValueError(
                f"skip_months ({skip_months}) must be < lookback_months ({lookback_months})"
            )
        if lookback_months - skip_months < 2:
            raise ValueError(
                "effective window (lookback_months - skip_months) must be >= 2 "
                "so that a rolling std can be computed"
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
        if signal_scale <= 0:
            raise ValueError(f"signal_scale must be positive, got {signal_scale}")

        self.lookback_months = lookback_months
        self.skip_months = skip_months
        self.vol_target_annual = vol_target_annual
        self.vol_lookback_days = vol_lookback_days
        self.annualization = annualization
        self.max_leverage_per_asset = max_leverage_per_asset
        self.signal_scale = signal_scale

    # ------------------------------------------------------------------
    # StrategyProtocol.generate_signals
    # ------------------------------------------------------------------
    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return a target-weights DataFrame aligned to ``prices``."""
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        # 1. Daily log returns and rolling realised vol (annualised).
        daily_log_returns = np.log(prices / prices.shift(1))
        daily_vol = daily_log_returns.rolling(self.vol_lookback_days).std(ddof=1) * np.sqrt(
            self.annualization
        )

        # 2. Monthly returns for the z-score signal.
        month_end_prices = prices.resample("ME").last()
        monthly_log_returns = np.log(month_end_prices / month_end_prices.shift(1))

        effective_window = self.lookback_months - self.skip_months
        roll_mean = monthly_log_returns.rolling(effective_window).mean().shift(self.skip_months)
        roll_std = monthly_log_returns.rolling(effective_window).std(ddof=1).shift(self.skip_months)

        # 3. t-statistic-style z-score. Guard against zero std.
        with np.errstate(divide="ignore", invalid="ignore"):
            z_score = roll_mean / roll_std
        z_score = z_score.replace([np.inf, -np.inf], np.nan)

        # 4. tanh saturation → continuous signal in (-1, +1). Numpy
        #    ufuncs preserve DataFrame identity via __array_ufunc__,
        #    but we cast for mypy strict.
        signal_np = np.tanh(self.signal_scale * z_score.to_numpy())
        signal = pd.DataFrame(signal_np, index=z_score.index, columns=z_score.columns)

        # 5. Monthly realised vol scalar.
        monthly_vol = daily_vol.resample("ME").last()
        with np.errstate(divide="ignore", invalid="ignore"):
            vol_scalar = self.vol_target_annual / monthly_vol
        vol_scalar = vol_scalar.replace([np.inf, -np.inf], np.nan)

        # 6. Combine, clip to leverage cap, forward-fill to daily.
        monthly_weights = signal * vol_scalar
        monthly_weights = monthly_weights.clip(
            lower=-self.max_leverage_per_asset,
            upper=self.max_leverage_per_asset,
        )

        daily_weights = monthly_weights.reindex(prices.index).ffill().fillna(0.0)
        return cast(pd.DataFrame, daily_weights)
