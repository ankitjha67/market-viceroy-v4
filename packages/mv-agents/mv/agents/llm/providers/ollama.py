"""Ollama local-LLM adapter (PRD FR-A7) — offline, local-first.

Talks to a local Ollama server's ``/api/chat`` endpoint (Qwen/Llama, etc.).
Because the model runs locally there is no marginal dollar cost. The HTTP call
is offline-only (``# pragma: no cover``); the request-build and response-parse
are pure and unit-tested via an injectable ``transport``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests
from mv.agents.llm.client import LLMError, LLMRequest, LLMResponse

Transport = Callable[[dict[str, Any]], dict[str, Any]]

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaClient:
    """A local Ollama chat client. ``transport`` is injectable for testing."""

    provider = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5",
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport: Transport = transport if transport is not None else self._http_post

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one chat completion; raise :class:`LLMError` on failure."""
        payload = self._build_payload(request)
        start = time.monotonic()
        raw = self._transport(payload)
        latency_ms = (time.monotonic() - start) * 1000.0
        return self._parse(raw, latency_ms)

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

    def _parse(self, raw: dict[str, Any], latency_ms: float) -> LLMResponse:
        try:
            text = raw["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMError(f"ollama: malformed response: {exc}") from exc
        return LLMResponse(
            text=str(text),
            provider=self.provider,
            model=self.model,
            input_tokens=int(raw.get("prompt_eval_count", 0)),
            output_tokens=int(raw.get("eval_count", 0)),
            latency_ms=latency_ms,
            cost_usd=0.0,  # local model: no marginal dollar cost
        )

    def _http_post(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - network I/O, offline only
        try:
            resp = requests.post(f"{self._base_url}/api/chat", json=payload, timeout=self._timeout)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except requests.RequestException as exc:
            raise LLMError(f"ollama: request failed: {exc}") from exc
        return data
