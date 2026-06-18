"""The LLM seam: provider-agnostic client, per-agent router, offline adapters.

Deterministic-first (FR-A7/A9): agents reason without any LLM unless one is
routed; :func:`~mv.agents.llm.client.reason_or_fallback` falls back to the
deterministic reasoner on any failure. See :mod:`.client` and :mod:`.router`.
"""

from __future__ import annotations

from mv.agents.llm.client import (
    LLMClient,
    LLMError,
    LLMRequest,
    LLMResponse,
    ReasonResult,
    reason_or_fallback,
)
from mv.agents.llm.router import LLMRouter, deterministic_router

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "ReasonResult",
    "deterministic_router",
    "reason_or_fallback",
]
