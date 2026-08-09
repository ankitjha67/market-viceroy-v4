"""Tests for the pure performance-metrics panel (mv.api.metrics)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.api.metrics import performance_metrics
from mv.postmortem.trades import ClosedTrade, Fill, reconstruct_closed_trades

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, qty: str, price: str) -> Fill:
    return Fill(
        instrument="BTC/USDT", side=side, qty=Decimal(qty), fill_price=Decimal(price), ts=_TS
    )


def _trades(*legs: tuple[str, str, str]) -> list[ClosedTrade]:
    return reconstruct_closed_trades([_fill(*leg) for leg in legs])


def test_empty_inputs_are_empty() -> None:
    assert performance_metrics([], []) == {}


def test_trade_stats_winrate_and_profit_factor() -> None:
    # Two round trips: +10 (buy 1@100, sell 1@110) and -5 (buy 1@100, sell 1@95).
    trades = _trades(
        ("BUY", "1", "100"),
        ("SELL", "1", "110"),
        ("BUY", "1", "100"),
        ("SELL", "1", "95"),
    )
    m = performance_metrics([Decimal("5000"), Decimal("5010"), Decimal("5005")], trades)
    assert m["n_trades"] == "2"
    assert m["win_rate"] == "0.5"
    assert m["profit_factor"] == "2.0"  # gross profit 10 / gross loss 5
    assert m["total_pnl"] == "5"
    assert m["largest_win"] == "10"
    assert m["largest_loss"] == "-5"
    # India crypto tax (approximation, labelled). Per trade the drag is
    # max(30% of the gross gain, 1% TDS on the sale) because TDS is withheld
    # tax credited against the liability, not an additive expense:
    #   winner  +10 gross -> max(3.00, 1% of 110 = 1.10) = 3.00
    #   loser    -5 gross -> max(0.00, 1% of  95 = 0.95) = 0.95
    assert m["tax_drag_approx"] == "3.95"
    assert m["after_tax_pnl_approx"] == "1.05"  # +5 pre-tax, still positive
    assert "TDS" in m["tax_basis"]


def test_tds_uses_the_sale_leg_for_a_short_round_trip() -> None:
    # Section 194S attaches to the sale. For a SHORT the sale is the ENTRY leg
    # (the cover is a buy), so charging the exit under-withheld on every
    # profitable short.
    trades = _trades(("SELL", "1", "100"), ("BUY", "1", "60"))
    m = performance_metrics([Decimal("5000")], trades)
    # gross gain +40 -> liability 12.00; TDS on the 100 sale = 1.00 -> max = 12.
    assert Decimal(m["tax_drag_approx"]) == Decimal("12")


def test_taxable_gain_is_gross_of_fees() -> None:
    # 115BBH allows only cost of acquisition; brokerage is not deductible, so
    # the tax base must not be the fee-netted PnL.
    fills = [_fill("BUY", "1", "100"), _fill("SELL", "1", "110")]
    fills[1] = Fill(
        instrument="BTC/USDT",
        side="SELL",
        qty=Decimal("1"),
        fill_price=Decimal("110"),
        ts=_TS,
        fees=Decimal("2"),
    )
    trades = reconstruct_closed_trades(fills)
    m = performance_metrics([Decimal("5000")], trades)
    # Gross gain is 10 (not 8 after the 2 of fees) -> liability 3.00 > TDS 1.10.
    assert Decimal(m["tax_drag_approx"]) == Decimal("3")


def test_profit_factor_capped_when_no_losses() -> None:
    trades = _trades(("BUY", "1", "100"), ("SELL", "1", "110"))
    m = performance_metrics([Decimal("5000")], trades)
    assert m["profit_factor"] == "999.99"  # no losing trades -> capped


def test_max_drawdown_from_equity_curve() -> None:
    # Peak 5100 then trough 4998 -> dd = (5100-4998)/5100.
    curve = [Decimal("5000"), Decimal("5100"), Decimal("4998"), Decimal("5050")]
    m = performance_metrics(curve, [])
    assert m["n_trades"] == "0"
    expected = round(float((Decimal("5100") - Decimal("4998")) / Decimal("5100")), 4)
    assert m["max_drawdown"] == str(expected)


def test_total_return_from_curve() -> None:
    m = performance_metrics([Decimal("5000"), Decimal("5075")], [])
    assert m["total_return"] == "0.015"  # (5075-5000)/5000
