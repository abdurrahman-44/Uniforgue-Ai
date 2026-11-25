"""Module K — Community (Private-by-Default Publishing, Licensing, Ratings, Reports)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, log_audit
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.entities import CommunityPost, Report, User, UserProfile

router = APIRouter(prefix="/community", tags=["Community"])


class CommunityPostCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    category: str = Field(pattern="^(template|resource|diagram|study_material|showcase)$")
    summary: str = Field(min_length=10, max_length=1000)
    content_markdown: str = Field(default="", max_length=30000)
    tags: list[str] = Field(default_factory=list)
    license_name: str = Field(default="CC-BY-4.0", pattern="^(CC-BY-4.0|CC0-1.0|MIT|Apache-2.0|All-Rights-Reserved)$")
    publish_now: bool = False  # Private by default; user must explicitly publish


class RatePostRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class ReportCreateRequest(BaseModel):
    target_type: str = Field(default="community_post", pattern="^(community_post|template|user)$")
    target_id: str
    reason: str = Field(min_length=3, max_length=128)
    details: str | None = Field(default=None, max_length=2000)


def _serialize_post(p: CommunityPost, author_name: str) -> dict[str, Any]:
    avg_rating = round(p.rating_sum / p.rating_count, 2) if p.rating_count > 0 else 0.0
    return {
        "id": p.id,
        "author_id": p.author_id,
        "author_name": author_name,
        "title": p.title,
        "category": p.category,
        "summary": p.summary,
        "content_markdown": p.content_markdown,
        "tags": p.tags,
        "license_name": p.license_name,
        "is_published": p.is_published,
        "moderation_status": p.moderation_status,
        "average_rating": avg_rating,
        "rating_count": p.rating_count,
        "created_at": p.created_at.isoformat(),
    }


@router.get("/posts")
async def list_community_posts(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    mine_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns ONLY explicitly published & approved posts to other users; drafts visible solely to author."""
    stmt = (
        select(CommunityPost, UserProfile.full_name)
        .outerjoin(UserProfile, UserProfile.user_id == CommunityPost.author_id)
        .where(CommunityPost.deleted_at.is_(None))
    )
    if mine_only:
        stmt = stmt.where(CommunityPost.author_id == user.id)
    else:
        stmt = stmt.where(
            CommunityPost.is_published.is_(True),
            CommunityPost.moderation_status == "approved",
        )
    if category:
        stmt = stmt.where(CommunityPost.category == category)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(CommunityPost.title.ilike(like), CommunityPost.summary.ilike(like)))

    rows = (await db.execute(stmt.order_by(CommunityPost.created_at.desc()).limit(60))).all()
    return {"posts": [_serialize_post(p, name or "Student") for p, name in rows]}


@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_community_post(
    body: CommunityPostCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = CommunityPost(
        author_id=user.id,
        title=body.title.strip(),
        category=body.category,
        summary=body.summary.strip(),
        content_markdown=body.content_markdown,
        tags=[t.strip().lower() for t in body.tags if t.strip()][:10],
        license_name=body.license_name,
        is_published=body.publish_now,
        moderation_status="approved",
    )
    db.add(post)
    await db.flush()
    await log_audit(db, user.id, "community.create_post", "community_post", post.id, details={"published": post.is_published})
    await db.commit()
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    return {"post": _serialize_post(post, profile.full_name if profile else "Student")}


@router.post("/posts/{post_id}/publish")
async def toggle_publish(
    post_id: str,
    publish: bool = Query(default=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = (
        await db.execute(
            select(CommunityPost).where(CommunityPost.id == post_id, CommunityPost.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not post:
        raise NotFoundError("Community post")
    if post.author_id != user.id:
        raise ForbiddenError("Only the owner can change publication visibility.")
    post.is_published = publish
    await db.commit()
    return {"id": post.id, "is_published": post.is_published}


@router.post("/posts/{post_id}/rate")
async def rate_post(
    post_id: str,
    body: RatePostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = (
        await db.execute(
            select(CommunityPost).where(
                CommunityPost.id == post_id,
                CommunityPost.is_published.is_(True),
                CommunityPost.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not post:
        raise NotFoundError("Published community post")
    ratings = dict(post.ratings_by_user or {})
    ratings[user.id] = body.rating
    post.ratings_by_user = ratings
    post.rating_count = len(ratings)
    post.rating_sum = sum(ratings.values())
    await db.commit()
    return {
        "id": post.id,
        "average_rating": round(post.rating_sum / post.rating_count, 2),
        "rating_count": post.rating_count,
    }


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ReportCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rep = Report(
        reporter_id=user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason.strip(),
        details=body.details,
        status="open",
    )
    db.add(rep)
    await db.flush()
    await log_audit(db, user.id, "community.report", body.target_type, body.target_id)
    await db.commit()
    return {"report": {"id": rep.id, "status": rep.status, "created_at": rep.created_at.isoformat()}}


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = (
        await db.execute(
            select(CommunityPost).where(CommunityPost.id == post_id, CommunityPost.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not post:
        raise NotFoundError("Community post")
    if post.author_id != user.id and user.role not in {"admin", "moderator"}:
        raise ForbiddenError("Not authorized to delete this post.")
    post.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"deleted": True}
