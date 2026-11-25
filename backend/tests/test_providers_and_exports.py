"""Unit tests for AI provider adapters, GPT-6 Astra payload builder, fallback & fair-use limits."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import ProviderUnavailableError
from app.providers.ai_providers import (
    AIOrchestrationService,
    AIRequest,
    AIResponse,
    BaseAIProvider,
    OpenAIAstraProvider,
)


class _FailingProvider(BaseAIProvider):
    name = "failing_primary"
    model = "gpt-6-astra"

    def is_configured(self) -> bool:
        return True

    async def generate(self, req: AIRequest) -> AIResponse:
        raise ProviderUnavailableError(self.name, "Simulated upstream timeout")

    async def stream(self, req: AIRequest):
        raise ProviderUnavailableError(self.name, "Simulated stream timeout")
        yield ""  # pragma: no cover

    async def health_check(self) -> dict:
        return {"provider": self.name, "configured": True}


class _HealthyFallbackProvider(BaseAIProvider):
    name = "healthy_fallback"
    model = "llama3.2"

    def is_configured(self) -> bool:
        return True

    async def generate(self, req: AIRequest) -> AIResponse:
        return AIResponse(
            content=f"Echo with {len(req.context_blocks)} context blocks",
            provider=self.name,
            model=self.model,
            tokens_in=15,
            tokens_out=10,
        )

    async def stream(self, req: AIRequest):
        yield "chunk1"

    async def health_check(self) -> dict:
        return {"provider": self.name, "configured": True}


def test_gpt6_astra_payload_uses_verified_model_and_structured_schema():
    provider = OpenAIAstraProvider(api_key="test-key", model="gpt-6-astra", reasoning_effort="high")
    req = AIRequest(
        prompt="Summarize methodology",
        context_blocks=["[DOCUMENT: SRS] Section 1"],
        json_schema={"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
    )
    payload = provider._build_payload(req, stream=False)
    assert payload["model"] == "gpt-6-astra"
    assert payload["reasoning_effort"] == "high"
    assert payload["response_format"]["type"] == "json_schema"
    assert any("Authorized Project Context" in str(m["content"]) for m in payload["messages"])


@pytest.mark.asyncio
async def test_ai_orchestrator_provider_fallback_on_failure():
    svc = AIOrchestrationService(providers=[_FailingProvider(), _HealthyFallbackProvider()])
    res = await svc.generate(AIRequest(prompt="Explain ACID", context_blocks=["ctx1"]))
    assert res.provider == "healthy_fallback"
    assert "1 context blocks" in res.content


@pytest.mark.asyncio
async def test_ai_orchestrator_honest_unavailable_when_no_provider_configured():
    svc = AIOrchestrationService(providers=[OpenAIAstraProvider(api_key="")])
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await svc.generate(AIRequest(prompt="Hello"))
    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health_endpoint_reports_honest_provider_readiness(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"]["connected"] is True
    assert body["providers"]["image"]["available"] is False
    assert body["providers"]["video"]["local_ffmpeg_available"] is True
