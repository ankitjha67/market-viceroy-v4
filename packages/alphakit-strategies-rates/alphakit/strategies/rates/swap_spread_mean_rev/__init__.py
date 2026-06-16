"""Swap-Treasury spread mean-reversion via z-score on the log-price spread.

Foundational: Liu, Longstaff & Mandell (2006), *The Market Price of
Risk in Interest Rate Swaps*, Journal of Business 79(5).
DOI: https://doi.org/10.1086/505250

Primary methodology: Duarte, Longstaff & Yu (2007), *Risk and Return
in Fixed-Income Arbitrage: Nickels in Front of a Steamroller?*,
Review of Financial Studies 20(3), 769–811.
DOI: https://doi.org/10.1093/rfs/hhl026
"""

from __future__ import annotations

from alphakit.strategies.rates.swap_spread_mean_rev.strategy import SwapSpreadMeanRev

__all__ = ["SwapSpreadMeanRev"]
