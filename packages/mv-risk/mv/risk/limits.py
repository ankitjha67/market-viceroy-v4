"""Hard risk limits — inviolable infrastructure (PRD FR-R1/R3, BR-003).

These bound every order. They are Operator-set and may be tightened or loosened
by the Operator only; no agent and no autonomy setting may override them. All
values are ``Decimal`` ratios so the money arithmetic in the engine stays
exact. The defaults are the Operator-chosen **Aggressive** profile.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RiskLimits(BaseModel):
    """Per-account hard limits. Ratios are fractions of current equity."""

    model_config = ConfigDict(frozen=True)

    max_position_pct: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    """Max absolute notional of any single position / equity."""

    gross_exposure_cap: Decimal = Field(default=Decimal("1.0"), gt=0)
    """Max sum of absolute position notionals / equity."""

    net_exposure_cap: Decimal = Field(default=Decimal("1.0"), gt=0)
    """Max absolute net (signed) notional / equity."""

    concentration_pct: Decimal = Field(default=Decimal("0.50"), gt=0, le=1)
    """Max single-asset concentration / equity."""

    daily_loss_limit_pct: Decimal = Field(default=Decimal("0.03"), gt=0, le=1)
    """Daily realized+unrealized loss vs the day's starting equity."""

    max_drawdown_pct: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    """Drawdown from peak equity that trips the breaker."""

    kelly_fraction_cap: Decimal = Field(default=Decimal("0.50"), gt=0, le=1)
    """Hard ceiling on the fraction of equity any single position may use."""

    @classmethod
    def aggressive(cls) -> RiskLimits:
        """The Operator-chosen Phase-1 defaults."""
        return cls()

    @classmethod
    def moderate(cls) -> RiskLimits:
        return cls(
            max_position_pct=Decimal("0.10"),
            daily_loss_limit_pct=Decimal("0.02"),
            max_drawdown_pct=Decimal("0.15"),
            kelly_fraction_cap=Decimal("0.50"),
        )

    @classmethod
    def conservative(cls) -> RiskLimits:
        return cls(
            max_position_pct=Decimal("0.05"),
            daily_loss_limit_pct=Decimal("0.01"),
            max_drawdown_pct=Decimal("0.10"),
            kelly_fraction_cap=Decimal("0.25"),
        )
