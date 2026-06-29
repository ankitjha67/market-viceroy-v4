"""Tests for the pure trade blotter (mv.api.blotter)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from mv.api.blotter import trade_rows
from mv.postmortem.trades import Fill, reconstruct_closed_trades

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, qty: str, price: str, offset: int = 0) -> Fill:
    return Fill(
        instrument="BTC/USDT",
        side=side,
        qty=Decimal(qty),
        fill_price=Decimal(price),
        ts=_T0 + timedelta(hours=offset),
    )


def test_blotter_long_round_trip() -> None:
    trades = reconstruct_closed_trades([_fill("BUY", "1", "100", 0), _fill("SELL", "1", "110", 2)])
    rows = trade_rows(trades)
    assert len(rows) == 1
    r = rows[0]
    assert r["instrument"] == "BTC/USDT"
    assert r["side"] == "LONG"
    assert r["entry"] == "100" and r["exit"] == "110"
    assert r["pnl"] == "10"
    assert r["return_pct"] == "0.1"  # 10 / (100 * 1)
    assert r["duration_s"] == "7200"  # 2 hours held


def test_blotter_short_round_trip() -> None:
    rows = trade_rows(
        reconstruct_closed_trades([_fill("SELL", "1", "110", 0), _fill("BUY", "1", "100", 1)])
    )
    assert rows[0]["side"] == "SHORT"
    assert rows[0]["pnl"] == "10"


def test_blotter_empty() -> None:
    assert trade_rows([]) == []
