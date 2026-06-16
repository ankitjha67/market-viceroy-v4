"""Options strategies — Phase 2 Session 2F.

Phase 2 target: 15 strategies on systematic short-volatility writes,
multi-leg short-volatility structures, Greeks-dependent positions,
variance-risk-premium harvesting, term-structure trades, substrate-
caveat skew trades, and VIX trades. All chain-consuming strategies
backtest against the synthetic-options adapter (ADR-005, Phase 2
Session 2C); VIX strategies consume CBOE indices (``^VIX``,
``^VIX3M``) and the front-month VIX futures continuous contract
(``VIX=F``) via the yfinance and yfinance-futures adapters
respectively. Strategy classes are added to ``__all__`` as each
per-strategy commit lands within Session 2F.

The shipping count is 15 rather than the originally-planned 20:
``diagonal_spread``, ``pin_risk_capture``, ``earnings_vol_crush``,
``ratio_spread_put``, and ``dispersion_trade_proxy`` were dropped
under the Phase 2 honesty-check (folklore mechanics without peer-
reviewed systematic-strategy citations, plus substrate mismatches
the synthetic chain cannot represent — pinning microstructure,
earnings-vol term structure, and individual-stock chains). Three
plan slugs were reframed: ``wheel_strategy → bxmp_overlay``,
``vix_front_back_spread → vix_3m_basis``,
``weekly_theta_harvest → weekly_short_volatility``. See
``docs/phase-2-amendments.md`` for the full audit trail.
"""

from __future__ import annotations

from alphakit.strategies.options.bxm_replication.strategy import BXMReplication
from alphakit.strategies.options.bxmp_overlay.strategy import BXMPOverlay
from alphakit.strategies.options.calendar_spread_atm.strategy import CalendarSpreadATM
from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
)
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
)
from alphakit.strategies.options.delta_hedged_straddle.strategy import (
    DeltaHedgedStraddle,
)
from alphakit.strategies.options.gamma_scalping_daily.strategy import GammaScalpingDaily
from alphakit.strategies.options.iron_condor_monthly.strategy import IronCondorMonthly
from alphakit.strategies.options.put_skew_premium.strategy import PutSkewPremium
from alphakit.strategies.options.short_strangle_monthly.strategy import (
    ShortStrangleMonthly,
)
from alphakit.strategies.options.skew_reversal.strategy import SkewReversal
from alphakit.strategies.options.variance_risk_premium_synthetic.strategy import (
    VarianceRiskPremiumSynthetic,
)
from alphakit.strategies.options.vix_3m_basis.strategy import VIX3MBasis
from alphakit.strategies.options.vix_term_structure_roll.strategy import (
    VIXTermStructureRoll,
)
from alphakit.strategies.options.weekly_short_volatility.strategy import (
    WeeklyShortVolatility,
)

__all__: list[str] = [
    "BXMPOverlay",
    "BXMReplication",
    "CalendarSpreadATM",
    "CashSecuredPutSystematic",
    "CoveredCallSystematic",
    "DeltaHedgedStraddle",
    "GammaScalpingDaily",
    "IronCondorMonthly",
    "PutSkewPremium",
    "ShortStrangleMonthly",
    "SkewReversal",
    "VIX3MBasis",
    "VIXTermStructureRoll",
    "VarianceRiskPremiumSynthetic",
    "WeeklyShortVolatility",
]
