"""Pure performance metrics for the Command Deck — the numbers a real desk reads.

Two honest sources, kept separate from the backtest/validation Sharpe (that lives
in the Strategy Lab gate): **trade statistics** over the journal's closed round
trips (win rate, profit factor, expectancy, avg/largest win-loss, a per-trade
Sharpe/Sortino) and **equity-curve risk** over the live session's per-tick equity
(max drawdown, total return), plus the India crypto-tax drag on realized trades
(Phase 14). Money is ``Decimal``; ratios are floats rendered as strings. Pure /
deterministic — no numpy, no I/O (the tax model is a pure dataclass).
"""

from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any

from alphakit.bridges.cost_model import IndiaCryptoTax
from mv.postmortem.trades import ClosedTrade

_ZERO = Decimal("0")
_PF_CAP = Decimal("999.99")  # profit factor when there are no losing trades


def _trade_return(trade: ClosedTrade) -> float:
    """Per-trade return = net PnL / entry notional (scale-free, for Sharpe/Sortino)."""
    notional = trade.entry_fill_price * trade.qty
    if notional <= _ZERO:
        return 0.0
    return float(trade.net_pnl() / notional)


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    sd = statistics.pstdev(returns)
    return statistics.fmean(returns) / sd if sd > 0 else 0.0


def _sortino(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    downside = [r for r in returns if r < 0]
    if not downside:
        return 0.0
    dd = statistics.pstdev(downside)
    return statistics.fmean(returns) / dd if dd > 0 else 0.0


def _max_drawdown(equity: list[Decimal]) -> Decimal:
    """Largest peak-to-trough decline on the equity curve, as a fraction."""
    peak = equity[0] if equity else _ZERO
    worst = _ZERO
    for value in equity:
        if value > peak:
            peak = value
        if peak > _ZERO:
            dd = (peak - value) / peak
            if dd > worst:
                worst = dd
    return worst


def performance_metrics(equity_curve: list[Decimal], trades: list[ClosedTrade]) -> dict[str, Any]:
    """Build the performance panel from the equity curve + closed round trips.

    Returns ``{}`` when there is nothing yet (cold loop), so the UI shows its empty
    state rather than a wall of zeros. With data, every key is present; trade
    stats are zeroed until the first round trip closes.
    """
    if not equity_curve and not trades:
        return {}

    pnls = [t.net_pnl() for t in trades]
    wins = [p for p in pnls if p > _ZERO]
    losses = [p for p in pnls if p < _ZERO]
    gross_profit = sum(wins, _ZERO)
    gross_loss = -sum(losses, _ZERO)  # positive magnitude
    n = len(pnls)

    if gross_loss > _ZERO:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = _PF_CAP if gross_profit > _ZERO else _ZERO

    returns = [_trade_return(t) for t in trades]
    start = equity_curve[0] if equity_curve else _ZERO
    last = equity_curve[-1] if equity_curve else _ZERO
    total_return = (last - start) / start if start > _ZERO else 0.0

    # India crypto tax on the realized round trips (Phase 14, FR-X2 honesty).
    # An APPROXIMATION, and labelled as one in the payload: per-trade rather
    # than per-assessment-year, and the refundable TDS excess is treated as not
    # yet reclaimed. Three modelling points that were wrong and now are not:
    #   - the taxable gain is GROSS of fees (s.115BBH allows only cost of
    #     acquisition; brokerage is not deductible), so netting fees first
    #     under-taxed every winner;
    #   - TDS attaches to the SALE leg, which for a short round trip is the
    #     ENTRY, not the exit;
    #   - TDS is withheld tax credited against the flat liability, not an
    #     additive expense (see IndiaCryptoTax.total).
    tax_model = IndiaCryptoTax()
    tax_drag = _ZERO
    for trade in trades:
        gross_gain = (
            Decimal(trade.direction) * (trade.exit_fill_price - trade.entry_fill_price) * trade.qty
        )
        sale_price = trade.exit_fill_price if trade.direction > 0 else trade.entry_fill_price
        tax_drag += tax_model.total(gain=gross_gain, transfer_notional=sale_price * trade.qty)

    return {
        "n_trades": str(n),
        "win_rate": str(round(len(wins) / n, 4)) if n else "0",
        "profit_factor": str(round(float(profit_factor), 2)),
        "expectancy": str(sum(pnls, _ZERO) / n) if n else "0",
        "avg_win": str(gross_profit / len(wins)) if wins else "0",
        "avg_loss": str(-gross_loss / len(losses)) if losses else "0",
        "largest_win": str(max(wins)) if wins else "0",
        "largest_loss": str(min(losses)) if losses else "0",
        "gross_profit": str(gross_profit),
        "gross_loss": str(gross_loss),
        "total_pnl": str(sum(pnls, _ZERO)),
        "tax_drag_approx": str(tax_drag),
        "after_tax_pnl_approx": str(sum(pnls, _ZERO) - tax_drag),
        "tax_basis": "IN crypto: 30% on gross gains (no loss offset) + 1% TDS on sales, credited",
        "sharpe": str(round(_sharpe(returns), 3)),
        "sortino": str(round(_sortino(returns), 3)),
        "max_drawdown": str(round(float(_max_drawdown(equity_curve)), 4)),
        "total_return": str(round(float(total_return), 4)),
    }


__all__ = ["performance_metrics"]
