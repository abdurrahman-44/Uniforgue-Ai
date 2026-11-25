"""Module F — Research Studio & Citations (Crossref, OpenAlex, Semantic Scholar, Verified Provenance)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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
from app.core.exceptions import AppError, NotFoundError
from app.models.entities import Citation, ResearchSource, User
from app.providers.research_providers import (
    format_citation,
    search_crossref,
    search_openalex,
    search_semantic_scholar,
    verify_doi_crossref,
)

router = APIRouter(tags=["Research Studio & Citations"])


class SourceSaveRequest(BaseModel):
    project_id: str | None = None
    title: str = Field(min_length=2, max_length=500)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1500, le=2100)
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    source_provider: str = "manual"
    external_id: str | None = None
    provenance_status: str = Field(default="retrieved", pattern="^(discovered|retrieved|verified)$")
    citation_count: int | None = None
    notes: str = ""


class SourceNotesUpdateRequest(BaseModel):
    notes: str


class CitationCreateRequest(BaseModel):
    source_id: str
    document_id: str | None = None
    claim_text: str = Field(min_length=2)
    page_range: str | None = None
    citation_style: str = "APA 7"


def _serialize_source(s: ResearchSource) -> dict[str, Any]:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "title": s.title,
        "authors": s.authors,
        "year": s.year,
        "venue": s.venue,
        "doi": s.doi,
        "url": s.url,
        "abstract": s.abstract,
        "source_provider": s.source_provider,
        "external_id": s.external_id,
        "provenance_status": s.provenance_status,
        "citation_count": s.citation_count,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
    }


@router.get("/research/discover")
async def discover_papers(
    q: str = Query(min_length=2, max_length=250),
    provider: str = Query(default="all", pattern="^(all|openalex|crossref|semantic_scholar)$"),
    limit: int = Query(default=8, ge=1, le=20),
    _user: User = Depends(get_current_user),
):
    """Query legitimate scholarly APIs (OpenAlex, Crossref, Semantic Scholar). Never fabricates papers."""
    results: list[dict[str, Any]] = []
    provider_errors: dict[str, str] = {}

    if provider in {"all", "openalex"}:
        try:
            results.extend(await search_openalex(q, limit=limit))
        except Exception as exc:
            provider_errors["openalex"] = f"OpenAlex query unavailable ({type(exc).__name__})"

    if provider in {"all", "crossref"}:
        try:
            results.extend(await search_crossref(q, limit=limit))
        except Exception as exc:
            provider_errors["crossref"] = f"Crossref query unavailable ({type(exc).__name__})"

    if provider in {"all", "semantic_scholar"}:
        try:
            results.extend(await search_semantic_scholar(q, limit=limit))
        except Exception as exc:
            provider_errors["semantic_scholar"] = f"Semantic Scholar query unavailable ({type(exc).__name__})"

    # Deduplicate by DOI or normalized title
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        key = (item.get("doi") or item.get("title", "")).lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    return {
        "query": q,
        "count": len(unique),
        "results": unique[: limit * 2],
        "provider_errors": provider_errors,
        "integrity_notice": "All results come directly from OpenAlex, Crossref, or Semantic Scholar APIs. Verify DOIs before final submission.",
    }


@router.get("/research/verify-doi")
async def verify_doi(
    doi: str = Query(min_length=5, max_length=150),
    _user: User = Depends(get_current_user),
):
    try:
        record = await verify_doi_crossref(doi)
    except Exception as exc:
        raise AppError(
            f"Crossref DOI verification service temporarily unreachable ({type(exc).__name__}).",
            code="DOI_SERVICE_UNAVAILABLE",
            status_code=503,
        )
    if not record:
        return {"verified": False, "doi": doi, "message": "DOI not found in Crossref registry."}
    return record


@router.get("/research/sources")
async def list_sources(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ResearchSource).where(
        ResearchSource.owner_id == user.id, ResearchSource.deleted_at.is_(None)
    )
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = stmt.where(ResearchSource.project_id == project_id)
    rows = (await db.execute(stmt.order_by(ResearchSource.created_at.desc()))).scalars().all()
    return {"sources": [_serialize_source(s) for s in rows]}


@router.post("/research/sources", status_code=status.HTTP_201_CREATED)
async def save_source(
    body: SourceSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    src = ResearchSource(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        title=body.title.strip(),
        authors=body.authors,
        year=body.year,
        venue=body.venue,
        doi=body.doi,
        url=body.url,
        abstract=body.abstract,
        source_provider=body.source_provider,
        external_id=body.external_id,
        provenance_status=body.provenance_status,
        citation_count=body.citation_count,
        notes=body.notes,
    )
    db.add(src)
    await db.flush()
    await log_audit(db, user.id, "research.save_source", "research_source", src.id)
    await db.commit()
    return {"source": _serialize_source(src)}


@router.post("/research/sources/{source_id}/verify")
async def verify_saved_source_doi(
    source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = (
        await db.execute(
            select(ResearchSource).where(
                ResearchSource.id == source_id,
                ResearchSource.owner_id == user.id,
                ResearchSource.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Research source")
    if not src.doi:
        raise AppError("This source has no DOI to verify.", code="NO_DOI", status_code=400)
    rec = await verify_doi_crossref(src.doi)
    if not rec:
        return {"verified": False, "source": _serialize_source(src)}
    src.provenance_status = "verified"
    if rec.get("url"):
        src.url = rec["url"]
    if rec.get("citation_count") is not None:
        src.citation_count = rec["citation_count"]
    await db.commit()
    return {"verified": True, "source": _serialize_source(src)}


@router.patch("/research/sources/{source_id}")
async def update_source_notes(
    source_id: str,
    body: SourceNotesUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = (
        await db.execute(
            select(ResearchSource).where(
                ResearchSource.id == source_id,
                ResearchSource.owner_id == user.id,
                ResearchSource.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Research source")
    src.notes = body.notes
    await db.commit()
    return {"source": _serialize_source(src)}


@router.delete("/research/sources/{source_id}")
async def delete_source(
    source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = (
        await db.execute(
            select(ResearchSource).where(
                ResearchSource.id == source_id,
                ResearchSource.owner_id == user.id,
                ResearchSource.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Research source")
    src.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"deleted": True}


@router.get("/research/literature-matrix")
async def generate_literature_matrix(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build a traceable methodology & gap comparison matrix purely from saved user sources."""
    stmt = select(ResearchSource).where(
        ResearchSource.owner_id == user.id, ResearchSource.deleted_at.is_(None)
    )
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = stmt.where(ResearchSource.project_id == project_id)
    sources = (await db.execute(stmt.order_by(ResearchSource.year.desc().nulls_last()))).scalars().all()
    rows = [
        {
            "source_id": s.id,
            "title": s.title,
            "authors": ", ".join(s.authors) or "Unknown",
            "year": s.year,
            "venue": s.venue or "Unspecified",
            "doi": s.doi,
            "provenance_status": s.provenance_status,
            "summary_excerpt": (s.abstract or s.notes or "Add research notes to compare methodology.")[:260],
        }
        for s in sources
    ]
    return {"count": len(rows), "matrix": rows}


