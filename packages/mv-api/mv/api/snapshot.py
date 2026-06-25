"""Pure snapshot helpers: turn journaled fills into the Command Deck's portfolio
and positions shapes.

Shared by the ``mv-serve`` loop (one-shot and continuous ``--watch`` mode) so the
P&L / position math lives in one tested place instead of being duplicated in the
CLI wrapper. Money is ``Decimal``; realized P&L is exact from closed round trips
and open positions are **marked to the live price** the loop passes in (the latest
bar close), so equity and the open-position P&L move with the market rather than
sitting frozen at the entry. Reuses :mod:`mv.postmortem.trades` (FIFO round trips
+ the open remainder). Pure and deterministic — no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from mv.postmortem.trades import Fill, open_positions, reconstruct_closed_trades

_ZERO = Decimal("0")


def realized_pnl(fills: list[Fill]) -> Decimal:
    """Realized net P&L over the closed round trips reconstructed from ``fills``."""
    total = _ZERO
    for trade in reconstruct_closed_trades(fills):
        total += trade.net_pnl()
    return total


def _last_fill_prices(fills: list[Fill]) -> dict[str, Decimal]:
    """Latest fill price per instrument — the mark fallback when no live price is given."""
    return {fill.instrument: fill.fill_price for fill in fills}


def _marked_positions(
    fills: list[Fill], marks: Mapping[str, Decimal] | None
) -> list[tuple[str, Decimal, Decimal, Decimal, Decimal]]:
    """``(instrument, net_qty, entry, mark, unrealized_pnl)`` for each open position.

    ``net_qty`` carries the sign (long > 0, short < 0); ``entry`` is the FIFO cost
    basis of the open lots; ``mark`` is the live price from ``marks`` when present
    (the loop passes the latest bar close), else the latest fill price. The
    unrealized P&L is ``(mark - entry) * net_qty``.
    """
    marks = marks or {}
    last_fill = _last_fill_prices(fills)
    out: list[tuple[str, Decimal, Decimal, Decimal, Decimal]] = []
    for pos in open_positions(fills):
        entry = pos.avg_price
        mark = marks.get(pos.instrument, last_fill.get(pos.instrument, entry))
        pnl = (mark - entry) * pos.net_qty
        out.append((pos.instrument, pos.net_qty, entry, mark, pnl))
    return out


def unrealized_pnl(fills: list[Fill], marks: Mapping[str, Decimal] | None = None) -> Decimal:
    """Unrealized mark-to-market P&L over the open positions (``marks`` -> live price)."""
    return sum((pnl for *_, pnl in _marked_positions(fills, marks)), _ZERO)


def portfolio_from_fills(
    fills: list[Fill],
    start_equity: Decimal,
    marks: Mapping[str, Decimal] | None = None,
    peak_equity: Decimal | None = None,
) -> dict[str, Any]:
    """Build the Command Deck portfolio summary (the ``/api/v1/portfolio`` shape).

    ``equity`` is the starting equity plus realized P&L (closed round trips) plus
    the **unrealized** mark-to-market of the open positions (marked to the live
    prices in ``marks``); ``day_pnl`` is realized + unrealized. ``drawdown`` is the
    decline from the running ``peak_equity`` the caller threads across ticks (so it
    reflects the real high-water mark, not just this tick); when omitted it falls
    back to ``max(start_equity, equity)`` for the one-shot case. Money is rendered
    as strings (the UI formats, never re-computes as float).
    """
    realized = realized_pnl(fills)
    unrealized = unrealized_pnl(fills, marks)
    equity = start_equity + realized + unrealized
    peak = max(peak_equity if peak_equity is not None else start_equity, equity)
    drawdown = (peak - equity) / peak if peak > _ZERO else _ZERO
    return {
        "equity": str(equity),
        "day_pnl": str(realized + unrealized),
        "drawdown": str(drawdown),
        "peak_equity": str(peak),
    }


def positions_from_fills(
    fills: list[Fill], marks: Mapping[str, Decimal] | None = None
) -> list[dict[str, Any]]:
    """Open positions per instrument (the ``/api/v1/positions`` shape).

    Nets BUY/SELL into FIFO-basis open positions; the entry is the cost basis of
    the open lots, the ``mark`` is the live price from ``marks`` (else the latest
    fill price), and the P&L is the unrealized mark-vs-entry on the open quantity.
    Flat instruments are omitted. Deterministic ordering by instrument.
    """
    return [
        {
            "instrument": sym,
            "size": str(net),
            "entry": str(entry),
            "mark": str(mark),
            "pnl": str(pnl),
        }
        for sym, net, entry, mark, pnl in _marked_positions(fills, marks)
    ]


__all__ = ["portfolio_from_fills", "positions_from_fills", "realized_pnl", "unrealized_pnl"]
