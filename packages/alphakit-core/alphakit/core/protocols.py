"""Runtime-checkable protocols defining the AlphaKit engine seam.

These protocols are the *entire* interface that sub-packages must implement.
Keeping this file small, stable and dependency-light is critical to the
project's modular promise: a new engine, strategy or data feed plugs in by
implementing one of these three protocols, nothing more.

Design notes
------------
* ``runtime_checkable`` is enabled so downstream code can ``isinstance``-check
  objects against the protocol without forcing explicit subclassing. The cost
  is that only *method existence* is verified at runtime, not signatures;
  the real contract is enforced statically by mypy strict.
* We accept ``pd.DataFrame`` for prices and return ``pd.DataFrame`` for
  weights because that's the canonical shape for vectorised backtests
  (time × symbols). Signal-list-based strategies are a convenience layer
  built on top of this, not part of the core protocol.
* ``BacktestResult`` is defined here (not in ``metrics/``) because it is
  part of the protocol surface and would create a circular import otherwise.
"""

from __future__ import annotations

from datetime import datetime
from math import nan
from typing import Any, NoReturn, Protocol, runtime_checkable

import pandas as pd
from alphakit.core.data import OptionChain
from pydantic import BaseModel, ConfigDict, Field


def raise_chain_not_supported(feed_name: str) -> NoReturn:
    """Standard refusal used by feeds that don't serve option chains.

    Every non-options ``DataFeedProtocol`` implementation should
    delegate its ``fetch_chain`` body to this helper so the error
    message format stays consistent across the ecosystem.
    """
    raise NotImplementedError(f"{feed_name!r} does not support option chains")


class BacktestResult(BaseModel):
    """Uniform output of any ``BacktestEngineProtocol.run`` implementation.

    All engine bridges (internal, vectorbt, backtrader, LEAN) are required to
    normalise their native output into this structure so that strategies,
    notebooks and the benchmark runner can treat every engine identically.

    Headline metrics are exposed both via the ``metrics`` dict and via
    top-level property accessors (``result.sharpe``, ``result.max_dd``).
    Missing metrics return ``nan``, never raise.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    equity_curve: pd.Series
    """Total portfolio equity over time, indexed by bar timestamp."""

    returns: pd.Series
    """Per-bar portfolio returns, aligned to ``equity_curve``."""

    weights: pd.DataFrame
    """Target weights per symbol over time (time × symbols)."""

    metrics: dict[str, float] = Field(default_factory=dict)
    """Headline metrics (sharpe, max_drawdown, calmar, ...).

    Advanced users can access the full dict directly. Common metrics are
    also exposed as top-level properties below.
    """

    meta: dict[str, Any] = Field(default_factory=dict)
    """Free-form metadata: engine name, version, commit_sha, runtime."""

    @property
    def sharpe(self) -> float:
        """Sharpe ratio — convenience accessor for metrics['sharpe']."""
        return self.metrics.get("sharpe", nan)

    @property
    def sortino(self) -> float:
        """Sortino ratio — convenience accessor for metrics['sortino']."""
        return self.metrics.get("sortino", nan)

    @property
    def calmar(self) -> float:
        """Calmar ratio — convenience accessor for metrics['calmar']."""
        return self.metrics.get("calmar", nan)

    @property
    def max_dd(self) -> float:
        """Max drawdown — convenience accessor for metrics['max_drawdown']."""
        return self.metrics.get("max_drawdown", nan)

    @property
    def final_equity(self) -> float:
        """Final equity — convenience accessor for metrics['final_equity']."""
        return self.metrics.get("final_equity", nan)

    @property
    def total_return(self) -> float:
        """Total return — convenience accessor for metrics['total_return']."""
        return self.metrics.get("total_return", nan)

    @property
    def annualized_return(self) -> float:
        """Annualised return — convenience accessor."""
        return self.metrics.get("annualized_return", nan)

    @property
    def annualized_vol(self) -> float:
        """Annualised volatility — convenience accessor."""
        return self.metrics.get("annualized_vol", nan)


@runtime_checkable
class StrategyProtocol(Protocol):
    """The one interface every AlphaKit strategy implements.

    A strategy is a *pure* function of a price panel: given OHLCV data,
    produce a weights DataFrame. The framework handles sizing, execution,
    commissions and bookkeeping.

    Required class-level metadata
    -----------------------------
    * ``name``             — unique slug, e.g. ``"tsmom_12_1"``
    * ``family``           — strategy family, e.g. ``"trend"``
    * ``asset_classes``    — tuple of asset classes this strategy is valid for
    * ``paper_doi``        — DOI, arXiv link, or book ISBN. **Never blank.**
    * ``rebalance_frequency`` — ``"daily"`` | ``"weekly"`` | ``"monthly"`` | ...

    Optional class-level metadata
    -----------------------------
    * ``discrete_legs: tuple[str, ...]`` — column names whose target
      weights should be interpreted as **one-shot discrete trades**
      (vectorbt ``SizeType.Amount``) rather than continuous-rebalance
      target dollar exposures (``SizeType.TargetPercent``). The
      attribute is *not* declared on the Protocol body so that existing
      strategies remain ``isinstance(StrategyProtocol)``-conforming
      without modification; bridges access it via
      :func:`get_discrete_legs` which returns ``()`` when the
      attribute is absent.

      **When to declare.** Discretely-traded option legs whose price
      decays sharply across the position's lifecycle (premium → 0
      across a monthly cycle) cannot be modelled under the default
      continuous-rebalance semantics: a static ``weight = -1.0`` every
      bar means "rebalance to −100 % of equity in this asset every
      bar," which causes the bridge to sell ever-more contracts as the
      price decays, producing runaway short P&L. Declare such columns
      in ``discrete_legs`` to keep them at ``SizeType.Amount`` (one
      order per bar — the strategy emits the share count directly,
      no rebalancing).

      **When *not* to declare.** Continuous-exposure assets (equities,
      futures, FX) under TSMOM / mean-reversion / carry / value
      strategies must remain in the default
      ``SizeType.TargetPercent`` mode. The 83 strategies through
      Session 2E ship without ``discrete_legs`` and are therefore
      unaffected by this Protocol extension.

      Example::

          class CoveredCallSystematic:
              name = "covered_call_systematic"
              family = "options"
              # ... other required metadata ...
              # The synthetic short-call leg is a discrete trade; the
              # underlying SPY column stays continuous-rebalance.
              discrete_legs: tuple[str, ...] = ("SPY_CALL_OTM02PCT_M1",)
    """

    name: str
    family: str
    asset_classes: tuple[str, ...]
    paper_doi: str
    rebalance_frequency: str

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Transform a price panel into a target-weights DataFrame.

        Parameters
        ----------
        prices
            DataFrame indexed by timestamp, columns are instrument symbols,
            values are adjusted closing prices (float). May contain ``NaN``
            for instruments that did not yet trade.

        Returns
        -------
        weights
            DataFrame with the same index and columns as ``prices``. Each
            row is a set of target portfolio weights summing (by convention)
            to 1.0 for long-only strategies, to 0.0 for market-neutral,
            or unconstrained for leveraged/short strategies. ``NaN`` is
            interpreted as zero weight.

            For columns named in :attr:`discrete_legs`, weights are
            interpreted as one-shot share/contract counts instead of
            target percentages — see the Optional class-level metadata
            section above.
        """
        ...


