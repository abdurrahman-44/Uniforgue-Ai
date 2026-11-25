"""Celery background worker tasks for Redis-backed async video & media rendering."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from celery import Celery
from sqlalchemy import select

from app.core.config import settings

celery_app = Celery(
    "uniforge_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="uniforge.health_ping")
def worker_health_ping() -> dict[str, str]:
    return {"status": "ok", "worker": "uniforge-celery"}


async def _run_video_job(job_id: str, title: str, aspect_ratio: str, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    from app.core.database import AsyncSessionLocal
    from app.models.entities import GenerationEvent, GenerationJob, MediaAsset
    from app.providers.video_providers import assemble_storyboard_video_mp4, generate_srt_subtitles
    from app.services.storage_service import storage_service

    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))).scalar_one_or_none()
        if not job:
            return {"error": "Job not found"}
        job.status = "processing"
        job.progress_percent = 25
        db.add(GenerationEvent(job_id=job.id, event_type="processing", message="Worker rendering scenes via FFmpeg", progress_percent=25))
        await db.commit()

        try:
            scene_images: dict[int, bytes] = {}
            for idx, sc in enumerate(scenes):
                if sc.get("image_asset_id"):
                    asset = (
                        await db.execute(
                            select(MediaAsset).where(
                                MediaAsset.id == sc["image_asset_id"], MediaAsset.owner_id == job.user_id
                            )
                        )
                    ).scalar_one_or_none()
                    if asset:
                        scene_images[idx] = storage_service.get_bytes(asset.storage_key, asset.storage_backend)

            mp4_bytes = assemble_storyboard_video_mp4(scenes, aspect_ratio, scene_images)
            srt = generate_srt_subtitles(scenes)
            safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60] or "video"
            asset = await storage_service.save_asset(
                db=db,
                owner_id=job.user_id,
                filename=f"{safe_slug}.mp4",
                content=mp4_bytes,
                project_id=job.project_id,
                asset_type_override="video",
                metadata={"video_mode": "storyboard_assembled", "aspect_ratio": aspect_ratio, "subtitles_srt": srt},
            )
            job.status = "completed"
            job.progress_percent = 100
            job.result_asset_id = asset.id
            job.output_payload = {"video_mode": "storyboard_assembled", "asset_id": asset.id}
            job.completed_at = datetime.now(timezone.utc)
            db.add(GenerationEvent(job_id=job.id, event_type="completed", message="Async video assembly completed", progress_percent=100))
            await db.commit()
            return {"job_id": job.id, "status": "completed", "asset_id": asset.id}
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.add(GenerationEvent(job_id=job.id, event_type="failed", message=str(exc), progress_percent=0))
            await db.commit()
            return {"job_id": job.id, "status": "failed", "error": str(exc)}


@celery_app.task(name="uniforge.assemble_video_job")
def assemble_video_job_task(job_id: str, title: str, aspect_ratio: str, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Dispatched to Celery workers when USE_INLINE_JOB_RUNNER=false."""
    return asyncio.run(_run_video_job(job_id, title, aspect_ratio, scenes))
