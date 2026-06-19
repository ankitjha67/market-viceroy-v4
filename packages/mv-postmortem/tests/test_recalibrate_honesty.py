"""Unit tests for live-slippage recalibration (FR-X4) + projection honesty."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from mv.postmortem.honesty import HonestyTracker, projection_honesty
from mv.postmortem.recalibrate import (
    realized_slippage_bps,
    recalibrate_slippage,
)
from mv.postmortem.trades import Fill

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, fill_price: str, intended: str | None) -> Fill:
    return Fill(
        instrument="BTC/USDT",
        side=side,
        qty=Decimal("1"),
        fill_price=Decimal(fill_price),
        ts=_T0,
        intended_price=Decimal(intended) if intended is not None else None,
    )


# ---- recalibration (FR-X4) ----------------------------------------------------


def test_realized_slippage_buy_worse_is_positive() -> None:
    # Bought at 101 vs intended 100 -> +100 bps cost.
    assert realized_slippage_bps(_fill("BUY", "101", "100")) == 100.0


def test_realized_slippage_sell_worse_is_positive() -> None:
    # Sold at 99 vs intended 100 -> +100 bps cost.
    assert realized_slippage_bps(_fill("SELL", "99", "100")) == 100.0


def test_recalibrate_blends_prior_and_observation() -> None:
    fills = [_fill("BUY", "100.5", "100"), _fill("BUY", "100.5", "100")]  # +50 bps each
    cal = recalibrate_slippage(fills, prior_bps=10.0, weight=0.5)
    assert cal.n_fills == 2
    assert cal.observed_slippage_bps == 50.0
    assert cal.recommended_slippage_bps == 30.0  # 0.5*10 + 0.5*50


def test_recalibrate_floors_recommendation_at_zero() -> None:
    fills = [_fill("BUY", "99", "100")]  # filled better than intended (-100 bps)
    cal = recalibrate_slippage(fills, prior_bps=10.0, weight=1.0)
    assert cal.observed_slippage_bps == -100.0
    assert cal.recommended_slippage_bps == 0.0


def test_recalibrate_no_priced_fills_keeps_prior() -> None:
    cal = recalibrate_slippage([], prior_bps=12.0)
    assert cal.recommended_slippage_bps == 12.0
    assert cal.n_fills == 0


# ---- projection honesty (North Star) -----------------------------------------


def test_projection_gap_is_absolute_difference() -> None:
    assert abs(projection_honesty(1.2, 0.9) - 0.3) < 1e-9
    assert projection_honesty(0.5, 1.5) == 1.0  # symmetric


def test_tracker_update_and_tolerance() -> None:
    tracker = HonestyTracker()
    tracker.update("ema_cross", paper_sharpe=1.2, live_sharpe=1.0)
    assert tracker.within_tolerance("ema_cross", 0.5) is True
    tracker.update("rsi", paper_sharpe=1.5, live_sharpe=0.5)
    assert tracker.within_tolerance("rsi", 0.5) is False
    # An untracked strategy is vacuously within tolerance.
    assert tracker.within_tolerance("unknown", 0.1) is True


def test_tracker_worst() -> None:
    tracker = HonestyTracker()
    tracker.update("a", paper_sharpe=1.0, live_sharpe=0.9)  # 0.1
    tracker.update("b", paper_sharpe=1.0, live_sharpe=0.2)  # 0.8
    worst = tracker.worst()
    assert worst is not None and worst[0] == "b"
