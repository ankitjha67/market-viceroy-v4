"""Constrained, executable arbitrage (PRD §1.2, US-011, BR-007).

Executable scope: crypto cross-exchange, funding-rate, and triangular — every
edge shown after fees/slippage/transfer with a Red/Amber/Green executability
flag. Cross-border dislocations are monitor-only (never executable). See
:mod:`.cross_exchange`, :mod:`.funding_rate`, :mod:`.triangular`, :mod:`.engine`.
"""

from __future__ import annotations

from mv.intelligence.arbitrage.cross_exchange import VenueQuote, detect_cross_exchange
from mv.intelligence.arbitrage.engine import (
    cross_border_monitor,
    rank_opportunities,
    serialize,
)
from mv.intelligence.arbitrage.executability import (
    ArbOpportunity,
    Executability,
    classify_executability,
)
from mv.intelligence.arbitrage.funding_rate import detect_funding
from mv.intelligence.arbitrage.triangular import detect_triangular

__all__ = [
    "ArbOpportunity",
    "Executability",
    "VenueQuote",
    "classify_executability",
    "cross_border_monitor",
    "detect_cross_exchange",
    "detect_funding",
    "detect_triangular",
    "rank_opportunities",
    "serialize",
]
