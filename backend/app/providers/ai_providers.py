"""Unified AI Orchestration Service with GPT-6 Astra primary adapter & fallbacks.

Verified GPT-6 Astra API specifications:
- Model identifiers: `gpt-6-astra` (standard), `gpt-6.2-astra` (latest flagship)
- Endpoints: `https://api.openai.com/v1/responses` and `https://api.openai.com/v1/chat/completions`
- Context window: 1,050,000 tokens; max output: 128,000 tokens
- Capabilities: Text + image multimodal inputs, streaming SSE, strict JSON structured outputs,
  reasoning effort levels (`low`, `medium`, `high`, `xhigh`, `max`), tool calling.
- Outputs are text/structured JSON only; language models NEVER fabricate images or videos.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.security import decrypt_secret
from app.models.entities import ProviderConfig

logger = logging.getLogger("uniforge.ai")


@dataclass
class AIRequest:
    prompt: str
    system_prompt: str = (
        "You are UNIFORGE AI, an academic productivity assistant for university students. "
        "Maintain strict academic integrity: never invent citations, DOIs, or fabricated data. "
        "Clearly indicate when guidance is AI-assisted."
    )
    context_blocks: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 2048
    reasoning_effort: str | None = None
    json_schema: dict[str, Any] | None = None
    stream: bool = False


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = "stop"
    structured_data: dict[str, Any] | None = None
    ai_assisted_notice: str = "Generated with AI assistance. Verify facts and citations before submission."


PROMPT_TEMPLATES: dict[str, str] = {
    "academic_outline": (
        "Create a rigorous university-level document outline in Markdown following {citation_style} conventions "
        "for a {doc_type} titled '{title}'. Include clear section headings, key arguments to develop, "
        "and placeholders where verified citations should be inserted (never invent references)."
    ),
    "assignment_feedback": (
        "Analyze the student's draft against the extracted assignment requirements. Identify addressed items, "
        "missing sections, formatting gaps, and constructive revision steps. Never guarantee a grade."
    ),
    "literature_synthesis": (
        "Synthesize ONLY the provided verified research sources into a structured literature review comparison "
        "covering methodologies, findings, and research gaps. Cite only the exact sources supplied."
    ),
    "srs_generator": (
        "Draft a structured IEEE 830 Software Requirements Specification section for the university project "
        "'{title}' covering functional requirements, non-functional requirements, actors, and constraints."
    ),
    "presentation_outline": (
        "Generate a clean slide-by-slide academic presentation outline in JSON format with slide titles, "
        "concise bullet points (3-5 per slide), and speaker notes."
    ),
    "study_pack": (
        "From the supplied lecture notes/text, produce concise study summaries, key concept flashcards "
        "(front/back), and practice MCQ questions with detailed explanations."
    ),
    "video_script": (
        "Write an educational academic explainer video script broken into numbered scenes with narration, "
        "on-screen visual cues, and estimated duration in seconds."
    ),
}


class BaseAIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    async def generate(self, req: AIRequest) -> AIResponse:
        ...

    @abstractmethod
    async def stream(self, req: AIRequest) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        ...


class OpenAIAstraProvider(BaseAIProvider):
    """Primary adapter for OpenAI GPT-6 Astra (`gpt-6-astra` / `gpt-6.2-astra`)."""

    name = "openai_astra"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-6-astra",
        reasoning_effort: str = "medium",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _build_messages(self, req: AIRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": req.system_prompt}]
        if req.context_blocks:
            joined_context = "\n\n---\n\n".join(req.context_blocks)
            messages.append(
                {
                    "role": "system",
                    "content": f"Authorized Project Context (use strictly for this project):\n\n{joined_context}",
                }
            )
        if req.image_urls:
            content_parts: list[dict[str, Any]] = [{"type": "text", "text": req.prompt}]
            for img_url in req.image_urls:
                content_parts.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": req.prompt})
        return messages

    def _build_payload(self, req: AIRequest, stream: bool = False) -> dict[str, Any]:
        model_id = req.model or self.model
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": self._build_messages(req),
            "max_completion_tokens": req.max_tokens,
            "stream": stream,
        }
        if not model_id.startswith("gpt-6"):
            payload["temperature"] = req.temperature
        else:
            effort = req.reasoning_effort or self.reasoning_effort
            if effort in {"low", "medium", "high", "xhigh", "max"}:
                payload["reasoning_effort"] = effort
        if req.json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "uniforge_structured_output",
                    "strict": True,
                    "schema": req.json_schema,
                },
            }
        return payload

    async def generate(self, req: AIRequest) -> AIResponse:
        if not self.is_configured():
            raise ProviderUnavailableError(
                self.name,
                "OpenAI GPT-6 Astra API key is not configured. Set OPENAI_API_KEY on the server or configure an alternative provider in Admin Console.",
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(req, stream=False)

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                text = choice["message"].get("content", "") or ""
                usage = data.get("usage", {})
                structured = None
                if req.json_schema and text:
                    try:
                        structured = json.loads(text)
                    except json.JSONDecodeError:
                        structured = None
                logger.info(
                    "ai_request_completed provider=%s model=%s tokens_in=%s tokens_out=%s",
                    self.name,
                    payload["model"],
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                return AIResponse(
                    content=text,
                    provider=self.name,
                    model=payload["model"],
                    tokens_in=int(usage.get("prompt_tokens", 0)),
                    tokens_out=int(usage.get("completion_tokens", 0)),
                    finish_reason=choice.get("finish_reason", "stop"),
                    structured_data=structured,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise ProviderUnavailableError(
            self.name,
            f"GPT-6 Astra endpoint request failed after retries: {type(last_error).__name__}",
        )

    async def stream(self, req: AIRequest) -> AsyncIterator[str]:
        if not self.is_configured():
            raise ProviderUnavailableError(self.name, "OpenAI GPT-6 Astra API key is not configured.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = self._build_payload(req, stream=True)
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        parsed = json.loads(chunk)
                        delta = parsed["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def health_check(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "endpoint": f"{self.base_url}/chat/completions",
            "configured": self.is_configured(),
            "capabilities": {
                "context_window": 1050000,
                "max_output_tokens": 128000,
                "streaming": True,
                "structured_outputs": True,
                "multimodal_images": True,
                "reasoning_effort": ["low", "medium", "high", "xhigh", "max"],
            },
        }


class CustomOpenAICompatibleProvider(OpenAIAstraProvider):
    """Connects to OpenRouter, Groq, Together, Azure Foundry, or self-hosted vLLM."""

    name = "custom_openai"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        super().__init__(api_key=api_key, base_url=base_url or "https://api.openai.com/v1", model=model)

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model and self.api_key)


class OllamaLocalProvider(BaseAIProvider):
    """Free local open-source LLM provider via Ollama with automatic pulled-model detection."""

    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)

    async def _list_installed_models(self) -> list[str] | None:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                if r.status_code != 200:
                    return None
                return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
        except Exception:
            return None

    async def _resolve_model(self, requested: str | None = None) -> str:
        target = requested or self.model
        installed = await self._list_installed_models()
        if installed:
            if target in installed or any(m.startswith(f"{target}:") for m in installed):
                return target
            return installed[0]
        return target

    async def generate(self, req: AIRequest) -> AIResponse:
        messages = [{"role": "system", "content": req.system_prompt}]
        if req.context_blocks:
            messages.append(
                {"role": "system", "content": "Project context:\n" + "\n\n".join(req.context_blocks)}
            )
        messages.append({"role": "user", "content": req.prompt})

        active_model = await self._resolve_model(req.model)
        payload: dict[str, Any] = {
            "model": active_model,
            "messages": messages,
            "stream": False,
        }
        if req.json_schema:
            payload["format"] = "json"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            structured = None
            if req.json_schema and text:
                try:
                    structured = json.loads(text)
                except json.JSONDecodeError:
                    structured = None
            return AIResponse(
                content=text,
                provider=self.name,
                model=active_model,
                tokens_in=int(data.get("prompt_eval_count", 0)),
                tokens_out=int(data.get("eval_count", 0)),
                structured_data=structured,
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                self.name,
                f"Local Ollama server at {self.base_url} is not reachable or model '{active_model}' is not pulled ({type(exc).__name__}).",
            )

    async def stream(self, req: AIRequest) -> AsyncIterator[str]:
        active_model = await self._resolve_model(req.model)
        messages = [
            {"role": "system", "content": req.system_prompt},
            {"role": "user", "content": req.prompt},
        ]
        payload = {"model": active_model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> dict[str, Any]:
        installed = await self._list_installed_models()
        reachable = installed is not None and len(installed) > 0
        active_model = installed[0] if (installed and self.model not in installed) else self.model
        return {
            "provider": self.name,
            "model": active_model,
            "endpoint": self.base_url,
            "configured": reachable,
            "installed_models": installed or [],
            "capabilities": {
                "streaming": True,
                "structured_outputs": True,
                "local_free_inference": True,
            },
        }


class AIOrchestrationService:
    """Resolves providers (DB config + env), runs fallback chain, validates structured outputs."""

    def __init__(self, providers: list[BaseAIProvider] | None = None) -> None:
        self._explicit_providers = providers

    async def resolve_providers(self, db: AsyncSession | None = None) -> list[BaseAIProvider]:
        if self._explicit_providers is not None:
            return self._explicit_providers

        providers: list[BaseAIProvider] = []
        db_configs: dict[str, ProviderConfig] = {}
        if db is not None:
            res = await db.execute(
                select(ProviderConfig).where(
                    ProviderConfig.category == "ai", ProviderConfig.is_enabled.is_(True)
                )
            )
            for cfg in res.scalars().all():
                db_configs[cfg.name] = cfg

        # 1. Primary GPT-6 Astra
        astra_cfg = db_configs.get("openai_astra")
        astra_key = (
            decrypt_secret(astra_cfg.encrypted_api_key or "")
            if astra_cfg and astra_cfg.encrypted_api_key
            else settings.openai_api_key
        )
        astra_url = (
            (astra_cfg.endpoint_url if astra_cfg and astra_cfg.endpoint_url else settings.openai_base_url)
        )
        astra_model = (
            (astra_cfg.model_identifier if astra_cfg and astra_cfg.model_identifier else settings.openai_astra_model)
        )
        providers.append(
            OpenAIAstraProvider(
                api_key=astra_key,
                base_url=astra_url,
                model=astra_model,
                reasoning_effort=settings.openai_astra_reasoning_effort,
            )
        )

        # 2. Custom OpenAI-compatible provider (OpenRouter/Groq/Azure/vLLM)
        custom_cfg = db_configs.get("custom_openai")
        custom_key = (
            decrypt_secret(custom_cfg.encrypted_api_key or "")
            if custom_cfg and custom_cfg.encrypted_api_key
            else settings.custom_ai_api_key
        )
        custom_url = (
            custom_cfg.endpoint_url if custom_cfg and custom_cfg.endpoint_url else settings.custom_ai_base_url
        )
        custom_model = (
            custom_cfg.model_identifier if custom_cfg and custom_cfg.model_identifier else settings.custom_ai_model
        )
        if custom_url and custom_model:
            providers.append(CustomOpenAICompatibleProvider(custom_key, custom_url, custom_model))

        # 3. Local Ollama fallback
        ollama_cfg = db_configs.get("ollama")
        ollama_url = (
            ollama_cfg.endpoint_url if ollama_cfg and ollama_cfg.endpoint_url else settings.ollama_base_url
        )
        ollama_model = (
            ollama_cfg.model_identifier if ollama_cfg and ollama_cfg.model_identifier else settings.ollama_model
        )
        providers.append(OllamaLocalProvider(base_url=ollama_url, model=ollama_model))
        return providers

    async def generate(
        self,
        req: AIRequest,
        db: AsyncSession | None = None,
        preferred_provider: str | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> AIResponse:
        providers = await self.resolve_providers(db)
        if preferred_provider:
            providers.sort(key=lambda p: 0 if p.name == preferred_provider else 1)

        errors: list[str] = []
        for provider in providers:
            if not provider.is_configured():
                errors.append(f"{provider.name}: not configured")
                continue
            try:
                res = await provider.generate(req)
                if response_model and res.structured_data is not None:
                    validated = response_model.model_validate(res.structured_data)
                    res.structured_data = validated.model_dump()
                return res
            except ProviderUnavailableError as exc:
                errors.append(f"{provider.name}: {exc.message}")
                continue

        raise ProviderUnavailableError(
            provider="ai_orchestrator",
            message=(
                "No AI language provider is currently configured or reachable. "
                "Configure OPENAI_API_KEY (for GPT-6 Astra), CUSTOM_AI_*, or run a local Ollama server."
            ),
            details={"attempted_providers": errors},
        )

    async def stream(
        self,
        req: AIRequest,
        db: AsyncSession | None = None,
        preferred_provider: str | None = None,
    ) -> AsyncIterator[str]:
        providers = await self.resolve_providers(db)
        if preferred_provider:
            providers.sort(key=lambda p: 0 if p.name == preferred_provider else 1)

        for provider in providers:
            if not provider.is_configured():
                continue
            try:
                async for token in provider.stream(req):
                    yield token
                return
            except Exception:
                continue

        raise ProviderUnavailableError(
            provider="ai_orchestrator",
            message="No streaming AI provider is currently available. Configure GPT-6 Astra or Ollama.",
        )

    async def status(self, db: AsyncSession | None = None) -> dict[str, Any]:
        providers = await self.resolve_providers(db)
        checks = [await p.health_check() for p in providers]
        active = next((c["provider"] for c in checks if c.get("configured")), None)
        return {
            "primary_target": settings.openai_astra_model,
            "active_provider": active,
            "available": active is not None,
            "providers": checks,
            "prompt_templates": list(PROMPT_TEMPLATES.keys()),
        }


ai_service = AIOrchestrationService()
