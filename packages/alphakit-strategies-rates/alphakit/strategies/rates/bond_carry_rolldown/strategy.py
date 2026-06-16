"""Bond carry-and-rolldown — single-asset duration positioning conditional on curve slope.

Implementation notes
====================

Foundational paper
------------------
Fama, E. F. (1984).
*Forward rates as predictors of future spot rates*. Journal of
Financial Economics, 13(4), 509–528.
https://doi.org/10.1016/0304-405X(84)90013-8

Establishes that forward rates contain a non-zero term premium —
i.e. the unbiased-expectations hypothesis is rejected, and holding
period returns on long bonds vs short bonds are forecastable from
the slope of the curve.

Primary methodology
-------------------
Koijen, R. S. J., Moskowitz, T. J., Pedersen, L. H. & Vrugt, E. B.
(2018). *Carry*. Journal of Financial Economics, 127(2), 197–225.
https://doi.org/10.1016/j.jfineco.2017.11.002

Defines an asset's *carry* as the return it would earn if prices stayed
constant. For a coupon bond held to a sub-maturity horizon, that is
the current yield plus the *roll-down* — the price appreciation from
moving to a shorter point on a (positively-sloped) yield curve as the
bond ages. KMPV (2018) show that carry is a robust, persistent and
priced source of expected return across asset classes including bonds.

Why two papers
--------------
Fama (1984) provides the *foundational* term-premium-existence result.
Koijen et al. (2018) operationalise it into a tradeable carry signal
with a uniform definition that applies across asset classes. The
implementation here is a single-asset *time-series* version of the
KMPV bond-carry framework: rather than ranking many bonds cross-
sectionally (as KMPV does), it conditions a single-bond duration
position on whether the realised carry-and-rolldown (proxied by the
curve slope) is currently elevated vs history.

Cross-reference: ``packages/alphakit-strategies-carry/.../bond_carry_roll/``
in the carry family is the *cross-sectional* version of the same
KMPV framework. This rates-family strategy is the *time-series*
version on a single bond, anchored on the slope of the curve rather
than on a cross-section of bond returns. They share the foundational
intuition but trade orthogonal information.

Differentiation from the curve-steepener
----------------------------------------
The 2s10s steepener trades **mean-reversion of the slope itself**:
enter when the slope is *flat* (yield spread is narrow), bet on
re-steepening. ``bond_carry_rolldown`` does the *opposite* — enter
when the slope is *steep* (yield spread is wide), bet on capturing
the elevated carry while it persists. The two strategies are
complementary, not redundant; their expected ρ is moderately
*negative* in regimes where mean-reversion realises (steepener wins
when the spread narrows; carry-rolldown loses the same realisation),
and moderately *positive* in regimes where the spread persists
(steepener bleeds carry, carry-rolldown captures it).

Carry-and-rolldown signal
-------------------------
Direct yield curve construction is data-hungry; this implementation
uses a price-space proxy that is monotone in the curve slope. For
2-column ``prices`` ``[short_end, target_long_bond]``::

    log_spread = log(P_target) − log(P_short)

A *high* positive ``log_spread`` corresponds to the long-end having
out-performed the short-end recently — i.e. the yield spread is
*narrow* (curve is flat). Holding the long bond at a flat curve
yields zero rolldown and only the current yield: low expected
carry-rolldown.

A *low* negative ``log_spread`` corresponds to the long-end having
under-performed (or the curve having steepened) — i.e. the yield
spread is *wide*. Holding the long bond at a steep curve gives
positive rolldown plus the elevated long yield: high expected
carry-rolldown.

The signal is therefore::

    z = (log_spread − rolling_mean) / rolling_std
    long target_bond when z < −entry_threshold (steep curve, high carry)
    flat              when z > −exit_threshold

Position sizing
---------------
Single-asset trade. When entered, the strategy puts unit weight on
the target bond and zero on the short-end column (the short-end is
informational only — used to compute the slope proxy, not to take a
position). This is the simplest possible duration overlay; it is
*not* DV01-neutral and does carry parallel-shift exposure by design.
Users wanting a parallel-shift hedge should pair this with the
flattener or use a portfolio overlay.

Edge cases
----------
* Before ``zscore_window`` daily bars are available, the strategy
  emits zero weights.
* Constant prices on the slope proxy emit zero weights.
* The signal is event-driven; the position can flip from active to
  flat (or vice versa) on any bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class BondCarryRolldown:
    """Single-asset bond duration positioning conditional on curve slope.

    Parameters
    ----------
    zscore_window
        Trailing window for the slope proxy z-score (default ``252``).
    entry_threshold
        Z-score absolute threshold for entry (default ``1.0``). The
        position activates when ``z < −entry_threshold`` (steep curve,
        elevated carry).
    exit_threshold
        Z-score absolute threshold for exit (default ``0.25``). Hysteresis
        avoids whipsaw flips around the entry boundary.
    """

    name: str = "bond_carry_rolldown"
    family: str = "rates"
    asset_classes: tuple[str, ...] = ("bond",)
    paper_doi: str = "10.1016/j.jfineco.2017.11.002"  # KMPV 2018
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        zscore_window: int = 252,
        entry_threshold: float = 1.0,
        exit_threshold: float = 0.25,
    ) -> None:
        if zscore_window < 30:
            raise ValueError(f"zscore_window must be >= 30, got {zscore_window}")
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be positive, got {entry_threshold}")
        if exit_threshold < 0:
            raise ValueError(f"exit_threshold must be non-negative, got {exit_threshold}")
        if exit_threshold >= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be < entry_threshold "
                f"({entry_threshold}) for the entry/exit hysteresis to be well-defined"
            )

        self.zscore_window = zscore_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return long-only target-bond weights aligned to ``prices``.

        Parameters
        ----------
        prices
            Two-column DataFrame indexed by daily timestamps. Column
            order: short-end (informational, used to compute the slope
            proxy), target long bond (the actual position).

        Returns
        -------
        weights
            DataFrame aligned to ``prices``. The short-end column is
            always zero (no position taken). The target-bond column is
            +1.0 when the curve is steep enough (carry signal active)
            and 0.0 otherwise.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if prices.shape[1] != 2:
            raise ValueError(
                f"prices must have exactly 2 columns (short-end, target_long), "
                f"got {prices.shape[1]}"
            )
        if (prices <= 0).any().any():
            raise ValueError("prices must be strictly positive")

        short_col, target_col = prices.columns[0], prices.columns[1]
        log_spread = np.log(prices[target_col]) - np.log(prices[short_col])

        rolling_mean = log_spread.rolling(self.zscore_window).mean()
        rolling_std = log_spread.rolling(self.zscore_window).std(ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            zscore = (log_spread - rolling_mean) / rolling_std
        zscore = zscore.replace([np.inf, -np.inf], np.nan)

        signal = np.zeros(len(prices), dtype=np.float64)
        active = False
        z_arr = zscore.to_numpy()
        for i in range(len(z_arr)):
            if np.isnan(z_arr[i]):
                signal[i] = 0.0
                continue
            if not active and z_arr[i] < -self.entry_threshold:
                active = True
            elif active and z_arr[i] > -self.exit_threshold:
                active = False
            signal[i] = 1.0 if active else 0.0

        return pd.DataFrame(
            {short_col: np.zeros(len(prices)), target_col: signal},
            index=prices.index,
        )
