"""The MVP paper loop — wires the whole pipeline into a NautilusTrader node.

On each bar: governor close -> rolling window -> all strategies -> equal-weight
ensemble -> risk gate -> (if approved) a paper market order on the simulated
venue -> every step journaled (hash-chained). This is the US-001 loop; the same
``EnsembleStrategy`` runs live (only the venue/data clients swap).

NautilusTrader is untyped (Cython/Rust), so its objects are ``Any`` here.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import polars as pl
from alphakit.bridges.nautilus_bridge import bar_type_for, bars_from_frame, make_paper_engine
from mv.agents.baseline.runner import (
    GatedDecision,
    SignalStrategy,
    decide,
    strategy_signals,
)
from mv.agents.graph import build_agent_graph, run_decision
from mv.agents.roster.context import AgentContext
from mv.journal.journal import Journal
from mv.risk.engine import PortfolioState
from mv.risk.engine import RiskEngine as _RiskEngine
from mv.risk.live_guard import LiveGuardConfig, gate_live_order
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy


def _ns_to_dt(ts_ns: int) -> datetime:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc)


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


class EnsembleStrategy(Strategy):  # type: ignore[misc]  # nautilus_trader is untyped
    """Runs the ensemble + risk gate on each bar and submits paper orders."""

    def __init__(
        self,
        *,
        instrument: Any,
        bar_type: Any,
        strategies: list[SignalStrategy],
        risk_engine: _RiskEngine,
        journal: Journal,
        symbol: str,
        warmup: int,
        starting_equity: Decimal,
        hold_threshold: Decimal = Decimal("0.05"),
        live_guard: LiveGuardConfig | None = None,
        categories: Mapping[str, str] | None = None,
        regime_adaptive: bool = True,
        features: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__()
        self._instrument = instrument
        self._bar_type = bar_type
        self._strategies = strategies
        self._risk = risk_engine
        self._journal = journal
        self._symbol = symbol
        self._warmup = warmup
        self._equity = starting_equity
        self._hold_threshold = hold_threshold
        # None = pure paper (unchanged). A live config enforces BR-005 + the cap.
        self._live_guard = live_guard
        # Regime-adaptive ensemble weighting: when on (default) and categories are
        # known, the family weights track the detected market regime each bar.
        self._categories = categories if regime_adaptive else None
        # Point-in-time intel features for the agent path (Phase 14, FR-A2): the
        # serve loop refreshes these on a news cadence; an absent key means no
        # coverage and the matching analyst degrades to neutral honestly.
        self._features: Mapping[str, float] = dict(features or {})
        self._closes: list[float] = []
        self._times: list[datetime] = []
        # The live position as a SIGNED QUANTITY (long > 0, short < 0). Notional
        # is derived at the current mark, never accumulated: summing each leg's
        # own fill notional desynchronizes from the real position as soon as
        # price moves between legs (it can read flat while long, or short while
        # flat, which then suppresses exits and misreports exposure to risk).
        self._position_qty = Decimal("0")
        self._last_price = Decimal("0")
        self._last_ts = datetime.fromtimestamp(0, tz=timezone.utc)  # the latest bar's time

    @property
    def bars_seen(self) -> list[float]:
        """Every bar close this strategy actually processed (halt detection)."""
        return self._closes

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)

    def on_bar(self, bar: Any) -> None:
        close = bar.close.as_double()
        self._last_price = Decimal(str(close))
        ts = _ns_to_dt(bar.ts_event)
        self._last_ts = ts
        self._closes.append(close)
        self._times.append(ts)
        if len(self._closes) < self._warmup:
            return

        window = pd.DataFrame({self._symbol: self._closes}, index=pd.DatetimeIndex(self._times))
        snapshot_id = f"{self._symbol}:{ts.isoformat()}"
        # Exposure is the position marked at the CURRENT price, not the sum of
        # historical fill notionals (see _position_qty).
        position_notional = self._position_qty * self._last_price
        state = PortfolioState(
            equity=self._equity,
            peak_equity=self._equity,
            day_start_equity=self._equity,
            gross_exposure=position_notional.copy_abs(),
            net_exposure=position_notional,
            positions={self._symbol: position_notional},
        )
        gated = self._decide(window, ts, snapshot_id, state)
        self._record(gated)

        if gated.execute and gated.side is not None:
            desired = 1 if gated.side == "BUY" else -1
            if desired != _sign(self._position_qty):
                notional = gated.notional
                if self._live_guard is not None:
                    decision = gate_live_order(
                        self._live_guard,
                        key=self._symbol,
                        notional=notional,
                        equity=self._equity,
                    )
                    if not decision.allowed:
                        # BR-005: ungraduated -> no live order, journaled.
                        self._journal.append(
                            "live_blocked", {"symbol": self._symbol, "reason": decision.reason}
                        )
                        return
                    notional = decision.notional.copy_abs()
                self._submit(gated.side, notional)

    def _decide(
        self, window: pd.DataFrame, ts: datetime, snapshot_id: str, state: PortfolioState
    ) -> GatedDecision:
        """Produce the gated decision. The baseline ensembles all strategies,
        regime-weighting the families when ``categories`` are known."""
        return decide(
            self._strategies,
            window,
            symbol=self._symbol,
            ts=ts,
            snapshot_id=snapshot_id,
            equity=self._equity,
            risk_engine=self._risk,
            portfolio_state=state,
            hold_threshold=self._hold_threshold,
            categories=self._categories,
        )

    def _record(self, gated: GatedDecision) -> None:
        """Journal the regime + per-strategy signals + decision + risk (glass box)."""
        if gated.regime is not None:
            self._journal.append(
                "regime",
                {
                    "snapshot_id": gated.decision.snapshot_id,
                    "instrument": self._symbol,
                    "label": gated.regime.label,
                    "trend_score": f"{gated.regime.trend_score:.4f}",
                    "trend_weight": f"{gated.regime.trend_weight:.4f}",
                    "meanrev_weight": f"{gated.regime.meanrev_weight:.4f}",
                },
            )
        if gated.signals:
            self._journal.append(
                "signals",
                {
                    "snapshot_id": gated.decision.snapshot_id,
                    "instrument": self._symbol,
                    "action": gated.decision.action,
                    "signals": [
                        {"strategy": s.strategy, "weight": str(s.weight)} for s in gated.signals
                    ],
                },
            )
        self._journal.append("decision", gated.decision.model_dump(mode="json"))
        self._journal.append("risk_assessment", gated.risk.model_dump(mode="json"))

    def _submit(self, side: str, notional: Decimal) -> None:
        if self._last_price <= 0:
            return
        qty = self._instrument.make_qty(float(notional / self._last_price))
        order = self.order_factory.market(
            instrument_id=self._instrument.id,
            order_side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
            quantity=qty,
        )
        self.submit_order(order)

    def on_order_filled(self, event: Any) -> None:
        fill_price = Decimal(str(event.last_px.as_double()))
        qty = Decimal(str(event.last_qty.as_double()))
        is_buy = event.order_side == OrderSide.BUY
        self._position_qty += qty if is_buy else -qty
        # This leg's signed traded notional (a cash flow, not the position).
        leg_notional = qty * fill_price if is_buy else -(qty * fill_price)
        # Enrich the fill with the references attribution needs (Phase 5, FR-P1):
        # the intended/decision-reference price (the bar close the decision saw),
        # the realized fees, and the execution slippage vs intended.
        intended = self._last_price
        commission = getattr(event, "commission", None)
        fees = (
            Decimal(str(commission.as_double()))
            if commission is not None and hasattr(commission, "as_double")
            else Decimal("0")
        )
        slippage_bps = float((fill_price - intended) / intended * 10000) if intended > 0 else 0.0
        self._journal.append(
            "execution",
            {
                "symbol": self._symbol,
                "side": "BUY" if is_buy else "SELL",
                "price": str(fill_price),
                "qty": str(qty),
                "notional": str(leg_notional),
                "intended_price": str(intended),
                "decision_ref_price": str(intended),
                "fees": str(fees),
                "slippage_bps": slippage_bps,
                "bar_ts": self._last_ts.isoformat(),  # the bar the fill landed on (chart marker)
            },
        )


class AgentGraphStrategy(EnsembleStrategy):
    """Phase-4 loop path: the LangGraph agent pipeline replaces the ensemble.

    Same NautilusTrader plumbing as :class:`EnsembleStrategy` (window, sizing,
    submit, fills); only the decision changes — each bar runs the agent graph
    (Research → Analyst → Bull/Bear debate → Research Manager → Risk veto → PM),
    which journals the **full transcript** (analyst views, debate, verdict, risk,
    decision) itself. The Technical analyst consumes the same strategy ensemble,
    so this is continuous with the baseline while adding the debated, glass-box
    pipeline. The risk engine remains the inviolable gate.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._graph = build_agent_graph(journal=self._journal, risk_engine=self._risk)

    def _decide(
        self, window: pd.DataFrame, ts: datetime, snapshot_id: str, state: PortfolioState
    ) -> GatedDecision:
        signals = strategy_signals(self._strategies, window, self._symbol)
        ctx = AgentContext(
            instrument=self._symbol,
            ts=ts,
            snapshot_id=snapshot_id,
            features=self._features,
            signals=signals,
        )
        return run_decision(self._graph, ctx, portfolio_state=state, equity=self._equity)

    def _record(self, gated: GatedDecision) -> None:
        # The graph nodes already journaled the full transcript (analyst views,
        # debate turns, verdict, risk assessment, decision) — no double-journal.
        return None


