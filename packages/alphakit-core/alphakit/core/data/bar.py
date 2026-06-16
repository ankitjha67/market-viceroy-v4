"""OHLCV bar schema.

A :class:`Bar` is the atomic unit of vectorised-engine input. It is
immutable, strictly validated, and cheap to construct from a pandas row.

Invariants enforced at construction time
----------------------------------------
* ``high >= low``
* ``high >= open`` and ``high >= close``
* ``low  <= open`` and ``low  <= close``
* ``volume >= 0``
* all prices are finite (no ``NaN``, no ``inf``)

Violations raise a ``pydantic.ValidationError`` — by design. A silently
accepted malformed bar is a much more expensive failure than a noisy one.
"""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Bar(BaseModel):
    """A single OHLCV bar for one symbol at one timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    """Bar close time in UTC (or tz-aware if the feed provides tz)."""

    symbol: str = Field(min_length=1, max_length=32)
    """Instrument symbol (ticker, contract code, etc.)."""

    open: float = Field(ge=0.0)
    """Opening price. ``>= 0``."""

    high: float = Field(ge=0.0)
    """High price. ``>= max(open, close)``."""

    low: float = Field(ge=0.0)
    """Low price. ``<= min(open, close)``."""

    close: float = Field(ge=0.0)
    """Closing price. ``>= 0``."""

    volume: float = Field(ge=0.0)
    """Volume in contracts / shares / base-currency units. ``>= 0``."""

    @model_validator(mode="after")
    def _check_ohlc_consistency(self) -> Bar:
        """Enforce OHLC consistency and finiteness."""
        for field_name in ("open", "high", "low", "close", "volume"):
            value = getattr(self, field_name)
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value!r}")
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) < low ({self.low})")
        if self.high < self.open or self.high < self.close:
            raise ValueError(
                f"high ({self.high}) must be >= open ({self.open}) and close ({self.close})"
            )
        if self.low > self.open or self.low > self.close:
            raise ValueError(
                f"low ({self.low}) must be <= open ({self.open}) and close ({self.close})"
            )
        return self
