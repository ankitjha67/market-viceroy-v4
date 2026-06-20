"""Cost model v1 — liquidity-aware slippage, per-venue fees, India crypto tax.

Used to make paper fills realistic (PRD FR-X2) and, later, by the validation
gate's cost-aware PnL. All money is ``Decimal``; these are pure, deterministic
functions so every component is unit-tested. The NautilusTrader paper venue
applies the maker/taker fees in-venue; slippage and the India crypto tax are
applied by this model at the journaling/accounting boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

_BPS = Decimal("10000")


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    """Maker/taker fees in basis points of notional."""

    maker_bps: Decimal = Decimal("10")  # 0.10%
    taker_bps: Decimal = Decimal("10")

    def fee(self, notional: Decimal, *, maker: bool) -> Decimal:
        """Fee charged on an absolute ``notional`` (>= 0)."""
        bps = self.maker_bps if maker else self.taker_bps
        return notional.copy_abs() * bps / _BPS


# Indicative spot crypto fee schedules (bps). Recalibrated from real fills live.
VENUE_FEES: dict[str, FeeSchedule] = {
    "binance": FeeSchedule(Decimal("10"), Decimal("10")),
    "kraken": FeeSchedule(Decimal("16"), Decimal("26")),
    "coinbase": FeeSchedule(Decimal("40"), Decimal("60")),
}

_DEFAULT_FEES = FeeSchedule()


def venue_fees(venue: str) -> FeeSchedule:
    """Fee schedule for ``venue`` (a sane default for unknown venues)."""
    return VENUE_FEES.get(venue, _DEFAULT_FEES)


def slippage_bps(
    spread_bps: Decimal,
    order_notional: Decimal,
    depth_notional: Decimal,
    *,
    impact_coef: Decimal = Decimal("10"),
) -> Decimal:
    """Liquidity-aware slippage in bps: half-spread + size-vs-depth impact.

    Impact grows with the square root of the order's size relative to available
    depth (a standard concave market-impact shape). With no/zero depth the
    order is treated as fully impactful.
    """
    if spread_bps < 0:
        raise ValueError("spread_bps must be non-negative")
    half_spread = spread_bps / 2
    if depth_notional <= 0:
        ratio = Decimal(1)
    else:
        ratio = min(Decimal(1), order_notional.copy_abs() / depth_notional)
    return half_spread + impact_coef * ratio.sqrt()


def apply_slippage(
    reference_price: Decimal,
    side: Literal["BUY", "SELL"],
    slip_bps: Decimal,
) -> Decimal:
    """Adjust a reference price for slippage: worse for the taker either way."""
    adjustment = reference_price * slip_bps / _BPS
    return reference_price + adjustment if side == "BUY" else reference_price - adjustment


@dataclass(frozen=True, slots=True)
class IndiaCryptoTax:
    """India crypto tax: flat tax on gains + TDS on transfer value (PRD FR-X2)."""

    flat_rate_bps: Decimal = Decimal("3000")  # 30% flat on gains
    tds_bps: Decimal = Decimal("100")  # 1% TDS on transfer value

    def on_gain(self, gain: Decimal) -> Decimal:
        """Flat tax on a positive gain (zero on a loss — no offset)."""
        return max(Decimal(0), gain) * self.flat_rate_bps / _BPS

    def tds(self, transfer_notional: Decimal) -> Decimal:
        """TDS withheld on the absolute transfer value."""
        return transfer_notional.copy_abs() * self.tds_bps / _BPS

    def total(self, gain: Decimal, transfer_notional: Decimal) -> Decimal:
        """Total tax drag entering net PnL."""
        return self.on_gain(gain) + self.tds(transfer_notional)


# --- Live-fill slippage recalibration write-back (PRD FR-X4) ----------------
# The post-mortem recalibrates slippage from real fills and writes the result
# here; the live cost model then *reads* the empirical value instead of a stale
# estimate. This only informs the cost model — it never relaxes a risk limit.

_SLIPPAGE_CALIBRATION: dict[str, Decimal] = {}


def set_slippage_calibration(venue: str, slippage_bps_value: Decimal) -> None:
    """Record the empirically recalibrated slippage (bps) for ``venue`` (FR-X4)."""
    _SLIPPAGE_CALIBRATION[venue] = slippage_bps_value


def calibrated_slippage_bps(venue: str, fallback_bps: Decimal) -> Decimal:
    """The recalibrated slippage for ``venue`` if one was written back, else the model fallback."""
    return _SLIPPAGE_CALIBRATION.get(venue, fallback_bps)


def clear_slippage_calibration() -> None:
    """Drop all recalibrations (test isolation)."""
    _SLIPPAGE_CALIBRATION.clear()
