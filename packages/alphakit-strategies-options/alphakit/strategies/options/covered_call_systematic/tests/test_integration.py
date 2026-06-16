"""Integration tests for covered_call_systematic.

End-to-end pipeline:

1. Build a deterministic underlying-price series.
2. Wrap it in a fake feed mirroring
   ``test_synthetic_options.py``'s ``_FakeUnderlying`` pattern.
3. Build a :class:`SyntheticOptionsFeed` against the fake.
4. Call ``strategy.make_call_leg_prices(...)`` to construct the
   synthetic short-call premium series via ``fetch_chain``.
5. Run the strategy through the vectorbt bridge end-to-end —
   Mode 1 (canonical) uses the ``discrete_legs`` dispatch added in
   Session 2F's bridge architecture extension, so the call leg is
   priced under ``SizeType.Amount`` semantics and the bridge no
   longer crashes on intra-cycle zero-price bars or produces the
   continuous-rebalance runaway-short P&L documented in the
   bridge-investigation amendment.
6. Assert the :class:`BacktestResult` is internally consistent and
   the metrics reflect a covered-call P&L (not buy-and-hold).

Network is never touched; the synthetic-options adapter consumes
the fake underlying-feed at construction time.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import cast

import numpy as np
import pandas as pd
import pytest
from alphakit.bridges import vectorbt_bridge
from alphakit.core.data import OptionChain
from alphakit.core.protocols import (
    BacktestResult,
    get_discrete_legs,
    raise_chain_not_supported,
)
from alphakit.data.options.synthetic import SyntheticOptionsFeed
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
)


class _FakeUnderlying:
    """Deterministic stub feed that respects the ``end`` parameter.

    The synthetic-options adapter calls ``fetch(start, end)`` and uses
    the returned series's *last* element as the chain's spot price.
    For multi-date walks the fake must slice on ``end`` so that
    spot aligns with the as-of bar — otherwise every chain build
    sees the same far-future spot and the strategy picks
    nonsense strikes. This is the strict-slicing variant of the
    pattern used in ``test_synthetic_options.py`` (where only one
    chain is built per test, so slicing was unnecessary there).
    """

    name = "fake-underlying"

    def __init__(self, prices: pd.Series) -> None:
        self._prices = prices

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        end_ts = pd.Timestamp(end)
        sliced = self._prices.loc[:end_ts]
        return pd.DataFrame({symbols[0]: sliced.copy()})

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        raise_chain_not_supported(self.name)


def _deterministic_underlying(
    n: int = 800, end_date: date = date(2024, 12, 31), seed: int = 42
) -> pd.Series:
    """Strictly-positive underlying path with realistic ~20 % annualised vol.

    Mirrors test_synthetic_options.py::_deterministic_prices but with a
    longer history so the strategy has enough warm-up (252 bars for
    the synthetic chain's realized-vol window) plus several months
    of in-position data after warm-up.
    """
    rng = np.random.default_rng(seed)
    daily_log_returns = rng.standard_normal(n) * 0.013  # ≈ 20 % annualised
    values = 100.0 * np.exp(np.cumsum(daily_log_returns))
    index = pd.date_range(end=pd.Timestamp(end_date), periods=n, freq="B")
    return pd.Series(values, index=index, name="SPY")


def _build_strategy_and_feed(
    underlying: pd.Series,
) -> tuple[CoveredCallSystematic, SyntheticOptionsFeed]:
    fake = _FakeUnderlying(underlying)
    chain_feed = SyntheticOptionsFeed(underlying_feed=fake)
    strategy = CoveredCallSystematic(
        underlying_symbol="SPY",
        otm_pct=0.02,
        chain_feed=chain_feed,
    )
    return strategy, chain_feed


# ---------------------------------------------------------------------------
# make_call_leg_prices contract
# ---------------------------------------------------------------------------
def test_make_call_leg_prices_returns_named_series_aligned_to_underlying() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_call_leg_prices(underlying)
    assert isinstance(leg, pd.Series)
    assert leg.name == strategy.call_leg_symbol
    assert leg.index.equals(underlying.index)
    # Premia are non-negative (BS prices clamped at 0).
    assert (leg >= 0.0).all()


def test_make_call_leg_prices_writes_at_first_trading_day_of_each_month() -> None:
    """At least one in-position day per month after warm-up."""
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_call_leg_prices(underlying)
    idx = cast(pd.DatetimeIndex, leg.index)
    monthly_max = leg.groupby(idx.to_period("M")).max()
    # Allow the first ~14 months for the synthetic chain to build
    # enough realized-vol history (252-bar minimum, plus a couple of
    # months for the first month-start to land after warm-up). Months
    # after that should have an open position for at least part of
    # the month.
    post_warmup = monthly_max.iloc[14:]
    assert (post_warmup > 0).all(), (
        "expected at least one open-position day in each post-warm-up month; "
        f"empty months: {(post_warmup <= 0).sum()}"
    )


def test_make_call_leg_prices_rejects_non_series() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    with pytest.raises(TypeError, match="Series"):
        strategy.make_call_leg_prices(pd.DataFrame())  # type: ignore[arg-type]


def test_make_call_leg_prices_rejects_non_datetime_index() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    with pytest.raises(TypeError, match="DatetimeIndex"):
        strategy.make_call_leg_prices(pd.Series([100.0, 101.0]))


def test_make_call_leg_prices_handles_empty_input() -> None:
    strategy, _ = _build_strategy_and_feed(_deterministic_underlying())
    out = strategy.make_call_leg_prices(pd.Series([], dtype=float, index=pd.DatetimeIndex([])))
    assert out.empty
    assert out.name == strategy.call_leg_symbol


# ---------------------------------------------------------------------------
# Mode 1 — full covered call end-to-end through vectorbt_bridge
# ---------------------------------------------------------------------------
def test_full_covered_call_runs_through_vectorbt_bridge_with_discrete_legs() -> None:
    """Canonical Mode 1: 2-column panel, discrete_legs dispatched correctly.

    The bridge's pre-Session-2F continuous-rebalance interpretation
    of the call-leg weight would have crashed (zero-price bars) or
    produced runaway-short P&L. After Commit 1.5's discrete_legs
    dispatch, the call leg is treated as Amount semantics and the
    bridge produces a finite, internally-consistent BacktestResult.
    """
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)

    # Sanity: discrete_legs is wired correctly on this instance.
    assert get_discrete_legs(strategy) == (strategy.call_leg_symbol,)

    leg = strategy.make_call_leg_prices(underlying)
    prices = pd.DataFrame(
        {
            strategy.underlying_symbol: underlying,
            strategy.call_leg_symbol: leg,
        }
    )
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "covered_call_systematic"
    assert np.isfinite(result.metrics["sharpe"])
    assert np.isfinite(result.metrics["final_equity"])
    assert list(result.weights.columns) == list(prices.columns)
    # Underlying weight: +1.0 every bar.
    assert (result.weights[strategy.underlying_symbol] == 1.0).all()
    # Call-leg weights: -1 on at least some bars (writes), +1 on at
    # least some bars (closes), 0 elsewhere.
    leg_w = result.weights[strategy.call_leg_symbol].to_numpy()
    assert (leg_w == -1.0).any(), "expected at least one write event"
    assert (leg_w == 1.0).any(), "expected at least one close event"
    assert ((leg_w == 0.0) | (leg_w == 1.0) | (leg_w == -1.0)).all()


def test_mode_1_diverges_from_pure_buy_and_hold() -> None:
    """The covered-call P&L is *not* identical to long SPY alone.

    Confirms Mode 1 actually exercises the call-leg trades through
    the bridge's discrete_legs dispatch. If the dispatch were
    silently disabled (or the leg column were stripped, or the
    Amount semantics were misapplied as TargetPercent), the
    equity curves would be byte-identical to Mode 2 buy-and-hold.

    On the synthetic substrate the per-cycle premium is small
    (~$0.50-$1.00 because the chain's 5%-spaced strike grid pushes
    the "2 % OTM" target to 5 % OTM at the smallest available
    strike) and ITM-at-close vs OTM-at-close cycles partially
    cancel, so the *final* equity difference is modest. A robust
    invariant is that the equity curves *diverge somewhere* during
    the in-position phase.
    """
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    leg = strategy.make_call_leg_prices(underlying)

    # Mode 1: 2-column panel, discrete_legs dispatched.
    prices_mode_1 = pd.DataFrame(
        {strategy.underlying_symbol: underlying, strategy.call_leg_symbol: leg}
    )
    result_1 = vectorbt_bridge.run(strategy=strategy, prices=prices_mode_1)

    # Mode 2: 1-column panel, buy-and-hold.
    prices_mode_2 = pd.DataFrame({strategy.underlying_symbol: underlying})
    result_2 = vectorbt_bridge.run(strategy=strategy, prices=prices_mode_2)

    # The two equity curves must differ at *some* point in time —
    # even if the final divergence is modest after canceling cycles.
    # Empirical max |diff| on this seed/length is ~$5.75; the
    # threshold $4 gives margin while remaining strong enough to
    # catch silent dispatch failures (which produce max |diff| = 0).
    # Per-cycle premia are small (~$0.50–$1.00) because the
    # synthetic chain's 5%-spaced strike grid effectively pushes the
    # 2 % OTM target to 5 % OTM at the smallest available strike,
    # and ITM-at-close vs OTM-at-close cycles partially cancel — so
    # the asserted threshold is calibrated empirically rather than
    # to the textbook ~$5 × 17 cycles ≈ $85 figure.
    aligned_diff = (result_1.equity_curve - result_2.equity_curve).abs()
    max_diff = float(aligned_diff.max())
    assert max_diff > 4.0, (
        "Mode 1 and Mode 2 equity curves should diverge during the "
        "in-position phase due to call-leg mark-to-market; got "
        f"max |diff| = {max_diff:.4f}. If 0, discrete_legs dispatch "
        "is not being applied to the call leg."
    )

    # Also confirm the call-leg actually traded at some point under
    # Mode 1 (i.e. the strategy's lifecycle detection ran).
    leg_w = result_1.weights[strategy.call_leg_symbol].to_numpy()
    assert (leg_w == -1.0).sum() >= 1, "expected at least one write event in Mode 1"
    assert (leg_w == 1.0).sum() >= 1, "expected at least one close event in Mode 1"


# ---------------------------------------------------------------------------
# Mode 2 — buy-and-hold approximation (benchmark runner fallback)
# ---------------------------------------------------------------------------
def test_buy_and_hold_mode_runs_through_vectorbt_bridge() -> None:
    """Mode 2 (standard benchmark-runner path): only the underlying column."""
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert isinstance(result, BacktestResult)
    assert result.meta["strategy"] == "covered_call_systematic"
    assert np.isfinite(result.metrics["sharpe"])
    assert (result.weights[strategy.underlying_symbol] == 1.0).all()


def test_full_pipeline_is_deterministic() -> None:
    underlying = _deterministic_underlying()
    strategy_a, _ = _build_strategy_and_feed(underlying)
    strategy_b, _ = _build_strategy_and_feed(underlying)
    leg_a = strategy_a.make_call_leg_prices(underlying)
    leg_b = strategy_b.make_call_leg_prices(underlying)
    pd.testing.assert_series_equal(leg_a, leg_b)


def test_strategy_name_stable_in_meta() -> None:
    underlying = _deterministic_underlying()
    strategy, _ = _build_strategy_and_feed(underlying)
    prices = pd.DataFrame({strategy.underlying_symbol: underlying})
    result = vectorbt_bridge.run(strategy=strategy, prices=prices)
    assert result.meta["strategy"] == "covered_call_systematic"
