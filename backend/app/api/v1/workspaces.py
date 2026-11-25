"""Workspace Management & Team Membership."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_workspace_access, get_current_user, log_audit, push_notification
from app.core.database import get_db
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.entities import User, Workspace, WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    is_personal: bool = False


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class MemberAddRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="editor", pattern="^(editor|viewer)$")


@router.get("")
async def list_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_ws_ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    rows = (
        await db.execute(
            select(Workspace)
            .where(
                Workspace.deleted_at.is_(None),
                or_(Workspace.owner_id == user.id, Workspace.id.in_(member_ws_ids)),
            )
            .order_by(Workspace.is_personal.desc(), Workspace.created_at.asc())
        )
    ).scalars().all()
    return {
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "slug": w.slug,
                "description": w.description,
                "visibility": w.visibility,
                "is_personal": w.is_personal,
                "owner_id": w.owner_id,
                "created_at": w.created_at.isoformat(),
            }
            for w in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    body: WorkspaceCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-") or "workspace"
    ws = Workspace(
        owner_id=user.id,
        name=body.name.strip(),
        slug=f"{base_slug[:60]}-{uuid.uuid4().hex[:6]}",
        description=body.description,
        visibility="private",
        is_personal=body.is_personal,
    )
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    await log_audit(db, user.id, "workspace.create", "workspace", ws.id)
    await db.commit()
    return {
        "workspace": {
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "visibility": ws.visibility,
            "is_personal": ws.is_personal,
            "owner_id": ws.owner_id,
            "created_at": ws.created_at.isoformat(),
        }
    }


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await ensure_workspace_access(db, workspace_id, user)
    members = (
        await db.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == ws.id)
        )
    ).all()
    return {
        "workspace": {
            "id": ws.id,
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "visibility": ws.visibility,
            "is_personal": ws.is_personal,
            "owner_id": ws.owner_id,
            "members": [
                {"user_id": u.id, "email": u.email, "role": m.role} for m, u in members
            ],
        }
    }


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await ensure_workspace_access(db, workspace_id, user, require_write=True)
    if ws.owner_id != user.id:
        raise ForbiddenError("Only the workspace owner can modify workspace settings.")
    if body.name is not None:
        ws.name = body.name.strip()
    if body.description is not None:
        ws.description = body.description
    await log_audit(db, user.id, "workspace.update", "workspace", ws.id)
    await db.commit()
    return {"workspace": {"id": ws.id, "name": ws.name, "description": ws.description}}


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: str,
    body: MemberAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await ensure_workspace_access(db, workspace_id, user, require_write=True)
    if ws.owner_id != user.id:
        raise ForbiddenError("Only the workspace owner can invite team members.")
    target = (
        await db.execute(
            select(User).where(User.email == body.email.lower().strip(), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not target:
        raise NotFoundError("Invited user")
    exists = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id, WorkspaceMember.user_id == target.id
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise ConflictError("User is already a member of this workspace.")

    member = WorkspaceMember(workspace_id=ws.id, user_id=target.id, role=body.role)
    db.add(member)
    await push_notification(
        db,
        target.id,
        title=f"Added to workspace '{ws.name}'",
        message=f"You have been granted {body.role} access to workspace '{ws.name}'.",
        category="workspace",
        action_url="/workspaces",
    )
    await log_audit(db, user.id, "workspace.add_member", "workspace", ws.id, details={"member_id": target.id, "role": body.role})
    await db.commit()
    return {"member": {"user_id": target.id, "email": target.email, "role": member.role}}


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await ensure_workspace_access(db, workspace_id, user, require_write=True)
    if ws.owner_id != user.id:
        raise ForbiddenError("Only the workspace owner can delete a workspace.")
    ws.deleted_at = datetime.now(timezone.utc)
    await log_audit(db, user.id, "workspace.delete", "workspace", ws.id)
    await db.commit()
    return {"deleted": True}
