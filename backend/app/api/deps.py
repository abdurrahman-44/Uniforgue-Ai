"""Shared API dependencies: Auth, RBAC, Workspace/Project isolation, Audit Logs, WebSockets."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Request, WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_token
from app.models.entities import (
    AcademicProject,
    AuditLog,
    Notification,
    User,
    UserSession,
    Workspace,
    WorkspaceMember,
)


class ConnectionManager:
    """Manages per-user WebSocket connections for live notifications and job progress."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        if websocket in self._connections[user_id]:
            self._connections[user_id].remove(websocket)

    async def send_to_user(self, user_id: str, event: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


ws_manager = ConnectionManager()


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    cookie_token = request.cookies.get("uniforge_access_token")
    if cookie_token:
        return cookie_token
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_token(request)
    if not token:
        raise UnauthorizedError("Missing authentication credentials.")

    try:
        payload = decode_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired access token.")

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type.")

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise UnauthorizedError("Malformed authentication token.")

    sess = (
        await db.execute(select(UserSession).where(UserSession.id == session_id))
    ).scalar_one_or_none()
    if not sess or sess.revoked_at is not None:
        raise UnauthorizedError("Session has been revoked.")

    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("Account is inactive or deleted.")
    if user.is_suspended:
        raise ForbiddenError(f"Account suspended: {user.suspension_reason or 'Policy violation'}")

    request.state.session_id = session_id
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise ForbiddenError("Administrator privileges required.")
    return user


async def require_moderator_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"admin", "moderator"}:
        raise ForbiddenError("Moderator or administrator privileges required.")
    return user


async def ensure_workspace_access(
    db: AsyncSession,
    workspace_id: str,
    user: User,
    require_write: bool = False,
) -> Workspace:
    ws = (
        await db.execute(
            select(Workspace).where(Workspace.id == workspace_id, Workspace.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not ws:
        raise NotFoundError("Workspace")

    if ws.owner_id == user.id:
        return ws

    membership = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise ForbiddenError("You do not have access to this workspace.")
    if require_write and membership.role == "viewer":
        raise ForbiddenError("Viewer role cannot modify resources in this workspace.")
    return ws


async def ensure_project_access(
    db: AsyncSession,
    project_id: str,
    user: User,
    require_write: bool = False,
) -> AcademicProject:
    proj = (
        await db.execute(
            select(AcademicProject).where(
                AcademicProject.id == project_id, AcademicProject.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not proj:
        raise NotFoundError("Academic project")
    await ensure_workspace_access(db, proj.workspace_id, user, require_write=require_write)
    return proj


async def get_default_workspace(db: AsyncSession, user: User) -> Workspace:
    ws = (
        await db.execute(
            select(Workspace)
            .where(Workspace.owner_id == user.id, Workspace.deleted_at.is_(None))
            .order_by(Workspace.is_personal.desc(), Workspace.created_at.asc())
        )
    ).scalars().first()
    if not ws:
        ws = Workspace(
            owner_id=user.id,
            name="Personal Academic Workspace",
            slug=f"personal-{user.id[:8]}",
            description="Default private academic workspace",
            visibility="private",
            is_personal=True,
        )
        db.add(ws)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
        await db.flush()
    return ws


async def log_audit(
    db: AsyncSession,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details or {},
    )
    db.add(entry)
    await db.flush()
    return entry


async def push_notification(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    category: str = "system",
    action_url: str | None = None,
) -> Notification:
    note = Notification(
        user_id=user_id,
        category=category,
        title=title,
        message=message,
        action_url=action_url,
    )
    db.add(note)
    await db.flush()
    await ws_manager.send_to_user(
        user_id,
        {
            "type": "notification",
            "data": {
                "id": note.id,
                "category": note.category,
                "title": note.title,
                "message": note.message,
                "action_url": note.action_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    return note
