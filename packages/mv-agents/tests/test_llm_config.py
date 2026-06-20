"""Unit tests for building an LLMRouter from config (FR-A7)."""

from __future__ import annotations

import pytest
from mv.agents.llm.config import router_from_config
from mv.agents.llm.providers import AnthropicClient, OllamaClient


def test_empty_config_is_deterministic() -> None:
    router = router_from_config(None)
    assert router.client_for("technical_analyst") is None
    assert router_from_config({}).client_for("x") is None


def test_per_agent_and_default_routing() -> None:
    router = router_from_config(
        {
            "research_manager": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            "default": {"provider": "ollama", "model": "qwen2.5"},
        }
    )
    rm = router.client_for("research_manager")
    assert isinstance(rm, AnthropicClient)
    assert rm.model == "claude-sonnet-4-6"
    # An unlisted agent gets the default client.
    other = router.client_for("technical_analyst")
    assert isinstance(other, OllamaClient)


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown LLM provider"):
        router_from_config({"x": {"provider": "gpt5"}})
