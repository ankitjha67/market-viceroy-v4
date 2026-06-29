"""Tests for the pure Command Deck snapshot helpers (mv.api.snapshot)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.api.snapshot import (
    portfolio_from_fills,
    positions_from_fills,
    realized_pnl,
    unrealized_pnl,
)
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


def _fill_sym(instrument: str, side: str, qty: str, price: str) -> Fill:
    return Fill(
        instrument=instrument, side=side, qty=Decimal(qty), fill_price=Decimal(price), ts=_TS
    )


def test_positions_and_portfolio_aggregate_across_instruments() -> None:
    # The multi-instrument loop journals all symbols into one book; the snapshot
    # nets per instrument and the portfolio sums across them.
    fills = [
        _fill_sym("BTC/USDT", "BUY", "1", "100"),
        _fill_sym("ETH/USDT", "BUY", "2", "50"),
    ]
    marks = {"BTC/USDT": Decimal("110"), "ETH/USDT": Decimal("60")}
    rows = positions_from_fills(fills, marks=marks)
    assert {r["instrument"] for r in rows} == {"BTC/USDT", "ETH/USDT"}
    p = portfolio_from_fills(fills, Decimal("1000"), marks=marks)
    # unrealized: BTC (110-100)*1 = 10 + ETH (60-50)*2 = 20 -> 30
    assert p["equity"] == "1030"
    assert p["day_pnl"] == "30"


def test_positions_marked_to_live_price_not_entry() -> None:
    # A single open lot: without a live mark the old code showed mark == entry and
    # pnl 0 (the frozen-dashboard bug). With the live mark it reflects the market.
    rows = positions_from_fills([_fill("BUY", "1", "100")], marks={"BTC/USDT": Decimal("130")})
    assert rows == [
        {"instrument": "BTC/USDT", "size": "1", "entry": "100", "mark": "130", "pnl": "30"}
    ]


def test_positions_short_marked_to_live_price() -> None:
    # Short 1 @ 100; price falls to 80 -> the short is +20 unrealized.
    rows = positions_from_fills([_fill("SELL", "1", "100")], marks={"BTC/USDT": Decimal("80")})
    assert rows == [
        {"instrument": "BTC/USDT", "size": "-1", "entry": "100", "mark": "80", "pnl": "20"}
    ]


def test_unrealized_pnl_marks_open_position() -> None:
    assert unrealized_pnl([_fill("BUY", "2", "100")], {"BTC/USDT": Decimal("110")}) == Decimal("20")
    assert unrealized_pnl([]) == Decimal("0")


def test_portfolio_includes_unrealized_marktomarket() -> None:
    # Hold 1 bought @ 100, live mark 150 -> equity = 1000 + 50 unrealized (was frozen
    # at 1000 before the mark-to-market fix).
    p = portfolio_from_fills(
        [_fill("BUY", "1", "100")], Decimal("1000"), marks={"BTC/USDT": Decimal("150")}
    )
    assert p["equity"] == "1050"
    assert p["day_pnl"] == "50"
    assert p["drawdown"] == "0"
    assert p["peak_equity"] == "1050"


def test_portfolio_drawdown_from_running_peak() -> None:
    # Equity 950 against a threaded high-water mark of 1100 -> a real drawdown
    # (the field was hardcoded "0" before).
    p = portfolio_from_fills(
        [_fill("BUY", "1", "100")],
        Decimal("1000"),
        marks={"BTC/USDT": Decimal("50")},
        peak_equity=Decimal("1100"),
    )
    assert p["equity"] == "950"  # 1000 + (50 - 100) * 1
    assert p["peak_equity"] == "1100"
    assert p["drawdown"] == str((Decimal("1100") - Decimal("950")) / Decimal("1100"))
