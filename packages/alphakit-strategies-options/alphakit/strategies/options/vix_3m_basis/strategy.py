"""VIX spot vs 3-month constant-maturity basis trade.

Reframe of `vix_front_back_spread`
----------------------------------
The original Phase 2 plan (`vix_front_back_spread`) targeted a
front-vs-back-month VIX futures calendar spread. yfinance
exposes only a single continuous front-month VIX futures
contract (``VIX=F``); back-month per-maturity contracts are
not available. The strategy was reframed to trade the **spot
vs 3-month constant-maturity index basis** (^VIX vs ^VIX3M),
which Alexander, Korovilas & Kapraun (2015) study explicitly
under the same theoretical framework. See
``docs/phase-2-amendments.md`` 2026-05-01 entry "reframe
vix_front_back_spread → vix_3m_basis".

Foundational paper
------------------
Whaley, R. E. (2009). *Understanding VIX*. Journal of Portfolio
Management, 35(2), 98-105.
https://doi.org/10.3905/JPM.2009.35.2.098

Primary methodology
-------------------
Alexander, C., Korovilas, D. & Kapraun, J. (2015).
*Diversification with Volatility Products*. Journal of
International Money and Finance, 65, 213-235.
https://doi.org/10.1016/j.jimonfin.2015.10.005

Alexander et al. study the term-structure of VIX-related
products and document a systematic basis trade between spot VIX
and the 3-month constant-maturity index (^VIX3M):

* When ``VIX_spot < VIX3M`` (curve in **contango**): SHORT the
  3-month leg (or its tradeable proxy, e.g. VXZ ETN). Profit
  from the 3-month leg's roll-down convergence.
* When ``VIX_spot > VIX3M`` (curve in **backwardation**): LONG
  the 3-month leg.

The trade has lower turnover than the spot-vs-front-month
basis (``vix_term_structure_roll``) because the 3-month
constant-maturity index moves more slowly than the front-month
future.

Differentiation from `vix_term_structure_roll` (Commit 15)
----------------------------------------------------------
* `vix_term_structure_roll`: spot vs FRONT-month future
  (~30-day tenor) — Simon-Campasano 2014.
* `vix_3m_basis` (this strategy): spot vs 3-MONTH constant
  maturity (~90-day tenor) — Alexander/Korovilas/Kapraun 2015.

Cluster expectation: ρ ≈ 0.55-0.75 with
`vix_term_structure_roll` — different tenors of the same
underlying basis-trade family. The 3-month basis is more
stable but produces smaller per-cycle P&L.

Implementation
--------------
Composition wrapper over
:class:`~alphakit.strategies.options.vix_term_structure_roll.strategy.VIXTermStructureRoll`
with the second symbol changed from ``VIX=F`` to ``^VIX3M``.

Note: ^VIX3M is a CBOE INDEX, not a tradeable instrument. Real
production use requires VXZ ETN (or similar tradeable proxy).
The strategy emits weights on the ^VIX3M *column* as a proxy;
documented in ``known_failures.md``.

Bridge integration
------------------
Inherited from ``VIXTermStructureRoll``: standard TargetPercent
dispatch on the second symbol; first symbol (^VIX) is
signal-source only. No discrete legs.

yfinance passthrough assumption
-------------------------------
Both ``^VIX`` and ``^VIX3M`` are CBOE indices with caret-prefix
tickers handled by yfinance.download standard passthrough.
Real-data shape verification deferred to Session 2H.
"""

from __future__ import annotations

import pandas as pd
from alphakit.strategies.options.vix_term_structure_roll.strategy import (
    VIXTermStructureRoll,
)


class VIX3MBasis:
    """VIX spot vs 3-month constant-maturity basis trade.

    Parameters
    ----------
    spot_symbol
        Column name for VIX spot. Defaults to ``"^VIX"``.
    longer_symbol
        Column name for the 3-month constant-maturity tradeable
        proxy. Defaults to ``"^VIX3M"`` (CBOE 3-Month VIX index;
        real production should use VXZ ETN as the tradeable
        proxy — see known_failures.md).
    """

    name: str = "vix_3m_basis"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("volatility",)
    paper_doi: str = "10.1016/j.jimonfin.2015.10.005"  # Alexander et al. 2015
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        spot_symbol: str = "^VIX",
        longer_symbol: str = "^VIX3M",
    ) -> None:
        # Composition wrapper: delegate to VIXTermStructureRoll
        # with the second symbol redirected to ^VIX3M.
        self._inner = VIXTermStructureRoll(
            spot_symbol=spot_symbol,
            futures_symbol=longer_symbol,
        )
        self.spot_symbol = spot_symbol
        self.longer_symbol = longer_symbol

    @property
    def futures_symbol(self) -> str:
        """Alias for ``longer_symbol`` to preserve interface symmetry
        with the front-month basis sibling.
        """
        return self.longer_symbol

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Delegate to inner ``VIXTermStructureRoll``."""
        return self._inner.generate_signals(prices)
