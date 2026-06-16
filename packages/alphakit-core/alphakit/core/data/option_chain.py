"""Option chain schema.

An :class:`OptionChain` is a snapshot of the full options market on a
given underlying at a single point in time. It is built from a list of
:class:`OptionQuote` rows and exposes convenience accessors for strike
and expiry slicing.

Design notes
------------
* We model the chain as a collection of explicit ``OptionQuote`` rows
  rather than a nested dict so that (a) serialisation is trivial,
  (b) pandas round-tripping is straightforward, and (c) strategies can
  filter by arbitrary predicates without knowing the internal layout.
* Greeks are optional — not every feed provides them, and strategies
  that need greeks should compute them themselves from IV + spot.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OptionRight(str, Enum):
    """Call or put."""

    CALL = "call"
    PUT = "put"


class OptionQuote(BaseModel):
    """A single option quote at a moment in time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    expiry: date
    """Expiration date."""

    strike: float = Field(gt=0.0)
    """Strike price (strictly positive)."""

    right: OptionRight
    """Call or put."""

    bid: float | None = Field(default=None, ge=0.0)
    """Best bid, if available."""

    ask: float | None = Field(default=None, ge=0.0)
    """Best ask, if available."""

    last: float | None = Field(default=None, ge=0.0)
    """Last trade price, if available."""

    volume: float | None = Field(default=None, ge=0.0)
    """Traded volume, if available."""

    open_interest: float | None = Field(default=None, ge=0.0)
    """Open interest, if available."""

    iv: float | None = Field(default=None, ge=0.0)
    """Implied volatility, if available."""

    delta: float | None = None
    """Delta greek, if available."""

    gamma: float | None = None
    """Gamma greek, if available."""

    vega: float | None = None
    """Vega greek, if available."""

    theta: float | None = None
    """Theta greek, if available."""

    @property
    def mid(self) -> float | None:
        """Mid price, or ``None`` if bid/ask are unknown."""
        if self.bid is None or self.ask is None:
            return None
        return 0.5 * (self.bid + self.ask)


class OptionChain(BaseModel):
    """A full option chain snapshot on a single underlying."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    as_of: datetime
    """Timestamp of this snapshot."""

    underlying: str = Field(min_length=1)
    """Underlying symbol (e.g. ``"SPY"``, ``"BTC"``)."""

    spot: float = Field(gt=0.0)
    """Spot price of the underlying at ``as_of``."""

    quotes: tuple[OptionQuote, ...]
    """All option quotes in the chain. Tuple for immutability."""

    def expiries(self) -> tuple[date, ...]:
        """Sorted unique expirations present in the chain."""
        return tuple(sorted({q.expiry for q in self.quotes}))

    def strikes(self, expiry: date | None = None) -> tuple[float, ...]:
        """Sorted unique strikes, optionally filtered to one expiry."""
        if expiry is None:
            strikes = {q.strike for q in self.quotes}
        else:
            strikes = {q.strike for q in self.quotes if q.expiry == expiry}
        return tuple(sorted(strikes))

    def filter(
        self,
        *,
        expiry: date | None = None,
        right: OptionRight | None = None,
    ) -> tuple[OptionQuote, ...]:
        """Return quotes matching the given expiry and/or right."""
        rows = self.quotes
        if expiry is not None:
            rows = tuple(q for q in rows if q.expiry == expiry)
        if right is not None:
            rows = tuple(q for q in rows if q.right == right)
        return rows
