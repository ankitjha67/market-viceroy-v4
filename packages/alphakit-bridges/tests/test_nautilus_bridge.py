"""Tests for the NautilusTrader paper bridge.

The fill test runs a real (offline, deterministic) NautilusTrader paper
backtest — no network, no Docker — proving a market order fills on the
simulated venue with maker/taker fees applied.
"""

from __future__ import annotations

import polars as pl
import pytest
from alphakit.bridges.nautilus_bridge import (
    bar_type_for,
    bars_from_frame,
    make_paper_engine,
)
from mv.failover.normalize import normalize_ohlcv
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy

_HOUR_MS = 3_600_000
_BASE_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z


class _BuyOnce(Strategy):  # type: ignore[misc]  # nautilus_trader is untyped (Any)
    """Submit one market buy on the first bar, then hold."""

    def __init__(self, bar_type: object, instrument_id: object) -> None:
        super().__init__()
        self.bar_type = bar_type
        self.instrument_id = instrument_id
        self.done = False

    def on_start(self) -> None:
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: object) -> None:
        if not self.done:
            instrument = self.cache.instrument(self.instrument_id)
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=instrument.make_qty(1),
            )
            self.submit_order(order)
            self.done = True


def _rising_frame() -> pl.DataFrame:
    rows = []
    price = 40_000.0
    for i in range(30):
        price *= 1.01
        rows.append([_BASE_MS + i * _HOUR_MS, price, price * 1.002, price * 0.998, price, 10.0])
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def test_bar_type_for_rejects_unknown_timeframe() -> None:
    instrument = TestInstrumentProvider.btcusdt_binance()
    with pytest.raises(ValueError, match="unsupported timeframe"):
        bar_type_for(instrument.id, "7s")


def test_paper_market_order_fills_with_fees() -> None:
    instrument = TestInstrumentProvider.btcusdt_binance()
    engine = make_paper_engine(venue="BINANCE")
    try:
        engine.add_instrument(instrument)
        bar_type = bar_type_for(instrument.id, "1h")
        bars = bars_from_frame(_rising_frame(), bar_type, instrument)
        assert len(bars) == 30
        engine.add_data(bars)
        engine.add_strategy(_BuyOnce(bar_type, instrument.id))
        engine.run()

        positions = engine.cache.positions()
        assert len(positions) == 1
        position = positions[0]
        assert position.quantity == instrument.make_qty(1)
        # Taker fee charged at open -> realized PnL starts negative by the fee.
        assert position.realized_pnl.as_double() < 0.0
    finally:
        engine.dispose()
