"""Options expiry-payoff analytics: exact breakevens, extrema, scenario grid.

Adopted from the Vibe-Trading review (their options payoff workflow): expiry
P&L for a multi-leg position is piecewise linear in spot, so breakevens and
extrema are computed EXACTLY from the kink structure — no sampling, no
root-finding error. Short legs are negative quantities; ``premium`` is the
per-unit price paid (long) or received (short, via the sign of qty). Pure and
deterministic; floats (analytics, not accounting money).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class OptionLeg:
    """One leg: right, strike, signed quantity (short < 0), per-unit premium."""

    right: Literal["C", "P"]
    strike: float
    qty: float
    premium: float


def payoff_at(legs: list[OptionLeg], spot: float) -> float:
    """Expiry P&L of the position at ``spot``."""
    total = 0.0
    for leg in legs:
        intrinsic = max(0.0, spot - leg.strike) if leg.right == "C" else max(0.0, leg.strike - spot)
        total += leg.qty * (intrinsic - leg.premium)
    return total


def _kinks(legs: list[OptionLeg]) -> list[float]:
    points = sorted({leg.strike for leg in legs})
    return points or [0.0]


def _slope_above(legs: list[OptionLeg], x: float) -> float:
    return sum(leg.qty for leg in legs if leg.right == "C" and leg.strike <= x) - sum(
        leg.qty for leg in legs if leg.right == "P" and leg.strike > x
    )


def breakevens(legs: list[OptionLeg]) -> list[float]:
    """Every spot where expiry P&L crosses zero, exact, ascending.

    A segment lying exactly on zero contributes its endpoints (the boundary of
    the zero-P&L interval), matching how a desk quotes 'flat between A and B'.
    """
    if not legs:
        return []
    kinks = _kinks(legs)
    nodes = [0.0, *kinks]
    out: list[float] = []

    def push(x: float) -> None:
        if x >= 0 and all(abs(x - seen) > 1e-9 for seen in out):
            out.append(x)

    for i, left in enumerate(nodes):
        right = nodes[i + 1] if i + 1 < len(nodes) else None
        y_left = payoff_at(legs, left)
        slope = _slope_above(legs, left)
        if right is not None:
            y_right = payoff_at(legs, right)
            if abs(y_left) < 1e-12 and abs(y_right) < 1e-12:
                push(left)
                push(right)
            elif y_left == 0.0:
                push(left)
            elif (y_left < 0 < y_right) or (y_right < 0 < y_left):
                push(left + (right - left) * (-y_left) / (y_right - y_left))
        else:
            if abs(y_left) < 1e-12:
                push(left)
            elif slope != 0.0:
                x = left - y_left / slope
                if x > left and (y_left < 0) == (slope > 0):
                    push(x)
    return sorted(out)


def extrema(legs: list[OptionLeg]) -> tuple[float, float]:
    """(max profit, max loss) at expiry; unbounded tails report +/-inf.

    Candidates are the kinks and spot 0; the upper tail's slope decides
    unboundedness above the last strike.
    """
    if not legs:
        return 0.0, 0.0
    candidates = [payoff_at(legs, x) for x in (0.0, *_kinks(legs))]
    best, worst = max(candidates), min(candidates)
    tail = _slope_above(legs, _kinks(legs)[-1] + 1.0)
    if tail > 0:
        best = float("inf")
    elif tail < 0:
        worst = float("-inf")
    return best, worst


def scenario_grid(legs: list[OptionLeg], spots: list[float]) -> list[tuple[float, float]]:
    """Expiry P&L over a spot grid (for the deck's scenario table)."""
    return [(spot, payoff_at(legs, spot)) for spot in spots]


__all__ = ["OptionLeg", "breakevens", "extrema", "payoff_at", "scenario_grid"]
