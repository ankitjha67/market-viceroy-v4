"""Reusable technical indicators (PRD FR-I1) — pure, causal, vectorized.

Each function takes a price panel (DatetimeIndex × symbols) and returns a frame
of the same shape. **Causal by construction**: only ``rolling`` / ``ewm`` /
``shift`` over past data, so a value at time *t* never uses *t+1* — these become
point-in-time technical features stamped by the bar time. No new deps.

Indicators were previously inlined per strategy; this is the shared library.
Returns use typed locals because pandas-stubs types ``DataFrame`` arithmetic
loosely (Any).
"""

from __future__ import annotations

import pandas as pd


def sma(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Simple moving average."""
    out: pd.DataFrame = prices.rolling(window, min_periods=window).mean()
    return out


def ema(prices: pd.DataFrame, span: int) -> pd.DataFrame:
    """Exponential moving average (no look-ahead: ``adjust=False``)."""
    out: pd.DataFrame = prices.ewm(span=span, adjust=False, min_periods=span).mean()
    return out


def momentum(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Trailing return over ``window`` bars: ``price_t / price_{t-window} - 1``."""
    out: pd.DataFrame = prices / prices.shift(window) - 1.0
    return out


def rolling_volatility(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling standard deviation of simple returns."""
    returns = prices.pct_change()
    out: pd.DataFrame = returns.rolling(window, min_periods=window).std()
    return out


def zscore(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling z-score: ``(price - mean) / std`` over ``window``."""
    mean = prices.rolling(window, min_periods=window).mean()
    std = prices.rolling(window, min_periods=window).std()
    out: pd.DataFrame = (prices - mean) / std
    return out


def drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    """Drawdown from the running peak: ``price / cummax - 1`` (<= 0)."""
    out: pd.DataFrame = prices / prices.cummax() - 1.0
    return out


def rsi(prices: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Wilder-style Relative Strength Index in [0, 100]."""
    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(window, min_periods=window).mean()
    avg_loss = loss.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    out: pd.DataFrame = 100.0 - 100.0 / (1.0 + rs)
    return out


def macd(prices: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.DataFrame:
    """MACD line: ``EMA(fast) - EMA(slow)``."""
    out: pd.DataFrame = ema(prices, fast) - ema(prices, slow)
    return out


def bollinger_percent_b(
    prices: pd.DataFrame, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Bollinger %b: position within the bands (0 = lower, 1 = upper)."""
    mid = prices.rolling(window, min_periods=window).mean()
    std = prices.rolling(window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    out: pd.DataFrame = (prices - lower) / (upper - lower)
    return out