def get_discrete_legs(strategy: StrategyProtocol) -> tuple[str, ...]:
    """Return the strategy's :attr:`discrete_legs` tuple, or ``()``.

    Bridges call this helper rather than ``getattr`` directly so the
    optional-Protocol-attribute access pattern is centralised and
    type-safe. The default ``()`` preserves the pre-Session-2F
    behaviour of every strategy that does not declare
    ``discrete_legs``: all output columns are interpreted under
    continuous-rebalance ``TargetPercent`` semantics.
    """
    legs = getattr(strategy, "discrete_legs", ())
    if not isinstance(legs, tuple):
        raise TypeError(
            f"strategy.discrete_legs must be a tuple of column names, got {type(legs).__name__}"
        )
    for leg in legs:
        if not isinstance(leg, str) or not leg:
            raise TypeError(
                f"strategy.discrete_legs entries must be non-empty strings, "
                f"got {leg!r} (type={type(leg).__name__})"
            )
    return legs


@runtime_checkable
class BacktestEngineProtocol(Protocol):
    """The single entrypoint every engine bridge exposes.

    Implementations include: the internal vectorised engine, vectorbt,
    backtrader, LEAN (Phase 2+), and nautilus (Phase 4+).
    """

    name: str
    """Engine identifier — ``"internal"``, ``"vectorbt"``, ``"backtrader"``, ..."""

    def run(
        self,
        strategy: StrategyProtocol,
        prices: pd.DataFrame,
        *,
        initial_cash: float = 100_000.0,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> BacktestResult:
        """Execute ``strategy`` on ``prices`` and return a normalised result."""
        ...


@runtime_checkable
class DataFeedProtocol(Protocol):
    """The interface every data adapter implements.

    Implementations include: yfinance, stooq, polygon, CCXT, Binance,
    Deribit, FRED, and synthetic-data helpers.
    """

    name: str
    """Feed identifier — ``"yfinance"``, ``"ccxt"``, ``"fred"``, ..."""

    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Return a price panel for ``symbols`` between ``start`` and ``end``.

        The returned DataFrame is always timestamp-indexed with one column
        per symbol containing adjusted close prices. Adapters that expose
        full OHLCV return a ``MultiIndex`` on columns (``symbol``, ``field``).
        """
        ...

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """Return an option-chain snapshot for ``underlying`` at ``as_of``.

        Feeds that do not provide options data (FRED, vanilla yfinance,
        CFTC, EIA, …) implement this by raising
        :class:`NotImplementedError` via
        :func:`alphakit.core.protocols.raise_chain_not_supported`.
        Options-capable feeds (Polygon, the synthetic-chain generator)
        return a real :class:`OptionChain`.
        """
        ...
