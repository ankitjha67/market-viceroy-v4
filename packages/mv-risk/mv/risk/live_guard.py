"""The live-order guard (PRD BR-005, FR-P6, FR-X1) — paper by default, capped live.

The same strategy code runs paper↔live; this guard is what makes the *live* path
safe. In **paper** mode every order passes at full size. In **live** mode an
order is allowed **only** if its strategy/instrument has been graduated (BR-005 —
no live without graduation), and its size is **clamped to the live capital cap**.
The inviolable :class:`~mv.risk.engine.RiskEngine` still gates the order
afterwards; this guard sits in front of it, not instead of it. Pure and
unit-tested; the loop calls it before submitting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Mode = Literal["paper", "live"]


@dataclass(frozen=True, slots=True)
class LiveGuardConfig:
    """How the loop should treat orders: paper (default) or capped live."""

    mode: Mode = "paper"
    graduated: frozenset[str] = field(default_factory=frozenset)
    """Strategy/instrument keys the Operator has graduated for live (FR-P6)."""
    live_cap_pct: Decimal = Decimal("0.01")
    """Live capital cap as a fraction of equity (Conservative default)."""


@dataclass(frozen=True, slots=True)
class LiveOrderDecision:
    """The guard's verdict for one order."""

    allowed: bool
    notional: Decimal  # possibly clamped to the live cap (0 when blocked)
    reason: str


def gate_live_order(
    config: LiveGuardConfig, *, key: str, notional: Decimal, equity: Decimal
) -> LiveOrderDecision:
    """Allow/clamp an order per the live guard (BR-005). Paper mode is a pass-through."""
    if config.mode == "paper":
        return LiveOrderDecision(True, notional, "paper mode")

    # Live mode: no live order for an ungraduated key (BR-005).
    if key not in config.graduated:
        return LiveOrderDecision(
            False, Decimal("0"), f"'{key}' not graduated — no live order (BR-005)"
        )

    cap = (config.live_cap_pct * equity).copy_abs()
    magnitude = min(notional.copy_abs(), cap)
    clamped = magnitude if notional >= 0 else -magnitude
    return LiveOrderDecision(True, clamped, f"graduated; clamped to {config.live_cap_pct} live cap")


__all__ = ["LiveGuardConfig", "LiveOrderDecision", "Mode", "gate_live_order"]
