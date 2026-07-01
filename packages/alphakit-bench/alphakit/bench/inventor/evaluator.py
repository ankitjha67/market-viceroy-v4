"""The real candidate evaluator — build the strategy, run the Phase-2 gate.

Turns a :class:`Candidate` spec into a live ``StrategyProtocol`` and grades it
through the existing :class:`ValidationGate` (fresh cost-aware backtest →
walk-forward → regime → deflated Sharpe → Monte-Carlo → decide). This is the
``Evaluator`` the inventor loop calls in production; the price frame is injected
(accumulated **real** bars offline; synthetic in tests). Synthetic data can never
grade ACTIVE (CLAUDE.md #4), so the honest "nothing survives on synthetic"
property flows straight through. A candidate that fails to build or backtest is
graded FAILED, never crashing the run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
from alphakit.bench.inventor.candidate import Candidate
from alphakit.bench.inventor.generate import ParamGrid
from alphakit.bench.inventor.inventor import Evaluator
from alphakit.bench.validation.gate import GateResult, GateStatus, ValidationGate
from alphakit.strategies.meanrev.bollinger_reversion.strategy import BollingerReversion
from alphakit.strategies.meanrev.rsi_reversion_2.strategy import RSIReversion2
from alphakit.strategies.meanrev.zscore_reversion.strategy import ZScoreReversion
from alphakit.strategies.trend.donchian_breakout_20.strategy import DonchianBreakout20
from alphakit.strategies.trend.ema_cross_12_26.strategy import EMACross1226
from alphakit.strategies.trend.sma_cross_10_30.strategy import SMACross1030


def _ema(p: dict[str, Any]) -> Any:
    return EMACross1226(
        fast_span=int(p["fast"]),
        slow_span=int(p["slow"]),
        long_only=bool(p.get("long_only", False)),
    )


def _sma(p: dict[str, Any]) -> Any:
    return SMACross1030(
        fast_window=int(p["fast"]),
        slow_window=int(p["slow"]),
        long_only=bool(p.get("long_only", False)),
    )


def _donchian(p: dict[str, Any]) -> Any:
    return DonchianBreakout20(window=int(p["window"]), long_only=bool(p.get("long_only", False)))


def _rsi(p: dict[str, Any]) -> Any:
    return RSIReversion2(
        period=int(p["period"]),
        lower_threshold=float(p.get("lower", 10.0)),
        upper_threshold=float(p.get("upper", 90.0)),
        long_only=bool(p.get("long_only", False)),
    )


def _bollinger(p: dict[str, Any]) -> Any:
    return BollingerReversion(
        period=int(p["period"]),
        num_std=float(p.get("num_std", 2.0)),
        long_only=bool(p.get("long_only", False)),
    )


def _zscore(p: dict[str, Any]) -> Any:
    return ZScoreReversion(
        lookback=int(p["lookback"]),
        threshold=float(p.get("threshold", 2.0)),
        long_only=bool(p.get("long_only", False)),
    )


# The parameterizable crypto-capable templates the inventor searches over.
STRATEGY_FACTORIES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "ema_cross": _ema,
    "sma_cross": _sma,
    "donchian": _donchian,
    "rsi_reversion": _rsi,
    "bollinger": _bollinger,
    "zscore": _zscore,
}

# The default search space (fast < slow enforced by ``valid_combo``).
DEFAULT_GRIDS: tuple[ParamGrid, ...] = (
    ParamGrid("ema_cross", "trend", {"fast": (8, 12, 16), "slow": (21, 26, 34)}),
    ParamGrid("sma_cross", "trend", {"fast": (10, 20), "slow": (30, 50)}),
    ParamGrid("donchian", "trend", {"window": (20, 34, 55)}),
    ParamGrid("rsi_reversion", "meanrev", {"period": (2, 7, 14)}),
    ParamGrid("bollinger", "meanrev", {"period": (14, 20), "num_std": (2.0, 2.5)}),
    ParamGrid("zscore", "meanrev", {"lookback": (14, 20, 30)}),
)


def valid_combo(_strategy: str, params: dict[str, Any]) -> bool:
    """Reject nonsensical combos (a fast span >= the slow span) before backtesting."""
    if "fast" in params and "slow" in params:
        return bool(params["fast"] < params["slow"])
    return True


def build_strategy(candidate: Candidate) -> Any:
    """Instantiate the live ``StrategyProtocol`` for ``candidate``."""
    factory = STRATEGY_FACTORIES.get(candidate.strategy)
    if factory is None:
        raise KeyError(f"no strategy factory for {candidate.strategy!r}")
    return factory(candidate.param_dict)


def candidate_evaluator(
    prices: pd.DataFrame, *, data_source: str, gate: ValidationGate
) -> Evaluator:
    """An :data:`Evaluator` that grades a candidate through the gate over ``prices``."""

    def evaluate(candidate: Candidate) -> GateResult:
        try:
            strategy = build_strategy(candidate)
            return gate.evaluate(candidate.name, strategy, prices, data_source=data_source)
        except Exception as exc:  # a broken candidate is a failed candidate, not a crash
            return GateResult(
                slug=candidate.name,
                status=GateStatus.FAILED,
                data_source=data_source,
                reasons=[f"eval error: {type(exc).__name__}: {exc}"],
            )

    return evaluate


__all__ = [
    "DEFAULT_GRIDS",
    "STRATEGY_FACTORIES",
    "build_strategy",
    "candidate_evaluator",
    "valid_combo",
]
