"""Causal PnL decomposition (PRD FR-P1) — signal/timing/sizing/slippage/fees/regime.

Splits a closed trade's realized net PnL into six components that **sum to net
PnL exactly** (the §6 invariant; US-005). The split is a telescoping additive
scheme over the prices the trade actually saw:

- **signal**   — the idiosyncratic directional edge, from the decision-reference
  price to the intended exit, at the reference size, *above the regime drift*.
- **timing**   — the entry-delay effect: the move between the decision reference
  and the intended entry, not captured because we entered later.
- **sizing**   — the marginal PnL from trading the actual size vs the reference.
- **slippage** — the execution give-up vs intended prices on both legs.
- **fees**     — total fees (a negative component).
- **regime**   — the benchmark/regime-driven slice of the move *plus* any
  reconciliation residual, so the six sum to the independently-realized net PnL.

With exact inputs the first five already reconcile to net and ``regime`` is the
pure benchmark drift; with approximate reconstruction inputs ``regime`` absorbs
the (typically small) residual — honestly labelled, never silently padded.
Money is ``Decimal``.
"""

from __future__ import annotations

from decimal import Decimal

from mv.postmortem.attribution import TradeAttribution
from mv.postmortem.trades import ClosedTrade


def decompose(trade: ClosedTrade) -> TradeAttribution:
    """Decompose ``trade``'s net PnL into the six causal components (sum to net)."""
    d = Decimal(trade.direction)
    q = trade.qty
    q0 = trade.target_qty
    p_dec = trade.decision_ref_price
    p_ent_int = trade.entry_intended_price
    p_ent = trade.entry_fill_price
    p_ext_int = trade.exit_intended_price
    p_ext = trade.exit_fill_price

    net = trade.net_pnl()

    # Directional edge from the decision reference to the intended exit, at the
    # reference size; the regime benchmark carves the market-driven slice out of
    # it so `signal` is the idiosyncratic alpha above the regime.
    regime_benchmark = d * trade.regime_drift * q0
    signal = d * (p_ext_int - p_dec) * q0 - regime_benchmark

    # Entry-delay: the move from the decision reference to the intended entry.
    timing = d * (p_dec - p_ent_int) * q0

    # Trading the actual size vs the reference size (at intended prices).
    sizing = d * (p_ext_int - p_ent_int) * (q - q0)

    # Execution give-up vs intended, on both legs, at the actual size.
    entry_slip = p_ent - p_ent_int
    exit_slip = p_ext - p_ext_int
    slippage = d * (exit_slip - entry_slip) * q

    fees = -trade.fees

    # Regime absorbs the benchmark slice plus any reconciliation residual so the
    # six components sum to the realized net PnL exactly.
    modeled = signal + timing + sizing + slippage + fees + regime_benchmark
    regime = regime_benchmark + (net - modeled)

    return TradeAttribution(
        trade_id=trade.trade_id,
        net_pnl=net,
        signal=signal,
        timing=timing,
        sizing=sizing,
        slippage=slippage,
        fees=fees,
        regime=regime,
    )


def components_sum(attr: TradeAttribution) -> Decimal:
    """Sum the six components; equals ``net_pnl`` by construction (a guard)."""
    parts = (attr.signal, attr.timing, attr.sizing, attr.slippage, attr.fees, attr.regime)
    total = Decimal("0")
    for part in parts:
        total += part if part is not None else Decimal("0")
    return total


__all__ = ["components_sum", "decompose"]
