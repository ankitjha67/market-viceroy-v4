"""Soybean-crush-spread mean-reversion trade.

Foundational: Working, H. (1949), *The Theory of Price of Storage*,
American Economic Review 39(6), 1254–1262. The original storage-
theory exposition that grounds physical-arbitrage spread trades.

Primary methodology: Simon, D. P. (1999), *The Soybean Crush
Spread: Empirical Evidence and Trading Strategies*, Journal of
Futures Markets 19(3), 271–289. Documents the soybean crush as a
mean-reverting risk-arbitrage trade between soybeans (ZS), soybean
meal (ZM), and soybean oil (ZL).
DOI: https://doi.org/10.1002/(SICI)1096-9934(199905)19:3<271::AID-FUT2>3.0.CO;2-S
"""

from __future__ import annotations

from alphakit.strategies.commodity.crush_spread.strategy import CrushSpread

__all__ = ["CrushSpread"]
