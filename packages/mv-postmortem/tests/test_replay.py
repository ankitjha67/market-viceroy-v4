"""Unit tests for counterfactual replay (FR-P3) — injected runner, no engine."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from mv.postmortem.replay import CounterfactualResult, ReplayVariable, realized_pnl, replay
from mv.postmortem.trades import Fill

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_replay_half_size_quantifies_the_cost() -> None:
    # A deterministic fake: PnL scales with size_multiplier (a winning scenario).
    def run(params: Mapping[str, Any]) -> Decimal:
        return Decimal("100") * Decimal(str(params["size_multiplier"]))

    result = replay(
        run,
        {"size_multiplier": 1.0},
        ReplayVariable("size_multiplier", actual=1.0, counterfactual=0.5),
    )
    assert isinstance(result, CounterfactualResult)
    assert result.actual_pnl == Decimal("100")
    assert result.counterfactual_pnl == Decimal("50")
    # Halving size would have earned less -> the alternative was worse.
    assert result.delta == Decimal("-50")
    assert result.alternative_was_better is False


def test_replay_flags_better_alternative() -> None:
    # In a losing scenario, half size loses less -> the alternative is better.
    def run(params: Mapping[str, Any]) -> Decimal:
        return Decimal("-100") * Decimal(str(params["size_multiplier"]))

    result = replay(
        run,
        {"size_multiplier": 1.0},
        ReplayVariable("size_multiplier", actual=1.0, counterfactual=0.5),
    )
    assert result.delta == Decimal("50")
    assert result.alternative_was_better is True


def test_realized_pnl_sums_closed_trades() -> None:
    fills = [
        Fill("BTC/USDT", "BUY", Decimal("1"), Decimal("100"), _T0),
        Fill("BTC/USDT", "SELL", Decimal("1"), Decimal("110"), _T0 + timedelta(hours=1)),
        Fill("BTC/USDT", "BUY", Decimal("1"), Decimal("110"), _T0 + timedelta(hours=2)),
        Fill("BTC/USDT", "SELL", Decimal("1"), Decimal("105"), _T0 + timedelta(hours=3)),
    ]
    # +10 on the first round trip, -5 on the second.
    assert realized_pnl(fills) == Decimal("5")
