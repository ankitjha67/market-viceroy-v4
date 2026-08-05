"""Tests for the swarm scenario simulator (determinism + stress behavior)."""

from __future__ import annotations

from mv.intelligence.swarm.simulator import SwarmConfig, preset_scenarios, run_presets, simulate


def test_same_seed_same_path_deterministic() -> None:
    config = SwarmConfig(sentiment_shock=-0.6)
    a = simulate(config, seed=7)
    b = simulate(config, seed=7)
    assert a.path == b.path
    assert simulate(config, seed=8).path != a.path  # the seed genuinely matters


def test_negative_shock_produces_early_drawdown() -> None:
    result = simulate(SwarmConfig(sentiment_shock=-0.8, noise_scale=0.0), seed=1)
    assert result.path[5] < 1.0  # herd selling moves price down early
    assert result.max_drawdown > 0.0
    assert result.worst_step_return < 0.0
    assert result.sentiment_trough <= -0.8


def test_liquidity_drought_amplifies_the_same_shock() -> None:
    base = SwarmConfig(sentiment_shock=-0.5, noise_scale=0.0)
    drought = SwarmConfig(sentiment_shock=-0.5, noise_scale=0.0, liquidity=1500.0)
    assert (
        simulate(drought, seed=3).max_drawdown > simulate(base, seed=3).max_drawdown
    )  # thin books make the identical crowd hit harder


def test_presets_run_and_disagree() -> None:
    names = set(preset_scenarios())
    assert {"news_shock", "euphoria", "liquidity_drought", "calm"} == names
    results = run_presets(seed=11)
    assert results["news_shock"].terminal_return < results["euphoria"].terminal_return


def test_path_is_bounded_by_step_clamp() -> None:
    # Even absurd crowd pressure cannot move more than 25 percent per step.
    result = simulate(SwarmConfig(sentiment_shock=-1.0, liquidity=1.0, noise_scale=0.0), seed=2)
    assert result.worst_step_return >= -0.25
