"""Tests for the real candidate evaluator (build strategy -> validation gate)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.bench.inventor.candidate import make_candidate
from alphakit.bench.inventor.evaluator import (
    DEFAULT_GRIDS,
    build_strategy,
    candidate_evaluator,
    valid_combo,
)
from alphakit.bench.inventor.generate import parameter_search
from alphakit.bench.inventor.inventor import run_inventor, survivors
from alphakit.bench.validation.gate import GateStatus, ValidationGate


def _prices(n: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    rng = np.random.default_rng(0)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, n))
    return pd.DataFrame({"BTC/USDT": closes}, index=idx)


def _gate() -> ValidationGate:
    return ValidationGate(n_trials=10, trials_sharpe_std=1.0)


def test_build_strategy_maps_every_family() -> None:
    specs = [
        ("ema_cross", {"fast": 8, "slow": 21}),
        ("sma_cross", {"fast": 10, "slow": 30}),
        ("donchian", {"window": 20}),
        ("rsi_reversion", {"period": 2}),
        ("bollinger", {"period": 20}),
        ("zscore", {"lookback": 20}),
    ]
    for strategy, params in specs:
        built = build_strategy(make_candidate(strategy, params))
        assert hasattr(built, "generate_signals"), strategy


def test_evaluator_runs_the_gate_and_synthetic_never_actives() -> None:
    evaluate = candidate_evaluator(_prices(), data_source="synthetic:test", gate=_gate())
    result = evaluate(make_candidate("ema_cross", {"fast": 8, "slow": 21}))
    assert result.status is GateStatus.OBSERVE  # synthetic can never be ACTIVE (#4)
    assert "deflated_sharpe" in result.metrics  # ... yet the stages actually ran


def test_broken_candidate_is_failed_not_a_crash() -> None:
    evaluate = candidate_evaluator(_prices(), data_source="real:test", gate=_gate())
    result = evaluate(make_candidate("nonexistent_template", {"x": 1}))
    assert result.status is GateStatus.FAILED
    assert any("eval error" in reason for reason in result.reasons)


def test_full_loop_on_synthetic_yields_no_survivors() -> None:
    # The real evaluator + the loop, end-to-end: on synthetic data nothing is
    # adoptable — the "validated, not proven" rail holds without a fake gate.
    candidates = parameter_search(list(DEFAULT_GRIDS), valid=valid_combo)[:3]
    evaluate = candidate_evaluator(_prices(), data_source="synthetic:test", gate=_gate())
    results = run_inventor(candidates, evaluate)
    assert results  # every candidate graded
    assert survivors(results) == []  # none adoptable on synthetic
