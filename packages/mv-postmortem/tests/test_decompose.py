"""Unit tests for the causal PnL decomposition (sums to net; FR-P1)."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal

from mv.postmortem.decompose import components_sum, decompose
from mv.postmortem.trades import ClosedTrade

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
_T1 = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _trade(**over: object) -> ClosedTrade:
    base: dict[str, object] = {
        "trade_id": "t1",
        "instrument": "BTC/USDT",
        "direction": 1,
        "qty": Decimal("2"),
        "decision_ref_price": Decimal("100"),
        "entry_intended_price": Decimal("101"),
        "entry_fill_price": Decimal("101.5"),
        "exit_intended_price": Decimal("110"),
        "exit_fill_price": Decimal("109.5"),
        "target_qty": Decimal("2"),
        "fees": Decimal("3"),
        "opened_at": _T0,
        "closed_at": _T1,
        "regime_drift": Decimal("0"),
    }
    base.update(over)
    return ClosedTrade(**base)  # type: ignore[arg-type]


def test_components_sum_to_net_exactly() -> None:
    attr = decompose(_trade())
    assert components_sum(attr) == attr.net_pnl
    assert attr.is_decomposed()


def test_winning_long_signal_positive() -> None:
    attr = decompose(_trade())
    # Long, price rose ~100 -> ~110: the directional signal dominates and is +.
    assert attr.signal is not None and attr.signal > 0
    assert attr.fees == Decimal("-3")


def test_slippage_is_negative_when_filled_worse() -> None:
    # Entry filled above intended, exit filled below intended -> give-up both legs.
    attr = decompose(_trade())
    assert attr.slippage is not None and attr.slippage < 0


def test_regime_carves_benchmark_out_of_signal() -> None:
    # Half the up-move was the regime drifting; signal should drop by that slice.
    flat = decompose(_trade(regime_drift=Decimal("0")))
    with_regime = decompose(_trade(regime_drift=Decimal("4")))
    assert flat.signal is not None and with_regime.signal is not None
    assert with_regime.signal < flat.signal
    # Sum-to-net invariant still holds with a regime benchmark.
    assert components_sum(with_regime) == with_regime.net_pnl


def test_sizing_zero_when_actual_equals_reference() -> None:
    attr = decompose(_trade(qty=Decimal("2"), target_qty=Decimal("2")))
    assert attr.sizing == Decimal("0")


def test_oversize_adds_sizing_component() -> None:
    attr = decompose(_trade(qty=Decimal("3"), target_qty=Decimal("2")))
    assert attr.sizing is not None and attr.sizing != Decimal("0")
    assert components_sum(attr) == attr.net_pnl


def test_short_direction_sums_to_net() -> None:
    attr = decompose(
        _trade(direction=-1, entry_fill_price=Decimal("110"), exit_fill_price=Decimal("100"))
    )
    assert components_sum(attr) == attr.net_pnl


def test_sum_to_net_property_random() -> None:
    rng = random.Random(20260618)
    for i in range(500):
        trade = ClosedTrade(
            trade_id=f"t{i}",
            instrument="X",
            direction=rng.choice((1, -1)),
            qty=Decimal(str(rng.randint(1, 50))),
            decision_ref_price=Decimal(str(rng.randint(50, 200))),
            entry_intended_price=Decimal(str(rng.randint(50, 200))),
            entry_fill_price=Decimal(str(rng.randint(50, 200))),
            exit_intended_price=Decimal(str(rng.randint(50, 200))),
            exit_fill_price=Decimal(str(rng.randint(50, 200))),
            target_qty=Decimal(str(rng.randint(1, 50))),
            fees=Decimal(str(rng.randint(0, 20))),
            opened_at=_T0,
            closed_at=_T1,
            regime_drift=Decimal(str(rng.randint(-30, 30))),
        )
        attr = decompose(trade)
        assert components_sum(attr) == attr.net_pnl
