"""Unit tests for closed-trade reconstruction (FIFO round-trip pairing)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from mv.postmortem.trades import (
    Fill,
    OpenPosition,
    fill_from_journal,
    open_positions,
    reconstruct_closed_trades,
)

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, qty: str, price: str, *, offset: int = 0, **over: object) -> Fill:
    base: dict[str, object] = {
        "instrument": "BTC/USDT",
        "side": side,
        "qty": Decimal(qty),
        "fill_price": Decimal(price),
        "ts": _T0 + timedelta(hours=offset),
    }
    base.update(over)
    return Fill(**base)  # type: ignore[arg-type]


def test_simple_round_trip() -> None:
    fills = [_fill("BUY", "2", "100", offset=0), _fill("SELL", "2", "110", offset=1)]
    trades = reconstruct_closed_trades(fills)
    assert len(trades) == 1
    t = trades[0]
    assert t.direction == 1
    assert t.qty == Decimal("2")
    assert t.entry_fill_price == Decimal("100")
    assert t.exit_fill_price == Decimal("110")
    assert t.net_pnl() == Decimal("20")


def test_short_round_trip() -> None:
    fills = [_fill("SELL", "1", "110", offset=0), _fill("BUY", "1", "100", offset=1)]
    trades = reconstruct_closed_trades(fills)
    assert len(trades) == 1
    assert trades[0].direction == -1
    assert trades[0].net_pnl() == Decimal("10")


def test_partial_close_makes_two_trades() -> None:
    fills = [
        _fill("BUY", "3", "100", offset=0),
        _fill("SELL", "1", "105", offset=1),
        _fill("SELL", "2", "110", offset=2),
    ]
    trades = reconstruct_closed_trades(fills)
    assert len(trades) == 2
    assert trades[0].qty == Decimal("1")
    assert trades[1].qty == Decimal("2")


def test_unclosed_lot_has_no_trade() -> None:
    fills = [_fill("BUY", "2", "100")]
    assert reconstruct_closed_trades(fills) == []


def test_fees_prorated_to_matched_qty() -> None:
    fills = [
        _fill("BUY", "4", "100", offset=0, fees=Decimal("4")),
        _fill("SELL", "2", "110", offset=1, fees=Decimal("2")),
    ]
    trades = reconstruct_closed_trades(fills)
    # Entry fees 4 over 4 units -> 2 units = 2; exit fees 2 over 2 units = 2; total 4.
    assert trades[0].fees == Decimal("4")


def test_intended_and_reference_prices_carried() -> None:
    fills = [
        _fill(
            "BUY",
            "1",
            "101",
            offset=0,
            intended_price=Decimal("100.5"),
            decision_ref_price=Decimal("100"),
            target_qty=Decimal("2"),
        ),
        _fill("SELL", "1", "110", offset=1, intended_price=Decimal("110.5")),
    ]
    t = reconstruct_closed_trades(fills)[0]
    assert t.decision_ref_price == Decimal("100")
    assert t.entry_intended_price == Decimal("100.5")
    assert t.exit_intended_price == Decimal("110.5")
    assert t.target_qty == Decimal("2")


def test_fill_from_journal_round_trips_through_reconstruction() -> None:
    entries = [
        {
            "symbol": "BTC/USDT",
            "side": "BUY",
            "qty": "1",
            "price": "101",
            "intended_price": "100.5",
            "decision_ref_price": "100",
            "fees": "0.5",
        },
        {"symbol": "BTC/USDT", "side": "SELL", "qty": "1", "price": "110", "fees": "0.5"},
    ]
    fills = [fill_from_journal(e, ts=_T0 + timedelta(hours=i)) for i, e in enumerate(entries)]
    trades = reconstruct_closed_trades(fills)
    assert len(trades) == 1
    assert trades[0].decision_ref_price == Decimal("100")
    assert trades[0].fees == Decimal("1.0")


def test_fill_from_journal_degrades_without_phase5_fields() -> None:
    fill = fill_from_journal({"symbol": "X", "side": "BUY", "qty": "1", "price": "100"}, ts=_T0)
    assert fill.intended_price is None
    assert fill.fees == Decimal("0")


def test_open_positions_remainder_after_partial_close() -> None:
    # BUY 3 @ 100, SELL 1 @ 120 -> 2 still open at the FIFO basis (100).
    out = open_positions([_fill("BUY", "3", "100"), _fill("SELL", "1", "120", offset=1)])
    assert out == [
        OpenPosition(instrument="BTC/USDT", net_qty=Decimal("2"), avg_price=Decimal("100"))
    ]


def test_open_positions_flat_is_empty() -> None:
    assert open_positions([_fill("BUY", "1", "100"), _fill("SELL", "1", "110", offset=1)]) == []


def test_open_positions_quantity_weighted_basis() -> None:
    # BUY 1 @ 100, BUY 1 @ 200 -> 2 open at the quantity-weighted basis (150).
    out = open_positions([_fill("BUY", "1", "100"), _fill("BUY", "1", "200", offset=1)])
    assert out == [
        OpenPosition(instrument="BTC/USDT", net_qty=Decimal("2"), avg_price=Decimal("150"))
    ]


def test_open_positions_short_is_signed_negative() -> None:
    out = open_positions([_fill("SELL", "2", "100")])
    assert out == [
        OpenPosition(instrument="BTC/USDT", net_qty=Decimal("-2"), avg_price=Decimal("100"))
    ]
