"""Option instrument (exchange-listed and OTC)."""

from __future__ import annotations

from datetime import date
from enum import Enum

from alphakit.core.data.option_chain import OptionRight
from alphakit.core.instruments.base import AssetClass, Instrument
from pydantic import Field


class OptionStyle(str, Enum):
    """American vs. European exercise style."""

    AMERICAN = "american"
    EUROPEAN = "european"
    BERMUDAN = "bermudan"


class Option(Instrument):
    """An exchange-listed or OTC option contract."""

    asset_class: AssetClass = Field(default=AssetClass.OPTION, frozen=True)

    underlying: str = Field(min_length=1, max_length=32)
    """Underlying symbol (equity ticker, future code, crypto pair...)."""

    strike: float = Field(gt=0.0)
    """Strike price. Strictly positive."""

    expiry: date
    """Expiration date."""

    right: OptionRight
    """Call or put."""

    style: OptionStyle = OptionStyle.AMERICAN
    """Exercise style. Defaults to American (US equity options)."""

    multiplier: float = Field(default=100.0, gt=0.0)
    """Contract multiplier. 100 for US equity options, 1 for crypto."""
