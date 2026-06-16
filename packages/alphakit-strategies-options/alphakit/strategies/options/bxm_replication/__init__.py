"""bxm_replication — canonical CBOE BXM index construction (Whaley 2002).

Foundational + Primary: Whaley, R. E. (2002),
*Return and Risk of CBOE Buy Write Monthly Index*, Journal of
Derivatives 10(2), 35-42.
DOI: https://doi.org/10.3905/jod.2002.319188
"""

from __future__ import annotations

from alphakit.strategies.options.bxm_replication.strategy import BXMReplication

__all__ = ["BXMReplication"]
