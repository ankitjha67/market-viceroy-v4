"""Unit tests for the LLM seam: router, FR-A9 fallback, and offline adapters.

No network: the adapters' HTTP post is replaced by an injected ``transport``,
so the full ``complete`` path (request-build -> parse -> cost/latency) is
exercised deterministically.
"""

from __future__ import annotations

from typing import Any

import pytest
from mv.agents.llm import (
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMRouter,
    deterministic_router,
    reason_or_fallback,
)
from mv.agents.llm.providers import AnthropicClient, OllamaClient


def _req(agent: str = "technical_analyst") -> LLMRequest:
    return LLMRequest(agent=agent, task="analyst_view", prompt="evidence", system="be terse")


class _FakeClient:
    provider = "fake"
    model = "fake-1"

    def __init__(self, *, text: str = "ok", fail: bool = False) -> None:
        self._text = text
        self._fail = fail

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self._fail:
            raise LLMError("boom")
        return LLMResponse(
            text=self._text,
            provider=self.provider,
            model=self.model,
            input_tokens=10,
            output_tokens=5,
            latency_ms=1.0,
            cost_usd=0.0,
        )


# ---- router -------------------------------------------------------------------


def test_router_default_and_override() -> None:
    a, b = _FakeClient(), _FakeClient()
    router = LLMRouter(routes={"research_manager": a}, default=b)
    assert router.client_for("research_manager") is a
    assert router.client_for("technical_analyst") is b


def test_deterministic_router_routes_nothing() -> None:
    assert deterministic_router().client_for("anything") is None


# ---- reason_or_fallback (FR-A9) ----------------------------------------------


def test_fallback_when_no_client() -> None:
    out = reason_or_fallback(None, _req(), parse=lambda r: r.text, fallback=lambda: "deterministic")
    assert out.record == "deterministic"
    assert out.used_llm is False
    assert out.llm_meta is None


def test_uses_llm_when_routed_and_parses() -> None:
    out = reason_or_fallback(
        _FakeClient(text="LLM"),
        _req(),
        parse=lambda r: r.text,
        fallback=lambda: "deterministic",
    )
    assert out.record == "LLM"
    assert out.used_llm is True
    assert out.llm_meta is not None
    assert out.llm_meta["provider"] == "fake"


def test_fallback_on_llm_error() -> None:
    out = reason_or_fallback(
        _FakeClient(fail=True),
        _req(),
        parse=lambda r: r.text,
        fallback=lambda: "deterministic",
    )
    assert out.record == "deterministic"
    assert out.used_llm is False
    assert out.llm_meta is not None
    assert out.llm_meta["fell_back"] is True
    assert "boom" in str(out.llm_meta["error"])


def test_fallback_on_parse_error() -> None:
    def _bad_parse(_: LLMResponse) -> str:
        raise ValueError("unparseable")

    out = reason_or_fallback(
        _FakeClient(text="garbage"),
        _req(),
        parse=_bad_parse,
        fallback=lambda: "deterministic",
    )
    assert out.record == "deterministic"
    assert out.used_llm is False
    assert out.llm_meta is not None and out.llm_meta["fell_back"] is True


def test_to_llm_meta_shape() -> None:
    meta = LLMResponse(
        "t", "anthropic", "claude-sonnet-4-6", 100, 50, 12.3456, 0.00105
    ).to_llm_meta()
    assert meta == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "input_tokens": 100,
        "output_tokens": 50,
        "latency_ms": 12.346,
        "cost_usd": 0.00105,
    }


# ---- Ollama adapter -----------------------------------------------------------


def test_ollama_build_payload_includes_system_and_user() -> None:
    client = OllamaClient(model="qwen2.5")
    payload = client._build_payload(_req())
    assert payload["model"] == "qwen2.5"
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["system", "user"]
    assert payload["stream"] is False


def test_ollama_complete_with_fake_transport() -> None:
    def transport(_: dict[str, Any]) -> dict[str, Any]:
        return {"message": {"content": "neutral"}, "prompt_eval_count": 10, "eval_count": 4}

    client = OllamaClient(transport=transport)
    resp = client.complete(_req())
    assert resp.text == "neutral"
    assert resp.provider == "ollama"
    assert resp.input_tokens == 10
    assert resp.output_tokens == 4
    assert resp.cost_usd == 0.0  # local model
    assert resp.latency_ms >= 0.0


def test_ollama_malformed_response_raises() -> None:
    def transport(_: dict[str, Any]) -> dict[str, Any]:
        return {"unexpected": True}

    client = OllamaClient(transport=transport)
    with pytest.raises(LLMError, match="malformed"):
        client.complete(_req())


# ---- Anthropic adapter --------------------------------------------------------


def test_anthropic_build_payload_includes_system() -> None:
    client = AnthropicClient(model="claude-sonnet-4-6")
    payload = client._build_payload(_req())
    assert payload["model"] == "claude-sonnet-4-6"
    assert payload["system"] == "be terse"
    assert payload["messages"][0]["role"] == "user"


def test_anthropic_complete_and_cost() -> None:
    def transport(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": "bullish"}],
            "usage": {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
        }

    client = AnthropicClient(model="claude-sonnet-4-6", transport=transport)
    resp = client.complete(_req())
    assert resp.text == "bullish"
    # 1M in @ $3 + 1M out @ $15 = $18.00
    assert resp.cost_usd == pytest.approx(18.0)


def test_anthropic_unknown_model_uses_default_price() -> None:
    def transport(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": "x"}],
            "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
        }

    client = AnthropicClient(model="some-future-model", transport=transport)
    resp = client.complete(_req())
    assert resp.cost_usd == pytest.approx(3.0)  # default input price


def test_anthropic_malformed_response_raises() -> None:
    def transport(_: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": "x"}]}  # missing usage

    client = AnthropicClient(transport=transport)
    with pytest.raises(LLMError, match="malformed"):
        client.complete(_req())
