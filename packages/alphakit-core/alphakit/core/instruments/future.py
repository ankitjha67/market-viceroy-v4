"""Futures instrument (including continuous contracts)."""

from __future__ import annotations

from datetime import date

from alphakit.core.instruments.base import AssetClass, Instrument
from pydantic import Field, model_validator


class Future(Instrument):
    """An exchange-listed futures contract.

    Both dated contracts (``expiry`` set) and continuous contracts
    (``expiry=None``) are supported. Continuous contracts are synthetic
    and should carry the splicing method in the ``notes`` field for audit.
    """

    asset_class: AssetClass = Field(default=AssetClass.FUTURE, frozen=True)

    root: str = Field(min_length=1, max_length=8)
    """Root symbol — e.g. ``"ES"`` for S&P E-mini, ``"CL"`` for WTI crude."""

    expiry: date | None = None
    """Expiration date. ``None`` means this is a continuous contract."""

    tick_size: float = Field(gt=0.0)
    """Minimum price increment in contract points."""

    multiplier: float = Field(gt=0.0)
    """Dollar value of one point move."""

    sector: str | None = Field(default=None, max_length=32)
    """High-level sector: ``"equity_index"``, ``"rates"``, ``"fx"``,
    ``"energy"``, ``"metals"``, ``"grains"``, ``"softs"``, ``"livestock"``..."""

    splicing_method: str | None = Field(default=None, max_length=32)
    """For continuous contracts: ``"panama"``, ``"ratio"``, ``"calendar"``..."""

    @model_validator(mode="after")
    def _check_continuous_consistency(self) -> Future:
        if self.expiry is None and self.splicing_method is None:
            raise ValueError("continuous future (expiry=None) must declare a splicing_method")
        return self
