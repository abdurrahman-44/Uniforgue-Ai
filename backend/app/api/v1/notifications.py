"""Notifications REST & Real-Time WebSocket Stream."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, ws_manager
from app.core.database import get_db
from app.core.security import decode_token
from app.models.entities import Notification, User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = (await db.execute(stmt.order_by(Notification.created_at.desc()).limit(50))).scalars().all()
    return {
        "notifications": [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "message": n.message,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "unread_count": sum(1 for n in rows if not n.is_read),
    }


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if note:
        note.is_read = True
        await db.commit()
    return {"read": True}


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.user_id == user.id, Notification.is_read.is_(False)
            )
        )
    ).scalars().all()
    for n in rows:
        n.is_read = True
    await db.commit()
    return {"updated": len(rows)}


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str = Query(default="")):
    user_id = None
    try:
        if token:
            payload = decode_token(token)
            if payload.get("type") == "access":
                user_id = payload.get("sub")
    except Exception:
        user_id = None

    if not user_id:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(user_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "user_id": user_id})
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
