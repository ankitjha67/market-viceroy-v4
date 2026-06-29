"""Pure trade blotter: the journal's closed round trips as display rows.

The "what did we actually trade" record a desk keeps — each entry→exit round trip
(reconstructed FIFO from the journaled fills) with its direction, prices, net
PnL, fees, return, and hold duration. Money is ``Decimal`` rendered as strings;
times as ISO. Pure / deterministic — no I/O.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mv.postmortem.trades import ClosedTrade

_ZERO = Decimal("0")


def trade_rows(trades: list[ClosedTrade]) -> list[dict[str, Any]]:
    """Closed round trips as blotter rows (chronological; the UI shows newest first)."""
    rows: list[dict[str, Any]] = []
    for trade in trades:
        notional = trade.entry_fill_price * trade.qty
        pnl = trade.net_pnl()
        return_pct = pnl / notional if notional > _ZERO else _ZERO
        rows.append(
            {
                "id": trade.trade_id,
                "instrument": trade.instrument,
                "side": "LONG" if trade.direction > 0 else "SHORT",
                "qty": str(trade.qty),
                "entry": str(trade.entry_fill_price),
                "exit": str(trade.exit_fill_price),
                "pnl": str(pnl),
                "fees": str(trade.fees),
                "return_pct": str(return_pct),
                "opened_at": trade.opened_at.isoformat(),
                "closed_at": trade.closed_at.isoformat(),
                "duration_s": str(int((trade.closed_at - trade.opened_at).total_seconds())),
            }
        )
    return rows


__all__ = ["trade_rows"]
