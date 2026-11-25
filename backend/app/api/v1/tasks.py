"""Academic Tasks & Assignment Deadlines Management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    get_current_user,
    get_default_workspace,
    log_audit,
)
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import Task, User

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    project_id: str | None = None
    status: str = Field(default="todo", pattern="^(todo|in_progress|done)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: datetime | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(todo|in_progress|done)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    due_date: datetime | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)


def _serialize_task(t: Task) -> dict:
    return {
        "id": t.id,
        "workspace_id": t.workspace_id,
        "project_id": t.project_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "progress_percent": t.progress_percent,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "created_at": t.created_at.isoformat(),
    }


@router.get("")
async def list_tasks(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task).where(Task.owner_id == user.id, Task.deleted_at.is_(None))
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = select(Task).where(Task.project_id == project_id, Task.deleted_at.is_(None))
    rows = (await db.execute(stmt.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc()))).scalars().all()
    return {"tasks": [_serialize_task(t) for t in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    task = Task(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        title=body.title.strip(),
        description=body.description,
        status=body.status,
        priority=body.priority,
        due_date=body.due_date,
        progress_percent=100 if body.status == "done" else body.progress_percent,
    )
    db.add(task)
    await db.flush()
    await log_audit(db, user.id, "task.create", "task", task.id)
    await db.commit()
    return {"task": _serialize_task(task)}


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = (
        await db.execute(
            select(Task).where(Task.id == task_id, Task.owner_id == user.id, Task.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    if body.status == "done" and body.progress_percent is None:
        task.progress_percent = 100
    await db.commit()
    return {"task": _serialize_task(task)}


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = (
        await db.execute(
            select(Task).where(Task.id == task_id, Task.owner_id == user.id, Task.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task")
    task.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"deleted": True}
