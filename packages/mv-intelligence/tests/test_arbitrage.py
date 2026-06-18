"""Unit tests for the executable arbitrage engine (after-cost edge + R/A/G)."""

from __future__ import annotations

from decimal import Decimal

from mv.intelligence.arbitrage import (
    VenueQuote,
    classify_executability,
    cross_border_monitor,
    detect_cross_exchange,
    detect_funding,
    detect_triangular,
    rank_opportunities,
    serialize,
)

# ---- executability rule (BR-007) ---------------------------------------------


def test_executability_red_when_negative_after_cost() -> None:
    assert classify_executability(Decimal("-3")) == "red"


def test_executability_amber_when_thin() -> None:
    assert classify_executability(Decimal("3")) == "amber"  # below the green threshold


def test_executability_amber_on_high_transfer_latency() -> None:
    assert classify_executability(Decimal("50"), transfer_latency_min=120) == "amber"


def test_executability_green_when_strong_and_executable() -> None:
    assert classify_executability(Decimal("50"), transfer_latency_min=5, depth_ok=True) == "green"


def test_cross_border_is_always_red_monitor_only() -> None:
    # Even a huge gross dislocation is monitor-only (LRS/FEMA, §1.2).
    opp = cross_border_monitor("NIFTY ADR vs local", Decimal("250"))
    assert opp.executability == "red"
    assert opp.kind == "cross_border"
    assert "monitor-only" in opp.detail


# ---- cross-exchange -----------------------------------------------------------


def test_cross_exchange_thin_spread_vanishes_after_cost() -> None:
    # A 12bps gross spread is eaten by fees (10+10 taker) + slippage + transfer.
    quotes = [
        VenueQuote(
            "binance",
            bid=Decimal("100.00"),
            ask=Decimal("100.00"),
            depth_notional=Decimal("1e6"),
            spread_bps=Decimal("2"),
        ),
        VenueQuote(
            "kraken",
            bid=Decimal("100.12"),
            ask=Decimal("100.12"),
            depth_notional=Decimal("1e6"),
            spread_bps=Decimal("2"),
        ),
    ]
    opp = detect_cross_exchange(quotes, order_notional=Decimal("10000"))
    assert opp is not None
    assert opp.gross_edge_bps > 0
    assert opp.after_cost_edge_bps < opp.gross_edge_bps
    assert opp.after_cost_edge_bps <= 0  # vanishes after cost
    assert opp.executability == "red"


def test_cross_exchange_wide_spread_can_be_executable() -> None:
    quotes = [
        VenueQuote(
            "binance",
            bid=Decimal("100"),
            ask=Decimal("100"),
            depth_notional=Decimal("1e9"),
            spread_bps=Decimal("1"),
        ),
        VenueQuote(
            "kraken",
            bid=Decimal("101"),
            ask=Decimal("101"),
            depth_notional=Decimal("1e9"),
            spread_bps=Decimal("1"),
        ),
    ]
    opp = detect_cross_exchange(quotes, order_notional=Decimal("1000"), transfer_latency_min=5)
    assert opp is not None
    assert opp.after_cost_edge_bps > 0
    assert opp.executability in {"green", "amber"}


def test_cross_exchange_needs_two_distinct_venues() -> None:
    one = [VenueQuote("binance", Decimal("100"), Decimal("100"), Decimal("1e6"), Decimal("2"))]
    assert detect_cross_exchange(one, order_notional=Decimal("1000")) is None


# ---- funding-rate -------------------------------------------------------------


def test_funding_positive_after_fees() -> None:
    opp = detect_funding(funding_rate_bps=Decimal("10"), periods=3, basis_bps=Decimal("20"))
    # 10*3 + 20 = 50 gross; 4 legs * 10bps = 40 cost; +10 after.
    assert opp.after_cost_edge_bps == Decimal("10")
    assert opp.executability == "green"


# ---- triangular ---------------------------------------------------------------


def test_triangular_product_above_one_is_edge() -> None:
    legs = [
        ("USDT/BTC", Decimal("1.01")),
        ("BTC/ETH", Decimal("1.005")),
        ("ETH/USDT", Decimal("1.0")),
    ]
    opp = detect_triangular(legs)
    assert opp.gross_edge_bps > 0
    assert opp.after_cost_edge_bps == opp.gross_edge_bps - Decimal("30")  # 3 legs * 10bps


def test_triangular_requires_three_legs() -> None:
    import pytest

    with pytest.raises(ValueError, match="at least 3 legs"):
        detect_triangular([("A/B", Decimal("1.0")), ("B/A", Decimal("1.0"))])


# ---- engine helpers -----------------------------------------------------------


def test_rank_orders_by_after_cost_desc() -> None:
    a = detect_funding(funding_rate_bps=Decimal("10"), periods=1)  # weak
    b = detect_funding(funding_rate_bps=Decimal("100"), periods=1)  # strong
    ranked = rank_opportunities([a, b])
    assert ranked[0] is b


def test_serialize_is_jsonable() -> None:
    opp = detect_funding(funding_rate_bps=Decimal("100"), periods=1)
    payload = serialize(opp)
    assert payload["kind"] == "funding_rate"
    assert isinstance(payload["after_cost_edge_bps"], str)
    assert payload["executability"] in {"green", "amber", "red"}
