"""Vol Desk data types — the evening gamma-screen record (the master-file row).

One :class:`GammaRow` per name holds the dealer-positioning + GEX levels the
system grades on. Derived quantities (db_change, cushion, R/R) are computed
properties so the grading logic reads them from one place. Decimal throughout;
pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class GammaRow:
    """One evening gamma-screen row: dealer positioning + the key GEX levels."""

    symbol: str
    spot: Decimal
    dealer_delta: Decimal  # current dealer delta balance (~0..1)
    prior_delta: Decimal  # prior session's delta balance
    grade: int  # 0..11 structural grade (the 11 boolean rules)
    minervini: int  # momentum score (B-Continuation gate)
    p_trans: Decimal  # positive transition level (entry trigger)
    n_trans: Decimal  # negative transition level (structural stop)
    zero_gex: Decimal  # zero-gamma flip level
    plus_gex: Decimal  # +GEX — the primary target (T1)
    cotmp: Decimal  # center of put mass — the structural floor
    cotmc: Decimal  # center of call mass — a T2 candidate
    spike_crash: bool = False  # +GEX target is a prior spike high (hard block)
    delta_pegged_2s: bool = False  # delta pegged at 1.00 for two sessions (sustained)

    @property
    def db_change(self) -> Decimal:
        """Delta-balance change vs the prior session (positive = recovering bullish)."""
        return self.dealer_delta - self.prior_delta

    @property
    def is_deep(self) -> bool:
        """Grade-11 'DEEP' — the top structural grade, which relaxes some thresholds."""
        return self.grade >= 11

    @property
    def cotmp_cushion(self) -> Decimal:
        """Fractional distance of spot above the center of put mass (the floor)."""
        return (self.spot - self.cotmp) / self.spot if self.spot > _ZERO else _ZERO

    @property
    def reward_risk(self) -> Decimal:
        """Upside to +GEX (T1) over downside to pTrans (entry sits just above pTrans)."""
        downside = self.spot - self.p_trans
        return (self.plus_gex - self.spot) / downside if downside > _ZERO else _ZERO


__all__ = ["GammaRow"]
