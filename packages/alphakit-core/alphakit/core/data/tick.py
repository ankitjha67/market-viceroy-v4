"""Tick (trade / quote update) schema.

A :class:`Tick` represents an individual trade print or a best-bid/best-ask
update. Microstructure strategies (Phase 4) consume millions of these, so
the model is kept deliberately minimal.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TickSide(str, Enum):
    """Which side of the book a tick refers to."""

    BID = "bid"
    ASK = "ask"
    TRADE = "trade"


class Tick(BaseModel):
    """A single trade or quote update."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    """Event time (tz-aware preferred)."""

    symbol: str = Field(min_length=1, max_length=32)
    """Instrument symbol."""

    price: float = Field(gt=0.0)
    """Trade price or quote level. Must be strictly positive."""

    size: float = Field(ge=0.0)
    """Trade size or quoted size. ``>= 0``."""

    side: TickSide
    """Whether this is a bid update, ask update or a trade print."""

    @model_validator(mode="after")
    def _check_finite(self) -> Tick:
        if not math.isfinite(self.price):
            raise ValueError(f"price must be finite, got {self.price!r}")
        if not math.isfinite(self.size):
            raise ValueError(f"size must be finite, got {self.size!r}")
        return self
