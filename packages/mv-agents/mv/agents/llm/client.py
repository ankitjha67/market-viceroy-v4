"""The LLM seam (PRD FR-A7/A9) — provider-agnostic client + the FR-A9 fallback.

Phase 4 is **deterministic-first**: every agent reasons from point-in-time
features with no network call by default. This module is the *optional*
enhancement seam — a typed :class:`LLMClient` protocol, a standardized
request/response (carrying provider/model/tokens/latency/cost for the journaled
``llm_meta``), and the non-negotiable FR-A9 rule in :func:`reason_or_fallback`:
an LLM is consulted only when one is routed for the agent, and **any** failure
(transport error, timeout, unparseable output) falls back to the deterministic
reasoner. An LLM is never on the path of a risk check.

The adapters' network I/O is offline-only and ``# pragma: no cover``; the
request-build, response-parse, cost/latency accounting, routing, and fallback
logic are all unit-tested (via injectable transports / fakes).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable


class LLMError(Exception):
    """Any LLM-call failure: transport, timeout, or unparseable output."""


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """A provider-agnostic completion request for one agent/task."""

    agent: str
    """The routing key — which agent is asking (e.g. ``"technical_analyst"``)."""

    task: str
    """The task label (e.g. ``"analyst_view"``), recorded for routing/telemetry."""

    prompt: str
    """The user prompt (the rendered evidence the agent reasons over)."""

    system: str = ""
    """Optional system instruction."""

    max_tokens: int = 1024
    """Output token cap."""

    temperature: float = 0.0
    """Sampling temperature; 0.0 keeps offline reasoning as stable as possible."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """A normalized completion result; ``to_llm_meta`` feeds the journaled record."""

    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float

    def to_llm_meta(self) -> dict[str, object]:
        """The ``AgentEnvelope.llm_meta`` payload (provider/tokens/latency/cost)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": round(self.latency_ms, 3),
            "cost_usd": round(self.cost_usd, 8),
        }


@runtime_checkable
class LLMClient(Protocol):
    """The minimal contract every provider adapter satisfies."""

    provider: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion; raise :class:`LLMError` on any failure."""
        ...


T = TypeVar("T")


@dataclass(frozen=True)
class ReasonResult(Generic[T]):
    """The outcome of :func:`reason_or_fallback` — the record plus provenance."""

    record: T
    """The produced record (LLM-parsed or deterministic-fallback)."""

    used_llm: bool
    """True only if an LLM produced ``record`` (False on no-route or fallback)."""

    llm_meta: dict[str, object] | None
    """Provider/tokens/latency/cost when the LLM was used; a fell-back note on
    failure; ``None`` when no LLM was routed."""


def reason_or_fallback(
    client: LLMClient | None,
    request: LLMRequest,
    *,
    parse: Callable[[LLMResponse], T],
    fallback: Callable[[], T],
) -> ReasonResult[T]:
    """Try the routed LLM, else fall back to the deterministic reasoner (FR-A9).

    No client routed -> the deterministic ``fallback`` runs, no network touched.
    A client routed -> it is called and its text parsed into a typed record; on
    **any** ``LLMError`` or ``ValueError`` (transport/timeout/parse), the
    deterministic ``fallback`` runs and the failure is recorded in ``llm_meta``.
    The risk check is downstream and never depends on this call succeeding.
    """
    if client is None:
        return ReasonResult(record=fallback(), used_llm=False, llm_meta=None)
    try:
        response = client.complete(request)
        record = parse(response)
    except (LLMError, ValueError) as exc:
        meta: dict[str, object] = {
            "provider": client.provider,
            "model": client.model,
            "error": str(exc),
            "fell_back": True,
        }
        return ReasonResult(record=fallback(), used_llm=False, llm_meta=meta)
    return ReasonResult(record=record, used_llm=True, llm_meta=response.to_llm_meta())
