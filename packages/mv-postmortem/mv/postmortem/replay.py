"""Counterfactual replay (PRD FR-P3) — the cost of the actual choice.

Re-runs a **recorded** scenario with exactly **one variable changed** (half size,
limit-vs-market, rotation on/off) and reports the PnL delta — what the actual
decision cost versus the alternative. The runner is **injected** (a
``params -> realized net PnL`` callable) so this module stays free of the paper-
loop/NautilusTrader dependency; the API and the offline demo wire
``run_paper_session`` over the recorded bars in. Deterministic over recorded
data — same point-in-time discipline as the live loop, no look-ahead.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from mv.postmortem.trades import Fill, reconstruct_closed_trades

# A replay runner: given a parameter set, return the scenario's realized net PnL.
PnLRunner = Callable[[Mapping[str, Any]], Decimal]


@dataclass(frozen=True, slots=True)
class ReplayVariable:
    """The single variable to change, with its actual and counterfactual values."""

    name: str  # e.g. "size_multiplier", "order_type", "use_agents"
    actual: Any
    counterfactual: Any


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    """The actual vs counterfactual PnL and the delta (positive = alt. was better)."""

    variable: str
    actual_pnl: Decimal
    counterfactual_pnl: Decimal
    delta: Decimal

    @property
    def alternative_was_better(self) -> bool:
        return self.delta > 0


def replay(
    run: PnLRunner, base_params: Mapping[str, Any], variable: ReplayVariable
) -> CounterfactualResult:
    """Run the scenario twice — actual vs one-variable-changed — and diff the PnL."""
    actual_pnl = run({**base_params, variable.name: variable.actual})
    counterfactual_pnl = run({**base_params, variable.name: variable.counterfactual})
    return CounterfactualResult(
        variable=variable.name,
        actual_pnl=actual_pnl,
        counterfactual_pnl=counterfactual_pnl,
        delta=counterfactual_pnl - actual_pnl,
    )


def realized_pnl(fills: list[Fill]) -> Decimal:
    """Sum the net PnL of every closed round trip reconstructed from ``fills``."""
    total = Decimal("0")
    for trade in reconstruct_closed_trades(fills):
        total += trade.net_pnl()
    return total


__all__ = ["CounterfactualResult", "PnLRunner", "ReplayVariable", "realized_pnl", "replay"]