def run_paper_session(
    *,
    frame: pl.DataFrame,
    symbol: str,
    timeframe: str,
    strategies: list[SignalStrategy],
    risk_engine: _RiskEngine,
    journal: Journal,
    instrument: Any,
    warmup: int = 30,
    starting_equity: Decimal = Decimal("1000000"),
    hold_threshold: Decimal = Decimal("0.05"),
    use_agents: bool = False,
    live_guard: LiveGuardConfig | None = None,
    categories: Mapping[str, str] | None = None,
    regime_adaptive: bool = True,
    features: Mapping[str, float] | None = None,
) -> Any:
    """Run one paper session over ``frame`` and return the engine (for inspection).

    ``use_agents`` selects the decision path: the Phase-1 deterministic ensemble
    (default) or the Phase-4 LangGraph agent pipeline. Both run the same
    strategies, sizing, and inviolable risk gate; the agent path adds the
    journaled debate transcript. ``live_guard`` (Phase 7) is ``None`` for pure
    paper; a live config enforces BR-005 (only graduated strategies trade) + the
    capital cap. The order path is identical paper↔live (FR-X1); only the venue
    clients differ for real go-live (the Operator's funded action).
    """
    engine = make_paper_engine(venue=instrument.id.venue.value)
    engine.add_instrument(instrument)
    bar_type = bar_type_for(instrument.id, timeframe)
    strategy_cls = AgentGraphStrategy if use_agents else EnsembleStrategy
    strategy = strategy_cls(
        instrument=instrument,
        bar_type=bar_type,
        strategies=strategies,
        risk_engine=risk_engine,
        journal=journal,
        symbol=symbol,
        warmup=warmup,
        starting_equity=starting_equity,
        hold_threshold=hold_threshold,
        live_guard=live_guard,
        categories=categories,
        regime_adaptive=regime_adaptive,
        features=features,
    )
    bars = bars_from_frame(frame, bar_type, instrument)
    engine.add_data(bars)
    engine.add_strategy(strategy)
    engine.run()
    # A venue-side failure (e.g. an account-balance breach) stops the engine
    # mid-window, and NautilusTrader's logging is bypassed, so the run would
    # otherwise end early in total silence and look like a quiet market. Compare
    # bars fed against bars actually processed and journal the shortfall.
    fed = len(bars)
    seen = len(strategy.bars_seen)
    if fed and seen < fed:
        journal.append(
            "session_halted",
            {
                "symbol": symbol,
                "bars_fed": fed,
                "bars_processed": seen,
                "reason": "engine stopped before the end of the window",
            },
        )
    return engine
