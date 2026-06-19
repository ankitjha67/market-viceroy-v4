"""Graduation gate (PRD BR-005, US-010, FR-P6) — paper record → live eligibility.

A strategy may reach **live capital** only after a *sustained honest paper
record*. This module computes **eligibility**; the actual promotion is a
separate Operator-authed, journaled action (FR-P6) — eligibility never
auto-promotes. The Operator-chosen **Conservative** bar is the default:

- the strategy is gate-``active`` (real-feed, validated — never synthetic),
- ≥ 3 months sustained paper, OOS Sharpe ≥ 1.0, max drawdown ≤ 10%,
  ≥ 100 paper trades, and
- once live, projection honesty |live − paper Sharpe| ≤ 0.5 (an *ongoing*
  check — absent before any live history, enforced after).

Initial live capital is capped at ≤ 1% of equity. Thresholds are stored config,
retunable. Money is ``Decimal``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# The gate status a strategy must hold to be allocatable (alphakit GateStatus.ACTIVE).
_ACTIVE = "active"


class GraduationThresholds(BaseModel):
    """The bar a paper record must clear to be live-eligible (Operator-set)."""

    model_config = ConfigDict(frozen=True)

    min_months_paper: float = Field(default=3.0, gt=0)
    min_oos_sharpe: float = Field(default=1.0)
    max_drawdown: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    min_trades: int = Field(default=100, ge=0)
    max_projection_gap: float = Field(default=0.5, ge=0)
    """Tolerance on |live − paper Sharpe| once live (projection honesty)."""
    live_cap_pct: Decimal = Field(default=Decimal("0.01"), gt=0, le=1)
    """Initial live capital cap as a fraction of equity."""

    @classmethod
    def conservative(cls) -> GraduationThresholds:
        """The Operator-chosen first-live bar (the defaults)."""
        return cls()

    @classmethod
    def moderate(cls) -> GraduationThresholds:
        return cls(
            min_months_paper=2.0,
            min_oos_sharpe=0.7,
            max_drawdown=Decimal("0.15"),
            min_trades=50,
            max_projection_gap=0.75,
            live_cap_pct=Decimal("0.02"),
        )

    @classmethod
    def aggressive(cls) -> GraduationThresholds:
        return cls(
            min_months_paper=1.0,
            min_oos_sharpe=0.5,
            max_drawdown=Decimal("0.20"),
            min_trades=30,
            max_projection_gap=1.0,
            live_cap_pct=Decimal("0.05"),
        )


@dataclass(frozen=True, slots=True)
class PaperRecord:
    """A strategy's sustained paper-trading record, the input to the gate."""

    strategy: str
    gate_status: str  # "active" | "observe" | "failed" (alphakit GateStatus)
    months_paper: float
    oos_sharpe: float
    max_drawdown: Decimal  # positive fraction of peak equity (0.08 = 8%)
    n_trades: int
    projection_honesty: float | None = None  # |live − paper Sharpe|; None pre-live


@dataclass(frozen=True, slots=True)
class GraduationVerdict:
    """The eligibility verdict + the live cap that would apply."""

    eligible: bool
    reasons: list[str] = field(default_factory=list)
    live_cap_pct: Decimal = Decimal("0")


def evaluate_graduation(
    record: PaperRecord, thresholds: GraduationThresholds | None = None
) -> GraduationVerdict:
    """Pure eligibility check (BR-005). Eligible only if **every** criterion passes."""
    bar = thresholds or GraduationThresholds.conservative()
    reasons: list[str] = []

    if record.gate_status != _ACTIVE:
        reasons.append(f"gate status '{record.gate_status}' is not 'active' (not allocatable)")
    if record.months_paper < bar.min_months_paper:
        reasons.append(f"paper record {record.months_paper:.1f}mo < {bar.min_months_paper:.1f}mo")
    if record.oos_sharpe < bar.min_oos_sharpe:
        reasons.append(f"OOS Sharpe {record.oos_sharpe:.2f} < {bar.min_oos_sharpe:.2f}")
    if record.max_drawdown > bar.max_drawdown:
        reasons.append(f"max drawdown {record.max_drawdown} > {bar.max_drawdown}")
    if record.n_trades < bar.min_trades:
        reasons.append(f"{record.n_trades} paper trades < {bar.min_trades}")
    # Projection honesty is an ongoing post-live check: enforced only when a live
    # record exists (None means no live history yet, so it cannot fail here).
    if record.projection_honesty is not None and record.projection_honesty > bar.max_projection_gap:
        reasons.append(
            f"projection gap {record.projection_honesty:.2f} > {bar.max_projection_gap:.2f}"
        )

    eligible = not reasons
    return GraduationVerdict(
        eligible=eligible,
        reasons=reasons,
        live_cap_pct=bar.live_cap_pct if eligible else Decimal("0"),
    )


__all__ = [
    "GraduationThresholds",
    "GraduationVerdict",
    "PaperRecord",
    "evaluate_graduation",
]
