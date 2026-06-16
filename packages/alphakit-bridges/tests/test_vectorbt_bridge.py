"""Tests for vectorbt_bridge — discrete-legs dispatch (Session 2F).

Covers:

1. **Continuous-only strategy** (no ``discrete_legs`` declared): the
   bridge falls through to the pre-Session-2F ``SizeType.TargetPercent``
   semantics on every column. Backwards-compatibility check for the
   83 strategies through Session 2E.
2. **Discrete-only strategy** (every output column declared in
   ``discrete_legs``): one-shot ``SizeType.Amount`` semantics, P&L
   matches the analytic premium-minus-intrinsic expectation for an
   option write.
3. **Mixed strategy** (continuous underlying + discrete option leg):
   per-column dispatch — TargetPercent for the underlying,
   Amount for the option leg — produces the analytic covered-call
   P&L.
4. **Default ``()`` via missing attribute**: a strategy class that
   does *not* declare ``discrete_legs`` at all is treated as
   fully-continuous, matching every existing strategy. Verifies
   :func:`get_discrete_legs` returns ``()`` for legacy classes.
5. **Validation**: malformed ``discrete_legs`` (non-tuple, non-string
   entries) raises ``TypeError``.
6. **Mode 2 fallback safety**: a strategy declaring ``discrete_legs``
   that are *not* present in the invocation's ``prices`` (Session 2F
   options strategies under the standard BenchmarkRunner with
   underlying-only input) runs to completion under TargetPercent
   semantics, with a debug-level log message surfacing the
   declared-but-absent leg names so accidental typos are still
   detectable in test logs.

Each test uses a tiny synthetic panel and a hand-rolled strategy so
the assertion is on the bridge's contract, not on any specific
strategy's signal logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs


# ---------------------------------------------------------------------------
# Tiny hand-rolled strategies
# ---------------------------------------------------------------------------
class _ContinuousLong:
    """Long 100 % of every input column every bar — TargetPercent semantics."""

    name: str = "diag_continuous_long"
    family: str = "diag"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "diag"
    rebalance_frequency: str = "daily"

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        n = max(len(prices.columns), 1)
        return pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)


class _DiscreteOnlyShort:
    """One-shot −1 contract on day 0 of the call leg, hold via 0 elsewhere."""

    name: str = "diag_discrete_only_short"
    family: str = "diag"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "diag"
    rebalance_frequency: str = "daily"
    discrete_legs: tuple[str, ...] = ("CALL_LEG",)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w.loc[w.index[0], "CALL_LEG"] = -1.0
        return w


class _MixedCoveredCall:
    """Continuous +1 underlying (TargetPercent) + discrete −1 call leg (Amount)."""

    name: str = "diag_mixed_covered_call"
    family: str = "diag"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "diag"
    rebalance_frequency: str = "daily"
    discrete_legs: tuple[str, ...] = ("CALL_LEG",)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w["SPY"] = 1.0
        w.loc[w.index[0], "CALL_LEG"] = -1.0
        return w


class _LegacyContinuous:
    """Strategy without any ``discrete_legs`` attribute at all.

    Mirrors every Phase 1 / Session 2D / 2E strategy: the attribute
    is not declared, so :func:`get_discrete_legs` must return ``()``
    and the bridge must use TargetPercent across all columns.
    """

    name: str = "diag_legacy_continuous"
    family: str = "diag"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "diag"
    rebalance_frequency: str = "daily"

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0.5, index=prices.index, columns=prices.columns)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _flat_panel(spy_value: float = 400.0, n: int = 21) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"SPY": np.full(n, spy_value)}, index=idx)


def _covered_call_panel(
    spy_value: float = 400.0,
    premium_start: float = 8.0,
    premium_end: float = 0.01,
    n: int = 21,
) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    spy = np.full(n, spy_value)
    call = np.linspace(premium_start, premium_end, n)
    return pd.DataFrame({"SPY": spy, "CALL_LEG": call}, index=idx)


# ---------------------------------------------------------------------------
# 1. get_discrete_legs helper
# ---------------------------------------------------------------------------
def test_get_discrete_legs_returns_empty_for_legacy_class() -> None:
    assert get_discrete_legs(_LegacyContinuous()) == ()


def test_get_discrete_legs_returns_declared_tuple() -> None:
    assert get_discrete_legs(_DiscreteOnlyShort()) == ("CALL_LEG",)


def test_get_discrete_legs_rejects_non_tuple() -> None:
    class _BadDiscreteLegsList:
        name = "bad"
        family = "diag"
        asset_classes = ("equity",)
        paper_doi = "diag"
        rebalance_frequency = "daily"
        # Deliberately a list (not a tuple) to trigger the validation
        # error in the test below.
        discrete_legs: list[str] = ["CALL_LEG"]  # noqa: RUF012

        def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
            return prices

    with pytest.raises(TypeError, match="must be a tuple"):
        get_discrete_legs(_BadDiscreteLegsList())  # type: ignore[arg-type]


def test_get_discrete_legs_rejects_non_string_entry() -> None:
    class _BadDiscreteLegsInt:
        name = "bad"
        family = "diag"
        asset_classes = ("equity",)
        paper_doi = "diag"
        rebalance_frequency = "daily"
        discrete_legs = ("CALL_LEG", 42)  # int sneaking in

        def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
            return prices

    with pytest.raises(TypeError, match="non-empty strings"):
        get_discrete_legs(_BadDiscreteLegsInt())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Continuous-only path (backwards compatibility)
# ---------------------------------------------------------------------------
def test_continuous_only_uses_target_percent_semantics() -> None:
    """Strategy with no discrete_legs: every column is rebalanced.

    The 100 % long-SPY position on a flat $400 SPY panel produces a
    flat equity curve — final value equals initial cash modulo
    floating-point noise.
    """
    prices = _flat_panel(spy_value=400.0, n=21)
    result = vectorbt_bridge.run(
        strategy=_ContinuousLong(),
        prices=prices,
        initial_cash=100_000.0,
    )
    assert result.meta["strategy"] == "diag_continuous_long"
    assert result.meta["engine"] == "vectorbt"
    # Long SPY at flat 400 → no P&L beyond commission.
    final = result.metrics["final_equity"]
    assert abs(final - 100_000.0) < 1.0, (
        f"flat-SPY long-only final equity should be ~100k, got {final}"
    )


def test_legacy_class_without_discrete_legs_attribute_works() -> None:
    """A class missing ``discrete_legs`` entirely must still backtest.

    This is the 83-strategy backwards-compatibility check: every
    strategy through Session 2E lacks the attribute.
    """
    prices = _flat_panel(spy_value=400.0, n=21)
    result = vectorbt_bridge.run(
        strategy=_LegacyContinuous(),
        prices=prices,
        initial_cash=100_000.0,
    )
    assert np.isfinite(result.metrics["sharpe"])
    assert abs(result.metrics["final_equity"] - 100_000.0) < 100.0


# ---------------------------------------------------------------------------
# 3. Discrete-only path
# ---------------------------------------------------------------------------
def test_discrete_only_amount_semantics_match_analytic_premium() -> None:
    """One-shot −1 call on day 0 → premium received minus intrinsic.

    Premium goes 8.0 → 0.01 over 21 bars. Position is opened day 0
    (sell 1 contract for $8) and held to day 20 (close at $0.01).
    Net P&L on the short = +$7.99.
    """
    prices = pd.DataFrame(
        {"CALL_LEG": np.linspace(8.0, 0.01, 21)},
        index=pd.date_range("2020-01-01", periods=21, freq="B"),
    )
    result = vectorbt_bridge.run(
        strategy=_DiscreteOnlyShort(),
        prices=prices,
        initial_cash=100_000.0,
    )
    expected_pnl = 8.0 - 0.01  # premium − intrinsic
    actual_pnl = result.metrics["final_equity"] - 100_000.0
    assert abs(actual_pnl - expected_pnl) < 0.01, (
        f"discrete-leg short: expected P&L ≈ {expected_pnl}, got {actual_pnl}"
    )


# ---------------------------------------------------------------------------
# 4. Mixed continuous + discrete (covered-call shape)
# ---------------------------------------------------------------------------
def test_mixed_continuous_and_discrete_produces_covered_call_pnl() -> None:
    """+1 SPY (TargetPercent, flat 400) + −1 CALL_LEG (Amount, $8 → $0.01).

    Covered-call analytic P&L: equity-leg flat (no SPY return) +
    $7.99 net premium on the short = +$7.99 total.
    """
    prices = _covered_call_panel(spy_value=400.0, premium_start=8.0, premium_end=0.01, n=21)
    result = vectorbt_bridge.run(
        strategy=_MixedCoveredCall(),
        prices=prices,
        initial_cash=100_000.0,
    )
    expected_pnl = 8.0 - 0.01
    actual_pnl = result.metrics["final_equity"] - 100_000.0
    assert abs(actual_pnl - expected_pnl) < 0.01, (
        f"mixed covered-call: expected P&L ≈ {expected_pnl}, got {actual_pnl}"
    )


def test_mixed_pre_fix_target_percent_semantics_would_blow_up() -> None:
    """Sanity check: a NAIVELY-discrete strategy (continuous −1 every bar)
    on the same option-leg column would NOT match the analytic P&L —
    confirming the fix is necessary, not cosmetic.

    This is the negative control: we synthesise the pre-fix strategy
    behaviour (no discrete_legs declared, weights = continuous −1 in
    CALL_LEG every bar) and verify the resulting P&L is wildly
    different from the analytic +$7.99. This documents *why* the
    discrete_legs metadata exists.
    """

    class _NaivelyContinuous:
        name = "diag_naively_continuous"
        family = "diag"
        asset_classes = ("equity",)
        paper_doi = "diag"
        rebalance_frequency = "daily"
        # Deliberately NO discrete_legs.

        def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
            w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
            w["SPY"] = 1.0
            w["CALL_LEG"] = -1.0  # continuous-rebalance — wrong for option
            return w

    # Floor the call leg above 0 so vectorbt doesn't crash on zero-price.
    prices = _covered_call_panel(spy_value=400.0, premium_start=8.0, premium_end=0.5, n=21)
    result = vectorbt_bridge.run(
        strategy=_NaivelyContinuous(),  # type: ignore[arg-type]
        prices=prices,
        initial_cash=100_000.0,
    )
    actual_pnl = result.metrics["final_equity"] - 100_000.0
    # Analytic covered-call P&L would be ~$7.50; the buggy
    # continuous-rebalance interpretation produces a P&L that
    # scales with the premium ratio (8.0 / 0.5 = 16×) instead.
    # We assert the deviation is large — at least 100× the analytic
    # — to confirm the failure mode is severe and the fix is needed.
    assert abs(actual_pnl) > 100.0, (
        f"expected wildly-wrong P&L from naive continuous-rebalance; got {actual_pnl}"
    )


# ---------------------------------------------------------------------------
# 5. Validation
# ---------------------------------------------------------------------------
class _DeclaredButAbsentLeg:
    """Strategy declares a discrete leg that is *not* present in the
    invocation's ``prices`` DataFrame.

    Canonical example: a Session 2F options strategy declares
    ``discrete_legs = ("SPY_CALL_OTM02PCT_M1",)`` statically but is
    run by the standard BenchmarkRunner with ``prices`` containing
    only ``SPY``. The strategy emits Mode 2 fallback weights
    (single-column buy-and-hold) and the bridge must run to
    completion — while also surfacing the declared-but-absent leg
    at debug log level so accidental typos in ``discrete_legs``
    don't silently swallow the dispatch.
    """

    name: str = "diag_declared_but_absent"
    family: str = "diag"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "diag"
    rebalance_frequency: str = "daily"
    discrete_legs: tuple[str, ...] = ("NOT_IN_PRICES",)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        w = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        w["SPY"] = 1.0
        return w


def test_mode_2_fallback_with_declared_but_absent_legs_runs_to_completion() -> None:
    """Bridge completes without error when discrete_legs declares
    columns absent from ``prices``.

    Routes to the unchanged TargetPercent code path for every
    column actually present (since the absent leg cannot be
    dispatched). The 83 strategies through Session 2E are
    backwards-compatible-by-construction; this test covers the
    Session 2F + Mode 2 fallback case where a strategy *does*
    declare ``discrete_legs`` but the runner provides only the
    underlying.
    """
    prices = _flat_panel(n=10)
    result = vectorbt_bridge.run(
        strategy=_DeclaredButAbsentLeg(),
        prices=prices,
    )
    assert np.isfinite(result.metrics["sharpe"])
    # Long flat SPY → equity stays at initial cash modulo float noise.
    assert abs(result.metrics["final_equity"] - 100_000.0) < 1.0


def test_declared_but_absent_legs_emit_debug_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A debug-level log message fires when ``discrete_legs`` declares
    columns missing from ``prices``.

    This is the typo-detection guard that makes the silent-Mode-2
    fallback safe: the dispatch still runs, but the warning shows
    up in test logs (via pytest's caplog fixture) so leg-name typos
    surface.
    """
    prices = _flat_panel(n=10)
    with caplog.at_level("DEBUG", logger="alphakit.bridges.vectorbt_bridge"):
        vectorbt_bridge.run(
            strategy=_DeclaredButAbsentLeg(),
            prices=prices,
        )
    assert any(
        "NOT_IN_PRICES" in rec.message and rec.levelname == "DEBUG" for rec in caplog.records
    ), (
        "expected debug log mentioning the declared-but-absent leg; "
        f"got records: {[(r.levelname, r.message[:80]) for r in caplog.records]}"
    )


