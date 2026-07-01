"""Vol Desk — GEX / dealer-positioning single-stock options swing logic (scaffold).

The **offline, testable core** of the Vol Desk system: the gamma-screen record,
the 5-filter setup grading (CONFIRMED / PENDING / BLOCKED), the 4-stop exit
framework, and the daily regime gate. It runs against a **mock** gamma screen so
the mechanical logic is verifiable now, while the real inputs — a paid US-options
GEX data domain behind the governor + the GEX computation engine — are the
Phase-12 follow-ons (see docs/PHASE12.md). Pure / deterministic; Decimal money;
no I/O and no real market data here.
"""

from __future__ import annotations

from mv.intelligence.gex.exits import ExitDecision, ExitThresholds, Position, evaluate_exit
from mv.intelligence.gex.grading import GradeThresholds, SetupVerdict, grade_setup
from mv.intelligence.gex.regime import (
    TRACK_B_CONTINUATION_MIN_GATES,
    TRACK_P2P_MIN_GATES,
    RegimeGate,
    RegimeSnapshot,
    RegimeThresholds,
    regime_gate,
)
from mv.intelligence.gex.types import GammaRow

__all__ = [
    "TRACK_B_CONTINUATION_MIN_GATES",
    "TRACK_P2P_MIN_GATES",
    "ExitDecision",
    "ExitThresholds",
    "GammaRow",
    "GradeThresholds",
    "Position",
    "RegimeGate",
    "RegimeSnapshot",
    "RegimeThresholds",
    "SetupVerdict",
    "evaluate_exit",
    "grade_setup",
    "regime_gate",
]
