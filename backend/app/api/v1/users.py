"""User Profile, Preferences, Personalized Student Dashboard & Global Search."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, log_audit
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    AcademicProject,
    AuditLog,
    Diagram,
    Document,
    GenerationJob,
    MediaAsset,
    Notification,
    Presentation,
    ResearchSource,
    StudyMaterial,
    Task,
    UsageRecord,
    User,
    UserProfile,
    UserSession,
    UserSettings,
    Workspace,
)

router = APIRouter(prefix="/users", tags=["Users & Dashboard"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    university: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    academic_level: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=2000)
    country: str | None = Field(default=None, max_length=100)
    avatar_asset_id: str | None = None


class SettingsUpdateRequest(BaseModel):
    theme: str | None = Field(default=None, pattern="^(dark|light|system)$")
    language: str | None = Field(default=None, max_length=16)
    reduced_motion: bool | None = None
    default_citation_style: str | None = Field(default=None, max_length=32)
    ai_context_opt_in: bool | None = None
    email_notifications: bool | None = None
    university_profile: dict[str, Any] | None = None


@router.get("/dashboard")
async def get_student_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Module A — Personalized Student Dashboard backed 100% by real database records."""
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    usettings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()

    workspaces = (
        await db.execute(
            select(Workspace)
            .where(Workspace.owner_id == user.id, Workspace.deleted_at.is_(None))
            .order_by(Workspace.created_at.asc())
            .limit(8)
        )
    ).scalars().all()

    projects = (
        await db.execute(
            select(AcademicProject)
            .where(AcademicProject.owner_id == user.id, AcademicProject.deleted_at.is_(None))
            .order_by(AcademicProject.updated_at.desc())
            .limit(6)
        )
    ).scalars().all()

    documents = (
        await db.execute(
            select(Document)
            .where(Document.owner_id == user.id, Document.deleted_at.is_(None))
            .order_by(Document.updated_at.desc())
            .limit(6)
        )
    ).scalars().all()

    media = (
        await db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.owner_id == user.id,
                MediaAsset.deleted_at.is_(None),
                MediaAsset.asset_type.in_(["image", "video"]),
            )
            .order_by(MediaAsset.created_at.desc())
            .limit(6)
        )
    ).scalars().all()

    tasks = (
        await db.execute(
            select(Task)
            .where(Task.owner_id == user.id, Task.deleted_at.is_(None))
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    notifications = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(8)
        )
    ).scalars().all()

    jobs = (
        await db.execute(
            select(GenerationJob)
            .where(GenerationJob.user_id == user.id)
            .order_by(GenerationJob.created_at.desc())
            .limit(6)
        )
    ).scalars().all()

    activity = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    # Counts & usage
    total_projects = int((await db.execute(select(func.count(AcademicProject.id)).where(AcademicProject.owner_id == user.id, AcademicProject.deleted_at.is_(None)))).scalar() or 0)
    total_docs = int((await db.execute(select(func.count(Document.id)).where(Document.owner_id == user.id, Document.deleted_at.is_(None)))).scalar() or 0)
    total_diagrams = int((await db.execute(select(func.count(Diagram.id)).where(Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)))).scalar() or 0)
    total_presentations = int((await db.execute(select(func.count(Presentation.id)).where(Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)))).scalar() or 0)
    total_sources = int((await db.execute(select(func.count(ResearchSource.id)).where(ResearchSource.owner_id == user.id, ResearchSource.deleted_at.is_(None)))).scalar() or 0)
    storage_used = int((await db.execute(select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)))).scalar() or 0)

    since_24h = datetime.now(timezone.utc) - timedelta(days=1)
    usage_rows = (
        await db.execute(
            select(UsageRecord.resource_type, func.coalesce(func.sum(UsageRecord.quantity), 0))
            .where(UsageRecord.user_id == user.id, UsageRecord.created_at >= since_24h)
            .group_by(UsageRecord.resource_type)
        )
    ).all()
    usage_map = {r[0]: int(r[1]) for r in usage_rows}

    completed_tasks = sum(1 for t in tasks if t.status == "done")
    task_completion = round((completed_tasks / len(tasks)) * 100) if tasks else 0

    return {
        "welcome": {
            "full_name": profile.full_name if profile else user.email.split("@")[0],
            "university": profile.university if profile else None,
            "department": profile.department if profile else None,
            "academic_level": profile.academic_level if profile else "undergraduate",
        },
        "stats": {
            "projects": total_projects,
            "documents": total_docs,
            "diagrams": total_diagrams,
            "presentations": total_presentations,
            "research_sources": total_sources,
            "task_completion_percent": task_completion,
            "storage_used_bytes": storage_used,
            "storage_quota_bytes": usettings.storage_quota_bytes if usettings else settings.default_quota_bytes,
        },
        "fair_use_status": {
            "ai_generation": {"used": usage_map.get("ai_generation", 0), "limit": settings.fair_use_ai_requests_per_day},
            "image_generation": {"used": usage_map.get("image_generation", 0), "limit": settings.fair_use_images_per_day},
            "video_generation": {"used": usage_map.get("video_generation", 0), "limit": settings.fair_use_videos_per_day},
            "document_export": {"used": usage_map.get("document_export", 0), "limit": settings.fair_use_exports_per_day},
        },
        "workspaces": [
            {"id": w.id, "name": w.name, "slug": w.slug, "is_personal": w.is_personal} for w in workspaces
        ],
        "projects": [
            {
                "id": p.id,
                "title": p.title,
                "course_code": p.course_code,
                "subject": p.subject,
                "status": p.status,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in projects
        ],
        "recent_documents": [
            {
                "id": d.id,
                "title": d.title,
                "doc_type": d.doc_type,
                "citation_style": d.citation_style,
                "word_count": d.word_count,
                "updated_at": d.updated_at.isoformat(),
            }
            for d in documents
        ],
        "recent_media": [
            {
                "id": m.id,
                "filename": m.original_filename,
                "asset_type": m.asset_type,
                "mime_type": m.mime_type,
                "size_bytes": m.size_bytes,
                "created_at": m.created_at.isoformat(),
            }
            for m in media
        ],
        "upcoming_tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "progress_percent": t.progress_percent,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "project_id": t.project_id,
            }
            for t in tasks
        ],
        "notifications": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "is_read": n.is_read,
                "action_url": n.action_url,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "recent_jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "provider": j.provider,
                "status": j.status,
                "progress_percent": j.progress_percent,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
        "recent_activity": [
            {
                "id": a.id,
                "action": a.action,
                "resource_type": a.resource_type,
                "created_at": a.created_at.isoformat(),
            }
            for a in activity
        ],
    }


