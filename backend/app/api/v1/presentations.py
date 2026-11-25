"""Module E — Presentation Studio (Slide Editor, Document/PDF-to-Deck, Real PPTX & PDF Export)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
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
from app.core.rate_limit import enforce_fair_use, record_usage
from app.models.entities import (
    Document,
    MediaAsset,
    Presentation,
    PresentationSlide,
    ResearchSource,
    User,
)
from app.services.presentation_service import (
    THEMES,
    build_slides_from_source,
    export_presentation_pdf,
    export_presentation_pptx,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/presentations", tags=["Presentation Studio"])


class SlideInput(BaseModel):
    layout: str = "title_and_bullets"
    title: str = Field(min_length=1, max_length=255)
    bullets: list[str] = Field(default_factory=list)
    body_text: str = ""
    speaker_notes: str = ""
    image_asset_id: str | None = None
    chart_data: dict[str, Any] | None = None


class PresentationCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    subtitle: str | None = None
    theme: str = "academic_navy"
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|4:3)$")
    project_id: str | None = None
    source_prompt: str | None = None
    source_document_id: str | None = None
    source_asset_id: str | None = None
    source_research_ids: list[str] = Field(default_factory=list)
    slide_count: int = Field(default=6, ge=2, le=25)
    slides: list[SlideInput] | None = None


class PresentationUpdateRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    theme: str | None = None
    aspect_ratio: str | None = None


class SlideReorderRequest(BaseModel):
    slide_ids: list[str]


def _serialize_slide(s: PresentationSlide) -> dict[str, Any]:
    return {
        "id": s.id,
        "order_index": s.order_index,
        "layout": s.layout,
        "title": s.title,
        "bullets": s.bullets,
        "body_text": s.body_text,
        "speaker_notes": s.speaker_notes,
        "image_asset_id": s.image_asset_id,
        "chart_data": s.chart_data,
    }


@router.get("/themes")
async def list_themes():
    return {"themes": list(THEMES.keys())}


@router.get("")
async def list_presentations(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Presentation).where(Presentation.owner_id == user.id, Presentation.deleted_at.is_(None))
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = stmt.where(Presentation.project_id == project_id)
    rows = (await db.execute(stmt.order_by(Presentation.updated_at.desc()))).scalars().all()
    return {
        "presentations": [
            {
                "id": p.id,
                "project_id": p.project_id,
                "title": p.title,
                "subtitle": p.subtitle,
                "theme": p.theme,
                "aspect_ratio": p.aspect_ratio,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_presentation(
    body: PresentationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    source_chunks: list[str] = []
    if body.source_prompt:
        source_chunks.append(body.source_prompt)
    if body.source_document_id:
        doc = (
            await db.execute(
                select(Document).where(Document.id == body.source_document_id, Document.owner_id == user.id)
            )
        ).scalar_one_or_none()
        if doc:
            source_chunks.append(doc.content_markdown)
    if body.source_asset_id:
        asset = (
            await db.execute(
                select(MediaAsset).where(MediaAsset.id == body.source_asset_id, MediaAsset.owner_id == user.id)
            )
        ).scalar_one_or_none()
        if asset and asset.extracted_text:
            source_chunks.append(asset.extracted_text)
    if body.source_research_ids:
        sources = (
            await db.execute(
                select(ResearchSource).where(
                    ResearchSource.id.in_(body.source_research_ids), ResearchSource.owner_id == user.id
                )
            )
        ).scalars().all()
        for src in sources:
            source_chunks.append(f"## {src.title}\n- Authors: {', '.join(src.authors)}\n- Year: {src.year}\n- {src.abstract or src.notes or 'Verified research source'}")

    prs = Presentation(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        title=body.title.strip(),
        subtitle=body.subtitle,
        theme=body.theme if body.theme in THEMES else "academic_navy",
        aspect_ratio=body.aspect_ratio,
    )
    db.add(prs)
    await db.flush()

    if body.slides:
        slide_specs = [s.model_dump() for s in body.slides]
    else:
        slide_specs = build_slides_from_source(body.title, "\n\n".join(source_chunks), slide_count=body.slide_count)

    created_slides: list[PresentationSlide] = []
    for idx, spec in enumerate(slide_specs):
        sl = PresentationSlide(
            presentation_id=prs.id,
            order_index=idx,
            layout=spec.get("layout", "title_and_bullets"),
            title=spec.get("title", f"Slide {idx + 1}"),
            bullets=spec.get("bullets", []),
            body_text=spec.get("body_text", ""),
            speaker_notes=spec.get("speaker_notes", ""),
            image_asset_id=spec.get("image_asset_id"),
            chart_data=spec.get("chart_data"),
        )
        db.add(sl)
        created_slides.append(sl)

    await db.flush()
    await log_audit(db, user.id, "presentation.create", "presentation", prs.id)
    await db.commit()
    return {
        "presentation": {
            "id": prs.id,
            "title": prs.title,
            "subtitle": prs.subtitle,
            "theme": prs.theme,
            "aspect_ratio": prs.aspect_ratio,
            "slides": [_serialize_slide(s) for s in created_slides],
        }
    }


@router.get("/{presentation_id}")
async def get_presentation(
    presentation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    slides = (
        await db.execute(
            select(PresentationSlide)
            .where(PresentationSlide.presentation_id == prs.id)
            .order_by(PresentationSlide.order_index.asc())
        )
    ).scalars().all()
    return {
        "presentation": {
            "id": prs.id,
            "project_id": prs.project_id,
            "title": prs.title,
            "subtitle": prs.subtitle,
            "theme": prs.theme,
            "aspect_ratio": prs.aspect_ratio,
            "slides": [_serialize_slide(s) for s in slides],
        }
    }


@router.patch("/{presentation_id}")
async def update_presentation(
    presentation_id: str,
    body: PresentationUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(prs, k, v)
    await db.commit()
    return {"presentation": {"id": prs.id, "title": prs.title, "theme": prs.theme, "aspect_ratio": prs.aspect_ratio}}


@router.post("/{presentation_id}/slides", status_code=status.HTTP_201_CREATED)
async def add_slide(
    presentation_id: str,
    body: SlideInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    existing = (
        await db.execute(select(PresentationSlide).where(PresentationSlide.presentation_id == prs.id))
    ).scalars().all()
    sl = PresentationSlide(
        presentation_id=prs.id,
        order_index=len(existing),
        **body.model_dump(),
    )
    db.add(sl)
    await db.commit()
    return {"slide": _serialize_slide(sl)}


@router.patch("/{presentation_id}/slides/{slide_id}")
async def update_slide(
    presentation_id: str,
    slide_id: str,
    body: SlideInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    sl = (
        await db.execute(
            select(PresentationSlide).where(
                PresentationSlide.id == slide_id, PresentationSlide.presentation_id == prs.id
            )
        )
    ).scalar_one_or_none()
    if not sl:
        raise NotFoundError("Slide")
    for k, v in body.model_dump().items():
        setattr(sl, k, v)
    await db.commit()
    return {"slide": _serialize_slide(sl)}


@router.post("/{presentation_id}/reorder")
async def reorder_slides(
    presentation_id: str,
    body: SlideReorderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    slides = (
        await db.execute(select(PresentationSlide).where(PresentationSlide.presentation_id == prs.id))
    ).scalars().all()
    by_id = {s.id: s for s in slides}
    for idx, sid in enumerate(body.slide_ids):
        if sid in by_id:
            by_id[sid].order_index = idx
    await db.commit()
    return {"reordered": True}


@router.delete("/{presentation_id}/slides/{slide_id}")
async def delete_slide(
    presentation_id: str,
    slide_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    sl = (
        await db.execute(
            select(PresentationSlide).where(
                PresentationSlide.id == slide_id, PresentationSlide.presentation_id == prs.id
            )
        )
    ).scalar_one_or_none()
    if not sl:
        raise NotFoundError("Slide")
    await db.delete(sl)
    await db.commit()
    return {"deleted": True}


@router.get("/{presentation_id}/export")
async def export_presentation(
    presentation_id: str,
    format: str = Query(default="pptx", pattern="^(pptx|pdf)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real python-pptx PowerPoint export and ReportLab PDF slide deck export."""
    await enforce_fair_use(db, user.id, "document_export", user.role)
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    slides = (
        await db.execute(
            select(PresentationSlide)
            .where(PresentationSlide.presentation_id == prs.id)
            .order_by(PresentationSlide.order_index.asc())
        )
    ).scalars().all()
    slides_data = [_serialize_slide(s) for s in slides]

    # Load any referenced user-owned slide images
    img_ids = [s["image_asset_id"] for s in slides_data if s.get("image_asset_id")]
    image_lookup: dict[str, bytes] = {}
    if img_ids:
        assets = (
            await db.execute(
                select(MediaAsset).where(MediaAsset.id.in_(img_ids), MediaAsset.owner_id == user.id)
            )
        ).scalars().all()
        for a in assets:
            try:
                image_lookup[a.id] = storage_service.get_bytes(a.storage_key, a.storage_backend)
            except Exception:
                pass

    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in prs.title)[:80] or "presentation"
    if format == "pptx":
        content = export_presentation_pptx(
            prs.title, prs.subtitle, prs.theme, slides_data, prs.aspect_ratio, image_lookup
        )
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ext = "pptx"
    else:
        content = export_presentation_pdf(prs.title, prs.theme, slides_data)
        media_type = "application/pdf"
        ext = "pdf"

    await record_usage(db, user.id, "document_export", metadata={"presentation_id": prs.id, "format": format})
    await log_audit(db, user.id, "presentation.export", "presentation", prs.id, details={"format": format})
    await db.commit()
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_slug}.{ext}"'},
    )


@router.delete("/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prs = (
        await db.execute(
            select(Presentation).where(
                Presentation.id == presentation_id, Presentation.owner_id == user.id, Presentation.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not prs:
        raise NotFoundError("Presentation")
    prs.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"deleted": True}
