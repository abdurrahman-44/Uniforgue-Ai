"""Module B — AI Image Studio (Provider Adapters, Academic Visual Mode & Local Pillow Tools)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    get_current_user,
    get_default_workspace,
    log_audit,
    push_notification,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ProviderUnavailableError
from app.core.rate_limit import enforce_fair_use, record_usage
from app.core.security import create_signed_download_token
from app.models.entities import GenerationEvent, GenerationJob, MediaAsset, User
from app.providers.image_providers import (
    ACADEMIC_STYLE_PROMPTS,
    ImageGenerationRequest,
    enhance_academic_prompt,
    image_provider_service,
    process_local_image_operation,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/images", tags=["AI Image Studio"])


class ImageGenerateBody(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    style: str = "academic_illustration"
    aspect_ratio: str = Field(default="1:1", pattern="^(1:1|16:9|9:16|4:3)$")
    resolution: str = "1024x1024"
    academic_visual_mode: bool = False
    operation: str = Field(default="text_to_image", pattern="^(text_to_image|image_to_image|variation)$")
    reference_asset_id: str | None = None
    project_id: str | None = None


class PromptEnhanceBody(BaseModel):
    prompt: str = Field(min_length=2, max_length=1500)
    style: str = "academic_illustration"
    academic_visual_mode: bool = True


class LocalImageProcessBody(BaseModel):
    asset_id: str
    operation: str = Field(pattern="^(upscale|enhance|remove_background|replace_background)$")
    scale_factor: float = Field(default=2.0, ge=1.25, le=4.0)
    background_hex: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")


def _asset_to_dict(a: MediaAsset) -> dict[str, Any]:
    sig, exp = create_signed_download_token(a.id, a.owner_id, ttl_seconds=1800)
    return {
        "id": a.id,
        "filename": a.original_filename,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "project_id": a.project_id,
        "metadata": a.extra_metadata,
        "download_url": f"{settings.api_v1_prefix}/files/{a.id}/download?uid={a.owner_id}&exp={exp}&sig={sig}",
        "created_at": a.created_at.isoformat(),
    }


@router.get("/status")
async def image_studio_status(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    st = await image_provider_service.status(db)
    return {**st, "styles": list(ACADEMIC_STYLE_PROMPTS.keys())}


@router.post("/enhance-prompt")
async def enhance_prompt(body: PromptEnhanceBody, _user: User = Depends(get_current_user)):
    return {
        "original_prompt": body.prompt,
        "enhanced_prompt": enhance_academic_prompt(body.prompt, body.style, body.academic_visual_mode),
        "style": body.style,
        "academic_visual_mode": body.academic_visual_mode,
    }


@router.get("/gallery")
async def list_image_gallery(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assets = (
        await db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.owner_id == user.id,
                MediaAsset.asset_type == "image",
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(MediaAsset.created_at.desc())
            .limit(60)
        )
    ).scalars().all()
    jobs = (
        await db.execute(
            select(GenerationJob)
            .where(GenerationJob.user_id == user.id, GenerationJob.job_type == "image")
            .order_by(GenerationJob.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return {
        "images": [_asset_to_dict(a) for a in assets],
        "jobs": [
            {
                "id": j.id,
                "provider": j.provider,
                "status": j.status,
                "progress_percent": j.progress_percent,
                "result_asset_id": j.result_asset_id,
                "error_code": j.error_code,
                "error_message": j.error_message,
                "input_payload": j.input_payload,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_image(
    body: ImageGenerateBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute real image generation via configured provider adapter; NEVER fabricates images when unavailable."""
    await enforce_fair_use(db, user.id, "image_generation", user.role)
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    provider = await image_provider_service.resolve_provider(db)
    job = GenerationJob(
        user_id=user.id,
        project_id=body.project_id,
        job_type="image",
        provider=provider.name if provider else "unconfigured",
        model_name=provider.model if provider else None,
        status="queued",
        progress_percent=5,
        input_payload=body.model_dump(),
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()
    db.add(GenerationEvent(job_id=job.id, event_type="queued", message="Image generation job created", progress_percent=5))

    if provider is None:
        job.status = "failed"
        job.error_code = "PROVIDER_UNAVAILABLE"
        job.error_message = (
            "No generative image provider is configured on the server. "
            "Configure IMAGE_PROVIDER (openai, huggingface, or self-hosted comfyui) in .env or Admin Console."
        )
        job.completed_at = datetime.now(timezone.utc)
        db.add(GenerationEvent(job_id=job.id, event_type="failed", message=job.error_message, progress_percent=0))
        await db.commit()
        raise ProviderUnavailableError("image_studio", job.error_message, details={"job_id": job.id})

    ref_bytes: bytes | None = None
    if body.reference_asset_id:
        ref = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id == body.reference_asset_id,
                    MediaAsset.owner_id == user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not ref:
            raise NotFoundError("Reference image")
        ref_bytes = storage_service.get_bytes(ref.storage_key, ref.storage_backend)

    try:
        res = await provider.generate(
            ImageGenerationRequest(
                prompt=body.prompt,
                style=body.style,
                aspect_ratio=body.aspect_ratio,
                resolution=body.resolution,
                academic_visual_mode=body.academic_visual_mode,
                reference_image_bytes=ref_bytes,
                operation=body.operation,
            )
        )
        asset = await storage_service.save_asset(
            db=db,
            owner_id=user.id,
            filename=f"generated_{job.id[:8]}.png",
            content=res.image_bytes,
            workspace_id=ws_id,
            project_id=body.project_id,
            asset_type_override="image",
            metadata={
                "provider": res.provider,
                "model": res.model,
                "prompt": body.prompt,
                "enhanced_prompt": res.enhanced_prompt,
                "style": body.style,
                "academic_visual_mode": body.academic_visual_mode,
                "width": res.width,
                "height": res.height,
            },
        )
        job.status = "completed"
        job.progress_percent = 100
        job.result_asset_id = asset.id
        job.completed_at = datetime.now(timezone.utc)
        db.add(GenerationEvent(job_id=job.id, event_type="completed", message="Image generated and saved", progress_percent=100))
        await record_usage(db, user.id, "image_generation", provider=res.provider, model_name=res.model)
        await push_notification(
            db, user.id, "Image Ready", f"Generated image using {res.provider} ({res.model}).", "image", "/image-studio"
        )
        await log_audit(db, user.id, "image.generate", "media_asset", asset.id)
        await db.commit()
        return {"job_id": job.id, "status": "completed", "image": _asset_to_dict(asset)}
    except ProviderUnavailableError as exc:
        job.status = "failed"
        job.error_code = exc.code
        job.error_message = exc.message
        job.completed_at = datetime.now(timezone.utc)
        db.add(GenerationEvent(job_id=job.id, event_type="failed", message=exc.message, progress_percent=0))
        await db.commit()
        raise


@router.post("/process-local", status_code=status.HTTP_201_CREATED)
async def process_local_image(
    body: LocalImageProcessBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real local Pillow image processing (upscale, enhance, background removal/replacement)."""
    src = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == body.asset_id,
                MediaAsset.owner_id == user.id,
                MediaAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Image asset")

    raw = storage_service.get_bytes(src.storage_key, src.storage_backend)
    processed, w, h = process_local_image_operation(
        raw, body.operation, scale_factor=body.scale_factor, background_hex=body.background_hex
    )
    out_asset = await storage_service.save_asset(
        db=db,
        owner_id=user.id,
        filename=f"{body.operation}_{src.filename.rsplit('.', 1)[0]}.png",
        content=processed,
        workspace_id=src.workspace_id,
        project_id=src.project_id,
        asset_type_override="image",
        metadata={
            "operation": body.operation,
            "source_asset_id": src.id,
            "processing_mode": "deterministic_local_pillow",
            "width": w,
            "height": h,
        },
    )
    await log_audit(db, user.id, f"image.{body.operation}", "media_asset", out_asset.id)
    await db.commit()
    return {"image": _asset_to_dict(out_asset)}
