"""Redis-backed kill-switch state — shared between the loop and the API/CLI.

So a ``mv-kill`` from the operator halts the running loop: both read/write the
same Redis flag. DB I/O (``# pragma: no cover``); the in-memory state in
``mv.risk.kill_switch`` carries the unit coverage.
"""

from __future__ import annotations

from typing import Any

_KILL_KEY = "risk:kill_switch:tripped"


class RedisKillSwitchState:
    """Implements ``KillSwitchState`` over a Redis flag."""

    def __init__(self, redis_client: Any, *, key: str = _KILL_KEY) -> None:
        self._redis = redis_client
        self._key = key

    def is_tripped(self) -> bool:  # pragma: no cover - Redis I/O
        return bool(self._redis.get(self._key) == "1")

    def set_tripped(self, tripped: bool) -> None:  # pragma: no cover - Redis I/O
        self._redis.set(self._key, "1" if tripped else "0")
