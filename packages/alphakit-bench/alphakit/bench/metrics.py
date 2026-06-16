"""Extended benchmark metrics beyond the core sharpe/sortino/calmar set.

Computes:
- turnover_annual: annualised portfolio turnover from weight changes
- capacity_usd_bn: order-of-magnitude capacity estimate
- regime_performance: bull/bear/sideways Sharpe using trailing vol
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.core.metrics.returns import sharpe_ratio


def turnover_annual(weights: pd.DataFrame, annualization: int = 252) -> float:
    """Annualised single-sided turnover from a weights DataFrame.

    Turnover is the mean absolute weight change per bar, summed across
    assets, then annualised.
    """
    if weights.empty or len(weights) < 2:
        return 0.0
    delta = weights.diff().iloc[1:]
    per_bar = delta.abs().sum(axis=1).mean()
    return float(per_bar * annualization)


def capacity_estimate_bn(
    turnover: float,
    avg_daily_volume_usd: float = 5e9,
    participation_rate: float = 0.01,
) -> float:
    """Order-of-magnitude capacity estimate in USD billions.

    Uses a simple model: capacity = (participation_rate * ADV * 252) / turnover.
    This gives the AUM at which the strategy's trades would consume
    `participation_rate` of daily volume.

    Parameters
    ----------
    turnover
        Annualised single-sided turnover (from :func:`turnover_annual`).
    avg_daily_volume_usd
        Average daily dollar volume of the strategy's universe.
        Default $5B is a rough estimate for a liquid ETF basket.
    participation_rate
        Maximum fraction of daily volume the strategy can consume.
    """
    if turnover <= 0.0:
        return 0.0
    annual_volume = avg_daily_volume_usd * 252
    return float(participation_rate * annual_volume / turnover / 1e9)


def regime_performance(
    returns: pd.Series,
    *,
    vol_window: int = 60,
    bull_threshold: float = 0.15,
    bear_threshold: float = 0.25,
) -> dict[str, float]:
    """Compute Sharpe ratio in bull, bear, and sideways regimes.

    Regimes are classified by trailing realised volatility:
    - Bull: trailing vol < bull_threshold AND cumulative return positive
    - Bear: trailing vol > bear_threshold
    - Sideways: everything else

    Parameters
    ----------
    returns
        Daily portfolio returns (pd.Series with DatetimeIndex).
    vol_window
        Trailing window for vol estimation.
    bull_threshold
        Annualised vol below which the market is "calm" (bull candidate).
    bear_threshold
        Annualised vol above which the market is "stressed" (bear).
    """
    if len(returns) < vol_window + 1:
        return {
            "bull_market_sharpe": 0.0,
            "bear_market_sharpe": 0.0,
            "sideways_sharpe": 0.0,
        }

    trailing_vol = returns.rolling(vol_window).std(ddof=1) * np.sqrt(252)
    cum_ret = (1 + returns).cumprod()
    trailing_ret = cum_ret / cum_ret.shift(vol_window) - 1

    # Classify regimes
    bull_mask = (trailing_vol < bull_threshold) & (trailing_ret > 0)
    bear_mask = trailing_vol > bear_threshold
    sideways_mask = ~bull_mask & ~bear_mask

    def _sharpe(mask: pd.Series) -> float:
        r = returns[mask].dropna()
        if len(r) < 10:
            return 0.0
        return sharpe_ratio(r.to_numpy())

    return {
        "bull_market_sharpe": _sharpe(bull_mask),
        "bear_market_sharpe": _sharpe(bear_mask),
        "sideways_sharpe": _sharpe(sideways_mask),
    }
