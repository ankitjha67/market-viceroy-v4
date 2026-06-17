"""Unit tests for the cost model v1 (pure Decimal)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from alphakit.bridges.cost_model import (
    FeeSchedule,
    IndiaCryptoTax,
    apply_slippage,
    slippage_bps,
    venue_fees,
)


def test_fee_maker_taker() -> None:
    schedule = FeeSchedule(maker_bps=Decimal("10"), taker_bps=Decimal("20"))
    assert schedule.fee(Decimal("10000"), maker=True) == Decimal("10")
    assert schedule.fee(Decimal("10000"), maker=False) == Decimal("20")
    # Absolute notional.
    assert schedule.fee(Decimal("-10000"), maker=False) == Decimal("20")


def test_venue_fees_lookup_and_default() -> None:
    assert venue_fees("binance").taker_bps == Decimal("10")
    assert venue_fees("coinbase").taker_bps == Decimal("60")
    assert venue_fees("unknown").taker_bps == Decimal("10")  # default


def test_slippage_half_spread_plus_impact() -> None:
    # spread 4 bps -> half-spread 2; order == depth -> ratio 1 -> impact = coef.
    result = slippage_bps(Decimal("4"), Decimal("1000"), Decimal("1000"), impact_coef=Decimal("10"))
    assert result == Decimal("12")  # 2 + 10*sqrt(1)


def test_slippage_partial_depth() -> None:
    # order is 1/4 of depth -> sqrt(0.25) = 0.5 -> impact = 5; plus half-spread 1.
    result = slippage_bps(Decimal("2"), Decimal("250"), Decimal("1000"), impact_coef=Decimal("10"))
    assert result == Decimal("6")


def test_slippage_zero_depth_is_full_impact() -> None:
    result = slippage_bps(Decimal("0"), Decimal("100"), Decimal("0"), impact_coef=Decimal("10"))
    assert result == Decimal("10")  # ratio 1 -> impact 10, no spread


def test_slippage_rejects_negative_spread() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        slippage_bps(Decimal("-1"), Decimal("1"), Decimal("1"))


def test_apply_slippage_direction() -> None:
    # 10 bps on 100 -> 0.1 worse for the taker.
    assert apply_slippage(Decimal("100"), "BUY", Decimal("10")) == Decimal("100.1")
    assert apply_slippage(Decimal("100"), "SELL", Decimal("10")) == Decimal("99.9")


def test_india_tax_on_gain_and_tds() -> None:
    tax = IndiaCryptoTax()
    assert tax.on_gain(Decimal("1000")) == Decimal("300")  # 30%
    assert tax.on_gain(Decimal("-1000")) == Decimal("0")  # no tax on a loss
    assert tax.tds(Decimal("10000")) == Decimal("100")  # 1%
    assert tax.total(Decimal("1000"), Decimal("10000")) == Decimal("400")
