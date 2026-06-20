"""NautilusTrader paper/live execution bridge (PRD FR-X1; CLAUDE.md backbone).

NautilusTrader is the execution spine: a strategy submits orders *inside* the
engine's event loop, and the SAME strategy code runs in the paper simulated
venue and live (only the data/exec clients swap) — this is the paper↔live
parity property. This module provides the paper-venue wiring the Step-7 loop
builds on:

- :func:`make_paper_engine` — a CASH paper venue with maker/taker fees applied
  in-venue (cost model v1; slippage + India crypto tax are applied at the
  journaling boundary, see :mod:`alphakit.bridges.cost_model`).
- :func:`bars_from_frame` — convert the governor's normalized Polars bars
  (``mv.failover.normalize.BARS_COLUMNS``) into NautilusTrader ``Bar`` objects.

NautilusTrader is an untyped (Cython/Rust) dependency, so engine/instrument
objects are typed ``Any`` here (as the other bridges treat their engines).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import polars as pl
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import MakerTakerFeeModel
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

NAME = "nautilus"

# Our bar timeframes -> NautilusTrader (step, aggregation).
_TIMEFRAME_TO_SPEC: dict[str, tuple[int, str]] = {
    "1m": (1, "MINUTE"),
    "3m": (3, "MINUTE"),
    "5m": (5, "MINUTE"),
    "15m": (15, "MINUTE"),
    "30m": (30, "MINUTE"),
    "1h": (1, "HOUR"),
    "2h": (2, "HOUR"),
    "4h": (4, "HOUR"),
    "6h": (6, "HOUR"),
    "12h": (12, "HOUR"),
    "1d": (1, "DAY"),
}


def make_paper_engine(
    *,
    venue: str = "BINANCE",
    starting_balance: Decimal = Decimal("1000000"),
    currency: Any = USDT,
) -> Any:
    """Build a CASH paper venue with in-venue maker/taker fees.

    A multi-currency CASH wallet (``base_currency=None``) so a crypto pair debits
    the quote currency and credits the base, with Decimal-precise balances.
    Logging is bypassed so multiple engines can run in one process (e.g. a test
    suite) without re-initializing NautilusTrader's global logging subsystem.
    """
    engine = BacktestEngine(config=BacktestEngineConfig(logging=LoggingConfig(bypass_logging=True)))
    engine.add_venue(
        venue=Venue(venue),
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=None,
        starting_balances=[Money(starting_balance, currency)],
        fee_model=MakerTakerFeeModel(),
    )
    return engine


def bar_type_for(instrument_id: Any, timeframe: str) -> Any:
    """Build a NautilusTrader ``BarType`` for ``instrument_id`` at ``timeframe``."""
    if timeframe not in _TIMEFRAME_TO_SPEC:
        raise ValueError(f"unsupported timeframe {timeframe!r}")
    step, aggregation = _TIMEFRAME_TO_SPEC[timeframe]
    return BarType.from_str(f"{instrument_id}-{step}-{aggregation}-LAST-EXTERNAL")


def bars_from_frame(frame: pl.DataFrame, bar_type: Any, instrument: Any) -> list[Any]:
    """Convert a normalized Polars bar frame into NautilusTrader ``Bar`` objects.

    The frame must have the canonical bars columns (``ts`` as a UTC datetime,
    plus open/high/low/close/volume), as produced by the Failover Governor.
    """
    bars: list[Any] = []
    for row in frame.sort("ts").iter_rows(named=True):
        ts = row["ts"]
        assert isinstance(ts, datetime)
        # A tz-naive timestamp would be read as host-local time by .timestamp();
        # normalize to UTC so bar times never shift by the machine's offset.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_ns = int(ts.timestamp() * 1_000_000_000)
        bars.append(
            Bar(
                bar_type=bar_type,
                open=instrument.make_price(row["open"]),
                high=instrument.make_price(row["high"]),
                low=instrument.make_price(row["low"]),
                close=instrument.make_price(row["close"]),
                volume=instrument.make_qty(row["volume"]),
                ts_event=ts_ns,
                ts_init=ts_ns,
            )
        )
    return bars
