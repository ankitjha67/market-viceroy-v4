"""Vol Desk exit framework — the only thing that governs an open position.

Once in, the entry filters no longer apply. Four stops (structural nTrans close,
a hard -10% below pTrans, a day-7 time stop, a stalling rule) plus the T1/+GEX
profit rule (take it, or lock the stop to entry and ride to T2). The single point
of discretion is at T1; everything else is mechanical. Pure / deterministic —
the caller supplies the current row + the day count + recent daily progress.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from mv.intelligence.gex.types import GammaRow

_ZERO = Decimal("0")
Action = Literal["HOLD", "WATCH", "EXIT", "LOCK_T1", "TAKE_T1"]


@dataclass(frozen=True, slots=True)
class Position:
    """An open Vol Desk position."""

    symbol: str
    entry: Decimal
    entry_day: int  # the session index the position was opened on
    t1: Decimal  # +GEX target
    t1_locked: bool = False


@dataclass(frozen=True, slots=True)
class ExitThresholds:
    """The stop parameters (the system's stated defaults)."""

    hard_stop: Decimal = Decimal("0.10")  # -10% from entry (while below pTrans)
    time_stop_day: int = 7
    time_stop_progress: Decimal = Decimal("0.50")  # >= 50% of the way to T1 by day 7
    stall_daily: Decimal = Decimal("0.10")  # < 10%/day progress ...
    stall_sessions: int = 3  # ... for 3 consecutive sessions -> exit


@dataclass(frozen=True, slots=True)
class ExitDecision:
    action: Action
    reason: str


def progress_to_t1(pos: Position, spot: Decimal) -> Decimal:
    """Fraction of the entry -> T1 distance covered (can be < 0 when underwater)."""
    span = pos.t1 - pos.entry
    return (spot - pos.entry) / span if span > _ZERO else _ZERO


def evaluate_exit(
    pos: Position,
    row: GammaRow,
    *,
    day: int,
    daily_progress: Sequence[Decimal] = (),
    thresholds: ExitThresholds = ExitThresholds(),
    take_profit_at_t1: bool = False,
) -> ExitDecision:
    """The exit decision for an open position given the latest data.

    Stops are checked before the target (protect capital first). At T1,
    ``take_profit_at_t1`` chooses between banking the gain (TAKE_T1) and locking
    the stop to entry to ride toward T2 (LOCK_T1) — the system's one discretionary
    fork. ``daily_progress`` is the recent per-session progress toward T1 (for the
    stalling rule).
    """
    # Stop 1 — structural: a close below nTrans.
    if row.spot < row.n_trans:
        return ExitDecision("EXIT", "stop 1: closed below nTrans")
    # Stop 2 — hard: -10% from entry while below pTrans.
    if row.spot <= pos.entry * (Decimal("1") - thresholds.hard_stop) and row.spot < row.p_trans:
        return ExitDecision("EXIT", "stop 2: -10% from entry and below pTrans")
    # Target — T1 (+GEX) reached.
    if row.spot >= pos.t1:
        if take_profit_at_t1:
            return ExitDecision("TAKE_T1", "T1 (+GEX) reached: bank the gain")
        return ExitDecision("LOCK_T1", "T1 (+GEX) reached: lock stop to entry, ride to T2")
    progress = progress_to_t1(pos, row.spot)
    # Stop 3 — time: by day 7, need >= 50% progress.
    if day - pos.entry_day >= thresholds.time_stop_day and progress < thresholds.time_stop_progress:
        return ExitDecision("EXIT", f"stop 3: day {day - pos.entry_day}, only {progress:.0%} to T1")
    # Stop 4 — stalling: < 10%/day for the last 3 sessions.
    recent = list(daily_progress)[-thresholds.stall_sessions :]
    if len(recent) >= thresholds.stall_sessions and all(p < thresholds.stall_daily for p in recent):
        return ExitDecision("EXIT", "stop 4: stalling < 10%/day x3")
    # Hold states.
    if row.spot > row.p_trans:
        return ExitDecision("HOLD", "CONFIRMED: above pTrans")
    return ExitDecision("WATCH", "below pTrans but above nTrans: hold, add nothing")


__all__ = ["ExitDecision", "ExitThresholds", "Position", "evaluate_exit", "progress_to_t1"]
