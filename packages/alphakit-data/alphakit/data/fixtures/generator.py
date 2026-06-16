"""Synthetic fixture data generator for deterministic benchmarks.

Generates realistic-looking price series with configurable drift
and volatility per asset class. Uses a fixed seed for reproducibility.

These fixtures are used when:
1. Network is unavailable (no yfinance)
2. Deterministic test runs are needed
3. CI benchmark regression checks
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Realistic drift/vol profiles per ticker (annualised)
_PROFILES: dict[str, tuple[float, float]] = {
    # Equities
    "SPY": (0.08, 0.16),
    "QQQ": (0.12, 0.20),
    "EFA": (0.04, 0.17),
    "EEM": (0.03, 0.22),
    "IWM": (0.07, 0.20),
    # Bonds
    "AGG": (0.02, 0.04),
    "TLT": (0.03, 0.14),
    "HYG": (0.04, 0.08),
    # Commodities
    "GLD": (0.05, 0.15),
    "DBC": (0.01, 0.18),
    "USO": (-0.02, 0.35),
    # Volatility
    "VIXY": (-0.40, 0.70),
    # FX (as USD-denominated indices)
    "AUDUSD": (0.01, 0.10),
    "CADUSD": (0.005, 0.08),
    "CHFUSD": (0.01, 0.09),
    "EURUSD": (0.005, 0.08),
    "GBPUSD": (0.005, 0.09),
    "JPYUSD": (-0.01, 0.09),
    "NOKUSD": (0.005, 0.12),
    "NZDUSD": (0.01, 0.11),
    "SEKUSD": (0.005, 0.11),
    # Crypto
    "BTC-USD": (0.30, 0.60),
    "ETH-USD": (0.25, 0.70),
}

# Default fallback for unknown tickers
_DEFAULT_PROFILE = (0.05, 0.15)


def generate_fixture_prices(
    symbols: list[str],
    start: str = "2005-01-01",
    end: str = "2025-12-31",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic daily price data for the given symbols.

    Returns a DataFrame indexed by business day with adjusted close
    prices that exhibit realistic drift, volatility, and moderate
    correlation between assets.

    Parameters
    ----------
    symbols
        List of ticker symbols.
    start, end
        Date range as ISO strings.
    seed
        Random seed for reproducibility.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="B")
    n_days = len(idx)

    # Generate correlated returns using a simple factor model:
    # r_i = beta_i * f_market + eps_i
    market_factor = rng.normal(0.0003, 0.008, size=n_days)

    prices_dict: dict[str, np.ndarray] = {}
    for i, sym in enumerate(symbols):
        drift, vol = _PROFILES.get(sym, _DEFAULT_PROFILE)
        daily_drift = drift / 252
        daily_vol = vol / np.sqrt(252)

        # Factor loading (0.3-0.8 correlation with market)
        beta = 0.3 + 0.5 * (i % 5) / 4
        idio_vol = daily_vol * np.sqrt(1 - beta**2)

        noise = rng.normal(0, idio_vol, size=n_days)
        returns = daily_drift + beta * market_factor + noise

        # Add occasional vol clusters (GARCH-like)
        vol_state = np.ones(n_days)
        for t in range(1, n_days):
            vol_state[t] = 0.94 * vol_state[t - 1] + 0.06 * (returns[t - 1] ** 2) / (daily_vol**2)
        vol_state = np.clip(vol_state, 0.5, 3.0)
        returns = returns * np.sqrt(vol_state)

        prices = 100.0 * np.exp(np.cumsum(returns))
        prices_dict[sym] = prices

    return pd.DataFrame(prices_dict, index=idx)
