"""Regressions for the smaller robustness-sweep findings."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.api.metrics import performance_metrics
from mv.api.prom import prometheus_text
from mv.journal.journal import Journal
from mv.postmortem.trades import Fill, reconstruct_closed_trades
from mv.risk.kill_switch import KillSwitch

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fill(side: str, qty: str, price: str) -> Fill:
    return Fill(
        instrument="BTC/USDT", side=side, qty=Decimal(qty), fill_price=Decimal(price), ts=_TS
    )


def test_prometheus_omits_non_finite_samples() -> None:
    # NaN/Inf are worse than a missing sample: they poison every rate and
    # average computed over the series.
    text = prometheus_text(
        portfolio={"equity": float("nan"), "day_pnl": float("inf"), "drawdown": "0.02"},
        positions_count=0,
        kill_tripped=False,
        sources=[],
    )
    assert "nan" not in text.lower()
    assert "inf" not in text.lower()
    assert "mv_drawdown_ratio 0.02" in text


def test_prometheus_keeps_each_metric_family_contiguous() -> None:
    # The text format requires all samples of a metric to sit together;
    # interleaving by source is rejected by promtool and strict scrapers.
    text = prometheus_text(
        portfolio={},
        positions_count=0,
        kill_tripped=False,
        sources=[
            {"source": "binance", "latency_p50_ms": 12, "latency_p95_ms": 40},
            {"source": "kraken", "latency_p50_ms": 9, "latency_p95_ms": 30},
        ],
    )
    lines = [ln for ln in text.splitlines() if ln.startswith("mv_source_latency_p50_ms")]
    body = text.splitlines()
    first = body.index(lines[0])
    assert body[first + 1].startswith("mv_source_latency_p50_ms"), "family must be contiguous"
    assert text.count("# TYPE mv_source_latency_p50_ms") == 1


def test_zero_quantity_fills_do_not_create_phantom_trades() -> None:
    # A zero-qty execution used to emit a ClosedTrade with qty 0 and PnL 0,
    # diluting win rate and expectancy and adding an empty blotter row.
    fills = [
        _fill("BUY", "0", "100"),  # not a trade
        _fill("BUY", "1", "100"),
        _fill("SELL", "1", "110"),  # the only real round trip: +10
    ]
    trades = reconstruct_closed_trades(fills)
    assert len(trades) == 1
    m = performance_metrics([Decimal("1000")], trades)
    assert m["n_trades"] == "1"
    assert m["win_rate"] == "1.0"
    assert m["expectancy"] == "10"


def test_sharpe_uses_the_sample_stdev() -> None:
    # Population stdev overstated Sharpe by sqrt(n/(n-1)): 2.0 vs 1.414 at n=2.
    trades = reconstruct_closed_trades(
        [
            _fill("BUY", "1", "100"),
            _fill("SELL", "1", "101"),  # +1%
            _fill("BUY", "1", "100"),
            _fill("SELL", "1", "103"),  # +3%
        ]
    )
    m = performance_metrics([Decimal("1000")], trades)
    assert abs(float(m["sharpe"]) - 1.414) < 0.01


def test_sortino_signals_no_losers_like_profit_factor_does() -> None:
    # Two tiles describing the same fact must not say opposite things: a 999.99
    # profit factor beside a 0.0 Sortino read as "no risk-adjusted return".
    trades = reconstruct_closed_trades(
        [
            _fill("BUY", "1", "100"),
            _fill("SELL", "1", "101"),
            _fill("BUY", "1", "100"),
            _fill("SELL", "1", "103"),
        ]
    )
    m = performance_metrics([Decimal("1000")], trades)
    assert m["profit_factor"] == "999.99"
    assert float(m["sortino"]) > 0


def test_portfolio_history_is_clamped() -> None:
    points = [{"ts": str(i), "equity": "1000"} for i in range(3000)]
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token="operator-secret",
        portfolio_history_provider=lambda: points,
    )
    client = TestClient(create_app(state))
    assert len(client.get("/api/v1/portfolio/history").json()) == 1000  # default
    assert len(client.get("/api/v1/portfolio/history?limit=50").json()) == 50
    assert client.get("/api/v1/portfolio/history?limit=99999").status_code == 422
    # The most recent points, not the oldest.
    assert client.get("/api/v1/portfolio/history?limit=1").json()[0]["ts"] == "2999"
