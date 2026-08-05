"""Tests for the options payoff analytics (exact breakevens + extrema)."""

from __future__ import annotations

from mv.intelligence.options_payoff import (
    OptionLeg,
    breakevens,
    extrema,
    payoff_at,
    scenario_grid,
)


def test_long_straddle_breakevens_are_exact() -> None:
    legs = [OptionLeg("C", 100.0, 1.0, 4.0), OptionLeg("P", 100.0, 1.0, 3.0)]
    assert breakevens(legs) == [93.0, 107.0]  # K -/+ total premium
    best, worst = extrema(legs)
    assert best == float("inf")  # unbounded upside
    assert worst == -7.0  # both premiums at the strike


def test_short_strangle_has_bounded_profit_unbounded_loss() -> None:
    legs = [OptionLeg("C", 110.0, -1.0, 2.0), OptionLeg("P", 90.0, -1.0, 2.0)]
    best, worst = extrema(legs)
    assert best == 4.0  # both premiums kept between the strikes
    assert worst == float("-inf")
    assert breakevens(legs) == [86.0, 114.0]


def test_covered_call_style_spread_breakeven() -> None:
    # Bull call spread 100/110 for a 4.0 net debit: breakeven at 104.
    legs = [OptionLeg("C", 100.0, 1.0, 6.0), OptionLeg("C", 110.0, -1.0, 2.0)]
    assert breakevens(legs) == [104.0]
    best, worst = extrema(legs)
    assert best == 6.0  # width 10 minus debit 4
    assert worst == -4.0


def test_scenario_grid_matches_pointwise_payoff() -> None:
    legs = [OptionLeg("P", 100.0, 1.0, 5.0)]
    grid = scenario_grid(legs, [80.0, 100.0, 120.0])
    assert grid == [(80.0, 15.0), (100.0, -5.0), (120.0, -5.0)]
    assert payoff_at(legs, 80.0) == 15.0


def test_empty_position_is_flat() -> None:
    assert breakevens([]) == []
    assert extrema([]) == (0.0, 0.0)
