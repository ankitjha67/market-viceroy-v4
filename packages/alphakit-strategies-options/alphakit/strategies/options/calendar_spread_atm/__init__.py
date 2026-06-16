"""calendar_spread_atm — short front-month ATM call + long back-month ATM call.

Foundational + Primary: Goyal, A. & Saretto, A. (2009).
*Cross-Section of Option Returns and Volatility*, Journal of
Finance 64(4), 1857-1898.
DOI: https://doi.org/10.1111/j.1540-6261.2009.01493.x
"""

from __future__ import annotations

from alphakit.strategies.options.calendar_spread_atm.strategy import CalendarSpreadATM

__all__ = ["CalendarSpreadATM"]
