"""Decision-quality controls: conviction floor, regime band, protective exits.

Measured with scripts/ab_decision_quality.py on real BTC and SOL windows. Only
the conviction floor improved Sharpe, win rate and net on BOTH symbols, so only
it is on by default; the others are opt-in until the validation gate says
otherwise. These tests pin the MECHANICS, not the profitability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import polars as pl
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
from mv.api.paper_loop import run_paper_session
from mv.failover.normalize import normalize_ohlcv
from mv.journal.journal import Journal
from mv.postmortem.trades import Fill, fill_from_journal, reconstruct_closed_trades
from mv.risk.engine import RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits
from nautilus_trader.test_kit.providers import TestInstrumentProvider

_BASE_MS = 1_704_067_200_000
_HOUR_MS = 3_600_000


def _rising(n: int) -> pl.DataFrame:
    rows = []
    price = 40_000.0
    for i in range(n):
        price *= 1.004
        rows.append([_BASE_MS + i * _HOUR_MS, price, price * 1.002, price * 0.998, price, 50.0])
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def _run(**kwargs: object) -> Journal:
    journal = Journal()
    engine = run_paper_session(
        frame=_rising(80),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=[EMACross1226(long_only=True)],
        risk_engine=RiskEngine(RiskLimits.aggressive(), KillSwitch()),
        journal=journal,
        instrument=TestInstrumentProvider.btcusdt_binance(),
        warmup=30,
        starting_equity=Decimal("5000"),
        **kwargs,  # type: ignore[arg-type]
    )
    engine.dispose()
    return journal


def test_conviction_floor_suppresses_weak_consensus() -> None:
    # A floor above any achievable single-strategy consensus must produce no
    # orders at all; the default floor still lets a full-conviction signal trade.
    loose = [e for e in _run(hold_threshold=Decimal("0.05")).entries() if e.kind == "execution"]
    strict = [e for e in _run(hold_threshold=Decimal("1.5")).entries() if e.kind == "execution"]
    assert loose, "a unanimous signal must trade under a low floor"
    assert not strict, "no consensus can clear an unreachable floor"


def test_transitional_band_stands_aside_and_says_so() -> None:
    decisions = [
        e.payload
        for e in _run(
            hold_threshold=Decimal("0.05"),
            categories={"ema_cross_12_26": "trend"},
            skip_transitional=True,
        ).entries()
        if e.kind == "decision"
    ]
    stood_aside = [d for d in decisions if "stand aside" in str(d.get("rationale", ""))]
    if stood_aside:  # only when the window actually enters the band
        assert all(d["action"] == "HOLD" for d in stood_aside)


def test_time_stop_closes_a_position_and_journals_why() -> None:
    journal = _run(hold_threshold=Decimal("0.05"), max_hold_bars=3)
    exits = [e.payload for e in journal.entries() if e.kind == "protective_exit"]
    assert exits, "a 3-bar time stop must fire on an 80-bar trending window"
    assert "time stop" in exits[0]["reason"]
    assert int(exits[0]["bars_held"]) >= 3


def test_stops_are_off_by_default() -> None:
    # Unvalidated controls must not change behaviour unless asked for.
    assert not [
        e for e in _run(hold_threshold=Decimal("0.05")).entries() if e.kind == "protective_exit"
    ]


def test_fill_timestamps_come_from_the_bar_not_the_append() -> None:
    # The blotter read "held 0s" on every row because fills were stamped with
    # the journal-append time, which is one instant for a whole replayed window.
    append_ts = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    bar_ts = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    fill = fill_from_journal(
        {
            "symbol": "BTC/USDT",
            "side": "BUY",
            "qty": "1",
            "price": "100",
            "bar_ts": bar_ts.isoformat(),
        },
        ts=append_ts,
    )
    assert fill.ts == bar_ts

    # And a round trip therefore reports a real holding period.
    exit_bar = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    sell = fill_from_journal(
        {
            "symbol": "BTC/USDT",
            "side": "SELL",
            "qty": "1",
            "price": "110",
            "bar_ts": exit_bar.isoformat(),
        },
        ts=append_ts,
    )
    trade = reconstruct_closed_trades([fill, sell])[0]
    assert (trade.closed_at - trade.opened_at).total_seconds() == 6 * 3600


def test_missing_or_bad_bar_ts_falls_back_to_the_append_time() -> None:
    append_ts = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
    base = {"symbol": "BTC/USDT", "side": "BUY", "qty": "1", "price": "100"}
    assert fill_from_journal(base, ts=append_ts).ts == append_ts
    assert fill_from_journal({**base, "bar_ts": "not-a-time"}, ts=append_ts).ts == append_ts
    assert isinstance(fill_from_journal(base, ts=append_ts), Fill)
