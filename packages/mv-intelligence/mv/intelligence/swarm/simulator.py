"""Swarm scenario simulator — deterministic agent-based stress paths.

MiroFish-inspired, clean-room, and deliberately NOT an LLM system: where
MiroFish simulates thousands of persona agents with language models, this
engine simulates a market crowd with four mechanical agent species (trend
followers, mean reverters, noise traders, sentiment herders with contagion)
reacting to an injected shock. The output is price paths and stress statistics
for the PLANNED scenario-engine slot (ARCHITECTURE.md Section 26): what does a
news shock, a liquidity drought, or a euphoria spiral plausibly do to the path
our strategies would then trade? Seeded and fully deterministic (injected RNG);
pure; no network, no LLM, no AGPL code.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random


@dataclass(frozen=True, slots=True)
class SwarmConfig:
    """The crowd mix and market mechanics for one scenario run."""

    n_agents: int = 400
    trend_share: float = 0.30
    reverter_share: float = 0.25
    herder_share: float = 0.30  # noise traders take the remainder
    steps: int = 120
    liquidity: float = 5000.0  # demand units absorbed per 1.0 of price move
    sentiment_shock: float = 0.0  # initial herd sentiment in [-1, 1]
    shock_decay: float = 0.97  # per-step decay of the injected shock
    contagion: float = 0.35  # how strongly realized returns feed sentiment
    noise_scale: float = 0.4


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """One simulated path plus the stress statistics the risk desk reads."""

    path: tuple[float, ...]  # price levels, starting at 1.0
    terminal_return: float
    max_drawdown: float
    worst_step_return: float
    sentiment_trough: float


def simulate(config: SwarmConfig, *, seed: int) -> ScenarioResult:
    """Run one seeded scenario; identical inputs always yield identical paths."""
    rng = Random(seed)
    n = max(1, config.n_agents)
    n_trend = int(n * config.trend_share)
    n_revert = int(n * config.reverter_share)
    n_herd = int(n * config.herder_share)
    n_noise = max(0, n - n_trend - n_revert - n_herd)

    price = 1.0
    anchor = 1.0  # the reverters' fair-value memory (slow-moving)
    sentiment = max(-1.0, min(1.0, config.sentiment_shock))
    shock = sentiment
    last_return = 0.0

    path = [price]
    peak = price
    max_dd = 0.0
    worst_step = 0.0
    trough = sentiment

    for _ in range(config.steps):
        demand = 0.0
        demand += n_trend * max(-1.0, min(1.0, last_return * 25.0))
        deviation = (anchor - price) / anchor if anchor > 0 else 0.0
        demand += n_revert * max(-1.0, min(1.0, deviation * 10.0))
        demand += n_herd * sentiment
        demand += sum(rng.uniform(-config.noise_scale, config.noise_scale) for _ in range(n_noise))

        step_return = demand / config.liquidity if config.liquidity > 0 else 0.0
        step_return = max(-0.25, min(0.25, step_return))
        price *= 1.0 + step_return
        anchor += (price - anchor) * 0.02

        shock *= config.shock_decay
        sentiment = max(
            -1.0, min(1.0, shock + config.contagion * max(-1.0, min(1.0, step_return * 25.0)))
        )

        last_return = step_return
        path.append(price)
        peak = max(peak, price)
        max_dd = max(max_dd, (peak - price) / peak if peak > 0 else 0.0)
        worst_step = min(worst_step, step_return)
        trough = min(trough, sentiment)

    return ScenarioResult(
        path=tuple(path),
        terminal_return=price - 1.0,
        max_drawdown=max_dd,
        worst_step_return=worst_step,
        sentiment_trough=trough,
    )


def preset_scenarios() -> dict[str, SwarmConfig]:
    """The named stress presets the risk desk runs (Section 26 targets)."""
    return {
        "news_shock": SwarmConfig(sentiment_shock=-0.6),
        "euphoria": SwarmConfig(sentiment_shock=0.6),
        "liquidity_drought": SwarmConfig(sentiment_shock=-0.3, liquidity=1500.0),
        "calm": SwarmConfig(),
    }


def run_presets(*, seed: int) -> dict[str, ScenarioResult]:
    """All presets under one seed (comparable across scenarios)."""
    return {name: simulate(cfg, seed=seed) for name, cfg in preset_scenarios().items()}


__all__ = ["ScenarioResult", "SwarmConfig", "preset_scenarios", "run_presets", "simulate"]
