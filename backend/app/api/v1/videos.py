"""Module C — AI Video Studio (Storyboards, SRT Subtitles, Real FFmpeg Assembly, Trim & Merge)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
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
from app.core.exceptions import NotFoundError
from app.core.rate_limit import enforce_fair_use, record_usage
from app.core.security import create_signed_download_token
from app.models.entities import (
    GenerationEvent,
    GenerationJob,
    MediaAsset,
    Presentation,
    PresentationSlide,
    User,
)
from app.providers.video_providers import (
    assemble_storyboard_video_mp4,
    generate_srt_subtitles,
    merge_videos_mp4,
    submit_external_generative_video,
    synthesize_openai_tts_voiceover,
    trim_video_mp4,
    video_provider_status,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/videos", tags=["AI Video Studio"])


class StoryboardScene(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    narration: str = Field(default="", max_length=1500)
    visual_notes: str = Field(default="", max_length=1000)
    duration_seconds: float = Field(default=3.0, ge=1.0, le=30.0)
    background_color: str = "#0A1024"
    image_asset_id: str | None = None


class ScriptPlanRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    target_duration_seconds: int = Field(default=30, ge=10, le=300)
    scene_count: int = Field(default=5, ge=2, le=12)


class StoryboardAssembleRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1|4:3)$")
    project_id: str | None = None
    voiceover_asset_id: str | None = None
    auto_tts_voiceover: bool = False
    scenes: list[StoryboardScene] = Field(min_length=1, max_length=20)


class PresentationToVideoRequest(BaseModel):
    presentation_id: str
    seconds_per_slide: float = Field(default=4.0, ge=1.5, le=20.0)
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1|4:3)$")


class VideoTrimRequest(BaseModel):
    asset_id: str
    start_seconds: float = Field(ge=0.0)
    end_seconds: float = Field(gt=0.0)


class VideoMergeRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=2, max_length=10)
    title: str = Field(default="Merged Academic Video", min_length=2, max_length=200)


class GenerativeVideoRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=1000)
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16|1:1)$")
    project_id: str | None = None


def _video_asset_dict(a: MediaAsset) -> dict[str, Any]:
    sig, exp = create_signed_download_token(a.id, a.owner_id, ttl_seconds=1800)
    return {
        "id": a.id,
        "filename": a.original_filename,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "metadata": a.extra_metadata,
        "download_url": f"{settings.api_v1_prefix}/files/{a.id}/download?uid={a.owner_id}&exp={exp}&sig={sig}",
        "created_at": a.created_at.isoformat(),
    }


@router.get("/status")
async def get_video_status(_user: User = Depends(get_current_user)):
    return video_provider_status()


@router.get("/library")
async def list_videos(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    videos = (
        await db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.owner_id == user.id,
                MediaAsset.asset_type == "video",
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(MediaAsset.created_at.desc())
            .limit(40)
        )
    ).scalars().all()
    jobs = (
        await db.execute(
            select(GenerationJob)
            .where(
                GenerationJob.user_id == user.id,
                GenerationJob.job_type.in_(["video_assemble", "video_gen", "video_edit"]),
            )
            .order_by(GenerationJob.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return {
        "videos": [_video_asset_dict(v) for v in videos],
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "provider": j.provider,
                "status": j.status,
                "progress_percent": j.progress_percent,
                "result_asset_id": j.result_asset_id,
                "output_payload": j.output_payload,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
    }


@router.post("/plan-storyboard")
async def plan_storyboard(body: ScriptPlanRequest, _user: User = Depends(get_current_user)):
    """Create a structured academic video script & scene-by-scene storyboard plan."""
    per_scene = max(2.0, round(body.target_duration_seconds / body.scene_count, 1))
    arc = [
        ("Introduction & Hook", f"Introduce {body.topic} and state why it matters in current academic study."),
        ("Core Concept Breakdown", f"Define the key principles and terminology behind {body.topic}."),
        ("Methodology & Visual Flow", f"Walk step-by-step through how {body.topic} operates in practice."),
        ("Evidence & Case Example", f"Highlight an illustrative real-world or scholarly example of {body.topic}."),
        ("Summary & Takeaways", f"Recap the three essential takeaways about {body.topic} for exam/presentation review."),
    ]
    scenes = []
    for i in range(body.scene_count):
        title, narr = arc[i % len(arc)]
        scenes.append(
            {
                "title": f"{i + 1}. {title}",
                "narration": narr,
                "visual_notes": f"Academic graphic overlay illustrating {title.lower()}",
                "duration_seconds": per_scene,
                "background_color": "#0A1024",
            }
        )
    return {
        "topic": body.topic,
        "scenes": scenes,
        "srt_preview": generate_srt_subtitles(scenes),
    }


@router.post("/subtitles/srt")
async def export_srt(scenes: list[StoryboardScene], _user: User = Depends(get_current_user)):
    srt = generate_srt_subtitles([s.model_dump() for s in scenes])
    return Response(
        content=srt.encode("utf-8"),
        media_type="application/x-subrip",
        headers={"Content-Disposition": 'attachment; filename="subtitles.srt"'},
    )


@router.post("/assemble", status_code=status.HTTP_201_CREATED)
async def assemble_video(
    body: StoryboardAssembleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real FFmpeg storyboard-to-MP4 assembly (clearly labeled `storyboard_assembled`)."""
    await enforce_fair_use(db, user.id, "video_generation", user.role)
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    job = GenerationJob(
        user_id=user.id,
        project_id=body.project_id,
        job_type="video_assemble",
        provider="local_ffmpeg",
        model_name="storyboard_assembled",
        status="processing",
        progress_percent=20,
        input_payload={"title": body.title, "scene_count": len(body.scenes), "aspect_ratio": body.aspect_ratio},
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    scene_dicts = [s.model_dump() for s in body.scenes]
    scene_images: dict[int, bytes] = {}
    for idx, sc in enumerate(body.scenes):
        if sc.image_asset_id:
            asset = (
                await db.execute(
                    select(MediaAsset).where(MediaAsset.id == sc.image_asset_id, MediaAsset.owner_id == user.id)
                )
            ).scalar_one_or_none()
            if asset:
                try:
                    scene_images[idx] = storage_service.get_bytes(asset.storage_key, asset.storage_backend)
                except Exception:
                    pass

    voiceover_bytes: bytes | None = None
    voiceover_ext = ".mp3"
    if body.voiceover_asset_id:
        vo_asset = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id == body.voiceover_asset_id,
                    MediaAsset.owner_id == user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if vo_asset:
            voiceover_bytes = storage_service.get_bytes(vo_asset.storage_key, vo_asset.storage_backend)
            voiceover_ext = ".wav" if vo_asset.filename.lower().endswith(".wav") else ".mp3"
    elif body.auto_tts_voiceover:
        full_script = " ".join(s.get("narration", "") for s in scene_dicts if s.get("narration"))
        voiceover_bytes = await synthesize_openai_tts_voiceover(full_script)

    # Dispatch asynchronously via Celery when Redis worker mode is active
    if not settings.use_inline_job_runner:
        from app.workers.celery_app import assemble_video_job_task

        job.status = "queued"
        job.progress_percent = 5
        await db.commit()
        assemble_video_job_task.delay(job.id, body.title, body.aspect_ratio, scene_dicts)
        return {"job_id": job.id, "status": "queued", "video_mode": "storyboard_assembled"}

    try:
        mp4_bytes = assemble_storyboard_video_mp4(
            scene_dicts, body.aspect_ratio, scene_images, voiceover_bytes, voiceover_ext
        )
        srt_text = generate_srt_subtitles(scene_dicts)
        safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in body.title)[:60] or "video"
        video_asset = await storage_service.save_asset(
            db=db,
            owner_id=user.id,
            filename=f"{safe_slug}.mp4",
            content=mp4_bytes,
            workspace_id=ws_id,
            project_id=body.project_id,
            asset_type_override="video",
            metadata={
                "video_mode": "storyboard_assembled",
                "aspect_ratio": body.aspect_ratio,
                "scene_count": len(scene_dicts),
                "total_duration_seconds": sum(s["duration_seconds"] for s in scene_dicts),
                "subtitles_srt": srt_text,
            },
        )
        job.status = "completed"
        job.progress_percent = 100
        job.result_asset_id = video_asset.id
        job.output_payload = {"video_mode": "storyboard_assembled", "asset_id": video_asset.id}
        job.completed_at = datetime.now(timezone.utc)
        db.add(GenerationEvent(job_id=job.id, event_type="completed", message="FFmpeg storyboard video rendered", progress_percent=100))
        await record_usage(db, user.id, "video_generation", provider="local_ffmpeg", model_name="storyboard_assembled")
        await push_notification(db, user.id, "Video Rendered", f"'{body.title}' MP4 assembled with FFmpeg.", "video", "/video-studio")
        await log_audit(db, user.id, "video.assemble", "media_asset", video_asset.id)
        await db.commit()
        return {"job_id": job.id, "video_mode": "storyboard_assembled", "video": _video_asset_dict(video_asset), "subtitles_srt": srt_text}
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise


