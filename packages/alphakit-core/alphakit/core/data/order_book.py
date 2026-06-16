"""L2 order book schema.

An :class:`OrderBook` is a snapshot of the limit-order book up to some
depth on both sides. It is consumed by microstructure and market-making
strategies (Phase 4+).

Invariants enforced at construction time
----------------------------------------
* bids are sorted descending by price
* asks are sorted ascending by price
* ``best_bid < best_ask`` (book is not crossed)
* all sizes are non-negative
* all prices are strictly positive
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookLevel(BaseModel):
    """A single price level in the limit order book."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    price: float = Field(gt=0.0)
    size: float = Field(ge=0.0)


class OrderBook(BaseModel):
    """An L2 order book snapshot on one instrument."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    """Event time of this snapshot."""

    symbol: str = Field(min_length=1, max_length=32)
    """Instrument symbol."""

    bids: tuple[BookLevel, ...]
    """Bids sorted descending by price. ``bids[0]`` is best bid."""

    asks: tuple[BookLevel, ...]
    """Asks sorted ascending by price. ``asks[0]`` is best ask."""

    @model_validator(mode="after")
    def _check_sorted_and_not_crossed(self) -> OrderBook:
        """Enforce book ordering and non-crossed state."""
        for i in range(len(self.bids) - 1):
            if self.bids[i].price < self.bids[i + 1].price:
                raise ValueError(
                    f"bids must be sorted descending, "
                    f"got {self.bids[i].price} < {self.bids[i + 1].price}"
                )
        for i in range(len(self.asks) - 1):
            if self.asks[i].price > self.asks[i + 1].price:
                raise ValueError(
                    f"asks must be sorted ascending, "
                    f"got {self.asks[i].price} > {self.asks[i + 1].price}"
                )
        if self.bids and self.asks and self.bids[0].price >= self.asks[0].price:
            raise ValueError(
                f"crossed book: best bid {self.bids[0].price} >= best ask {self.asks[0].price}"
            )
        return self

    @property
    def best_bid(self) -> float | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return 0.5 * (self.best_bid + self.best_ask)

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid
