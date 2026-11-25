"""File Management & Signed Object Storage Downloads."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    get_current_user,
    get_default_workspace,
    log_audit,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import create_signed_download_token, verify_signed_download_token
from app.models.entities import MediaAsset, ProjectContext, User, UserSettings
from app.services.storage_service import storage_service

router = APIRouter(prefix="/files", tags=["File Management"])


def _serialize_asset(a: MediaAsset) -> dict:
    sig, exp = create_signed_download_token(a.id, a.owner_id, ttl_seconds=1800)
    return {
        "id": a.id,
        "filename": a.filename,
        "original_filename": a.original_filename,
        "mime_type": a.mime_type,
        "asset_type": a.asset_type,
        "size_bytes": a.size_bytes,
        "project_id": a.project_id,
        "workspace_id": a.workspace_id,
        "sha256_hash": a.sha256_hash,
        "has_extracted_text": bool(a.extracted_text),
        "extracted_preview": (a.extracted_text or "")[:300] if a.extracted_text else None,
        "metadata": a.extra_metadata,
        "download_url": f"{settings.api_v1_prefix}/files/{a.id}/download?uid={a.owner_id}&exp={exp}&sig={sig}",
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
async def list_files(
    project_id: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MediaAsset).where(
        MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
    )
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = stmt.where(MediaAsset.project_id == project_id)
    if asset_type:
        stmt = stmt.where(MediaAsset.asset_type == asset_type)
    rows = (await db.execute(stmt.order_by(MediaAsset.created_at.desc()).limit(100))).scalars().all()

    used = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
                    MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
                )
            )
        ).scalar()
        or 0
    )
    usettings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    quota = usettings.storage_quota_bytes if usettings else settings.default_quota_bytes

    return {
        "files": [_serialize_asset(a) for a in rows],
        "storage": {"used_bytes": used, "quota_bytes": quota},
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    add_to_project_context: bool = Form(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws_id: str
    if project_id:
        proj = await ensure_project_access(db, project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    content = await file.read()
    asset = await storage_service.save_asset(
        db=db,
        owner_id=user.id,
        filename=file.filename or "upload.bin",
        content=content,
        workspace_id=ws_id,
        project_id=project_id,
    )

    if project_id and add_to_project_context and asset.extracted_text:
        db.add(
            ProjectContext(
                project_id=project_id,
                owner_id=user.id,
                source_type="file",
                source_id=asset.id,
                title=asset.original_filename,
                content_excerpt=asset.extracted_text[:20000],
                include_in_ai_context=True,
                token_estimate=max(1, len(asset.extracted_text[:20000]) // 4),
            )
        )

    await log_audit(db, user.id, "file.upload", "media_asset", asset.id, details={"size_bytes": asset.size_bytes})
    await db.commit()
    return {"file": _serialize_asset(asset)}


@router.get("/{asset_id}/signed-url")
async def get_signed_url(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id, MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise NotFoundError("File asset")
    sig, exp = create_signed_download_token(asset.id, user.id, ttl_seconds=900)
    return {
        "download_url": f"{settings.api_v1_prefix}/files/{asset.id}/download?uid={user.id}&exp={exp}&sig={sig}",
        "expires_at": exp,
    }


@router.get("/{asset_id}/download")
async def download_file(
    asset_id: str,
    uid: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not verify_signed_download_token(asset_id, uid, exp, sig):
        raise ForbiddenError("Signed download link is invalid or expired.")
    asset = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id, MediaAsset.owner_id == uid, MediaAsset.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise NotFoundError("File asset")
    raw = storage_service.get_bytes(asset.storage_key, asset.storage_backend)
    return Response(
        content=raw,
        media_type=asset.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{asset.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{asset_id}")
async def delete_file(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = (
        await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id, MediaAsset.owner_id == user.id, MediaAsset.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not asset:
        raise NotFoundError("File asset")
    storage_service.delete_object(asset.storage_key, asset.storage_backend)
    asset.deleted_at = datetime.now(timezone.utc)
    await log_audit(db, user.id, "file.delete", "media_asset", asset.id)
    await db.commit()
    return {"deleted": True}
