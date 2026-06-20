"""Real-time broadcast hub for the Command Deck WebSocket (PRD §7 /ws/stream).

A tiny in-process pub/sub: the loop publishes events (ticks, decisions, fills,
source-health) and every connected WebSocket receives them. No external broker —
single-operator self-host. The UI polls as a fallback when the socket drops, so
the stream is an optimization, never the only path to the data.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BroadcastHub:
    """Fan-out of JSON-able events to all subscribed queues."""

    _subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a new subscriber queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Drop a subscriber (on disconnect)."""
        self._subscribers.discard(queue)

    def publish(self, kind: str, payload: dict[str, Any]) -> None:
        """Fan ``{kind, payload}`` out to every subscriber (drops on a full queue).

        ``asyncio.Queue`` is not thread-safe: call this on the API event-loop
        thread. A producer running on another thread (e.g. the NautilusTrader
        loop) must marshal across with
        ``loop.call_soon_threadsafe(hub.publish, kind, payload)``.
        """
        event = {"kind": kind, "payload": payload}
        for queue in list(self._subscribers):
            # A slow consumer must not block (or crash) the loop — drop on full.
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
