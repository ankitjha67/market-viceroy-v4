"""Live-slippage recalibration (PRD FR-X4) — learn the cost model from real fills.

Once live, real fills reveal the *actual* slippage versus the intended price.
This computes the empirical realized slippage (bps) from recorded fills and
blends it with the model's prior, so the cost model stops flattering net-PnL with
a stale estimate. Pure; reuses the Phase-5 :class:`~mv.postmortem.trades.Fill`
(which already carries intended vs actual prices). Recalibration *informs* the
cost model — it never relaxes a risk limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from mv.postmortem.trades import Fill

_BPS = 10_000.0


def realized_slippage_bps(fill: Fill) -> float:
    """Realized slippage of one fill in bps (positive = worse than intended)."""
    intended = fill.intended_price if fill.intended_price is not None else fill.fill_price
    if intended <= 0:
        return 0.0
    diff = fill.fill_price - intended  # for BUY: paying more is worse (positive)
    signed = diff if fill.side == "BUY" else -diff
    return float(signed / intended) * _BPS


@dataclass(frozen=True, slots=True)
class SlippageCalibration:
    """The recalibration result the cost model can adopt."""

    n_fills: int
    observed_slippage_bps: float  # mean realized slippage (may be negative)
    recommended_slippage_bps: float  # prior blended with the observation (>= 0)


def recalibrate_slippage(
    fills: list[Fill], *, prior_bps: float = 10.0, weight: float = 0.5
) -> SlippageCalibration:
    """Blend the model's ``prior_bps`` with the mean realized slippage from ``fills``.

    ``weight`` is how much to trust the observation (0 = keep the prior, 1 =
    replace it). With no priced fills the prior is returned unchanged. The
    recommendation is floored at 0 (a better-than-intended run does not imply a
    negative slippage assumption going forward).
    """
    realized = [
        realized_slippage_bps(fill)
        for fill in fills
        if (fill.intended_price if fill.intended_price is not None else fill.fill_price) > 0
    ]
    if not realized:
        return SlippageCalibration(0, prior_bps, prior_bps)
    observed = fmean(realized)
    recommended = (1.0 - weight) * prior_bps + weight * max(0.0, observed)
    return SlippageCalibration(len(realized), observed, recommended)


__all__ = ["SlippageCalibration", "realized_slippage_bps", "recalibrate_slippage"]
