"""Vol Desk regime overlay — the daily 3-gate go/no-go for new entries.

Basket (SPY/QQQ up > 0.5%), breadth (bull:bear > 3:1 across the universe), and
VIX dealer positioning (negative = bullish for equities). The mechanical P2P
track may enter at 2/3 on strong individual setups; the B-Continuation track
requires 3/3. A bearish HYG divergence flags smaller sizing (not a hard block).
Pure / deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

TRACK_P2P_MIN_GATES = 2  # mechanical P2P track: 2/3 gates
TRACK_B_CONTINUATION_MIN_GATES = 3  # B-Continuation track: all 3/3


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    """The market-breadth / vol inputs to the daily gate."""

    basket_change: Decimal  # the stronger of SPY/QQQ session change
    bull_bear_ratio: Decimal  # bull:bear name count across the 700-name universe
    vix_dealer_delta: Decimal  # VIX dealer positioning (negative = bullish equities)
    hyg_bearish: bool = False  # credit divergence -> size down on new entries


@dataclass(frozen=True, slots=True)
class RegimeThresholds:
    basket_min: Decimal = Decimal("0.005")  # +0.5%
    breadth_min: Decimal = Decimal("3.0")  # 3:1


@dataclass(frozen=True, slots=True)
class RegimeGate:
    """Which of the three gates passed today."""

    basket_ok: bool
    breadth_ok: bool
    vix_ok: bool
    hyg_bearish: bool

    @property
    def passed(self) -> int:
        return int(self.basket_ok) + int(self.breadth_ok) + int(self.vix_ok)

    def allows(self, *, need: int) -> bool:
        """Whether a track needing ``need`` gates may enter today."""
        return self.passed >= need


def regime_gate(
    snap: RegimeSnapshot, thresholds: RegimeThresholds = RegimeThresholds()
) -> RegimeGate:
    """Evaluate the three daily gates from a market snapshot."""
    return RegimeGate(
        basket_ok=snap.basket_change > thresholds.basket_min,
        breadth_ok=snap.bull_bear_ratio > thresholds.breadth_min,
        vix_ok=snap.vix_dealer_delta < 0,
        hyg_bearish=snap.hyg_bearish,
    )


__all__ = [
    "TRACK_B_CONTINUATION_MIN_GATES",
    "TRACK_P2P_MIN_GATES",
    "RegimeGate",
    "RegimeSnapshot",
    "RegimeThresholds",
    "regime_gate",
]
