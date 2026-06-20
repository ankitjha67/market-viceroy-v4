"""Unit tests for the live-order guard (BR-005, FR-P6, FR-X1)."""

from __future__ import annotations

from decimal import Decimal

from mv.risk.live_guard import LiveGuardConfig, gate_live_order

_EQUITY = Decimal("1000000")


def test_paper_mode_passes_full_size() -> None:
    config = LiveGuardConfig()  # paper by default
    decision = gate_live_order(config, key="BTC/USDT", notional=Decimal("500000"), equity=_EQUITY)
    assert decision.allowed is True
    assert decision.notional == Decimal("500000")


def test_live_mode_blocks_ungraduated() -> None:
    config = LiveGuardConfig(mode="live", graduated=frozenset())
    decision = gate_live_order(config, key="BTC/USDT", notional=Decimal("1000"), equity=_EQUITY)
    assert decision.allowed is False
    assert decision.notional == Decimal("0")
    assert "not graduated" in decision.reason


def test_live_mode_allows_graduated_but_clamps_to_cap() -> None:
    config = LiveGuardConfig(
        mode="live", graduated=frozenset({"BTC/USDT"}), live_cap_pct=Decimal("0.01")
    )
    # Asking for 500k but the 1% cap on 1M equity is 10k.
    decision = gate_live_order(config, key="BTC/USDT", notional=Decimal("500000"), equity=_EQUITY)
    assert decision.allowed is True
    assert decision.notional == Decimal("10000")


def test_live_clamp_preserves_sign() -> None:
    config = LiveGuardConfig(
        mode="live", graduated=frozenset({"BTC/USDT"}), live_cap_pct=Decimal("0.01")
    )
    decision = gate_live_order(config, key="BTC/USDT", notional=Decimal("-500000"), equity=_EQUITY)
    assert decision.notional == Decimal("-10000")


def test_live_under_cap_is_unchanged() -> None:
    config = LiveGuardConfig(
        mode="live", graduated=frozenset({"BTC/USDT"}), live_cap_pct=Decimal("0.01")
    )
    decision = gate_live_order(config, key="BTC/USDT", notional=Decimal("5000"), equity=_EQUITY)
    assert decision.notional == Decimal("5000")  # below the 10k cap, untouched
