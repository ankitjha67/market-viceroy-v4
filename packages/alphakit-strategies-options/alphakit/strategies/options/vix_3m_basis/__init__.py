"""vix_3m_basis — VIX spot vs 3-month constant-maturity basis trade.

Foundational: Whaley, R. E. (2009). *Understanding VIX*. Journal
of Portfolio Management 35(2), 98-105.
DOI: https://doi.org/10.3905/JPM.2009.35.2.098

Primary methodology: Alexander, C., Korovilas, D. & Kapraun, J.
(2015). *Diversification with Volatility Products*. Journal of
International Money and Finance 65, 213-235.
DOI: https://doi.org/10.1016/j.jimonfin.2015.10.005

Reframed from `vix_front_back_spread` per
`docs/phase-2-amendments.md` 2026-05-01 — yfinance does not
expose back-month VIX futures, so the original front-back-future
spread is not implementable. The reframe trades the
**spot vs 3-month constant-maturity index basis** instead, which
Alexander et al. study explicitly.
"""

from __future__ import annotations

from alphakit.strategies.options.vix_3m_basis.strategy import VIX3MBasis

__all__ = ["VIX3MBasis"]
