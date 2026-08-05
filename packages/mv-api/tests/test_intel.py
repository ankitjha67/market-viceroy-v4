"""Tests for the market-intel wire: features, payload, endpoint, Prometheus."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.api.intel import features_for, intel_payload, signed_efficiency
from mv.api.prom import prometheus_text
from mv.failover.adapters.funding_feed import FundingRate
from mv.intelligence.sources.fear_greed import FearGreed
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch

_FG = FearGreed(ts=datetime(2026, 8, 5, tzinfo=timezone.utc), value=80, label="Extreme Greed")
_FUNDING = {"BTC/USDT": FundingRate(symbol="BTC/USDT", rate=0.0005, open_interest=90000.0)}


def test_signed_efficiency_direction_and_coverage() -> None:
    up = [float(i) for i in range(40)]  # perfectly efficient up-move
    assert signed_efficiency(up) == 1.0
    down = [float(40 - i) for i in range(40)]
    assert signed_efficiency(down) == -1.0
    assert signed_efficiency([1.0, 2.0]) is None  # not enough history = no coverage


def test_features_for_maps_analyst_names_and_omits_uncovered() -> None:
    features = features_for(
        "BTC/USDT",
        news_sentiment={"BTC/USDT": 0.4},
        fear_greed=_FG,
        funding=_FUNDING,
        social={"CryptoCurrency": 0.2},
        regime_direction=0.7,
    )
    assert features["news_sentiment"] == 0.4
    assert features["flow"] == 1.0  # 5 bps per interval saturates the crowd score
    assert features["regime"] == 0.7
    assert abs(features["sentiment"] - 0.4) < 1e-9  # mean of F&G 0.6 and social 0.2
    # An uncovered symbol yields ABSENT keys, never fabricated neutrals.
    bare = features_for(
        "ETH/USDT",
        news_sentiment={},
        fear_greed=None,
        funding={},
        social={},
        regime_direction=None,
    )
    assert bare == {}


def test_intel_endpoint_serves_payload() -> None:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token="operator-secret",
        intel_provider=lambda: intel_payload(fear_greed=_FG, funding=_FUNDING, social={"a": 0.1}),
    )
    client = TestClient(create_app(state))
    body = client.get("/api/v1/intel").json()
    assert body["fear_greed"] == {"value": 80, "label": "Extreme Greed", "score": 0.6}
    assert body["funding"]["BTC/USDT"]["rate"] == 0.0005
    assert body["social"] == {"a": 0.1}


def test_prometheus_endpoint_and_renderer() -> None:
    state = ApiState(
        kill_switch=KillSwitch(),
        journal=Journal(),
        operator_token="operator-secret",
        portfolio_provider=lambda: {"equity": "5123.45", "day_pnl": "23.45", "drawdown": "0.01"},
        positions_provider=lambda: [{"symbol": "BTC/USDT"}],
        source_health_provider=lambda: [
            {"source": "ccxt:binance", "latency_p50_ms": 42, "latency_p95_ms": 90}
        ],
    )
    client = TestClient(create_app(state))
    text = client.get("/metrics").text
    assert "mv_up 1" in text
    assert "mv_equity_inr 5123.45" in text
    assert "mv_open_positions 1" in text
    assert "mv_kill_switch_tripped 0" in text
    assert 'mv_source_latency_p50_ms{source="ccxt:binance"} 42' in text


def test_prometheus_omits_unknowns_never_zero() -> None:
    text = prometheus_text(
        portfolio={"equity": "not-a-number"}, positions_count=0, kill_tripped=True, sources=[]
    )
    assert "mv_equity_inr" not in text  # unknown stays absent
    assert "mv_kill_switch_tripped 1" in text