@router.get("/search")
async def search_academic_resources(
    q: str = Query(min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search across all user-owned academic resources (strictly isolated to user)."""
    like = f"%{q.strip()}%"
    projects = (
        await db.execute(
            select(AcademicProject)
            .where(
                AcademicProject.owner_id == user.id,
                AcademicProject.deleted_at.is_(None),
                or_(AcademicProject.title.ilike(like), AcademicProject.description.ilike(like)),
            )
            .limit(8)
        )
    ).scalars().all()
    docs = (
        await db.execute(
            select(Document)
            .where(
                Document.owner_id == user.id,
                Document.deleted_at.is_(None),
                or_(Document.title.ilike(like), Document.content_markdown.ilike(like)),
            )
            .limit(8)
        )
    ).scalars().all()
    diagrams = (
        await db.execute(
            select(Diagram)
            .where(Diagram.owner_id == user.id, Diagram.deleted_at.is_(None), Diagram.title.ilike(like))
            .limit(8)
        )
    ).scalars().all()
    sources = (
        await db.execute(
            select(ResearchSource)
            .where(
                ResearchSource.owner_id == user.id,
                ResearchSource.deleted_at.is_(None),
                or_(ResearchSource.title.ilike(like), ResearchSource.notes.ilike(like)),
            )
            .limit(8)
        )
    ).scalars().all()
    study = (
        await db.execute(
            select(StudyMaterial)
            .where(
                StudyMaterial.owner_id == user.id,
                StudyMaterial.deleted_at.is_(None),
                or_(StudyMaterial.title.ilike(like), StudyMaterial.subject.ilike(like)),
            )
            .limit(8)
        )
    ).scalars().all()

    return {
        "query": q,
        "projects": [{"id": p.id, "title": p.title, "status": p.status} for p in projects],
        "documents": [{"id": d.id, "title": d.title, "doc_type": d.doc_type} for d in docs],
        "diagrams": [{"id": g.id, "title": g.title, "diagram_type": g.diagram_type} for g in diagrams],
        "research_sources": [{"id": s.id, "title": s.title, "year": s.year, "doi": s.doi} for s in sources],
        "study_materials": [{"id": m.id, "title": m.title, "subject": m.subject} for m in study],
    }


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user.id, full_name=body.full_name or user.email.split("@")[0])
        db.add(profile)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, val)
    await log_audit(db, user.id, "user.update_profile", "user_profile", user.id)
    await db.commit()
    return {
        "profile": {
            "full_name": profile.full_name,
            "university": profile.university,
            "department": profile.department,
            "academic_level": profile.academic_level,
            "bio": profile.bio,
            "country": profile.country,
            "avatar_asset_id": profile.avatar_asset_id,
        }
    }


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    usettings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    if not usettings:
        usettings = UserSettings(user_id=user.id)
        db.add(usettings)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(usettings, field, val)
    await log_audit(db, user.id, "user.update_settings", "user_settings", user.id)
    await db.commit()
    return {
        "settings": {
            "theme": usettings.theme,
            "language": usettings.language,
            "reduced_motion": usettings.reduced_motion,
            "default_citation_style": usettings.default_citation_style,
            "ai_context_opt_in": usettings.ai_context_opt_in,
            "email_notifications": usettings.email_notifications,
            "university_profile": usettings.university_profile,
        }
    }


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Privacy-first user-controlled account soft-deletion and session revocation."""
    now = datetime.now(timezone.utc)
    user.is_active = False
    user.deleted_at = now
    sessions = (await db.execute(select(UserSession).where(UserSession.user_id == user.id))).scalars().all()
    for s in sessions:
        s.revoked_at = now
    await log_audit(db, user.id, "user.delete_account", "user", user.id)
    await db.commit()
    return {"deleted": True, "message": "Account scheduled for deletion and all sessions revoked."}
