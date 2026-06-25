"""The live paper ensemble roster — the crypto-capable strategies the loop trades.

Phase 1 wired a 3-strategy MVP ensemble; this is the full set of catalog
strategies that both declare ``crypto`` in ``asset_classes`` and run on the
loop's single-symbol close-only window: five trend followers and four
mean-reversion strategies, **equal-weighted** (no naive best-switching —
CLAUDE.md #5). The remaining catalog strategies are cross-sectional / macro /
multi-leg and need panels or instruments crypto paper does not have, so they
stay observe-only in the Strategy Lab rather than trading here. Selection is by
strategy ``name`` so the served ``live_strategies`` list stays honest.
"""

from __future__ import annotations

from alphakit.strategies.meanrev.bollinger_reversion.strategy import BollingerReversion
from alphakit.strategies.meanrev.rsi_reversion_2.strategy import RSIReversion2
from alphakit.strategies.meanrev.rsi_reversion_14.strategy import RSIReversion14
from alphakit.strategies.meanrev.zscore_reversion.strategy import ZScoreReversion
from alphakit.strategies.trend.donchian_breakout_20.strategy import DonchianBreakout20
from alphakit.strategies.trend.donchian_breakout_55.strategy import DonchianBreakout55
from alphakit.strategies.trend.ema_cross_12_26.strategy import EMACross1226
from alphakit.strategies.trend.sma_cross_10_30.strategy import SMACross1030
from alphakit.strategies.trend.sma_cross_50_200.strategy import SMACross50200
from mv.agents.baseline.runner import SignalStrategy


def default_crypto_roster() -> list[SignalStrategy]:
    """The default equal-weight crypto paper ensemble (5 trend + 4 mean-reversion).

    Each strategy operates per-column on the loop's close-only window and emits a
    signed target weight; the deterministic ensemble combines them into one
    Buy/Sell/Hold. The trend followers keep the established long bias
    (``ema_cross`` long-only); the mean-reversion strategies trade both sides, so
    the ensemble is no longer one-directional.
    """
    return [
        EMACross1226(long_only=True),
        SMACross1030(),
        SMACross50200(),
        DonchianBreakout20(),
        DonchianBreakout55(),
        RSIReversion2(),
        RSIReversion14(),
        BollingerReversion(),
        ZScoreReversion(),
    ]


def available_names() -> list[str]:
    """Strategy names the ``--strategies`` override can select, in roster order."""
    return [s.name for s in default_crypto_roster()]


def roster_from_names(names: list[str]) -> list[SignalStrategy]:
    """Resolve a subset of the default roster by name (for the ``--strategies`` flag).

    Unknown names are skipped; ordering follows ``names``. Returns the matched
    strategies (possibly empty — the caller validates before running the loop).
    """
    by_name = {s.name: s for s in default_crypto_roster()}
    out: list[SignalStrategy] = []
    for raw in names:
        strat = by_name.get(raw.strip())
        if strat is not None:
            out.append(strat)
    return out


def roster_names(roster: list[SignalStrategy]) -> list[str]:
    """The names of the strategies in ``roster`` (for the served ``live_strategies``)."""
    return [s.name for s in roster]


__all__ = ["available_names", "default_crypto_roster", "roster_from_names", "roster_names"]
