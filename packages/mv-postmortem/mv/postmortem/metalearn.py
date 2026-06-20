"""Governed meta-learning (PRD FR-P5) — propose-only strategy-weight updates.

The platform's most important governance. Strategy weights are nudged toward
out-of-sample Sharpe under a **Bayesian prior** (shrinkage), then subject to:

1. a **regime-eligibility gate** (ineligible strategies get zero weight),
2. an **anti-whipsaw velocity cap** — all weights step toward the target by a
   single global rate so no weight moves more than ``max_velocity`` per update,
   while the weights still sum to 1, and
3. **held-out validation** — the proposal is ``adoptable`` only if it beats the
   current weights on a held-out return window.

The result is a :class:`WeightProposal`. **It is propose-only**: this function
never mutates the loop and never touches risk limits — the Operator adopts (or
not) via the improvement ledger. Trains on strategy OOS returns, never on FRED.
Pure / deterministic; uses stdlib ``statistics`` (no scipy/numpy).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean, pstdev

from mv.postmortem.improvement import ImprovementEntry


@dataclass(frozen=True, slots=True)
class WeightProposal:
    """A proposed strategy-weight set with its held-out validation verdict."""

    weights: dict[str, float]
    before_metric: float | None
    after_metric: float | None
    adoptable: bool

    def as_improvement(self, *, mistake_category: str | None = None) -> ImprovementEntry:
        """Render the proposal as an improvement-ledger entry (not yet adopted)."""
        changed = ", ".join(f"{name}:{weight:.3f}" for name, weight in sorted(self.weights.items()))
        return ImprovementEntry(
            change_kind="strategy_weight",
            change_desc=f"propose weights {{{changed}}}",
            mistake_category=mistake_category,
            before_metric=self.before_metric,
            after_metric=self.after_metric,
            adopted=False,
        )


def _shrink(oos_sharpe: float, prior: float, prior_strength: float) -> float:
    """Conjugate-style shrink of an OOS Sharpe toward the prior mean."""
    return (oos_sharpe + prior * prior_strength) / (1.0 + prior_strength)


def _normalize(scores: Mapping[str, float]) -> dict[str, float]:
    positive = {name: max(0.0, value) for name, value in scores.items()}
    total = sum(positive.values())
    if total == 0.0:
        n = len(scores)
        return dict.fromkeys(scores, 1.0 / n) if n else {}
    return {name: value / total for name, value in positive.items()}


def _rate_limited_step(
    current: Mapping[str, float], target: Mapping[str, float], max_velocity: float
) -> dict[str, float]:
    """Step every weight toward ``target`` by one global rate ≤ ``max_velocity``.

    Each weight moves by ``alpha * (target - current)`` where
    ``alpha = min(1, max_velocity / max|target - current|)``, so no single weight
    moves more than ``max_velocity`` and the weights still sum to 1.
    """
    deltas = {name: target[name] - current.get(name, 0.0) for name in target}
    max_step = max((abs(delta) for delta in deltas.values()), default=0.0)
    if max_step == 0.0:
        return dict(target)
    alpha = min(1.0, max_velocity / max_step)
    stepped = {name: current.get(name, 0.0) + alpha * deltas[name] for name in target}
    # Renormalize so the weights sum to 1 even when the strategy set changed
    # between updates (a key added/removed breaks the telescoping sum otherwise).
    total = sum(stepped.values())
    return {name: weight / total for name, weight in stepped.items()} if total else stepped


def _sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    sd = pstdev(returns)
    if sd == 0.0:
        return 0.0
    return fmean(returns) / sd


def _portfolio_sharpe(
    weights: Mapping[str, float], held_out: Mapping[str, Sequence[float]]
) -> float:
    names = [name for name in weights if name in held_out]
    if not names:
        return 0.0
    length = min(len(held_out[name]) for name in names)
    series = [sum(weights[name] * held_out[name][i] for name in names) for i in range(length)]
    return _sharpe(series)


def propose_weights(
    oos_sharpe: Mapping[str, float],
    current_weights: Mapping[str, float],
    *,
    prior: float = 0.0,
    prior_strength: float = 1.0,
    max_velocity: float = 0.1,
    regime_eligibility: Mapping[str, bool] | None = None,
    held_out: Mapping[str, Sequence[float]] | None = None,
) -> WeightProposal:
    """Propose governed strategy weights (propose-only; never mutates anything)."""
    eligibility = regime_eligibility or {}
    shrunk = {
        name: (0.0 if not eligibility.get(name, True) else _shrink(value, prior, prior_strength))
        for name, value in oos_sharpe.items()
    }
    target = _normalize(shrunk)
    proposed = _rate_limited_step(current_weights, target, max_velocity)

    before_metric: float | None = None
    after_metric: float | None = None
    adoptable = False
    if held_out is not None:
        before_metric = _portfolio_sharpe(current_weights, held_out)
        after_metric = _portfolio_sharpe(proposed, held_out)
        adoptable = after_metric > before_metric  # held-out improvement required

    return WeightProposal(
        weights=proposed,
        before_metric=before_metric,
        after_metric=after_metric,
        adoptable=adoptable,
    )


__all__ = ["WeightProposal", "propose_weights"]
