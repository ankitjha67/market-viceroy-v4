"""Unit tests for the hard risk limits."""

from __future__ import annotations

from decimal import Decimal

import pytest
from mv.risk.limits import RiskLimits
from pydantic import ValidationError


def test_aggressive_defaults() -> None:
    limits = RiskLimits.aggressive()
    assert limits.max_position_pct == Decimal("0.20")
    assert limits.daily_loss_limit_pct == Decimal("0.03")
    assert limits.max_drawdown_pct == Decimal("0.20")
    assert limits.kelly_fraction_cap == Decimal("0.50")
    # Default construction is the Aggressive profile.
    assert RiskLimits() == limits


def test_presets_tighten() -> None:
    cons = RiskLimits.conservative()
    mod = RiskLimits.moderate()
    assert cons.max_position_pct == Decimal("0.05")
    assert cons.daily_loss_limit_pct == Decimal("0.01")
    assert mod.max_position_pct == Decimal("0.10")


def test_limits_are_frozen() -> None:
    limits = RiskLimits()
    with pytest.raises(ValidationError):
        limits.max_position_pct = Decimal("0.5")


def test_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        RiskLimits(max_position_pct=Decimal("1.5"))
    with pytest.raises(ValidationError):
        RiskLimits(daily_loss_limit_pct=Decimal("0"))
