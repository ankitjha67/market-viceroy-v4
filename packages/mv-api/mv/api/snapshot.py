"""Pure snapshot helpers: turn journaled fills into the Command Deck's portfolio
and positions shapes.

Shared by the ``mv-serve`` loop (one-shot and continuous ``--watch`` mode) so the
P&L / position math lives in one tested place instead of being duplicated in the
CLI wrapper. Money is ``Decimal``; realized P&L is exact from closed round trips
(reusing :func:`mv.postmortem.trades.reconstruct_closed_trades`). Pure and
deterministic — no I/O.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from mv.postmortem.trades import Fill, reconstruct_closed_trades

_ZERO = Decimal("0")


def realized_pnl(fills: list[Fill]) -> Decimal:
    """Realized net P&L over the closed round trips reconstructed from ``fills``."""
    total = _ZERO
    for trade in reconstruct_closed_trades(fills):
        total += trade.net_pnl()
    return total


def portfolio_from_fills(fills: list[Fill], start_equity: Decimal) -> dict[str, Any]:
    """Build the Command Deck portfolio summary (the ``/api/v1/portfolio`` shape).

    ``day_pnl`` is the realized P&L over the session; ``equity`` is the starting
    equity plus that; ``peak_equity`` never dips below the start. Money is rendered
    as strings (the UI formats, never re-computes as float).
    """
    realized = realized_pnl(fills)
    equity = start_equity + realized
    return {
        "equity": str(equity),
        "day_pnl": str(realized),
        "drawdown": "0",
        "peak_equity": str(max(start_equity, equity)),
    }


def positions_from_fills(fills: list[Fill]) -> list[dict[str, Any]]:
    """Open positions per instrument (the ``/api/v1/positions`` shape).

    Nets BUY/SELL quantities per instrument; the displayed entry is the average
    fill on the net side (a paper approximation), the mark is the latest fill
    price, and the P&L is the unrealized mark-vs-entry on the open quantity. Flat
    instruments are omitted. Deterministic ordering by instrument.
    """
    longs: dict[str, list[Decimal]] = defaultdict(lambda: [_ZERO, _ZERO])
    shorts: dict[str, list[Decimal]] = defaultdict(lambda: [_ZERO, _ZERO])
    marks: dict[str, Decimal] = {}
    for fill in fills:
        book = longs if fill.side == "BUY" else shorts
        book[fill.instrument][0] += fill.qty
        book[fill.instrument][1] += fill.qty * fill.fill_price
        marks[fill.instrument] = fill.fill_price

    rows: list[dict[str, Any]] = []
    for sym in sorted(set(longs) | set(shorts)):
        net = longs[sym][0] - shorts[sym][0]
        if net == 0:
            continue
        side_book = longs[sym] if net > 0 else shorts[sym]
        entry = side_book[1] / side_book[0] if side_book[0] else _ZERO
        mark = marks.get(sym, entry)
        pnl = (mark - entry) * net  # net carries the sign (long +, short -)
        rows.append(
            {
                "instrument": sym,
                "size": str(net),
                "entry": str(entry),
                "mark": str(mark),
                "pnl": str(pnl),
            }
        )
    return rows


__all__ = ["portfolio_from_fills", "positions_from_fills", "realized_pnl"]
