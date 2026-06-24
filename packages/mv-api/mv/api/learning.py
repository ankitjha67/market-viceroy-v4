"""Live post-mortem surface: the mistake taxonomy over the journal's closed trades.

Reuses the Phase-5 engine — `reconstruct_closed_trades` → `decompose` →
`classify` → `mistake_stats` — so the dashboard's Learning tile and the
Post-Mortem Room show real, cause-tagged mistakes as losing trades close, rather
than only via the offline `scripts/run_postmortem.py`. Pure / deterministic;
money rendered as strings for the API. The governed improvement *ledger*
(propose-only meta-learning) stays an offline pass — it needs out-of-sample
Sharpe + a held-out window the live tick loop does not have.
"""

from __future__ import annotations

from typing import Any

from mv.postmortem.decompose import decompose
from mv.postmortem.mistakes import classify, mistake_stats
from mv.postmortem.trades import Fill, reconstruct_closed_trades


def mistakes_from_fills(fills: list[Fill]) -> dict[str, dict[str, Any]]:
    """Classify the closed round trips in ``fills`` into the mistake taxonomy and
    roll up per category as ``{category: {count, cost}}`` (FR-P2).

    Only losing round trips are classified; a winning trade contributes nothing.
    ``cost`` is the cumulative adverse magnitude rendered as a string.
    """
    mistakes = []
    for trade in reconstruct_closed_trades(fills):
        mistake = classify(decompose(trade))
        if mistake is not None:
            mistakes.append(mistake)
    return {
        category: {"count": stat.count, "cost": str(stat.cost)}
        for category, stat in mistake_stats(mistakes).items()
    }


__all__ = ["mistakes_from_fills"]
