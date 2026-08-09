"""The live position must be a signed QUANTITY, not accumulated fill notional.

Regression for the desync that suppressed exits: summing each leg's own fill
notional only equals the position while price is unchanged. Once price moves
between legs, the accumulator can read flat while the book is still long (so
the flip guard refuses the exit the ensemble asked for) or read short while the
book is flat (so the loop doubles a short).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from mv.api.paper_loop import EnsembleStrategy
from mv.journal.journal import Journal
from mv.risk.engine import RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.test_kit.providers import TestInstrumentProvider


class _Value:
    def __init__(self, value: float) -> None:
        self._value = value

    def as_double(self) -> float:
        return self._value


class _FillEvent:
    """The duck-typed subset of OrderFilled that on_order_filled reads."""

    def __init__(self, side: Any, qty: float, price: float) -> None:
        self.order_side = side
        self.last_qty = _Value(qty)
        self.last_px = _Value(price)
        self.commission = _Value(0.0)


def _strategy() -> EnsembleStrategy:
    instrument = TestInstrumentProvider.btcusdt_binance()
    from alphakit.bridges.nautilus_bridge import bar_type_for

    return EnsembleStrategy(
        instrument=instrument,
        bar_type=bar_type_for(instrument.id, "1h"),
        strategies=[],
        risk_engine=RiskEngine(RiskLimits.aggressive(), KillSwitch()),
        journal=Journal(),
        symbol="BTC/USDT",
        warmup=30,
        starting_equity=Decimal("1000"),
    )


def test_partial_exit_at_a_higher_price_stays_long() -> None:
    strategy = _strategy()
    strategy.on_order_filled(_FillEvent(OrderSide.BUY, 1.0, 100.0))
    assert strategy._position_qty == Decimal("1")

    # Sell HALF the quantity after price doubles. The old accumulator booked
    # +100 then -100 and read FLAT while the book is still long 0.5.
    strategy.on_order_filled(_FillEvent(OrderSide.SELL, 0.5, 200.0))
    assert strategy._position_qty == Decimal("0.5"), "still long after a partial exit"


def test_full_exit_at_a_lower_price_is_flat_not_long() -> None:
    strategy = _strategy()
    strategy.on_order_filled(_FillEvent(OrderSide.BUY, 1.0, 200.0))
    strategy.on_order_filled(_FillEvent(OrderSide.SELL, 1.0, 100.0))
    # The old accumulator booked +200 then -100 and read LONG 100 while flat,
    # which suppressed the next BUY the ensemble asked for.
    assert strategy._position_qty == Decimal("0"), "flat after a full exit"


def test_flip_to_short_is_signed_by_quantity() -> None:
    strategy = _strategy()
    strategy.on_order_filled(_FillEvent(OrderSide.BUY, 1.0, 100.0))
    strategy.on_order_filled(_FillEvent(OrderSide.SELL, 3.0, 50.0))
    # Cash flow would read +100 - 150 = -50 (looks short 50 notional); the true
    # book is short 2 units, worth 100 at the current price.
    assert strategy._position_qty == Decimal("-2")
    assert strategy._position_qty * Decimal("50") == Decimal("-100")


def test_journaled_leg_notional_is_the_trade_not_the_position() -> None:
    strategy = _strategy()
    strategy.on_order_filled(_FillEvent(OrderSide.BUY, 2.0, 100.0))
    strategy.on_order_filled(_FillEvent(OrderSide.SELL, 1.0, 300.0))
    legs = [e.payload for e in strategy._journal.entries() if e.kind == "execution"]
    assert Decimal(legs[0]["notional"]) == Decimal("200")  # this leg's own cash flow
    assert Decimal(legs[1]["notional"]) == Decimal("-300")
    assert [leg["side"] for leg in legs] == ["BUY", "SELL"]
