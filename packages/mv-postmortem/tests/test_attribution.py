"""Unit tests for the Phase-1 attribution stub."""

from __future__ import annotations

from decimal import Decimal

from mv.postmortem.attribution import attribute


def test_records_net_pnl() -> None:
    a = attribute("trade-1", Decimal("125.50"))
    assert a.trade_id == "trade-1"
    assert a.net_pnl == Decimal("125.50")
    assert a.is_decomposed() is False  # decomposition is Phase 5


def test_records_fees() -> None:
    a = attribute("trade-2", Decimal("-10"), fees=Decimal("0.42"))
    assert a.fees == Decimal("0.42")
    assert a.is_decomposed() is False  # other components still unset
