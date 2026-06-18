"""Unit tests for governed meta-learning (FR-P5) — propose-only, anti-whipsaw."""

from __future__ import annotations

from mv.postmortem.metalearn import propose_weights


def test_weights_sum_to_one() -> None:
    proposal = propose_weights({"a": 1.5, "b": 0.5}, {"a": 0.5, "b": 0.5}, max_velocity=1.0)
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9


def test_higher_oos_sharpe_gets_more_weight() -> None:
    proposal = propose_weights(
        {"a": 2.0, "b": 0.0}, {"a": 0.5, "b": 0.5}, max_velocity=1.0, prior_strength=0.0
    )
    assert proposal.weights["a"] > proposal.weights["b"]


def test_anti_whipsaw_cap_is_respected() -> None:
    # A strong tilt but a tight velocity cap: no weight may move more than 0.05.
    current = {"a": 0.5, "b": 0.5}
    proposal = propose_weights(
        {"a": 5.0, "b": -1.0}, current, max_velocity=0.05, prior_strength=0.0
    )
    for name, weight in proposal.weights.items():
        assert abs(weight - current[name]) <= 0.05 + 1e-9
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9


def test_regime_ineligible_strategy_is_zeroed() -> None:
    proposal = propose_weights(
        {"a": 1.0, "b": 1.0},
        {"a": 0.5, "b": 0.5},
        max_velocity=1.0,
        regime_eligibility={"a": True, "b": False},
    )
    assert proposal.weights["b"] == 0.0
    assert proposal.weights["a"] == 1.0


def test_shrinkage_pulls_toward_prior() -> None:
    # Against a positive prior, stronger shrinkage pulls the tilt back toward
    # equal weights (the prior dominates); no shrinkage lets the signal tilt hard.
    shrunk = propose_weights(
        {"a": 2.0, "b": 1.0}, {"a": 0.5, "b": 0.5}, max_velocity=1.0, prior=1.0, prior_strength=20.0
    )
    unshrunk = propose_weights(
        {"a": 2.0, "b": 1.0}, {"a": 0.5, "b": 0.5}, max_velocity=1.0, prior=1.0, prior_strength=0.0
    )
    # Heavily shrunk weights sit closer to 0.5 than the unshrunk tilt.
    assert abs(shrunk.weights["a"] - 0.5) < abs(unshrunk.weights["a"] - 0.5)


def test_adoptable_only_on_held_out_improvement() -> None:
    # 'a' has positive held-out returns, 'b' negative; tilting to 'a' should help.
    held_out = {"a": [0.02, 0.01, 0.03, 0.02], "b": [-0.02, -0.01, -0.03, -0.02]}
    proposal = propose_weights(
        {"a": 2.0, "b": 0.0},
        {"a": 0.5, "b": 0.5},
        max_velocity=1.0,
        prior_strength=0.0,
        held_out=held_out,
    )
    assert proposal.before_metric is not None and proposal.after_metric is not None
    assert proposal.after_metric > proposal.before_metric
    assert proposal.adoptable is True


def test_not_adoptable_without_held_out() -> None:
    proposal = propose_weights({"a": 2.0, "b": 0.0}, {"a": 0.5, "b": 0.5})
    assert proposal.adoptable is False
    assert proposal.before_metric is None


def test_proposal_renders_to_unadopted_ledger_entry() -> None:
    proposal = propose_weights({"a": 1.0, "b": 1.0}, {"a": 0.5, "b": 0.5})
    entry = proposal.as_improvement(mistake_category="false_signal")
    assert entry.change_kind == "strategy_weight"
    assert entry.adopted is False
    assert entry.mistake_category == "false_signal"
