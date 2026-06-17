"""Attribution — Phase-1 stub (PRD FR-P1).

Phase 1 records realized net PnL per closed trade. The full causal
decomposition into signal / timing / sizing / slippage / fees / regime
components that sum to net PnL — plus the mistake taxonomy and counterfactual
replay — is **Phase 5**. This is a labeled stub, not a passed-off
implementation: the decomposition fields stay ``None`` until then.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TradeAttribution:
    """Per-trade PnL attribution. Components are None until Phase 5."""

    trade_id: str
    net_pnl: Decimal
    fees: Decimal | None = None
    signal: Decimal | None = None
    timing: Decimal | None = None
    sizing: Decimal | None = None
    slippage: Decimal | None = None
    regime: Decimal | None = None

    def is_decomposed(self) -> bool:
        """True once the full causal decomposition is populated (Phase 5)."""
        return all(
            component is not None
            for component in (
                self.signal,
                self.timing,
                self.sizing,
                self.slippage,
                self.fees,
                self.regime,
            )
        )


def attribute(trade_id: str, net_pnl: Decimal, *, fees: Decimal | None = None) -> TradeAttribution:
    """Record a closed trade's net PnL (Phase-1 stub; full decomposition Phase 5)."""
    return TradeAttribution(trade_id=trade_id, net_pnl=net_pnl, fees=fees)
