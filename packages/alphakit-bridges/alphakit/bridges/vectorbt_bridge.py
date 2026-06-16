"""Bridge to the `vectorbt <https://vectorbt.dev>`_ backtester.

Vectorbt is the fastest open-source Python backtester for daily-ish
strategies: it compiles signals into NumPy/Numba kernels that run in the
low-millisecond range for thousands of symbols.

This bridge adapts any :class:`~alphakit.core.protocols.StrategyProtocol`
that emits a weights DataFrame into a ``vbt.Portfolio.from_orders`` call,
then normalises the result into :class:`BacktestResult`.

Design notes
------------
* The import of ``vectorbt`` is local to :func:`run` so that simply
  loading ``alphakit.bridges`` does not pull in Numba / NumPy ABI
  compatibility issues.
* We route via ``from_orders`` (not ``from_signals``) because weights are
  the strategy's native output; converting to entry/exit booleans would
  lose information.
* Commission and slippage are expressed in **basis points** of notional
  to match the rest of AlphaKit, then translated into vectorbt's
  fractional representation at call time.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import numpy as np
import pandas as pd
from alphakit.core.metrics.drawdown import max_drawdown
from alphakit.core.metrics.returns import calmar_ratio, sharpe_ratio, sortino_ratio
from alphakit.core.protocols import (
    BacktestResult,
    StrategyProtocol,
    get_discrete_legs,
)

NAME: str = "vectorbt"

logger = logging.getLogger(__name__)


def _import_vectorbt() -> Any:
    """Import vectorbt lazily, raising a helpful error on failure."""
    try:
        import vectorbt as vbt
    except ImportError as exc:  # pragma: no cover - exercised only w/o vbt
        raise ImportError(
            "vectorbt is required for the vectorbt_bridge. "
            "Install with `pip install 'alphakit-bridges[vectorbt]'` "
            "or `pip install vectorbt`."
        ) from exc
    return vbt


def run(
    strategy: StrategyProtocol,
    prices: pd.DataFrame,
    *,
    initial_cash: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    frequency: str = "1D",
) -> BacktestResult:
    """Backtest ``strategy`` on ``prices`` with vectorbt.

    Parameters
    ----------
    strategy
        Any object satisfying :class:`StrategyProtocol`.
    prices
        DataFrame indexed by timestamp, columns are instrument symbols,
        values are adjusted close prices.
    initial_cash
        Starting cash balance in the portfolio base currency.
    commission_bps
        Round-trip commission in basis points of notional.
    slippage_bps
        Execution slippage in basis points of notional.
    frequency
        Pandas offset alias describing the bar frequency — passed to
        vectorbt for annualisation.
    """
    if prices.empty:
        raise ValueError("prices DataFrame is empty")
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("commission_bps and slippage_bps must be non-negative")
    if initial_cash <= 0:
        raise ValueError(f"initial_cash must be positive, got {initial_cash}")

    vbt = _import_vectorbt()

    # 1. Ask the strategy for a target-weights panel and align it to prices.
    weights = strategy.generate_signals(prices)
    weights = weights.reindex_like(prices).fillna(0.0)

    # 2. Translate weights into size orders interpretable by vectorbt.
    #
    #    Default semantics: every column is rebalanced to a target
    #    percentage of equity each bar (``SizeType.TargetPercent``).
    #    This is correct for every strategy through Session 2E (TSMOM,
    #    mean-reversion, carry, value, volatility, rates, commodity)
    #    where the strategy expresses continuous-exposure positions.
    #
    #    Session 2F extension: strategies declaring
    #    ``discrete_legs: tuple[str, ...]`` flag specific columns whose
    #    weights are *one-shot* share/contract counts
    #    (``SizeType.Amount``). Without this, an option leg whose
    #    premium decays from $8 → $0 across the monthly cycle would
    #    cause the bridge to sell ever-more contracts to maintain a
    #    static −100 % dollar target, producing runaway short P&L.
    #
    #    Implementation: vectorbt's ``size_type`` accepts a per-column
    #    array, which is exactly the dispatch primitive we need —
    #    ``TargetPercent`` for continuous columns, ``Amount`` for
    #    discrete columns. No two-portfolio merge needed.
    declared_legs = get_discrete_legs(strategy)
    # Partition declared legs into those actually present in
    # ``prices`` (active dispatch targets) and those declared but
    # absent (Mode 2 fallback path or, possibly, a typo in the
    # declaration). A strategy may declare its discrete legs
    # statically (e.g. ``("SPY_CALL_OTM02PCT_M1",)``) but be invoked
    # on a smaller universe — the canonical case is Session 2F's
    # options strategies being run by the standard BenchmarkRunner
    # with only the underlying column. In that fallback mode the
    # strategy emits single-column buy-and-hold weights and the
    # discrete leg is genuinely absent.
    #
    # Bridge contract: silently use ``present_legs`` for the
    # size_type dispatch (so the fallback runs to completion), but
    # ``logger.debug`` any ``missing_legs`` so typos surface in
    # tests / debug log streams. Tests can use pytest's ``caplog``
    # fixture to verify the warning fires.
    present_legs = tuple(c for c in declared_legs if c in prices.columns)
    missing_legs = tuple(c for c in declared_legs if c not in prices.columns)

    if missing_legs:
        logger.debug(
            "Strategy %s declared discrete_legs %s but columns %s not in "
            "prices.columns. Treating as Mode 2 fallback (continuous-rebalance "
            "TargetPercent semantics for the absent legs); ensure declared "
            "leg names are typo-free or this may silently swallow the "
            "discrete-mode dispatch.",
            strategy.name,
            declared_legs,
            missing_legs,
        )

    # Restrict the order simulation to columns the strategy actually trades.
    # A column whose target weight is identically zero across every bar — the
    # canonical case being an *informational* regime input (a raw FRED
    # level/probability carried in ``prices`` only so ``generate_signals`` can
    # read it) — contributes nothing to P&L, yet vectorbt still issues a
    # zero-target order for it and rejects its price via
    # "order.price must be finite and greater than 0". A recession probability
    # of 0.0, or a negative real-yield level, legitimately violates that. We
    # drop such columns before ``from_orders``; doing so is exactly P&L-neutral
    # (0 shares * any finite price = 0). The full ``weights`` panel is still
    # returned in the result for transparency/turnover accounting.
    traded_mask = (weights != 0.0).any(axis=0)
    if bool(traded_mask.any()):
        traded_cols = [c for c in weights.columns if traded_mask[c]]
        close_in = prices[traded_cols]
        size_in = weights[traded_cols]
    else:
        # Degenerate all-cash strategy: keep the full panel (original behavior).
        close_in = prices
        size_in = weights

    active_legs = tuple(c for c in present_legs if c in close_in.columns)
    if active_legs:
        size_type_per_column = np.array(
            [
                vbt.portfolio.enums.SizeType.Amount
                if col in active_legs
                else vbt.portfolio.enums.SizeType.TargetPercent
                for col in close_in.columns
            ],
            dtype=int,
        )
    else:
        size_type_per_column = vbt.portfolio.enums.SizeType.TargetPercent

    fees = commission_bps / 10_000.0
    slippage = slippage_bps / 10_000.0

    portfolio = vbt.Portfolio.from_orders(
        close=close_in,
        size=size_in,
        size_type=size_type_per_column,
        init_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        freq=frequency,
        group_by=True,  # treat all symbols as a single portfolio
        cash_sharing=True,
    )

    # 3. Extract the equity curve and per-bar returns as pandas objects.
    equity_raw = portfolio.value()
    equity_curve = cast(
        pd.Series, equity_raw.squeeze() if hasattr(equity_raw, "squeeze") else equity_raw
    )
    if not isinstance(equity_curve, pd.Series):
        equity_curve = pd.Series(equity_curve, index=prices.index)
    equity_curve = equity_curve.astype(float)
    equity_curve.name = "equity"

    returns = equity_curve.pct_change().fillna(0.0)
    returns.name = "returns"

    # 4. Headline metrics from our own implementation (not vbt's) so that
    #    every engine reports the same numbers.
    returns_arr = returns.to_numpy()
    metrics: dict[str, float] = {
        "sharpe": sharpe_ratio(returns_arr),
        "sortino": sortino_ratio(returns_arr),
        "calmar": calmar_ratio(returns_arr),
        "max_drawdown": max_drawdown(returns_arr),
        "final_equity": float(equity_curve.iloc[-1]),
        "total_return": float(equity_curve.iloc[-1] / initial_cash - 1.0),
    }
    if np.isfinite(returns_arr).any():
        metrics["annualized_return"] = float(np.mean(returns_arr) * 252)
        metrics["annualized_vol"] = float(np.std(returns_arr, ddof=1) * np.sqrt(252))
    else:
        metrics["annualized_return"] = 0.0
        metrics["annualized_vol"] = 0.0

    return BacktestResult(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        metrics=metrics,
        meta={
            "engine": NAME,
            "initial_cash": initial_cash,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "frequency": frequency,
            "strategy": strategy.name,
            "family": strategy.family,
            "paper_doi": strategy.paper_doi,
        },
    )
