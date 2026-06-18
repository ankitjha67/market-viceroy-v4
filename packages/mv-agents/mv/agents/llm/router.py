"""Per-agent LLM routing (PRD FR-A7) — hybrid, configurable, deterministic-default.

Maps an agent id to the :class:`~mv.agents.llm.client.LLMClient` it should use
(e.g. a local Ollama model for cheap analysts, a cloud model for the Research
Manager's harder synthesis). An unrouted agent returns ``None`` -> the caller
runs the deterministic reasoner. The default route (``None`` unless set) keeps
the whole graph deterministic in CI with no configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from mv.agents.llm.client import LLMClient


@dataclass(frozen=True)
class LLMRouter:
    """Resolve an agent id to its LLM client (or ``None`` for deterministic)."""

    routes: Mapping[str, LLMClient] = field(default_factory=dict)
    """Per-agent overrides, keyed by ``AgentEnvelope.agent`` id."""

    default: LLMClient | None = None
    """The fallback client for agents not in ``routes`` (``None`` = deterministic)."""

    def client_for(self, agent: str) -> LLMClient | None:
        """The client routed for ``agent``, or ``None`` if deterministic."""
        return self.routes.get(agent, self.default)


def deterministic_router() -> LLMRouter:
    """A router that routes nothing — every agent reasons deterministically."""
    return LLMRouter()
