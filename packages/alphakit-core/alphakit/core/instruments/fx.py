"""FX (foreign exchange) pair instrument."""

from __future__ import annotations

from enum import Enum

from alphakit.core.instruments.base import AssetClass, Instrument
from pydantic import Field, model_validator


class FXTenor(str, Enum):
    """Settlement tenor for an FX deal."""

    SPOT = "spot"
    TN = "tn"  # tom-next
    SN = "sn"  # spot-next
    FORWARD_1W = "1w"
    FORWARD_2W = "2w"
    FORWARD_1M = "1m"
    FORWARD_3M = "3m"
    FORWARD_6M = "6m"
    FORWARD_1Y = "1y"
    NDF = "ndf"  # non-deliverable forward


class FXPair(Instrument):
    """A single FX pair (e.g. ``EURUSD``) at a given tenor."""

    asset_class: AssetClass = Field(default=AssetClass.FX, frozen=True)

    base: str = Field(min_length=3, max_length=4)
    """Base currency (ISO 4217)."""

    quote: str = Field(min_length=3, max_length=4)
    """Quote / counter currency (ISO 4217)."""

    tenor: FXTenor = FXTenor.SPOT
    """Settlement tenor. Defaults to spot."""

    @model_validator(mode="after")
    def _check_base_ne_quote(self) -> FXPair:
        if self.base.upper() == self.quote.upper():
            raise ValueError(f"base and quote must differ, got {self.base!r}")
        return self
