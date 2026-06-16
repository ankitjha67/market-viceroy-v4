"""Equity (common stock / ADR / ETF) instrument."""

from __future__ import annotations

from alphakit.core.instruments.base import AssetClass, Instrument
from pydantic import Field


class Equity(Instrument):
    """A common stock, ADR, or equity ETF."""

    asset_class: AssetClass = Field(default=AssetClass.EQUITY, frozen=True)

    sector: str | None = Field(default=None, max_length=64)
    """GICS sector, if known."""

    industry: str | None = Field(default=None, max_length=128)
    """GICS industry, if known."""

    market_cap_usd: float | None = Field(default=None, ge=0.0)
    """Market capitalisation in USD, if known."""

    is_etf: bool = False
    """``True`` for ETFs / ETNs, ``False`` for common stock."""

    country: str | None = Field(default=None, min_length=2, max_length=3)
    """ISO 3166 alpha-2 or alpha-3 country code of primary listing."""
