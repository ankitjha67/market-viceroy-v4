"""mv-postmortem — Post-Mortem & Learning Engine (PRD §4.7, FR-P1–P5).

The causal post-mortem surface: attribution (decompose realized PnL into
signal/timing/sizing/slippage/fees/regime), the mistake taxonomy, counterfactual
replay, the improvement ledger, and **governed, propose-only** meta-learning.
See :mod:`.decompose`, :mod:`.mistakes`, :mod:`.replay`, :mod:`.improvement`,
:mod:`.metalearn`.
"""

from __future__ import annotations

from mv.postmortem.attribution import TradeAttribution, attribute
from mv.postmortem.decompose import components_sum, decompose
from mv.postmortem.improvement import (
    ImprovementEntry,
    ImprovementLedger,
    ImprovementStore,
)
from mv.postmortem.metalearn import WeightProposal, propose_weights
from mv.postmortem.mistakes import Mistake, MistakeContext, classify, mistake_stats
from mv.postmortem.replay import CounterfactualResult, ReplayVariable, realized_pnl, replay
from mv.postmortem.trades import (
    ClosedTrade,
    Fill,
    OpenPosition,
    fill_from_journal,
    open_positions,
    reconstruct_closed_trades,
)

__version__: str = "0.0.1"

__all__ = [
    "ClosedTrade",
    "CounterfactualResult",
    "Fill",
    "ImprovementEntry",
    "ImprovementLedger",
    "ImprovementStore",
    "Mistake",
    "MistakeContext",
    "OpenPosition",
    "ReplayVariable",
    "TradeAttribution",
    "WeightProposal",
    "__version__",
    "attribute",
    "classify",
    "components_sum",
    "decompose",
    "fill_from_journal",
    "mistake_stats",
    "open_positions",
    "propose_weights",
    "realized_pnl",
    "reconstruct_closed_trades",
    "replay",
]
