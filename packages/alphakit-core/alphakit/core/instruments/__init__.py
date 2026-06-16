"""Instrument hierarchy.

All instruments inherit from :class:`Instrument` and are immutable pydantic
v2 models. Strategies should declare which asset classes they support via
:attr:`StrategyProtocol.asset_classes`, and the bridge layer will refuse to
dispatch a strategy onto an unsupported instrument type.
"""

from __future__ import annotations

from alphakit.core.instruments.base import AssetClass, Instrument
from alphakit.core.instruments.crypto import CryptoKind, CryptoPair
from alphakit.core.instruments.equity import Equity
from alphakit.core.instruments.future import Future
from alphakit.core.instruments.fx import FXPair, FXTenor
from alphakit.core.instruments.option import Option, OptionStyle

__all__ = [
    "AssetClass",
    "CryptoKind",
    "CryptoPair",
    "Equity",
    "FXPair",
    "FXTenor",
    "Future",
    "Instrument",
    "Option",
    "OptionStyle",
]
