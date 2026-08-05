"""Tests for the perp funding-rate adapter (normalization + flow mapping)."""

from __future__ import annotations

from typing import Any

from mv.failover.adapters.funding_feed import (
    funding_flow_score,
    normalize_funding,
    perp_symbol,
    spot_symbol,
)


def test_symbol_mapping_round_trips() -> None:
    assert perp_symbol("BTC/USDT") == "BTC/USDT:USDT"
    assert perp_symbol("BTC/USDT:USDT") == "BTC/USDT:USDT"  # idempotent
    assert spot_symbol("BTC/USDT:USDT") == "BTC/USDT"


def test_normalize_funding_keys_by_spot_and_drops_missing_rates() -> None:
    raw: dict[str, dict[str, Any]] = {
        "BTC/USDT:USDT": {
            "symbol": "BTC/USDT:USDT",
            "fundingRate": 0.0001,
            "openInterestAmount": 91000.5,
        },
        "ETH/USDT:USDT": {"symbol": "ETH/USDT:USDT", "fundingRate": None},
        "SOL/USDT:USDT": {"symbol": "SOL/USDT:USDT", "fundingRate": True},  # bool is not a rate
    }
    out = normalize_funding(raw)
    assert set(out) == {"BTC/USDT"}  # missing/bool rates never masquerade as 0
    assert out["BTC/USDT"].rate == 0.0001
    assert out["BTC/USDT"].open_interest == 91000.5


def test_funding_flow_score_saturates_and_signs() -> None:
    assert funding_flow_score(0.0005) == 1.0  # crowded long saturates
    assert funding_flow_score(-0.001) == -1.0
    assert abs(funding_flow_score(0.0001) - 0.2) < 1e-12
    assert funding_flow_score(0.1, saturation=0) == 0.0  # degenerate guard
