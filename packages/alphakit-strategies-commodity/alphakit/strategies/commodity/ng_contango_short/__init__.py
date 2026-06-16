"""Natural-gas short-only contango trade on the front-vs-next-month curve.

Foundational: Bessembinder, H. (1992), *Systematic Risk, Hedging
Pressure, and Risk Premiums in Futures Markets*, Review of Financial
Studies 5(4), 637–667.
DOI: https://doi.org/10.1093/rfs/5.4.637

Primary methodology: Erb, C. B. & Harvey, C. R. (2006), *The
Strategic and Tactical Value of Commodity Futures*, Financial
Analysts Journal 62(2), 69–97. Section III applied to the
canonical-most-contangoed commodity (natural gas).
DOI: https://doi.org/10.2469/faj.v62.n2.4084
"""

from __future__ import annotations

from alphakit.strategies.commodity.ng_contango_short.strategy import NGContangoShort

__all__ = ["NGContangoShort"]
