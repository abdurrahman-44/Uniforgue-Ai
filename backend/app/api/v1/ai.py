"""Unified AI Orchestration Endpoints (GPT-6 Astra Primary + Fallbacks + Streaming)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_project_access, get_current_user, log_audit
from app.core.database import get_db
from app.core.rate_limit import enforce_fair_use, record_usage
from app.models.entities import ProjectContext, User
from app.providers.ai_providers import PROMPT_TEMPLATES, AIRequest, ai_service
from app.services.retrieval_service import rank_project_context

router = APIRouter(prefix="/ai", tags=["AI Orchestration"])


class AIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    template_name: str | None = None
    template_vars: dict[str, str] = Field(default_factory=dict)
    project_id: str | None = None
    context_ids: list[str] | None = None
    preferred_provider: str | None = None
    model: str | None = None
    reasoning_effort: str | None = Field(default=None, pattern="^(low|medium|high|xhigh|max)$")
    temperature: float = Field(default=0.3, ge=0.0, le=1.5)
    max_tokens: int = Field(default=2048, ge=64, le=32000)
    json_schema: dict[str, Any] | None = None


async def _load_isolated_project_context(
    db: AsyncSession,
    user: User,
    project_id: str | None,
    context_ids: list[str] | None,
    query: str = "",
) -> list[str]:
    """Strictly retrieves & semantically ranks context ONLY for the requested project accessible by this user."""
    if not project_id:
        return []
    proj = await ensure_project_access(db, project_id, user)
    stmt = select(ProjectContext).where(
        ProjectContext.project_id == proj.id,
        ProjectContext.include_in_ai_context.is_(True),
    )
    if context_ids:
        stmt = stmt.where(ProjectContext.id.in_(context_ids))
    items = (await db.execute(stmt)).scalars().all()
    ranked = rank_project_context(query, items, top_k=8)
    return [
        f"[{item.source_type.upper()}: {item.title} | relevance={score}]\n{item.content_excerpt}"
        for item, score in ranked
    ]


@router.get("/status")
async def get_ai_status(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_service.status(db)


@router.get("/templates")
async def list_prompt_templates(_user: User = Depends(get_current_user)):
    return {"templates": PROMPT_TEMPLATES}


@router.post("/generate")
async def generate_ai_response(
    body: AIGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quota = await enforce_fair_use(db, user.id, "ai_generation", user.role)
    context_blocks = await _load_isolated_project_context(
        db, user, body.project_id, body.context_ids, query=body.prompt
    )

    prompt = body.prompt
    if body.template_name and body.template_name in PROMPT_TEMPLATES:
        try:
            prefix = PROMPT_TEMPLATES[body.template_name].format(**body.template_vars)
        except KeyError:
            prefix = PROMPT_TEMPLATES[body.template_name]
        prompt = f"{prefix}\n\nStudent Request:\n{body.prompt}"

    ai_req = AIRequest(
        prompt=prompt,
        context_blocks=context_blocks,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        reasoning_effort=body.reasoning_effort,
        json_schema=body.json_schema,
    )
    res = await ai_service.generate(ai_req, db=db, preferred_provider=body.preferred_provider)

    await record_usage(
        db,
        user.id,
        "ai_generation",
        quantity=1,
        provider=res.provider,
        model_name=res.model,
        tokens_in=res.tokens_in,
        tokens_out=res.tokens_out,
        metadata={"project_id": body.project_id, "context_blocks_used": len(context_blocks)},
    )
    await log_audit(db, user.id, "ai.generate", "ai_request", body.project_id, details={"provider": res.provider, "model": res.model})
    await db.commit()

    return {
        "content": res.content,
        "structured_data": res.structured_data,
        "provider": res.provider,
        "model": res.model,
        "usage": {"tokens_in": res.tokens_in, "tokens_out": res.tokens_out},
        "context_blocks_used": len(context_blocks),
        "fair_use": {**quota, "remaining": max(0, quota["remaining"] - 1)},
        "ai_assisted_notice": res.ai_assisted_notice,
    }


@router.post("/stream")
async def stream_ai_response(
    body: AIGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_fair_use(db, user.id, "ai_generation", user.role)
    context_blocks = await _load_isolated_project_context(
        db, user, body.project_id, body.context_ids, query=body.prompt
    )
    ai_req = AIRequest(
        prompt=body.prompt,
        context_blocks=context_blocks,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        reasoning_effort=body.reasoning_effort,
        stream=True,
    )

    async def event_stream():
        try:
            async for chunk in ai_service.stream(ai_req, db=db, preferred_provider=body.preferred_provider):
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
