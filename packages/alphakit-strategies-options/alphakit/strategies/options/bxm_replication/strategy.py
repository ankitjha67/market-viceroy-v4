"""Canonical CBOE BXM index replication on synthetic chains.

Whaley, R. E. (2002). *Return and Risk of CBOE Buy Write Monthly
Index*. Journal of Derivatives, 10(2), 35-42.
https://doi.org/10.3905/jod.2002.319188

The BXM index is the *exactly-ATM* monthly call write on the S&P 500
cash index — the parametric special-case of
``covered_call_systematic`` with ``otm_pct = 0.0``. Whereas
``covered_call_systematic`` ships the practitioner-aligned 2 % OTM
variant (Israelov-Nielsen 2014), ``bxm_replication`` ships the
index-construction reference: the canonical BXM rule, sole anchor.

Differentiation from ``covered_call_systematic``
------------------------------------------------
* **Strike rule.** ``bxm_replication`` writes the ATM call (strike
  = spot at write); ``covered_call_systematic`` defaults to 2 % OTM.
  On the synthetic chain's 9-strike grid (``0.80, 0.85, …, 1.20`` ×
  spot) the ATM strike is exactly the 1.00 multiplier, so the BXM
  rule snaps cleanly to that grid point.
* **Citation.** Sole anchor: Whaley 2002. The 2 % OTM variant cites
  Israelov-Nielsen 2014 as primary because that's the paper whose
  decomposition the variant replicates; for ATM-BXM, Whaley 2002
  *is* the methodology paper.
* **Cluster expectation.** ρ ≈ 0.95-1.00 with
  ``covered_call_systematic`` — the two strategies differ only by
  one strike-grid multiplier. They ship as parametric variants for
  users who want either the canonical index methodology
  (``bxm_replication``) or the practitioner-aligned offset
  (``covered_call_systematic``).

Implementation
--------------
This class is a thin composition wrapper over
:class:`~alphakit.strategies.options.covered_call_systematic.strategy.CoveredCallSystematic`
with ``otm_pct = 0.0`` fixed and metadata redirected at the
Whaley 2002 sole anchor. The ``StrategyProtocol`` surface
(``name``, ``family``, ``asset_classes``, ``paper_doi``,
``rebalance_frequency``, ``discrete_legs``, ``generate_signals``)
plus the chain-construction helper ``make_call_leg_prices`` are
re-exposed via delegation; the inner instance is owned at
construction time. The bridge integration via ``discrete_legs`` is
identical to the parent strategy — the leg symbol just encodes
``OTM00PCT`` (zero offset) instead of ``OTM02PCT``.

See ``covered_call_systematic/strategy.py`` for the full
implementation rationale (lifecycle state machine, Mode 1 vs
Mode 2 weights, ``_LEG_FLAT_FLOOR`` / ``_LEG_PRICE_EPSILON`` ).
"""

from __future__ import annotations

import pandas as pd
from alphakit.core.protocols import DataFeedProtocol
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
)


class BXMReplication:
    """CBOE BXM index replication: monthly ATM call write on synthetic chains.

    Parameters
    ----------
    underlying_symbol
        Column name for the underlying. Defaults to ``"SPY"``.
    chain_feed
        Optional explicit feed object for chain access. When
        ``None`` (default), resolves
        ``FeedRegistry.get("synthetic-options")`` lazily.
    """

    name: str = "bxm_replication"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("equity",)
    paper_doi: str = "10.3905/jod.2002.319188"  # Whaley 2002 (sole anchor)
    rebalance_frequency: str = "monthly"

    discrete_legs: tuple[str, ...]

    def __init__(
        self,
        *,
        underlying_symbol: str = "SPY",
        chain_feed: DataFeedProtocol | None = None,
    ) -> None:
        self._inner = CoveredCallSystematic(
            underlying_symbol=underlying_symbol,
            otm_pct=0.0,
            chain_feed=chain_feed,
        )
        self.underlying_symbol = underlying_symbol
        self.discrete_legs = self._inner.discrete_legs

    @property
    def chain_feed(self) -> DataFeedProtocol:
        return self._inner.chain_feed

    @property
    def call_leg_symbol(self) -> str:
        """Synthetic ATM-call leg column name.

        Format: ``f"{underlying}_CALL_OTM00PCT_M1"`` — encodes the
        zero-offset (ATM) Whaley 2002 BXM rule.
        """
        return self._inner.call_leg_symbol

    def make_call_leg_prices(
        self,
        underlying_prices: pd.Series,
        *,
        chain_feed: DataFeedProtocol | None = None,
    ) -> pd.Series:
        """Delegate to the inner ``CoveredCallSystematic`` with otm_pct=0."""
        return self._inner.make_call_leg_prices(underlying_prices, chain_feed=chain_feed)

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Delegate to the inner ``CoveredCallSystematic`` with otm_pct=0."""
        weights = self._inner.generate_signals(prices)
        # Override meta-style attribute access by re-stamping the
        # weights DataFrame's columns to remain identical to the
        # input — the bridge reads ``strategy.name`` from the
        # outer (this) object and ``strategy.discrete_legs`` from
        # the same. No structural change to the weights.
        return weights
