"""Ornstein-Uhlenbeck process mean reversion (Avellaneda & Lee 2010).

Reference
---------
Avellaneda, M. & Lee, J.-H. (2010). Statistical Arbitrage in the
US Equities Market. *Quantitative Finance*, 10(7), 761-782.
DOI: 10.1080/14697680902743953.

The OU process models price as mean-reverting with a characteristic
half-life. The strategy estimates the OU parameters via OLS regression
of price changes on lagged price levels, computes the half-life of
mean reversion, and sizes positions proportional to the Z-score of
the OU residual, scaled by the inverse of the half-life.

Rules
-----
For each asset:
  1. Estimate OU parameters: dx = theta*(mu - x)*dt + sigma*dW
  2. Compute half-life = ln(2) / theta
  3. Z-score of deviation from estimated mean
  4. Weight = −Z-score / (n * half_life_scale) clipped to [−1/n, +1/n]
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class OUProcessTrade:
    """OU-process calibration mean reversion — half-life-based sizing."""

    name: str = "ou_process_trade"
    family: str = "meanrev"
    asset_classes: tuple[str, ...] = ("equity", "future", "fx", "commodity", "crypto")
    paper_doi: str = "10.1080/14697680902743953"  # Avellaneda & Lee (2010)
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        lookback: int = 60,
        max_half_life: int = 120,
        long_only: bool = False,
    ) -> None:
        if lookback <= 2:
            raise ValueError(f"lookback must be > 2, got {lookback}")
        if max_half_life <= 0:
            raise ValueError(f"max_half_life must be positive, got {max_half_life}")
        self.lookback = lookback
        self.max_half_life = max_half_life
        self.long_only = long_only

    def _estimate_ou(self, series: np.ndarray) -> tuple[float, float, float]:
        """Estimate OU parameters via OLS: dx = a + b*x + eps.

        Returns (theta, mu, half_life).  theta = -b, mu = -a/b.
        If the estimate is non-mean-reverting (b >= 0), returns
        (0, 0, inf).
        """
        x = series[:-1]
        dx = np.diff(series)
        n = len(dx)
        if n < 3:
            return 0.0, 0.0, float("inf")

        # OLS: dx = a + b * x
        x_mean = x.mean()
        dx_mean = dx.mean()
        ss_xx = float(np.sum((x - x_mean) ** 2))
        if ss_xx < 1e-15:
            return 0.0, 0.0, float("inf")
        ss_xy = float(np.sum((x - x_mean) * (dx - dx_mean)))
        b = ss_xy / ss_xx
        a = dx_mean - b * x_mean

        if b >= 0:
            return 0.0, 0.0, float("inf")

        theta = -b
        mu = -a / b
        half_life = np.log(2) / theta
        return float(theta), float(mu), float(half_life)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        n_assets = len(prices.columns)
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        log_prices = np.log(prices.to_numpy())

        for col_idx, _col in enumerate(prices.columns):
            for i in range(self.lookback, len(prices)):
                window = log_prices[i - self.lookback : i + 1, col_idx]
                _theta, mu, half_life = self._estimate_ou(window)

                if half_life > self.max_half_life or half_life <= 0:
                    continue

                # Z-score of current log-price deviation from OU mean
                current = window[-1]
                std = float(np.std(window, ddof=1))
                if std < 1e-15:
                    continue

                zscore = (current - mu) / std
                # Position proportional to negative z-score, scaled by
                # inverse half-life (faster reversion → larger position)
                raw_weight = -zscore * min(1.0, 10.0 / half_life)
                clipped = float(np.clip(raw_weight, -1.0, 1.0))
                weights.iat[i, col_idx] = clipped / n_assets

        if self.long_only:
            weights = weights.clip(lower=0.0)

        return weights
