"""VIX spot-vs-front-month basis trade (Simon-Campasano 2014).

Foundational paper
------------------
Whaley, R. E. (2009). *Understanding VIX*. Journal of Portfolio
Management, 35(2), 98-105.
https://doi.org/10.3905/JPM.2009.35.2.098

Whaley documents the construction and properties of the CBOE
Volatility Index (VIX) — the model-free implied-vol measure
underlying the VIX-futures market. The VIX-futures basis (spot
minus front-month future) is the canonical signal in this
strategy family.

Primary methodology
-------------------
Simon, D. P. & Campasano, J. (2014). *The VIX Futures Basis:
Evidence and Trading Strategies*. Journal of Derivatives, 21(3),
54-69. https://doi.org/10.3905/jod.2014.21.3.054

Simon-Campasano study the VIX-futures basis empirically and
document a systematic trading rule:

* When ``VIX_spot < VIX_front_future`` (curve in **contango**,
  futures expected to roll DOWN toward spot at expiry): SHORT
  the front-month future. Profit from roll-down convergence.
* When ``VIX_spot > VIX_front_future`` (curve in
  **backwardation**, futures expected to roll UP toward spot):
  LONG the front-month future. Profit from roll-up convergence.

The signal is *unconditional* — sign of the basis determines
direction; magnitude does not size the position (per the
canonical Simon-Campasano spec).

Differentiation from Phase 1 ``vix_term_structure``
---------------------------------------------------
Phase 1's ``vix_term_structure`` (volatility family) uses
**realized vol of SPY as a proxy for VIX** — no real VIX feed
was available in Phase 1.

Phase 2's ``vix_term_structure_roll`` consumes **real ^VIX
(yfinance equity passthrough) + VIX=F (yfinance-futures
passthrough)** for the actual basis. The two slugs co-exist on
main: Phase 1's ``vix_term_structure`` stays as the realized-vol-
proxied version; this strategy is the canonical real-data
implementation.

Cluster expectation: ρ ≈ 0.40-0.65 with Phase 1 sibling
(realized-vol proxy correlates loosely with real VIX); much
higher ρ with Phase 1's ``vix_roll_short`` (similar
roll-yield direction).

Strategy structure
------------------
For each daily bar:

1. Read ``^VIX`` (spot index) and ``VIX=F`` (front-month
   future) from input prices.
2. Compute basis = ``VIX_spot − VIX_front_future``.
3. Position on ``VIX=F``:

   * ``+1.0`` (long) when ``basis > 0`` (backwardation)
   * ``-1.0`` (short) when ``basis < 0`` (contango)
   * ``0.0`` when basis ≈ 0 (within numerical noise)

   Continuous TargetPercent semantics — daily rebalance to the
   signed weight.
4. ``^VIX`` is *not* traded; it's the signal source only.

Bridge integration
------------------
No discrete legs (VIX=F is a continuous-exposure instrument
under TargetPercent semantics). The bridge handles this
strategy with the standard pre-Session-2F dispatch pattern.

yfinance passthrough assumption
-------------------------------
``^VIX`` and ``VIX=F`` are handled by yfinance's standard
ticker passthrough — yfinance.download accepts both symbols
without special handling. Real-data shape verification is
deferred to Session 2H benchmark-runner real-feed runs;
integration tests mock the yfinance response shape (see
``tests/test_integration.py``).

Documented in ``known_failures.md`` §9.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_BASIS_EPSILON: float = 1e-6  # threshold below which basis is "noise"


class VIXTermStructureRoll:
    """VIX spot-vs-front-month basis trade.

    Parameters
    ----------
    spot_symbol
        Column name for VIX spot. Defaults to ``"^VIX"`` (CBOE
        spot VIX index).
    futures_symbol
        Column name for VIX front-month futures continuous
        contract. Defaults to ``"VIX=F"`` (yfinance continuous
        VIX front-month).
    """

    name: str = "vix_term_structure_roll"
    family: str = "options"
    asset_classes: tuple[str, ...] = ("volatility",)
    paper_doi: str = "10.3905/jod.2014.21.3.054"  # Simon-Campasano 2014
    rebalance_frequency: str = "daily"

    def __init__(
        self,
        *,
        spot_symbol: str = "^VIX",
        futures_symbol: str = "VIX=F",
    ) -> None:
        if not spot_symbol:
            raise ValueError("spot_symbol must be a non-empty string")
        if not futures_symbol:
            raise ValueError("futures_symbol must be a non-empty string")
        if spot_symbol == futures_symbol:
            raise ValueError(f"spot_symbol and futures_symbol must differ; both = {spot_symbol!r}")
        self.spot_symbol = spot_symbol
        self.futures_symbol = futures_symbol

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Return Simon-Campasano basis-trade weights.

        Mode 1 (full strategy):
            ^VIX     = 0 (signal-only column, not traded)
            VIX=F    = sign(VIX − VIX_F) every bar (TargetPercent)
            other    = 0
        Mode 2 (futures-only, no spot):
            All weights 0 — strategy needs both columns to compute
            the basis.
        """
        if not isinstance(prices, pd.DataFrame):
            raise TypeError(f"prices must be a DataFrame, got {type(prices).__name__}")
        if prices.empty:
            return pd.DataFrame(index=prices.index, columns=prices.columns, dtype=float)
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError(f"prices must have a DatetimeIndex, got {type(prices.index).__name__}")
        if self.futures_symbol not in prices.columns:
            raise KeyError(
                f"prices must contain the VIX futures column "
                f"{self.futures_symbol!r}; got columns={list(prices.columns)}"
            )
        # Spot is required to compute the basis; without it the
        # strategy cannot fire (Mode 2 fallback = all-zero weights).
        weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        if self.spot_symbol not in prices.columns:
            return weights

        spot = prices[self.spot_symbol].to_numpy(dtype=float)
        front = prices[self.futures_symbol].to_numpy(dtype=float)
        basis = spot - front
        # +1 when backwardation (spot > front), -1 contango.
        signal = np.where(
            basis > _BASIS_EPSILON,
            1.0,
            np.where(basis < -_BASIS_EPSILON, -1.0, 0.0),
        )
        weights[self.futures_symbol] = signal
        return weights
