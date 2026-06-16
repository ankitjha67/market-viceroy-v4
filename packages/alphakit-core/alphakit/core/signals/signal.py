"""Signal type emitted by strategies.

A :class:`Signal` is an optional, higher-level abstraction over the
weights DataFrame returned by :meth:`StrategyProtocol.generate_signals`.
Strategies that think in terms of discrete entry/exit events (e.g.
breakout, event-driven) can emit ``Signal`` objects and let a helper
convert them to a weights panel.

This file intentionally does not import any engine, portfolio, or
execution code — signals are plain value objects.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum

from alphakit.core.instruments.base import Instrument
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalDirection(str, Enum):
    """Direction of a strategy signal."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class Signal(BaseModel):
    """A single strategy signal on one instrument at one timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    """When the signal was generated (end-of-bar, typically)."""

    instrument: Instrument
    """The instrument this signal refers to."""

    direction: SignalDirection
    """LONG, SHORT, or FLAT (close existing exposure)."""

    size: float = Field(ge=0.0, le=10.0)
    """Target fractional weight in portfolio (0.0–1.0 for long-only,
    up to 10.0 for leveraged strategies). Ignored when ``direction`` is FLAT."""

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    """Strategy-reported confidence in ``[0, 1]``. Consumers may use this
    for signal aggregation across sub-strategies."""

    target_price: float | None = Field(default=None, gt=0.0)
    """Optional entry limit. ``None`` means execute at next bar open."""

    note: str | None = Field(default=None, max_length=256)
    """Optional free-form annotation for debugging / attribution."""

    @model_validator(mode="after")
    def _check_finite(self) -> Signal:
        if not math.isfinite(self.size):
            raise ValueError(f"size must be finite, got {self.size!r}")
        if not math.isfinite(self.confidence):
            raise ValueError(f"confidence must be finite, got {self.confidence!r}")
        if self.direction == SignalDirection.FLAT and self.size != 0.0:
            raise ValueError(f"FLAT signal must have size=0.0, got {self.size!r}")
        return self
