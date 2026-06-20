"""Build an :class:`LLMRouter` from configuration (PRD FR-A7).

Turns a plain config mapping — agent id → ``{provider, model}`` — into a router
that points each agent at a real LLM client, with everything unconfigured
staying **deterministic** (the FR-A9 default). The providers are the offline
adapters; an empty/missing config yields a fully deterministic router, so this
is opt-in and CI stays deterministic without it. Keys are read from env inside
the adapters at call time — never from this config.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mv.agents.llm.client import LLMClient
from mv.agents.llm.providers.anthropic import AnthropicClient
from mv.agents.llm.providers.ollama import OllamaClient
from mv.agents.llm.router import LLMRouter


def _build_client(spec: Mapping[str, Any]) -> LLMClient:
    provider = str(spec.get("provider", "")).lower()
    model = spec.get("model")
    if provider == "ollama":
        return OllamaClient(model) if model else OllamaClient()
    if provider == "anthropic":
        return AnthropicClient(model) if model else AnthropicClient()
    raise ValueError(f"unknown LLM provider in config: {provider!r}")


def router_from_config(config: Mapping[str, Mapping[str, Any]] | None) -> LLMRouter:
    """Build a per-agent :class:`LLMRouter` from ``config`` (default: deterministic).

    ``config`` maps an agent id (or ``"default"``) to ``{provider, model}``.
    Unlisted agents reason deterministically. An empty/``None`` config returns a
    router that routes nothing.
    """
    if not config:
        return LLMRouter()
    routes: dict[str, LLMClient] = {}
    default: LLMClient | None = None
    for agent, spec in config.items():
        client = _build_client(spec)
        if agent == "default":
            default = client
        else:
            routes[agent] = client
    return LLMRouter(routes=routes, default=default)


__all__ = ["router_from_config"]
