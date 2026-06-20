"""Unit tests for the pre-trade risk engine (FR-R1; demonstrates US-007 veto)."""

from __future__ import annotations

from decimal import Decimal

from mv.risk.engine import PortfolioState, ProposedTrade, RiskEngine
from mv.risk.events import EventSink, RiskVetoEvent
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits


def _state(
    *,
    equity: str = "100000",
    peak: str = "100000",
    day_start: str = "100000",
    gross: str = "0",
    net: str = "0",
    positions: dict[str, Decimal] | None = None,
) -> PortfolioState:
    return PortfolioState(
        equity=Decimal(equity),
        peak_equity=Decimal(peak),
        day_start_equity=Decimal(day_start),
        gross_exposure=Decimal(gross),
        net_exposure=Decimal(net),
        positions=positions or {},
    )


def _engine(sink: EventSink | None = None) -> tuple[RiskEngine, KillSwitch]:
    ks = KillSwitch()
    engine = RiskEngine(RiskLimits.aggressive(), ks, event_sink=sink or (lambda _e: None))
    return engine, ks


def _buy(notional: str, instrument: str = "BTC/USDT") -> ProposedTrade:
    return ProposedTrade(instrument=instrument, side="BUY", notional=Decimal(notional))


def test_approves_within_limits() -> None:
    engine, _ = _engine()
    result = engine.check(_buy("10000"), _state())
    assert result.approved is True
    assert result.breached_limits == ()
    # Headroom = 20% of 100k position cap (the binding per-position cap), no current pos.
    assert result.max_size_allowed == Decimal("20000.00")


def test_blown_account_breaks_the_account_level_breakers() -> None:
    # A non-positive day-start / peak equity (a blown account) must trip the
    # inviolable breakers, not silently skip them.
    engine, _ = _engine()
    result = engine.check(_buy("1"), _state(equity="0", peak="0", day_start="0"))
    assert result.approved is False
    assert "daily_loss" in result.breached_limits
    assert "max_drawdown" in result.breached_limits


def test_max_position_veto_emits_event() -> None:
    events: list[object] = []
    engine, _ = _engine(events.append)
    result = engine.check(_buy("25000"), _state())
    assert result.approved is False
    assert "max_position" in result.breached_limits
    assert "concentration" not in result.breached_limits  # 25k < 50k
    assert any(isinstance(e, RiskVetoEvent) for e in events)


def test_concentration_and_kelly_breach() -> None:
    engine, _ = _engine()
    result = engine.check(_buy("60000"), _state())
    assert {"max_position", "concentration", "kelly_cap"} <= set(result.breached_limits)


def test_sell_reduces_position_ok() -> None:
    engine, _ = _engine()
    state = _state(positions={"BTC/USDT": Decimal("15000")}, gross="15000", net="15000")
    result = engine.check(ProposedTrade("BTC/USDT", "SELL", Decimal("10000")), state)
    assert result.approved is True  # ends at 5000 notional


def test_gross_exposure_breach() -> None:
    engine, _ = _engine()
    state = _state(gross="95000", net="0")
    result = engine.check(_buy("10000"), state)
    assert "gross_exposure" in result.breached_limits


def test_net_exposure_breach() -> None:
    engine, _ = _engine()
    state = _state(gross="95000", net="95000", positions={"ETH/USDT": Decimal("95000")})
    result = engine.check(_buy("10000"), state)
    assert "net_exposure" in result.breached_limits


def test_daily_loss_breach() -> None:
    engine, _ = _engine()
    # Down 4% on the day vs a 3% limit; drawdown stays under 20%.
    state = _state(equity="96000", peak="100000", day_start="100000")
    result = engine.check(_buy("1000"), state)
    assert result.breached_limits == ("daily_loss",)


def test_max_drawdown_breach() -> None:
    engine, _ = _engine()
    # 25% below peak vs a 20% breaker; day flat so no daily-loss breach.
    state = _state(equity="75000", peak="100000", day_start="75000")
    result = engine.check(_buy("1000"), state)
    assert "max_drawdown" in result.breached_limits


def test_kill_switch_rejects_everything() -> None:
    events: list[object] = []
    engine, ks = _engine(events.append)
    ks.trip(reason="manual halt")
    result = engine.check(_buy("1"), _state())
    assert result.approved is False
    assert result.breached_limits == ("kill_switch",)
    assert result.max_size_allowed == Decimal("0")
    assert any(isinstance(e, RiskVetoEvent) for e in events)
