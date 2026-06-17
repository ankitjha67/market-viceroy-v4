"""The MVP paper loop — wires the whole pipeline into a NautilusTrader node.

On each bar: governor close -> rolling window -> all strategies -> equal-weight
ensemble -> risk gate -> (if approved) a paper market order on the simulated
venue -> every step journaled (hash-chained). This is the US-001 loop; the same
``EnsembleStrategy`` runs live (only the venue/data clients swap).

NautilusTrader is untyped (Cython/Rust), so its objects are ``Any`` here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import polars as pl
from alphakit.bridges.nautilus_bridge import bar_type_for, bars_from_frame, make_paper_engine
from mv.agents.baseline.runner import SignalStrategy, decide
from mv.journal.journal import Journal
from mv.risk.engine import PortfolioState
from mv.risk.engine import RiskEngine as _RiskEngine
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
        self._closes: list[float] = []
        self._times: list[datetime] = []
        self._position_notional = Decimal("0")
        self._last_price = Decimal("0")

    def on_start(self) -> None:
        self.subscribe_bars(self._bar_type)

    def on_bar(self, bar: Any) -> None:
        close = bar.close.as_double()
        self._last_price = Decimal(str(close))
        ts = _ns_to_dt(bar.ts_event)
        self._closes.append(close)
        self._times.append(ts)
        if len(self._closes) < self._warmup:
            return

        window = pd.DataFrame({self._symbol: self._closes}, index=pd.DatetimeIndex(self._times))
        snapshot_id = f"{self._symbol}:{ts.isoformat()}"
        state = PortfolioState(
            equity=self._equity,
            peak_equity=self._equity,
            day_start_equity=self._equity,
            gross_exposure=self._position_notional.copy_abs(),
            net_exposure=self._position_notional,
            positions={self._symbol: self._position_notional},
        )
        gated = decide(
            self._strategies,
            window,
            symbol=self._symbol,
            ts=ts,
            snapshot_id=snapshot_id,
            equity=self._equity,
            risk_engine=self._risk,
            portfolio_state=state,
            hold_threshold=self._hold_threshold,
        )
        self._journal.append("decision", gated.decision.model_dump(mode="json"))
        self._journal.append("risk_assessment", gated.risk.model_dump(mode="json"))

        if gated.execute and gated.side is not None:
            desired = 1 if gated.side == "BUY" else -1
            if desired != _sign(self._position_notional):
                self._submit(gated.side, gated.notional)

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
        signed = qty * fill_price
        if event.order_side != OrderSide.BUY:
            signed = -signed
        self._position_notional += signed
        self._journal.append(
            "execution",
            {
                "symbol": self._symbol,
                "side": "BUY" if event.order_side == OrderSide.BUY else "SELL",
                "price": str(fill_price),
                "qty": str(qty),
                "notional": str(signed),
            },
        )


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
) -> Any:
    """Run one paper session over ``frame`` and return the engine (for inspection)."""
    engine = make_paper_engine(venue=instrument.id.venue.value)
    engine.add_instrument(instrument)
    bar_type = bar_type_for(instrument.id, timeframe)
    strategy = EnsembleStrategy(
        instrument=instrument,
        bar_type=bar_type,
        strategies=strategies,
        risk_engine=risk_engine,
        journal=journal,
        symbol=symbol,
        warmup=warmup,
        starting_equity=starting_equity,
        hold_threshold=hold_threshold,
    )
    engine.add_data(bars_from_frame(frame, bar_type, instrument))
    engine.add_strategy(strategy)
    engine.run()
    return engine
