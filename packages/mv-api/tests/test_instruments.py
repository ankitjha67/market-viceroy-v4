"""Tests for the generic crypto instrument factory (mv.api.instruments)."""

from __future__ import annotations

import pytest
from mv.api.instruments import crypto_instrument


def test_builds_instruments_for_the_majors() -> None:
    for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "XRP/USDT", "LTC/USDT"]:
        inst = crypto_instrument(sym)
        assert str(inst.id) == sym.replace("/", "") + ".BINANCE"
        # Prices/sizes round-trip through the instrument's precision (loop needs this).
        assert inst.make_price(123.45) is not None
        assert inst.make_qty(0.001) is not None


def test_rejects_malformed_symbols() -> None:
    with pytest.raises(ValueError):
        crypto_instrument("BTCUSDT")  # no slash
    with pytest.raises(ValueError):
        crypto_instrument("A/B/C")  # too many parts
