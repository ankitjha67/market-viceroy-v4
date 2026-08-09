"""Intel features must be applied AS-OF, never to bars that predate them.

Regression for a look-ahead introduced when the Phase-14 sources were wired to
the agents: the serve loop replays a whole growing window each tick, so passing
one CURRENT reading into the session let every historical bar's re-decision see
today's sentiment. Point-in-time is a non-negotiable rail, so a reading applies
only to bars at or after the moment it was observed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import polars as pl
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
from mv.api.paper_loop import run_paper_session
from mv.failover.normalize import normalize_ohlcv
from mv.journal.journal import Journal
from mv.risk.engine import RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits
from nautilus_trader.test_kit.providers import TestInstrumentProvider

_BASE_MS = 1_704_067_200_000
_HOUR_MS = 3_600_000
_BASE_TS = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _frame(n: int) -> pl.DataFrame:
    rows = []
    price = 40_000.0
    for i in range(n):
        price *= 1.005
        rows.append([_BASE_MS + i * _HOUR_MS, price, price * 1.002, price * 0.998, price, 50.0])
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def _run(features: dict[str, float], as_of: datetime | None) -> list[dict[str, object]]:
    journal = Journal()
    engine = run_paper_session(
        frame=_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=[EMACross1226(long_only=True)],
        risk_engine=RiskEngine(RiskLimits.aggressive(), KillSwitch()),
        journal=journal,
        instrument=TestInstrumentProvider.btcusdt_binance(),
        warmup=30,
        starting_equity=Decimal("5000"),
        use_agents=True,
        features=features,
        features_as_of=as_of,
    )
    try:
        return [
            e.payload
            for e in journal.entries()
            if e.kind == "analyst_view" and e.payload.get("agent") == "sentiment_analyst"
        ]
    finally:
        engine.dispose()


def test_a_reading_never_reaches_bars_that_predate_it() -> None:
    # The reading is observed at bar 45; bars 30-44 must not see it.
    as_of = _BASE_TS + timedelta(hours=45)
    views = _run({"sentiment": 0.9}, as_of)
    assert views, "the agent path must journal sentiment views"
    early = [v for v in views if datetime.fromisoformat(str(v["ts"])) < as_of]
    late = [v for v in views if datetime.fromisoformat(str(v["ts"])) >= as_of]
    assert early and late, "the window must straddle the observation time"
    assert all(v["stance"] == "neutral" for v in early), "look-ahead: a future reading leaked"
    assert all(v["stance"] == "bullish" for v in late), "the reading must apply once knowable"


def test_without_a_stamp_the_reading_applies_throughout() -> None:
    # A caller with no as-of (a one-shot session over recorded bars) keeps the
    # previous behavior: the features describe the whole frame.
    views = _run({"sentiment": 0.9}, None)
    assert views and all(v["stance"] == "bullish" for v in views)


def test_regime_is_derived_causally_per_bar_not_supplied() -> None:
    # A caller-supplied 'regime' must be ignored: the session recomputes it from
    # the closes it has actually seen, so it can never carry future information.
    journal = Journal()
    engine = run_paper_session(
        frame=_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=[EMACross1226(long_only=True)],
        risk_engine=RiskEngine(RiskLimits.aggressive(), KillSwitch()),
        journal=journal,
        instrument=TestInstrumentProvider.btcusdt_binance(),
        warmup=30,
        starting_equity=Decimal("5000"),
        use_agents=True,
        features={"regime": -1.0},  # a bearish regime that contradicts the uptrend
        features_as_of=None,
    )
    try:
        macro = [
            e.payload
            for e in journal.entries()
            if e.kind == "analyst_view" and e.payload.get("agent") == "macro_analyst"
        ]
        # The frame rises monotonically, so the causal regime is bullish despite
        # the bearish value the caller passed in.
        assert macro and all(v["stance"] == "bullish" for v in macro)
    finally:
        engine.dispose()
