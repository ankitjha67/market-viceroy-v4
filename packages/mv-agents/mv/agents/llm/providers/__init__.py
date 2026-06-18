"""Offline LLM provider adapters: local Ollama and cloud Anthropic."""

from __future__ import annotations

from mv.agents.llm.providers.anthropic import AnthropicClient
from mv.agents.llm.providers.ollama import OllamaClient

__all__ = ["AnthropicClient", "OllamaClient"]
