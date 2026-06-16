"""AlphaKit core package: protocols, data, instruments, portfolio, metrics.

This package defines the thin, stable interface that every AlphaKit strategy,
engine bridge and data adapter consumes. Everything downstream (strategies,
bridges, data adapters) depends on ``alphakit.core`` — but ``alphakit.core``
never depends on them.
"""

from __future__ import annotations

from alphakit.core.data.bar import Bar
from alphakit.core.instruments.base import Instrument
from alphakit.core.portfolio.portfolio import Portfolio
from alphakit.core.protocols import (
    BacktestEngineProtocol,
    DataFeedProtocol,
    StrategyProtocol,
)
from alphakit.core.signals.signal import Signal

__all__ = [
    "BacktestEngineProtocol",
    "Bar",
    "DataFeedProtocol",
    "Instrument",
    "Portfolio",
    "Signal",
    "StrategyProtocol",
]

__version__ = "0.0.1"
