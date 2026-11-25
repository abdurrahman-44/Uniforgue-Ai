"""Async Generation Jobs Status, Event History & Retry Endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, log_audit
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.models.entities import GenerationEvent, GenerationJob, User

router = APIRouter(prefix="/jobs", tags=["Generation Jobs"])


def _serialize_job(job: GenerationJob, events: list[GenerationEvent] | None = None) -> dict:
    data = {
        "id": job.id,
        "project_id": job.project_id,
        "job_type": job.job_type,
        "provider": job.provider,
        "model_name": job.model_name,
        "status": job.status,
        "progress_percent": job.progress_percent,
        "result_asset_id": job.result_asset_id,
        "output_payload": job.output_payload,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat(),
    }
    if events is not None:
        data["events"] = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "message": e.message,
                "progress_percent": e.progress_percent,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    return data


@router.get("")
async def list_jobs(
    job_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GenerationJob).where(GenerationJob.user_id == user.id)
    if job_type:
        stmt = stmt.where(GenerationJob.job_type == job_type)
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    jobs = (await db.execute(stmt.order_by(GenerationJob.created_at.desc()).limit(50))).scalars().all()
    return {"jobs": [_serialize_job(j) for j in jobs]}


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = (
        await db.execute(
            select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundError("Generation job")
    events = (
        await db.execute(
            select(GenerationEvent)
            .where(GenerationEvent.job_id == job.id)
            .order_by(GenerationEvent.created_at.asc())
        )
    ).scalars().all()
    return {"job": _serialize_job(job, events)}


@router.post("/{job_id}/retry")
async def retry_failed_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = (
        await db.execute(
            select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not job:
        raise NotFoundError("Generation job")
    if job.status not in {"failed", "cancelled"}:
        raise AppError("Only failed or cancelled jobs can be retried.", code="INVALID_JOB_STATE", status_code=400)

    job.status = "queued"
    job.progress_percent = 0
    job.error_code = None
    job.error_message = None
    job.started_at = datetime.now(timezone.utc)
    job.completed_at = None
    db.add(
        GenerationEvent(
            job_id=job.id,
            event_type="retried",
            message="Job re-queued by user for retry",
            progress_percent=0,
        )
    )
    await log_audit(db, user.id, "job.retry", "generation_job", job.id)
    await db.commit()
    return {"job": _serialize_job(job)}