@router.post("/from-presentation", status_code=status.HTTP_201_CREATED)
async def presentation_to_video(
    body: PresentationToVideoRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert a Presentation Studio deck into a real MP4 video with FFmpeg."""
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == body.presentation_id,
                Presentation.owner_id == user.id,
                Presentation.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    slides = (
        await db.execute(
            select(PresentationSlide)
            .where(PresentationSlide.presentation_id == prs.id)
            .order_by(PresentationSlide.order_index.asc())
        )
    ).scalars().all()
    scenes = [
        StoryboardScene(
            title=s.title,
            narration=s.speaker_notes or " • ".join(s.bullets or []),
            duration_seconds=body.seconds_per_slide,
            image_asset_id=s.image_asset_id,
        )
        for s in slides
    ]
    return await assemble_video(
        StoryboardAssembleRequest(
            title=f"{prs.title} (Video Deck)",
            aspect_ratio=body.aspect_ratio,
            project_id=prs.project_id,
            scenes=scenes,
        ),
        user=user,
        db=db,
    )


@router.post("/trim", status_code=status.HTTP_201_CREATED)
async def trim_video(
    body: VideoTrimRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == body.asset_id, MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Video asset")
    raw = storage_service.get_bytes(src.storage_key, src.storage_backend)
    trimmed = trim_video_mp4(raw, body.start_seconds, body.end_seconds)
    out = await storage_service.save_asset(
        db=db,
        owner_id=user.id,
        filename=f"trimmed_{src.filename}",
        content=trimmed,
        workspace_id=src.workspace_id,
        project_id=src.project_id,
        asset_type_override="video",
        metadata={"video_mode": "ffmpeg_trimmed", "source_asset_id": src.id, "start": body.start_seconds, "end": body.end_seconds},
    )
    await db.commit()
    return {"video": _video_asset_dict(out)}


@router.post("/merge", status_code=status.HTTP_201_CREATED)
async def merge_videos(
    body: VideoMergeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    blobs: list[bytes] = []
    ws_id = None
    for aid in body.asset_ids:
        a = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id == aid, MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
                )
            )
        ).scalar_one_or_none()
        if not a:
            raise NotFoundError(f"Video asset {aid}")
        ws_id = ws_id or a.workspace_id
        blobs.append(storage_service.get_bytes(a.storage_key, a.storage_backend))
    merged = merge_videos_mp4(blobs)
    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in body.title)[:60] or "merged"
    out = await storage_service.save_asset(
        db=db,
        owner_id=user.id,
        filename=f"{safe_slug}.mp4",
        content=merged,
        workspace_id=ws_id,
        asset_type_override="video",
        metadata={"video_mode": "ffmpeg_merged", "source_asset_ids": body.asset_ids},
    )
    await db.commit()
    return {"video": _video_asset_dict(out)}


@router.post("/generate-neural")
async def generate_neural_video(
    body: GenerativeVideoRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """External generative text-to-video adapter (Replicate / Runway); honestly reports unavailable when unconfigured."""
    await enforce_fair_use(db, user.id, "video_generation", user.role)
    res = await submit_external_generative_video(body.prompt, body.aspect_ratio)
    job = GenerationJob(
        user_id=user.id,
        project_id=body.project_id,
        job_type="video_gen",
        provider=res["provider"],
        model_name="generative_video",
        status=res["status"],
        progress_percent=10,
        input_payload=body.model_dump(),
        output_payload=res,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await record_usage(db, user.id, "video_generation", provider=res["provider"], model_name="generative_video")
    await db.commit()
    return {"job_id": job.id, "video_mode": "generative_video", **res}
