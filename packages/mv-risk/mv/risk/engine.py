"""Pre-trade risk engine (PRD FR-R1) — the inviolable gate on every order.

``RiskEngine.check`` consults the kill-switch first (a tripped switch rejects
everything), then evaluates each hard limit against the proposed trade and the
current portfolio state. It returns an internal :class:`RiskResult`; the
decision pipeline wraps that into the journaled §5 ``RiskAssessment`` envelope
(keeping this package free of an agents dependency). Pure and deterministic —
no I/O — so every limit is unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from mv.risk.events import EventSink, RiskVetoEvent, null_sink
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """The account snapshot the risk checks evaluate against (all Decimal money)."""

    equity: Decimal
    peak_equity: Decimal
    day_start_equity: Decimal
    gross_exposure: Decimal  # sum of absolute position notionals
    net_exposure: Decimal  # signed sum of position notionals
    positions: dict[str, Decimal]  # symbol -> signed notional


@dataclass(frozen=True, slots=True)
class ProposedTrade:
    """A proposed order to size-check, as an absolute notional + side."""

    instrument: str
    side: Literal["BUY", "SELL"]
    notional: Decimal  # absolute (>= 0)


@dataclass(frozen=True, slots=True)
class RiskResult:
    """Internal verdict of a pre-trade check."""

    approved: bool
    breached_limits: tuple[str, ...]
    max_size_allowed: Decimal
    notes: str = ""


class RiskEngine:
    """Evaluates the hard limits and the kill-switch on every proposed order."""

    def __init__(
        self,
        limits: RiskLimits,
        kill_switch: KillSwitch,
        *,
        event_sink: EventSink = null_sink,
    ) -> None:
        self._limits = limits
        self._kill = kill_switch
        self._emit = event_sink

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def check(self, trade: ProposedTrade, state: PortfolioState) -> RiskResult:
        """Approve or veto ``trade`` given ``state``. Veto is absolute (BR-003)."""
        if self._kill.is_tripped():
            result = RiskResult(
                approved=False,
                breached_limits=("kill_switch",),
                max_size_allowed=_ZERO,
                notes="trading disabled by kill-switch",
            )
            self._emit(RiskVetoEvent(trade.instrument, result.breached_limits))
            return result

        limits = self._limits
        equity = state.equity
        signed = trade.notional if trade.side == "BUY" else -trade.notional
        current = state.positions.get(trade.instrument, _ZERO)
        new_notional = current + signed

        breaches: list[str] = []

        # Account-level breakers.
        if state.day_start_equity > 0:
            day_pnl = state.equity - state.day_start_equity
            if day_pnl <= -(limits.daily_loss_limit_pct * state.day_start_equity):
                breaches.append("daily_loss")
        if state.peak_equity > 0:
            drawdown = (state.peak_equity - state.equity) / state.peak_equity
            if drawdown >= limits.max_drawdown_pct:
                breaches.append("max_drawdown")

        # Per-position caps.
        position_cap = limits.max_position_pct * equity
        concentration_cap = limits.concentration_pct * equity
        kelly_cap = limits.kelly_fraction_cap * equity
        if abs(new_notional) > position_cap:
            breaches.append("max_position")
        if abs(new_notional) > concentration_cap:
            breaches.append("concentration")
        if abs(new_notional) > kelly_cap:
            breaches.append("kelly_cap")

        # Portfolio exposure caps.
        new_gross = state.gross_exposure - abs(current) + abs(new_notional)
        if new_gross > limits.gross_exposure_cap * equity:
            breaches.append("gross_exposure")
        new_net = state.net_exposure - current + new_notional
        if abs(new_net) > limits.net_exposure_cap * equity:
            breaches.append("net_exposure")

        # Headroom under the binding per-position cap (>= 0).
        binding = min(position_cap, concentration_cap, kelly_cap)
        max_size_allowed = max(_ZERO, binding - abs(current))

        approved = not breaches
        result = RiskResult(
            approved=approved,
            breached_limits=tuple(breaches),
            max_size_allowed=max_size_allowed,
            notes="ok" if approved else f"breached: {', '.join(breaches)}",
        )
        if not approved:
            self._emit(RiskVetoEvent(trade.instrument, result.breached_limits))
        return result
