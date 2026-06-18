"""Anthropic cloud-LLM adapter (PRD FR-A7) — offline, cost/latency accounted.

Talks to the Anthropic Messages API for the harder reasoning an Operator may
route to a cloud model. The API key is read from the ``ANTHROPIC_API_KEY``
environment variable at call time (never hardcoded; vault-supplied per
CLAUDE.md #6). Per-call token cost is computed from a published price table so
the journaled ``llm_meta`` carries real dollars. The HTTP call is offline-only
(``# pragma: no cover``); request-build, response-parse, and cost accounting are
pure and unit-tested via an injectable ``transport``.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import requests
from mv.agents.llm.client import LLMError, LLMRequest, LLMResponse

Transport = Callable[[dict[str, Any]], dict[str, Any]]

_DEFAULT_BASE_URL = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"

# USD per 1M tokens (input, output). Used only to stamp llm_meta; not a billing
# source of truth. Unknown models fall back to a mid-tier estimate.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
_DEFAULT_PRICE: tuple[float, float] = (3.0, 15.0)


class AnthropicClient:
    """An Anthropic Messages client. ``transport`` is injectable for testing."""

    provider = "anthropic"

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        *,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key  # if None, read from env at call time
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport: Transport = transport if transport is not None else self._http_post

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one message completion; raise :class:`LLMError` on failure."""
        payload = self._build_payload(request)
        start = time.monotonic()
        raw = self._transport(payload)
        latency_ms = (time.monotonic() - start) * 1000.0
        return self._parse(raw, latency_ms)

    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system:
            body["system"] = request.system
        return body

    def _cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        price_in, price_out = _PRICE_PER_MTOK.get(self.model, _DEFAULT_PRICE)
        return input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out

    def _parse(self, raw: dict[str, Any], latency_ms: float) -> LLMResponse:
        try:
            blocks = raw["content"]
            text = "".join(
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            usage = raw["usage"]
            input_tokens = int(usage["input_tokens"])
            output_tokens = int(usage["output_tokens"])
        except (KeyError, TypeError) as exc:
            raise LLMError(f"anthropic: malformed response: {exc}") from exc
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=self._cost_usd(input_tokens, output_tokens),
        )

    def _http_post(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:  # pragma: no cover - network I/O, offline only
        key = self._api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("anthropic: ANTHROPIC_API_KEY not set")
        headers = {
            "x-api-key": key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            resp = requests.post(
                f"{self._base_url}/v1/messages",
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except requests.RequestException as exc:
            raise LLMError(f"anthropic: request failed: {exc}") from exc
        return data
