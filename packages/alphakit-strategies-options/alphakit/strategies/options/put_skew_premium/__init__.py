"""put_skew_premium — short OTM put + long OTM call (risk reversal).

Foundational: Bakshi, G., Kapadia, N. & Madan, D. (2003),
*Stock Return Characteristics, Skew Laws, and the Differential
Pricing of Individual Equity Options*, Review of Financial
Studies 16(1), 101-143.
DOI: https://doi.org/10.1093/rfs/16.1.0101

Primary methodology: Garleanu, N., Pedersen, L. H. & Poteshman,
A. M. (2009), *Demand-Based Option Pricing*, Review of
Financial Studies 22(10), 4259-4299.
DOI: https://doi.org/10.1093/rfs/hhp005

⚠ SUBSTRATE CAVEAT: synthetic-options chain has flat IV across
strikes (ADR-005). This strategy's economic content (skew
premium harvest) cannot be properly tested on this substrate.
Real-feed verification path: Phase 3 with Polygon. See
``known_failures.md`` for full discussion.
"""

from __future__ import annotations

from alphakit.strategies.options.put_skew_premium.strategy import PutSkewPremium

__all__ = ["PutSkewPremium"]
