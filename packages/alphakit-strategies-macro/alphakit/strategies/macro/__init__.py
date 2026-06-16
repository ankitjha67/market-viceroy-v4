"""Macro / GTAA strategies — Phase 2 Session 2G.

Phase 2 target: 11 strategies covering static risk-parity allocations,
covariance-based portfolio construction, multi-asset and tactical
momentum, and macro regime allocators driven by exogenous FRED state
variables. Strategy classes are added to ``__all__`` as each
per-strategy commit lands within Session 2G.

The shipping count is 11 rather than the originally-planned 15:
``cape_country_rotation`` (cluster duplicate of Phase 1
``country_cape_rotation``), ``dollar_strength_tilt`` (no peer-reviewed
anchor for the "DXY momentum → EM equity short" signal),
``dual_momentum_gtaa`` (cluster duplicate of Phase 1
``dual_momentum_gem`` — same Antonacci 2014 paper and mechanic), and
``inflation_tilt_60_40_overlay`` (borderline cluster duplicate of
``inflation_regime_allocation`` — same CPI signal driver) were dropped
under the Phase 2 honesty-check. Five plan slugs were reframed under
citation upgrades or substrate-driven renames: ``risk_parity_3asset →
risk_parity_erc_3asset``, ``economic_regime_rotation →
growth_inflation_regime_rotation``,
``yield_curve_regime_asset_allocation → yield_curve_regime_allocation``,
``global_macro_momentum → gtaa_cross_asset_momentum``, and
``5_asset_tactical → vigilant_asset_allocation_5``. See
``docs/phase-2-amendments.md`` for the full audit trail of the 4 drops
and 5 reframes.

Covariance-based strategies (``risk_parity_erc_3asset``,
``min_variance_gtaa``, ``max_diversification``) share the
``alphakit.strategies.macro._covariance`` helper module (Ledoit-Wolf
shrinkage, rolling-window covariance, ERC / minimum-variance /
maximum-diversification solvers) — see Commit 1.5 in the Session 2G
ship order for the helper's gate-3 review.

Regime allocators (``growth_inflation_regime_rotation``,
``yield_curve_regime_allocation``, ``recession_probability_rotation``,
``fed_policy_tilt``, ``inflation_regime_allocation``) follow the
Session 2D "informational columns with zero weight" pattern
documented in ``docs/phase-2-amendments.md`` §2D (the
``2026-04-26 — Session 2D: signal-contract clarifications across rates
strategies`` entry, sub-section 3): FRED series enter
``generate_signals`` as input DataFrame columns and carry zero weight
in the output, while tradable assets carry the regime-conditional
allocation.
"""

from __future__ import annotations

from alphakit.strategies.macro.fed_policy_tilt.strategy import FedPolicyTilt
from alphakit.strategies.macro.growth_inflation_regime_rotation.strategy import (
    GrowthInflationRegimeRotation,
)
from alphakit.strategies.macro.gtaa_cross_asset_momentum.strategy import (
    GtaaCrossAssetMomentum,
)
from alphakit.strategies.macro.inflation_regime_allocation.strategy import (
    InflationRegimeAllocation,
)
from alphakit.strategies.macro.max_diversification.strategy import MaxDiversification
from alphakit.strategies.macro.min_variance_gtaa.strategy import MinVarianceGtaa
from alphakit.strategies.macro.permanent_portfolio.strategy import PermanentPortfolio
from alphakit.strategies.macro.recession_probability_rotation.strategy import (
    RecessionProbabilityRotation,
)
from alphakit.strategies.macro.risk_parity_erc_3asset.strategy import (
    RiskParityErc3Asset,
)
from alphakit.strategies.macro.vigilant_asset_allocation_5.strategy import (
    VigilantAssetAllocation5,
)
from alphakit.strategies.macro.yield_curve_regime_allocation.strategy import (
    YieldCurveRegimeAllocation,
)

__all__: list[str] = [
    "FedPolicyTilt",
    "GrowthInflationRegimeRotation",
    "GtaaCrossAssetMomentum",
    "InflationRegimeAllocation",
    "MaxDiversification",
    "MinVarianceGtaa",
    "PermanentPortfolio",
    "RecessionProbabilityRotation",
    "RiskParityErc3Asset",
    "VigilantAssetAllocation5",
    "YieldCurveRegimeAllocation",
]
