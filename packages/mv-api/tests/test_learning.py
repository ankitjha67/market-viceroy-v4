"""Tests for the live mistake-taxonomy surface (mv.api.learning)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.api.learning import mistakes_from_fills
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


def test_no_trades_no_mistakes() -> None:
    assert mistakes_from_fills([]) == {}


def test_winning_trade_has_no_mistake() -> None:
    # Buy 1 @ 100, sell 1 @ 110 -> profit -> no mistake classified.
    assert mistakes_from_fills([_fill("BUY", "1", "100"), _fill("SELL", "1", "110")]) == {}


def test_losing_trade_is_classified_with_cost() -> None:
    # Buy 1 @ 100, sell 1 @ 90 -> -10 loss; with no intended/ref differences the
    # whole loss lands on the directional (signal) component -> false_signal.
    out = mistakes_from_fills([_fill("BUY", "1", "100"), _fill("SELL", "1", "90")])
    assert out == {"false_signal": {"count": 1, "cost": "10"}}
