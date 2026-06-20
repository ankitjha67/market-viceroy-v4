"""Tests for the real-time broadcast hub + the /ws/stream WebSocket (Phase 9)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from mv.api.app import ApiState, create_app
from mv.api.ws import BroadcastHub
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch


def test_hub_fans_out_to_subscribers() -> None:
    hub = BroadcastHub()
    a = hub.subscribe()
    b = hub.subscribe()
    hub.publish("decision", {"action": "BUY"})
    assert a.get_nowait() == {"kind": "decision", "payload": {"action": "BUY"}}
    assert b.get_nowait()["kind"] == "decision"
    hub.unsubscribe(a)
    assert hub.subscriber_count == 1


def test_hub_drops_on_full_queue_without_raising() -> None:
    hub = BroadcastHub()
    q = hub.subscribe()
    # Fill past capacity; a slow consumer must not block (or crash) the loop.
    for _ in range(300):
        hub.publish("tick", {"n": 1})
    assert q.full()
    assert q.maxsize == 256


def test_websocket_rejects_without_token() -> None:
    from starlette.websockets import WebSocketDisconnect as WSDisconnect

    hub = BroadcastHub()
    state = ApiState(kill_switch=KillSwitch(), journal=Journal(), operator_token="t", hub=hub)
    client = TestClient(create_app(state))
    # No / wrong token -> the server closes the socket before accepting (1008).
    with pytest.raises(WSDisconnect), client.websocket_connect("/ws/stream?token=wrong") as ws:
        ws.receive_json()
    assert hub.subscriber_count == 0


def test_websocket_stream_delivers_published_events() -> None:
    hub = BroadcastHub()
    state = ApiState(kill_switch=KillSwitch(), journal=Journal(), operator_token="t", hub=hub)
    client = TestClient(create_app(state))
    with client.websocket_connect("/ws/stream?token=t") as ws:
        # Wait for the server handler to subscribe, then publish.
        for _ in range(200):
            if hub.subscriber_count > 0:
                break
            time.sleep(0.01)
        hub.publish("decision", {"action": "SELL", "instrument": "ETH/USDT"})
        event = ws.receive_json()
        assert event == {
            "kind": "decision",
            "payload": {"action": "SELL", "instrument": "ETH/USDT"},
        }
    # The subscriber is dropped on disconnect.
    for _ in range(200):
        if hub.subscriber_count == 0:
            break
        time.sleep(0.01)
    assert hub.subscriber_count == 0
