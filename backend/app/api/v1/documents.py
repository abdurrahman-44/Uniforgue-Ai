"""Module D — Academic Document Studio & Assignment Requirement Analyzer."""

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
from app.models.entities import Citation, Document, DocumentVersion, MediaAsset, User
from app.services.document_service import (
    CITATION_STYLES,
    DOCUMENT_TYPE_TEMPLATES,
    analyze_assignment_brief,
    build_template_markdown,
    count_words,
    export_document_docx,
    export_document_markdown,
    export_document_pdf,
    render_markdown_to_html,
)
from app.services.storage_service import storage_service

router = APIRouter(prefix="/documents", tags=["Academic Document Studio"])


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    doc_type: str = Field(default="assignment", max_length=64)
    citation_style: str = Field(default="APA 7", max_length=32)
    project_id: str | None = None
    content_markdown: str | None = None
    cover_page: dict[str, Any] = Field(default_factory=dict)
    formatting_profile: dict[str, Any] = Field(default_factory=dict)
    use_template: bool = True


class DocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    doc_type: str | None = None
    citation_style: str | None = None
    content_markdown: str | None = None
    sections_json: list[dict[str, Any]] | None = None
    cover_page: dict[str, Any] | None = None
    formatting_profile: dict[str, Any] | None = None
    change_summary: str | None = None
    save_version: bool = True
    expected_version: int | None = None


class AssignmentAnalyzeRequest(BaseModel):
    brief_text: str | None = None
    brief_asset_id: str | None = None
    document_id: str | None = None


