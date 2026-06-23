"""Tests for the pure Command Deck snapshot helpers (mv.api.snapshot)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.api.snapshot import portfolio_from_fills, positions_from_fills, realized_pnl
from mv.postmortem.trades import Fill

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, qty: str, price: str) -> Fill:
    return Fill(
        instrument="BTC/USDT",
        side=side,
        qty=Decimal(qty),
        fill_price=Decimal(price),
        ts=_TS,
    )


def test_realized_pnl_closed_roundtrip() -> None:
    fills = [_fill("BUY", "1", "100"), _fill("SELL", "1", "110")]
    assert realized_pnl(fills) == Decimal("10")


def test_realized_pnl_empty_is_zero() -> None:
    assert realized_pnl([]) == Decimal("0")


def test_portfolio_shape_and_values() -> None:
    fills = [_fill("BUY", "1", "100"), _fill("SELL", "1", "110")]
    p = portfolio_from_fills(fills, Decimal("1000"))
    assert p == {
        "equity": "1010",
        "day_pnl": "10",
        "drawdown": "0",
        "peak_equity": "1010",
    }


def test_portfolio_peak_never_below_start_on_loss() -> None:
    fills = [_fill("BUY", "1", "100"), _fill("SELL", "1", "90")]  # -10 realized
    p = portfolio_from_fills(fills, Decimal("1000"))
    assert p["equity"] == "990"
    assert p["day_pnl"] == "-10"
    assert p["peak_equity"] == "1000"  # max(start, equity)


def test_positions_open_long_unrealized() -> None:
    # BUY 2 @ 100, SELL 1 @ 120 -> net +1 long, avg entry 100, mark 120, pnl +20.
    rows = positions_from_fills([_fill("BUY", "2", "100"), _fill("SELL", "1", "120")])
    assert rows == [
        {"instrument": "BTC/USDT", "size": "1", "entry": "100", "mark": "120", "pnl": "20"}
    ]


def test_positions_flat_is_omitted() -> None:
    rows = positions_from_fills([_fill("BUY", "1", "100"), _fill("SELL", "1", "110")])
    assert rows == []
