"""Crypto pair instrument (spot / perpetual / dated)."""

from __future__ import annotations

from datetime import date
from enum import Enum

from alphakit.core.instruments.base import AssetClass, Instrument
from pydantic import Field, model_validator


class CryptoKind(str, Enum):
    """Which kind of crypto derivative (or spot)."""

    SPOT = "spot"
    PERP = "perp"  # perpetual swap
    DATED = "dated"  # dated future
    OPTION = "option"


class CryptoPair(Instrument):
    """A crypto trading pair on a specific exchange.

    Covers spot (``BTC/USDT``), perpetuals (``BTC-USDT-PERP``) and dated
    futures (``BTC-27SEP24``). Crypto options live in the separate
    :class:`Option` model since their expiry / strike semantics are the
    same as equity options.
    """

    asset_class: AssetClass = Field(default=AssetClass.CRYPTO, frozen=True)

    base: str = Field(min_length=1, max_length=16)
    """Base asset symbol (e.g. ``"BTC"``, ``"ETH"``)."""

    quote: str = Field(min_length=1, max_length=16)
    """Quote asset symbol (e.g. ``"USDT"``, ``"USD"``, ``"USDC"``)."""

    kind: CryptoKind = CryptoKind.SPOT
    """Spot, perpetual, or dated. Defaults to spot."""

    expiry: date | None = None
    """For dated futures only. Must be ``None`` for spot and perp."""

    @model_validator(mode="after")
    def _check_expiry_consistency(self) -> CryptoPair:
        if self.kind == CryptoKind.DATED and self.expiry is None:
            raise ValueError("dated crypto future must have an expiry")
        if self.kind in (CryptoKind.SPOT, CryptoKind.PERP) and self.expiry is not None:
            raise ValueError(f"{self.kind.value} must not have an expiry")
        if self.base.upper() == self.quote.upper():
            raise ValueError(f"base and quote must differ, got {self.base!r}")
        return self