def _serialize_doc(d: Document) -> dict[str, Any]:
    return {
        "id": d.id,
        "workspace_id": d.workspace_id,
        "project_id": d.project_id,
        "title": d.title,
        "doc_type": d.doc_type,
        "citation_style": d.citation_style,
        "content_markdown": d.content_markdown,
        "content_html": d.content_html,
        "sections_json": d.sections_json,
        "cover_page": d.cover_page,
        "formatting_profile": d.formatting_profile,
        "word_count": d.word_count,
        "version_number": d.version_number,
        "ai_assisted": d.ai_assisted,
        "assignment_requirements": d.assignment_requirements,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


@router.get("/templates")
async def list_document_templates():
    return {
        "document_types": DOCUMENT_TYPE_TEMPLATES,
        "citation_styles": CITATION_STYLES,
    }


@router.get("")
async def list_documents(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.owner_id == user.id, Document.deleted_at.is_(None))
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = select(Document).where(Document.project_id == project_id, Document.deleted_at.is_(None))
    rows = (await db.execute(stmt.order_by(Document.updated_at.desc()))).scalars().all()
    return {
        "documents": [
            {
                "id": d.id,
                "project_id": d.project_id,
                "title": d.title,
                "doc_type": d.doc_type,
                "citation_style": d.citation_style,
                "word_count": d.word_count,
                "version_number": d.version_number,
                "updated_at": d.updated_at.isoformat(),
            }
            for d in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    md = body.content_markdown
    if md is None:
        md = (
            build_template_markdown(body.title, body.doc_type, body.citation_style)
            if body.use_template
            else f"# {body.title}\n\n"
        )

    doc = Document(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        title=body.title.strip(),
        doc_type=body.doc_type,
        citation_style=body.citation_style,
        content_markdown=md,
        content_html=render_markdown_to_html(md),
        cover_page=body.cover_page or {"enabled": True, "author": user.email},
        formatting_profile=body.formatting_profile or {"page_size": "A4", "font_size": 11, "line_spacing": 1.5, "include_toc": True},
        word_count=count_words(md),
        version_number=1,
    )
    db.add(doc)
    await db.flush()
    db.add(
        DocumentVersion(
            document_id=doc.id,
            created_by=user.id,
            version_number=1,
            title=doc.title,
            content_markdown=doc.content_markdown,
            word_count=doc.word_count,
            change_summary="Initial version",
        )
    )
    await log_audit(db, user.id, "document.create", "document", doc.id)
    await db.commit()
    return {"document": _serialize_doc(doc)}


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")
    citations = (
        await db.execute(select(Citation).where(Citation.document_id == doc.id))
    ).scalars().all()
    return {
        "document": _serialize_doc(doc),
        "citations": [
            {
                "id": c.id,
                "source_id": c.source_id,
                "claim_text": c.claim_text,
                "formatted_inline": c.formatted_inline,
                "formatted_bibliography": c.formatted_bibliography,
            }
            for c in citations
        ],
    }


@router.patch("/{document_id}")
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")

    # Optimistic concurrency guard when caller supplies expected_version
    if body.expected_version is not None and body.expected_version != doc.version_number:
        from app.core.exceptions import ConflictError

        raise ConflictError(
            f"Document was updated concurrently (expected v{body.expected_version}, current v{doc.version_number}). Reload before saving."
        )

    if body.title is not None:
        doc.title = body.title.strip()
    if body.doc_type is not None:
        doc.doc_type = body.doc_type
    if body.citation_style is not None:
        doc.citation_style = body.citation_style
    if body.content_markdown is not None:
        doc.content_markdown = body.content_markdown
        doc.content_html = render_markdown_to_html(body.content_markdown)
        doc.word_count = count_words(body.content_markdown)
    if body.sections_json is not None:
        doc.sections_json = body.sections_json
    if body.cover_page is not None:
        doc.cover_page = body.cover_page
    if body.formatting_profile is not None:
        doc.formatting_profile = body.formatting_profile

    if body.save_version:
        doc.version_number += 1
        db.add(
            DocumentVersion(
                document_id=doc.id,
                created_by=user.id,
                version_number=doc.version_number,
                title=doc.title,
                content_markdown=doc.content_markdown,
                sections_json=doc.sections_json,
                word_count=doc.word_count,
                change_summary=body.change_summary or f"Saved version {doc.version_number}",
            )
        )

    await db.commit()
    return {"document": _serialize_doc(doc)}


@router.get("/{document_id}/versions")
async def list_document_versions(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")
    versions = (
        await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
        )
    ).scalars().all()
    return {
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "title": v.title,
                "word_count": v.word_count,
                "change_summary": v.change_summary,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]
    }


@router.post("/{document_id}/versions/{version_id}/restore")
async def restore_document_version(
    document_id: str,
    version_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")
    ver = (
        await db.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id, DocumentVersion.document_id == doc.id
            )
        )
    ).scalar_one_or_none()
    if not ver:
        raise NotFoundError("Document version")

    doc.title = ver.title
    doc.content_markdown = ver.content_markdown
    doc.content_html = render_markdown_to_html(ver.content_markdown)
    doc.word_count = ver.word_count
    doc.version_number += 1
    db.add(
        DocumentVersion(
            document_id=doc.id,
            created_by=user.id,
            version_number=doc.version_number,
            title=doc.title,
            content_markdown=doc.content_markdown,
            word_count=doc.word_count,
            change_summary=f"Restored from version {ver.version_number}",
        )
    )
    await db.commit()
    return {"document": _serialize_doc(doc)}


@router.get("/{document_id}/export")
async def export_document(
    document_id: str,
    format: str = Query(default="pdf", pattern="^(pdf|docx|md)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Real PDF (ReportLab), DOCX (python-docx), and Markdown export."""
    await enforce_fair_use(db, user.id, "document_export", user.role)
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")

    citations = (
        await db.execute(select(Citation).where(Citation.document_id == doc.id))
    ).scalars().all()
    bibliography = [c.formatted_bibliography for c in citations]

    # Resolve any user-owned embedded images referenced via ![Caption](asset://<id>)
    import re as _re

    referenced_ids = list(set(_re.findall(r"asset://([a-zA-Z0-9-]+)", doc.content_markdown or "")))
    image_lookup: dict[str, bytes] = {}
    if referenced_ids:
        img_assets = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(referenced_ids),
                    MediaAsset.owner_id == user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        for a in img_assets:
            try:
                image_lookup[a.id] = storage_service.get_bytes(a.storage_key, a.storage_backend)
            except Exception:
                pass

    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in doc.title)[:80] or "document"

    if format == "pdf":
        data = export_document_pdf(
            title=doc.title,
            content_markdown=doc.content_markdown,
            citation_style=doc.citation_style,
            cover_page=doc.cover_page,
            formatting_profile=doc.formatting_profile,
            bibliography=bibliography,
            image_lookup=image_lookup,
        )
        media_type = "application/pdf"
        ext = "pdf"
    elif format == "docx":
        data = export_document_docx(
            title=doc.title,
            content_markdown=doc.content_markdown,
            citation_style=doc.citation_style,
            cover_page=doc.cover_page,
            formatting_profile=doc.formatting_profile,
            bibliography=bibliography,
            image_lookup=image_lookup,
        )
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ext = "docx"
    else:
        data = export_document_markdown(doc.title, doc.content_markdown, doc.citation_style, bibliography)
        media_type = "text/markdown; charset=utf-8"
        ext = "md"

    await record_usage(db, user.id, "document_export", metadata={"document_id": doc.id, "format": format})
    await log_audit(db, user.id, "document.export", "document", doc.id, details={"format": format})
    await db.commit()

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_slug}.{ext}"'},
    )


@router.post("/analyze-assignment")
async def analyze_assignment(
    body: AssignmentAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assignment Requirement Analyzer: extracts requirements from PDF/DOCX/text & checks draft compliance."""
    brief_text = body.brief_text or ""
    if body.brief_asset_id:
        asset = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id == body.brief_asset_id,
                    MediaAsset.owner_id == user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not asset:
            raise NotFoundError("Assignment brief file")
        brief_text = (asset.extracted_text or "") + ("\n" + brief_text if brief_text else "")

    draft_md = ""
    doc = None
    if body.document_id:
        doc = (
            await db.execute(
                select(Document).where(
                    Document.id == body.document_id,
                    Document.owner_id == user.id,
                    Document.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not doc:
            raise NotFoundError("Document")
        draft_md = doc.content_markdown

    analysis = analyze_assignment_brief(brief_text, draft_md)
    if doc:
        doc.assignment_requirements = analysis
        await db.commit()

    return {"analysis": analysis}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.owner_id == user.id, Document.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise NotFoundError("Document")
    doc.deleted_at = datetime.now(timezone.utc)
    await log_audit(db, user.id, "document.delete", "document", doc.id)
    await db.commit()
    return {"deleted": True}
