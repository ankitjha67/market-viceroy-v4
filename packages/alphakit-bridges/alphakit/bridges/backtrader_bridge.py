"""Bridge to the `backtrader <https://www.backtrader.com>`_ backtester.

Backtrader is an event-driven backtester: strategies subclass
``bt.Strategy`` and implement ``next()``. This bridge adapts any
:class:`StrategyProtocol` into such a subclass by pre-computing the
weights panel up-front and looking up the row for each timestamp in
``next()``.

Design notes
------------
* We pre-compute weights once before running the Cerebro loop. This
  keeps the bridge simple and ensures vectorbt and backtrader produce
  numerically identical results on the same strategy (modulo execution
  lag).
* Backtrader's order lag is one bar: orders placed in ``next()`` on
  bar ``t`` execute at the open of bar ``t+1``. We accept this — it is
  the standard backtrader semantics and matches realistic execution.
* The import of ``backtrader`` is local to :func:`run` so ``import
  alphakit.bridges`` stays cheap.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
from alphakit.core.metrics.drawdown import max_drawdown
from alphakit.core.metrics.returns import calmar_ratio, sharpe_ratio, sortino_ratio
from alphakit.core.protocols import BacktestResult, StrategyProtocol

NAME: str = "backtrader"


def _import_backtrader() -> Any:
    """Lazy import of backtrader with a helpful error message."""
    try:
        import backtrader as bt
    except ImportError as exc:  # pragma: no cover - exercised only w/o bt
        raise ImportError(
            "backtrader is required for the backtrader_bridge. "
            "Install with `pip install 'alphakit-bridges[backtrader]'` "
            "or `pip install backtrader`."
        ) from exc
    return bt


def _make_strategy_class(weights: pd.DataFrame, bt_module: Any) -> Any:
    """Build a ``bt.Strategy`` subclass that replays ``weights`` on ``next``."""

    captured_weights = weights

    class _WeightsReplayStrategy(bt_module.Strategy):  # type: ignore[misc]
        def __init__(self) -> None:
            self._weights_df: pd.DataFrame = captured_weights
            self._datas_by_name: dict[str, Any] = {d._name: d for d in self.datas}

        def next(self) -> None:
            ts = self.datas[0].datetime.datetime(0)
            # Align to weights index — forward-fill missing timestamps.
            try:
                row = self._weights_df.loc[:ts].iloc[-1]
            except (KeyError, IndexError):
                return
            total_value = float(self.broker.getvalue())
            for symbol, target_weight in row.items():
                if symbol not in self._datas_by_name:
                    continue
                data = self._datas_by_name[symbol]
                price = float(data.close[0])
                if price <= 0 or not np.isfinite(price):
                    continue
                target_notional = float(target_weight) * total_value
                target_qty = target_notional / price
                current_qty = float(self.getposition(data).size)
                delta = target_qty - current_qty
                if abs(delta * price) < 1e-6:
                    continue
                if delta > 0:
                    self.buy(data=data, size=delta)
                else:
                    self.sell(data=data, size=-delta)

    return _WeightsReplayStrategy


def run(
    strategy: StrategyProtocol,
    prices: pd.DataFrame,
    *,
    initial_cash: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    """Backtest ``strategy`` on ``prices`` with backtrader.

    Slippage is applied as a fixed fractional adjustment on the broker;
    commission is applied as a percentage fee per trade. Both are
    expressed in basis points and translated at call time.
    """
    if prices.empty:
        raise ValueError("prices DataFrame is empty")
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("commission_bps and slippage_bps must be non-negative")
    if initial_cash <= 0:
        raise ValueError(f"initial_cash must be positive, got {initial_cash}")

    bt = _import_backtrader()

    weights = strategy.generate_signals(prices)
    weights = weights.reindex_like(prices).fillna(0.0)

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.set_cash(initial_cash)
    cerebro.broker.setcommission(commission=commission_bps / 10_000.0)
    if slippage_bps > 0:
        cerebro.broker.set_slippage_perc(perc=slippage_bps / 10_000.0)

    for symbol in prices.columns:
        feed_df = pd.DataFrame(
            {
                "open": prices[symbol],
                "high": prices[symbol],
                "low": prices[symbol],
                "close": prices[symbol],
                "volume": 0,
                "openinterest": 0,
            }
        )
        data_feed = bt.feeds.PandasData(dataname=feed_df, name=str(symbol))
        cerebro.adddata(data_feed)

    strategy_cls = _make_strategy_class(weights, bt)
    cerebro.addstrategy(strategy_cls)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="time_return")
    cerebro.run()

    # Extract the broker equity curve from the TimeReturn analyzer.
    analyzer_result = cast(
        dict[Any, float], cerebro.runstrats[0][0].analyzers.time_return.get_analysis()
    )
    if analyzer_result:
        timestamps = list(analyzer_result.keys())
        ret_values = list(analyzer_result.values())
        returns = pd.Series(
            ret_values, index=pd.DatetimeIndex(timestamps), dtype=float, name="returns"
        )
        equity_curve = (1.0 + returns).cumprod() * initial_cash
    else:
        returns = pd.Series(
            [0.0] * len(prices.index), index=prices.index, dtype=float, name="returns"
        )
        equity_curve = pd.Series(
            [initial_cash] * len(prices.index), index=prices.index, dtype=float
        )
    equity_curve.name = "equity"

    returns_arr = returns.to_numpy()
    metrics: dict[str, float] = {
        "sharpe": sharpe_ratio(returns_arr),
        "sortino": sortino_ratio(returns_arr),
        "calmar": calmar_ratio(returns_arr),
        "max_drawdown": max_drawdown(returns_arr),
        "final_equity": float(equity_curve.iloc[-1]),
        "total_return": float(equity_curve.iloc[-1] / initial_cash - 1.0),
    }
    if np.isfinite(returns_arr).any() and returns_arr.size > 1:
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
            "strategy": strategy.name,
            "family": strategy.family,
            "paper_doi": strategy.paper_doi,
        },
    )
