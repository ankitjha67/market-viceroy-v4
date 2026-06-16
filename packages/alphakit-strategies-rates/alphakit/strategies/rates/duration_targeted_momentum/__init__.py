"""Cross-sectional momentum on duration-adjusted bond returns.

Primary methodology: Durham (2015), *Momentum and the Term Structure
of Interest Rates*, Federal Reserve Board FEDS Working Paper 2015-103.
DOI: https://doi.org/10.17016/FEDS.2015.103
"""

from __future__ import annotations

from alphakit.strategies.rates.duration_targeted_momentum.strategy import (
    DurationTargetedMomentum,
)

__all__ = ["DurationTargetedMomentum"]
