"""Source adapters for the Failover Governor.

Crypto: :class:`~mv.failover.adapters.ccxt_feed.CcxtBarFeed`. Phase-6 breadth:
US (:class:`FinnhubBarFeed`, :class:`AlpacaBarFeed`), India
(:class:`AngelOneBarFeed`), FX (:class:`FrankfurterRateFeed`). All implement the
:class:`~mv.failover.feed.BarFeed` contract.
"""

from __future__ import annotations

from mv.failover.adapters.alpaca_feed import AlpacaBarFeed
from mv.failover.adapters.angelone_feed import AngelOneBarFeed
from mv.failover.adapters.ccxt_feed import CcxtBarFeed
from mv.failover.adapters.finnhub_feed import FinnhubBarFeed
from mv.failover.adapters.frankfurter_feed import FrankfurterRateFeed

__all__ = [
    "AlpacaBarFeed",
    "AngelOneBarFeed",
    "CcxtBarFeed",
    "FinnhubBarFeed",
    "FrankfurterRateFeed",
]
