"""The validation gate (PRD FR-V2/V3/V4, BR-001) — active / observe / failed.

A strategy reaches ``active`` (allocatable) ONLY by clearing every stage on
**real-feed** data: cost-aware net-positive, deflated-Sharpe significance,
walk-forward consistency, no catastrophic regime, and a Monte-Carlo lower bound
above zero. Synthetic-fixture results can never be ``active`` (CLAUDE.md #4) —
gross-positive alone never passes. The decision logic (:func:`decide`) is pure
and exhaustively unit-tested; :meth:`ValidationGate.evaluate` runs the stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from alphakit.bench.validation.deflated_sharpe import deflated_sharpe_ratio
from alphakit.bench.validation.monte_carlo import bootstrap_sharpe
from alphakit.bench.validation.regime import regime_consistency
from alphakit.bench.validation.walk_forward import walk_forward
from alphakit.bridges import vectorbt_bridge
from alphakit.core.metrics.returns import sharpe_ratio
from alphakit.core.protocols import StrategyProtocol


class GateStatus(str, Enum):
    ACTIVE = "active"
    OBSERVE = "observe"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GateThresholds:
    """Tunable gate thresholds (Operator-set; tightening is never weakening)."""

    min_deflated_sharpe: float = 0.95
    min_positive_window_fraction: float = 0.5
    min_regime_sharpe: float = -0.5


@dataclass(frozen=True, slots=True)
class GateInputs:
    """The stage outputs the decision rules judge."""

    data_source: str
    oos_sharpe: float
    net_positive: bool
    deflated_sharpe: float
    positive_window_fraction: float
    worst_regime_sharpe: float
    bootstrap_ci_low: float


@dataclass(frozen=True, slots=True)
class GateResult:
    """The gate verdict for one strategy."""

    slug: str
    status: GateStatus
    data_source: str
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def is_real_feed(data_source: str) -> bool:
    """True for a real-feed provenance tag (never for synthetic fixtures)."""
    tag = data_source.lower()
    return "real" in tag and "synthetic" not in tag


def decide(
    inputs: GateInputs, thresholds: GateThresholds | None = None
) -> tuple[GateStatus, list[str]]:
    """Pure decision: map stage outputs to active / observe / failed + reasons."""
    th = thresholds if thresholds is not None else GateThresholds()
    reasons: list[str] = []

    if not is_real_feed(inputs.data_source):
        return GateStatus.OBSERVE, [f"non-real data_source '{inputs.data_source}' cannot be active"]

    if inputs.oos_sharpe <= 0.0 or not inputs.net_positive:
        return GateStatus.FAILED, ["no out-of-sample edge (OOS Sharpe <= 0 or net-negative)"]

    if inputs.deflated_sharpe < th.min_deflated_sharpe:
        reasons.append(f"deflated Sharpe {inputs.deflated_sharpe:.3f} < {th.min_deflated_sharpe}")
    if inputs.positive_window_fraction < th.min_positive_window_fraction:
        reasons.append(
            f"walk-forward positive fraction {inputs.positive_window_fraction:.2f} "
            f"< {th.min_positive_window_fraction}"
        )
    if inputs.worst_regime_sharpe < th.min_regime_sharpe:
        reasons.append(
            f"worst-regime Sharpe {inputs.worst_regime_sharpe:.2f} < {th.min_regime_sharpe}"
        )
    if inputs.bootstrap_ci_low <= 0.0:
        reasons.append(f"Monte-Carlo Sharpe CI lower bound {inputs.bootstrap_ci_low:.3f} <= 0")

    if not reasons:
        return GateStatus.ACTIVE, ["cleared all gate stages on real-feed data"]
    return GateStatus.OBSERVE, reasons  # real but inconclusive — not active, not failed


def _moment(values: np.ndarray, power: int) -> float:
    std = float(values.std())
    if std == 0.0:
        return 0.0 if power == 3 else 3.0
    centered = values - values.mean()
    return float((centered**power).mean() / std**power)


@dataclass
class ValidationGate:
    """Runs the gate stages for a strategy and returns a :class:`GateResult`."""

    n_trials: int
    trials_sharpe_std: float
    thresholds: GateThresholds = field(default_factory=GateThresholds)
    commission_bps: float = 5.0
    slippage_bps: float = 0.0
    annualization: int = 252
    oos_fraction: float = 0.4
    seed: int = 12345

    def evaluate(
        self,
        slug: str,
        strategy: StrategyProtocol,
        prices: pd.DataFrame,
        *,
        data_source: str,
    ) -> GateResult:
        """Run cost-aware backtest → walk-forward → regime → DSR → Monte-Carlo → decide."""
        result = vectorbt_bridge.run(
            strategy, prices, commission_bps=self.commission_bps, slippage_bps=self.slippage_bps
        )
        n = len(result.returns)
        oos_start = int(n * (1.0 - self.oos_fraction))
        oos_returns = result.returns.iloc[oos_start:]
        oos_array = oos_returns.to_numpy()

        oos_sharpe = sharpe_ratio(oos_returns, annualization=self.annualization)
        per_period_sharpe = oos_sharpe / np.sqrt(self.annualization)
        dsr = deflated_sharpe_ratio(
            per_period_sharpe,
            len(oos_array),
            n_trials=self.n_trials,
            trials_sharpe_std=self.trials_sharpe_std,
            skew=_moment(oos_array, 3),
            kurtosis=_moment(oos_array, 4),
        )

        test_size = max(20, len(prices) // 10)
        wf = walk_forward(
            strategy,
            prices,
            test_size=test_size,
            step=test_size,
            min_train=max(60, len(prices) // 5),
            commission_bps=self.commission_bps,
            slippage_bps=self.slippage_bps,
            annualization=self.annualization,
        )
        regime = regime_consistency(oos_returns, floor=self.thresholds.min_regime_sharpe)
        mc = bootstrap_sharpe(oos_array, rng=np.random.default_rng(self.seed), n_resamples=500)
        net_positive = bool(float(np.prod(1.0 + oos_array)) > 1.0)

        inputs = GateInputs(
            data_source=data_source,
            oos_sharpe=oos_sharpe,
            net_positive=net_positive,
            deflated_sharpe=dsr,
            positive_window_fraction=wf.positive_window_fraction,
            worst_regime_sharpe=regime.worst_sharpe,
            bootstrap_ci_low=mc.ci_low,
        )
        status, reasons = decide(inputs, self.thresholds)
        return GateResult(
            slug=slug,
            status=status,
            data_source=data_source,
            reasons=reasons,
            metrics={
                "oos_sharpe": oos_sharpe,
                "deflated_sharpe": dsr,
                "walk_forward_positive_fraction": wf.positive_window_fraction,
                "worst_regime_sharpe": regime.worst_sharpe,
                "bootstrap_ci_low": mc.ci_low,
                "bootstrap_ci_high": mc.ci_high,
            },
        )
