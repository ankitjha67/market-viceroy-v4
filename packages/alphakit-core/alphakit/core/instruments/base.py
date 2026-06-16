"""Instrument base class.

Every traded thing in AlphaKit inherits from :class:`Instrument`. The base
is deliberately thin: symbol, exchange, currency, and an ``asset_class``
discriminator. Asset-class-specific detail lives in subclasses.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AssetClass(str, Enum):
    """The 14 asset classes AlphaKit supports across its phases."""

    EQUITY = "equity"
    FUTURE = "future"
    OPTION = "option"
    BOND = "bond"
    RATES = "rates"
    FX = "fx"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    INDEX = "index"
    ETF = "etf"
    CREDIT = "credit"
    VOLATILITY = "volatility"
    STRUCTURED = "structured"
    ALTERNATIVE = "alternative"


class Instrument(BaseModel):
    """Base class for every tradable thing.

    Subclasses add asset-class-specific fields (strike, expiry, multiplier,
    base/quote currency, etc.) but must never override :attr:`asset_class`
    — the discriminator is what the bridge layer uses to route.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=64)
    """Canonical symbol (ticker, contract code, pair name)."""

    exchange: str = Field(min_length=1, max_length=32)
    """Listing / trading venue, e.g. ``"NYSE"``, ``"CME"``, ``"BINANCE"``."""

    currency: str = Field(min_length=3, max_length=8)
    """ISO 4217-style currency code (``"USD"``, ``"EUR"``, ``"USDT"``, ...)."""

    asset_class: AssetClass
    """Discriminator used by the bridge layer for routing."""

    def __str__(self) -> str:
        return f"{self.asset_class.value}:{self.exchange}:{self.symbol}"
