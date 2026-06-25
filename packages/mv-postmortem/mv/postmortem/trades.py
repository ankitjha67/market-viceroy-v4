"""Closed-trade reconstruction (PRD FR-P1) — the input to attribution.

A :class:`ClosedTrade` is one entry→exit round trip with the **intended vs
actual** prices, sizes, fees, and the decision-reference price the signal saw —
everything the causal decomposition needs. :func:`reconstruct_closed_trades`
pairs journaled fills into round trips (FIFO per instrument), so 100% of closed
trades get an attribution record (US-005). Money is ``Decimal`` throughout.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

_ZERO = Decimal("0")


def _maybe_decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class Fill:
    """One paper/live fill, enriched with the references attribution needs."""

    instrument: str
    side: str  # "BUY" | "SELL"
    qty: Decimal  # filled quantity (> 0)
    fill_price: Decimal  # actual fill price
    ts: datetime
    intended_price: Decimal | None = None  # order's reference price (None -> fill)
    decision_ref_price: Decimal | None = None  # price the signal saw at decision
    fees: Decimal = _ZERO
    target_qty: Decimal | None = None  # the model's reference size (for sizing attr.)
    regime_drift: Decimal = _ZERO  # benchmark/regime price move over the hold


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    """An entry→exit round trip; the unit attribution decomposes."""

    trade_id: str
    instrument: str
    direction: int  # +1 long, -1 short
    qty: Decimal  # matched quantity
    decision_ref_price: Decimal
    entry_intended_price: Decimal
    entry_fill_price: Decimal
    exit_intended_price: Decimal
    exit_fill_price: Decimal
    target_qty: Decimal
    fees: Decimal
    opened_at: datetime
    closed_at: datetime
    regime_drift: Decimal = _ZERO

    def net_pnl(self) -> Decimal:
        """Realized net PnL on the actual fills, net of fees."""
        gross = Decimal(self.direction) * (self.exit_fill_price - self.entry_fill_price) * self.qty
        return gross - self.fees


@dataclass(frozen=True, slots=True)
class OpenPosition:
    """The still-open net position in one instrument after FIFO matching.

    ``net_qty`` carries the sign (long > 0, short < 0); ``avg_price`` is the
    quantity-weighted cost basis of the lots still open (the remainder after FIFO
    round-trip matching), so the unrealized mark-to-market is
    ``(mark - avg_price) * net_qty``.
    """

    instrument: str
    net_qty: Decimal
    avg_price: Decimal


def _intended(fill: Fill) -> Decimal:
    return fill.intended_price if fill.intended_price is not None else fill.fill_price


def _ref_price(fill: Fill) -> Decimal:
    return fill.decision_ref_price if fill.decision_ref_price is not None else _intended(fill)


@dataclass
class _OpenLot:
    fill: Fill
    remaining: Decimal


def _fifo_walk(fills: list[Fill]) -> tuple[list[ClosedTrade], dict[str, deque[_OpenLot]]]:
    """The shared FIFO pass: pair fills into round trips and keep the open remainder.

    A fill opens or extends a position; an opposite-side fill closes against the
    oldest open lot(s), matched lot-by-lot so partial closes produce one
    :class:`ClosedTrade` per matched slice. Returns the closed trades **and** the
    per-instrument lots still open at the end, so callers can read either side of
    the same walk without duplicating the matching logic. Deterministic.
    """
    open_lots: dict[str, deque[_OpenLot]] = defaultdict(deque)
    trades: list[ClosedTrade] = []
    counter = 0

    for fill in fills:
        lots = open_lots[fill.instrument]
        # Same side as the current open position (or flat) -> a new opening lot.
        if not lots or _same_side(lots[0].fill.side, fill.side):
            lots.append(_OpenLot(fill, fill.qty))
            continue

        # Opposite side -> close against the oldest lots.
        to_close = fill.qty
        while to_close > _ZERO and lots:
            lot = lots[0]
            matched = min(lot.remaining, to_close)
            counter += 1
            trades.append(_pair(f"t{counter}", lot.fill, fill, matched))
            lot.remaining -= matched
            to_close -= matched
            if lot.remaining == _ZERO:
                lots.popleft()
        if to_close > _ZERO:  # the close overfills -> the remainder opens the other way
            lots.append(_OpenLot(fill, to_close))

    return trades, open_lots


def reconstruct_closed_trades(fills: list[Fill]) -> list[ClosedTrade]:
    """Pair fills into entry→exit round trips (FIFO per instrument).

    Any still-open lot at the end is left unclosed (no attribution until it
    closes); see :func:`open_positions` for the open remainder of the same walk.
    Deterministic.
    """
    trades, _ = _fifo_walk(fills)
    return trades


def open_positions(fills: list[Fill]) -> list[OpenPosition]:
    """The net open position per instrument after FIFO round-trip matching.

    The complement of :func:`reconstruct_closed_trades`: what is still **open**
    after closing fills are matched FIFO against opening lots, aggregated to a
    signed net quantity and the quantity-weighted cost basis of the open lots.
    Flat instruments are omitted; ordering is deterministic by instrument. This
    is the basis the live mark-to-market P&L is computed against.
    """
    _, open_lots = _fifo_walk(fills)
    out: list[OpenPosition] = []
    for sym in sorted(open_lots):
        lots = open_lots[sym]
        qty = sum((lot.remaining for lot in lots), _ZERO)
        if qty == _ZERO:
            continue
        notional = sum((lot.remaining * lot.fill.fill_price for lot in lots), _ZERO)
        sign = Decimal(1) if lots[0].fill.side == "BUY" else Decimal(-1)
        out.append(OpenPosition(instrument=sym, net_qty=sign * qty, avg_price=notional / qty))
    return out


def _same_side(a: str, b: str) -> bool:
    return a == b


def _pair(trade_id: str, entry: Fill, exit_: Fill, qty: Decimal) -> ClosedTrade:
    direction = 1 if entry.side == "BUY" else -1
    return ClosedTrade(
        trade_id=trade_id,
        instrument=entry.instrument,
        direction=direction,
        qty=qty,
        decision_ref_price=_ref_price(entry),
        entry_intended_price=_intended(entry),
        entry_fill_price=entry.fill_price,
        exit_intended_price=_intended(exit_),
        exit_fill_price=exit_.fill_price,
        target_qty=entry.target_qty if entry.target_qty is not None else qty,
        # Fees of both legs, pro-rated to the matched quantity.
        fees=_prorate(entry.fees, qty, entry.qty) + _prorate(exit_.fees, qty, exit_.qty),
        opened_at=entry.ts,
        closed_at=exit_.ts,
        regime_drift=exit_.regime_drift,
    )


def _prorate(total_fees: Decimal, matched: Decimal, full: Decimal) -> Decimal:
    if full == _ZERO:
        return _ZERO
    return total_fees * matched / full


def fill_from_journal(payload: Mapping[str, Any], *, ts: datetime) -> Fill:
    """Build a :class:`Fill` from a journaled ``execution`` entry payload.

    The loop's enriched fill carries ``intended_price`` / ``decision_ref_price``
    / ``fees`` (Phase 5); older entries without them degrade gracefully (the
    intended/reference prices fall back to the fill price, fees to 0).
    """
    return Fill(
        instrument=str(payload["symbol"]),
        side=str(payload["side"]),
        qty=Decimal(str(payload["qty"])),
        fill_price=Decimal(str(payload["price"])),
        ts=ts,
        intended_price=_maybe_decimal(payload.get("intended_price")),
        decision_ref_price=_maybe_decimal(payload.get("decision_ref_price")),
        fees=Decimal(str(payload.get("fees", "0"))),
        target_qty=_maybe_decimal(payload.get("target_qty")),
        regime_drift=Decimal(str(payload.get("regime_drift", "0"))),
    )


__all__ = [
    "ClosedTrade",
    "Fill",
    "OpenPosition",
    "fill_from_journal",
    "open_positions",
    "reconstruct_closed_trades",
]
