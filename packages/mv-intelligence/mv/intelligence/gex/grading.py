"""Vol Desk setup grading — the five mechanical filters gating every entry.

Grade >= 9/11, db_change (with the DEEP + sustained-peg exceptions), COTMP cushion
(with the DEEP / high-db relaxation), no spike-crash, and R/R >= 2.0 -> a
:class:`SetupVerdict` of CONFIRMED / PENDING / BLOCKED with the per-filter reasons.
Thresholds live in :class:`GradeThresholds` so the encoded interpretation of the
system's rules is explicit and tunable. Pure / deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from mv.intelligence.gex.types import GammaRow

Status = Literal["CONFIRMED", "PENDING", "BLOCKED"]


@dataclass(frozen=True, slots=True)
class GradeThresholds:
    """The tunable bars for the five filters (the system's stated defaults)."""

    min_grade: int = 9
    db_change_min: Decimal = Decimal("0.50")
    db_change_min_deep: Decimal = Decimal("0.30")  # grade-11 DEEP
    db_change_high: Decimal = Decimal("0.70")  # "high db_change" -> cushion relaxation
    cushion_min: Decimal = Decimal("0.02")  # 2.0% above COTMP
    cushion_min_relaxed: Decimal = Decimal("0.01")  # 1.0% for DEEP / high-db
    reward_risk_min: Decimal = Decimal("2.0")
    pending_band: Decimal = Decimal("0.005")  # within 0.5% below pTrans -> watching


@dataclass(frozen=True, slots=True)
class SetupVerdict:
    """The graded outcome for one name: the actionable status + why."""

    symbol: str
    status: Status
    reward_risk: Decimal
    cushion: Decimal
    reasons: tuple[str, ...]


def grade_setup(
    row: GammaRow,
    thresholds: GradeThresholds = GradeThresholds(),
    *,
    confirmed_close_above_ptrans: bool = False,
) -> SetupVerdict:
    """Grade one gamma-screen row through the five filters.

    ``confirmed_close_above_ptrans`` is the entry trigger — the first 5-minute
    candle close above pTrans. Without it a passing setup is at most PENDING
    (watching); with it, and spot above pTrans, it is CONFIRMED.
    """
    reasons: list[str] = []
    blocked = False

    if row.grade < thresholds.min_grade:
        blocked = True
        reasons.append(f"grade {row.grade} < {thresholds.min_grade}")

    if row.spike_crash:
        blocked = True
        reasons.append("spike-crash target (hard block)")

    # db_change: a two-session peg at 1.00 is sustained (exempt); DEEP gets a lower bar.
    if row.delta_pegged_2s:
        reasons.append("db exempt: delta pegged 1.00 x2 (sustained)")
    else:
        db_min = thresholds.db_change_min_deep if row.is_deep else thresholds.db_change_min
        if row.db_change < db_min:
            blocked = True
            reasons.append(f"db_change {row.db_change} < {db_min}")

    # COTMP cushion: DEEP or a *high* db_change relaxes the floor from 2% to 1%.
    relaxed = row.is_deep or row.db_change >= thresholds.db_change_high
    cushion_min = thresholds.cushion_min_relaxed if relaxed else thresholds.cushion_min
    if row.cotmp_cushion < cushion_min:
        blocked = True
        reasons.append(f"cotmp cushion {row.cotmp_cushion:.2%} < {cushion_min:.0%}")

    if row.reward_risk < thresholds.reward_risk_min:
        blocked = True
        reasons.append(f"R/R {row.reward_risk:.2f} < {thresholds.reward_risk_min}")

    if not blocked and not reasons:
        reasons.append("all filters pass")
    status = _status(row, thresholds, blocked=blocked, confirmed=confirmed_close_above_ptrans)
    return SetupVerdict(
        symbol=row.symbol,
        status=status,
        reward_risk=row.reward_risk,
        cushion=row.cotmp_cushion,
        reasons=tuple(reasons),
    )


def _status(
    row: GammaRow, thresholds: GradeThresholds, *, blocked: bool, confirmed: bool
) -> Status:
    if blocked:
        return "BLOCKED"
    if confirmed and row.spot > row.p_trans:
        return "CONFIRMED"
    lower = row.p_trans * (Decimal("1") - thresholds.pending_band)
    if lower <= row.spot <= row.p_trans:  # within 0.5% below pTrans, watching the candle
        return "PENDING"
    if row.spot > row.p_trans:  # above pTrans but no confirmed 5-min close yet
        return "PENDING"
    return "BLOCKED"  # filters pass but spot is not in the actionable zone


__all__ = ["GradeThresholds", "SetupVerdict", "grade_setup"]
