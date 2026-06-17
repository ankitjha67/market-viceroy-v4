"""Cross-source reconciliation (PRD FR-D7 / BR-002).

When two or more sources report a value (e.g. the latest close) for the same
instrument, a disagreement beyond tolerance is a data-quality event and trading
on that instrument must halt — a bad tick must never trigger a trade. Pure.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """Outcome of comparing a value across sources."""

    ok: bool
    discrepancy: float
    """Relative spread (max - min) / mean across sources (0.0 if <2 sources)."""
    values: dict[str, float]


def reconcile_prices(values: dict[str, float], tolerance: float) -> ReconcileResult:
    """Compare a price across sources; ``ok`` is False if they disagree.

    With fewer than two sources there is nothing to reconcile (``ok=True``).
    Disagreement is the relative spread ``(max - min) / mean`` exceeding
    ``tolerance`` (e.g. ``0.005`` = 50 bps).
    """
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if len(values) < 2:
        return ReconcileResult(ok=True, discrepancy=0.0, values=dict(values))
    prices = list(values.values())
    mean = sum(prices) / len(prices)
    if mean == 0:
        raise ValueError("cannot reconcile around a zero mean price")
    discrepancy = (max(prices) - min(prices)) / abs(mean)
    return ReconcileResult(
        ok=discrepancy <= tolerance, discrepancy=discrepancy, values=dict(values)
    )
