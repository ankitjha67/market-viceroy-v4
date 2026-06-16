# alphakit-strategies-macro

Macro / GTAA strategies for [AlphaKit](https://github.com/ankitjha67/alphakit).

Phase 2 target: 11 strategies covering static risk-parity allocations
(permanent portfolio, equal-risk-contribution 3-asset, minimum-variance,
maximum-diversification), multi-asset and tactical momentum (cross-
asset GTAA momentum, vigilant asset allocation), and macro regime
allocators driven by exogenous FRED state variables (growth × inflation,
yield-curve regime, recession probability, Fed policy, inflation
regime). Covariance-based weighting strategies share the
`alphakit.strategies.macro._covariance` helper (Ledoit-Wolf shrinkage,
rolling-window covariance estimation, ERC / minimum-variance / maximum-
diversification solvers). Regime allocators follow the Session 2D
"informational columns with zero weight" pattern
(`docs/phase-2-amendments.md` §2D / amendments.md:309-328): FRED series
enter `generate_signals` as input DataFrame columns and carry zero
weight in the output, while tradable assets carry the regime-conditional
allocation.

The Session 2G shipping count is 11, not the originally-planned 15:
`cape_country_rotation` (cluster duplicate of Phase 1
`country_cape_rotation`), `dollar_strength_tilt` (no peer-reviewed
anchor — folklore "DXY momentum → EM equity short" signal),
`dual_momentum_gtaa` (cluster duplicate of Phase 1 `dual_momentum_gem`
— same Antonacci 2014 paper and mechanic), and
`inflation_tilt_60_40_overlay` (borderline cluster duplicate of
`inflation_regime_allocation` — same CPI signal driver) were dropped
under the Phase 2 honesty-check. Five plan slugs were reframed:
`risk_parity_3asset → risk_parity_erc_3asset`,
`economic_regime_rotation → growth_inflation_regime_rotation`,
`yield_curve_regime_asset_allocation → yield_curve_regime_allocation`,
`global_macro_momentum → gtaa_cross_asset_momentum`, and
`5_asset_tactical → vigilant_asset_allocation_5`. See
`docs/phase-2-amendments.md` for the full audit trail.