@router.get("/citations")
async def list_citations(
    document_id: str | None = Query(default=None),
    style: str = Query(default="APA 7"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Citation).where(Citation.owner_id == user.id)
    if document_id:
        stmt = stmt.where(Citation.document_id == document_id)
    rows = (await db.execute(stmt.order_by(Citation.created_at.desc()))).scalars().all()
    return {
        "style": style,
        "citations": [
            {
                "id": c.id,
                "source_id": c.source_id,
                "document_id": c.document_id,
                "claim_text": c.claim_text,
                "page_range": c.page_range,
                "citation_style": c.citation_style,
                "formatted_inline": c.formatted_inline,
                "formatted_bibliography": c.formatted_bibliography,
            }
            for c in rows
        ],
        "bibliography": [c.formatted_bibliography for c in rows],
    }


@router.post("/citations", status_code=status.HTTP_201_CREATED)
async def create_citation(
    body: CitationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    src = (
        await db.execute(
            select(ResearchSource).where(
                ResearchSource.id == body.source_id,
                ResearchSource.owner_id == user.id,
                ResearchSource.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not src:
        raise NotFoundError("Research source")

    inline, bib = format_citation(
        title=src.title,
        authors=src.authors,
        year=src.year,
        venue=src.venue,
        doi=src.doi,
        url=src.url,
        style=body.citation_style,
        page_range=body.page_range,
    )
    cit = Citation(
        source_id=src.id,
        document_id=body.document_id,
        owner_id=user.id,
        claim_text=body.claim_text,
        page_range=body.page_range,
        citation_style=body.citation_style,
        formatted_inline=inline,
        formatted_bibliography=bib,
    )
    db.add(cit)
    await db.commit()
    return {
        "citation": {
            "id": cit.id,
            "source_id": cit.source_id,
            "document_id": cit.document_id,
            "claim_text": cit.claim_text,
            "citation_style": cit.citation_style,
            "formatted_inline": cit.formatted_inline,
            "formatted_bibliography": cit.formatted_bibliography,
        }
    }
