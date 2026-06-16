"""skew_reversal — conditional short put when put-skew z-score > threshold.

Foundational: Bakshi, G., Kapadia, N. & Madan, D. (2003).
DOI: https://doi.org/10.1093/rfs/16.1.0101

Primary methodology: Garleanu, N., Pedersen, L. H. & Poteshman,
A. M. (2009).
DOI: https://doi.org/10.1093/rfs/hhp005

⚠ SUBSTRATE CAVEAT — synthetic chain has FLAT IV (ADR-005), so the
skew z-score is structurally zero and the trigger NEVER FIRES.
Strategy ships as faithful methodology implementation for Phase 3
real-feed verification (Polygon, ADR-004 stub).
"""

from __future__ import annotations

from alphakit.strategies.options.skew_reversal.strategy import SkewReversal

__all__ = ["SkewReversal"]