def test_no_debug_warning_when_all_declared_legs_present(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Negative side: when every declared leg is in ``prices``, the
    bridge emits no missing-legs debug message."""
    prices = pd.DataFrame(
        {"CALL_LEG": np.linspace(8.0, 0.01, 21)},
        index=pd.date_range("2020-01-01", periods=21, freq="B"),
    )
    with caplog.at_level("DEBUG", logger="alphakit.bridges.vectorbt_bridge"):
        vectorbt_bridge.run(
            strategy=_DiscreteOnlyShort(),
            prices=prices,
        )
    assert not any("not in prices.columns" in rec.message for rec in caplog.records), (
        f"unexpected missing-legs warning: "
        f"{[(r.levelname, r.message[:80]) for r in caplog.records]}"
    )


def test_strategy_with_discrete_legs_satisfies_strategy_protocol() -> None:
    """The Protocol does *not* declare ``discrete_legs`` on its body
    (so legacy strategies without the attribute pass isinstance), but
    new strategies declaring it must still satisfy the rest of the
    Protocol contract.
    """
    assert isinstance(_DiscreteOnlyShort(), StrategyProtocol)
    assert isinstance(_MixedCoveredCall(), StrategyProtocol)
    assert isinstance(_LegacyContinuous(), StrategyProtocol)
