"""Module L — Administration Console (Strict Admin RBAC, Provider Secrets Encrypted, Moderation, Audit Logs)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import log_audit, require_admin
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.entities import (
    AcademicProject,
    AuditLog,
    CommunityPost,
    Document,
    GenerationJob,
    MediaAsset,
    ProviderConfig,
    Report,
    UsageRecord,
    User,
    UserProfile,
)

router = APIRouter(prefix="/admin", tags=["Administration Console"])


class UserAdminUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(student|moderator|admin)$")
    is_suspended: bool | None = None
    suspension_reason: str | None = None
    is_active: bool | None = None


class ProviderConfigUpsertRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    category: str = Field(pattern="^(ai|image|video|research)$")
    endpoint_url: str | None = None
    model_identifier: str | None = None
    api_key: str | None = None  # Encrypted at rest; never returned raw
    is_enabled: bool = True
    is_primary: bool = False
    extra_config: dict[str, Any] = Field(default_factory=dict)


class ReportResolveRequest(BaseModel):
    status: str = Field(pattern="^(resolved|dismissed)$")
    resolution_notes: str | None = None
    hide_target_post: bool = False


@router.get("/overview")
async def admin_overview(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_users = int((await db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))).scalar() or 0)
    suspended_users = int((await db.execute(select(func.count(User.id)).where(User.is_suspended.is_(True)))).scalar() or 0)
    total_projects = int((await db.execute(select(func.count(AcademicProject.id)).where(AcademicProject.deleted_at.is_(None)))).scalar() or 0)
    total_documents = int((await db.execute(select(func.count(Document.id)).where(Document.deleted_at.is_(None)))).scalar() or 0)
    total_storage_bytes = int((await db.execute(select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(MediaAsset.deleted_at.is_(None)))).scalar() or 0)
    open_reports = int((await db.execute(select(func.count(Report.id)).where(Report.status == "open"))).scalar() or 0)
    failed_jobs = int((await db.execute(select(func.count(GenerationJob.id)).where(GenerationJob.status == "failed"))).scalar() or 0)
    total_jobs = int((await db.execute(select(func.count(GenerationJob.id)))).scalar() or 0)

    usage_breakdown = (
        await db.execute(
            select(UsageRecord.resource_type, func.coalesce(func.sum(UsageRecord.quantity), 0)).group_by(
                UsageRecord.resource_type
            )
        )
    ).all()

    return {
        "metrics": {
            "total_users": total_users,
            "suspended_users": suspended_users,
            "total_projects": total_projects,
            "total_documents": total_documents,
            "total_storage_bytes": total_storage_bytes,
            "open_reports": open_reports,
            "total_jobs": total_jobs,
            "failed_jobs": failed_jobs,
        },
        "usage_analytics": {row[0]: int(row[1]) for row in usage_breakdown},
    }


@router.get("/users")
async def admin_list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(User, UserProfile)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "full_name": p.full_name if p else "",
                "university": p.university if p else None,
                "role": u.role,
                "is_verified": u.is_verified,
                "is_active": u.is_active,
                "is_suspended": u.is_suspended,
                "suspension_reason": u.suspension_reason,
                "created_at": u.created_at.isoformat(),
            }
            for u, p in rows
        ]
    }


@router.patch("/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: UserAdminUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target:
        raise NotFoundError("User")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    await log_audit(db, admin.id, "admin.update_user", "user", target.id, details=body.model_dump(exclude_unset=True))
    await db.commit()
    return {
        "user": {
            "id": target.id,
            "email": target.email,
            "role": target.role,
            "is_suspended": target.is_suspended,
            "suspension_reason": target.suspension_reason,
        }
    }


@router.get("/providers")
async def admin_list_providers(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(ProviderConfig).order_by(ProviderConfig.category, ProviderConfig.name))).scalars().all()
    return {
        "providers": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "endpoint_url": p.endpoint_url,
                "model_identifier": p.model_identifier,
                "has_api_key": bool(p.encrypted_api_key),
                "masked_api_key": mask_secret(decrypt_secret(p.encrypted_api_key or "")) if p.encrypted_api_key else "",
                "is_enabled": p.is_enabled,
                "is_primary": p.is_primary,
                "extra_config": p.extra_config,
            }
            for p in rows
        ]
    }


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def admin_upsert_provider(
    body: ProviderConfigUpsertRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(ProviderConfig).where(ProviderConfig.name == body.name))).scalar_one_or_none()
    if not cfg:
        cfg = ProviderConfig(name=body.name, category=body.category)
        db.add(cfg)
    cfg.category = body.category
    cfg.endpoint_url = body.endpoint_url
    cfg.model_identifier = body.model_identifier
    cfg.is_enabled = body.is_enabled
    cfg.is_primary = body.is_primary
    cfg.extra_config = body.extra_config
    if body.api_key:
        cfg.encrypted_api_key = encrypt_secret(body.api_key)
    await db.flush()
    await log_audit(db, admin.id, "admin.upsert_provider", "provider_config", cfg.id, details={"name": cfg.name, "category": cfg.category})
    await db.commit()
    return {
        "provider": {
            "id": cfg.id,
            "name": cfg.name,
            "category": cfg.category,
            "model_identifier": cfg.model_identifier,
            "has_api_key": bool(cfg.encrypted_api_key),
            "is_enabled": cfg.is_enabled,
        }
    }


@router.delete("/providers/{provider_id}")
async def admin_delete_provider(
    provider_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(ProviderConfig).where(ProviderConfig.id == provider_id))).scalar_one_or_none()
    if not cfg:
        raise NotFoundError("Provider configuration")
    name = cfg.name
    await db.delete(cfg)
    await log_audit(db, admin.id, "admin.delete_provider", "provider_config", provider_id, details={"name": name})
    await db.commit()
    return {"deleted": True, "name": name}


@router.get("/jobs")
async def admin_list_jobs(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs = (
        await db.execute(select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(60))
    ).scalars().all()
    return {
        "jobs": [
            {
                "id": j.id,
                "user_id": j.user_id,
                "job_type": j.job_type,
                "provider": j.provider,
                "status": j.status,
                "progress_percent": j.progress_percent,
                "error_code": j.error_code,
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ]
    }


@router.get("/reports")
async def admin_list_reports(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Report).order_by(Report.created_at.desc()).limit(60))).scalars().all()
    return {
        "reports": [
            {
                "id": r.id,
                "reporter_id": r.reporter_id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "reason": r.reason,
                "details": r.details,
                "status": r.status,
                "resolution_notes": r.resolution_notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.patch("/reports/{report_id}")
async def admin_resolve_report(
    report_id: str,
    body: ReportResolveRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rep = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not rep:
        raise NotFoundError("Report")
    rep.status = body.status
    rep.resolved_by = admin.id
    rep.resolution_notes = body.resolution_notes
    if body.hide_target_post and rep.target_type == "community_post":
        post = (await db.execute(select(CommunityPost).where(CommunityPost.id == rep.target_id))).scalar_one_or_none()
        if post:
            post.moderation_status = "hidden"
    await log_audit(db, admin.id, "admin.resolve_report", "report", rep.id, details={"status": body.status})
    await db.commit()
    return {"report": {"id": rep.id, "status": rep.status}}


@router.get("/audit-logs")
async def admin_list_audit_logs(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    logs = (
        await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))
    ).scalars().all()
    return {
        "audit_logs": [
            {
                "id": a.id,
                "actor_id": a.actor_id,
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "ip_address": a.ip_address,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            }
            for a in logs
        ]
    }
