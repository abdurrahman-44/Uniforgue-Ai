"""Unified Academic Workspace Projects, Isolated AI Context & Project Development Studio (Modules G & J)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    ensure_workspace_access,
    get_current_user,
    get_default_workspace,
    log_audit,
)
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import (
    AcademicProject,
    Diagram,
    Document,
    DocumentVersion,
    MediaAsset,
    Presentation,
    ProjectContext,
    ResearchSource,
    Task,
    User,
)
from app.services.diagram_service import get_starter_diagram
from app.services.document_service import count_words, render_markdown_to_html

router = APIRouter(prefix="/projects", tags=["Academic Projects & Project Dev Studio"])


class ProjectCreateRequest(BaseModel):
    workspace_id: str | None = None
    title: str = Field(min_length=2, max_length=255)
    course_code: str | None = Field(default=None, max_length=64)
    subject: str | None = Field(default=None, max_length=120)
    description: str | None = None
    project_type: str = Field(default="research", max_length=64)
    citation_style: str = Field(default="APA 7", max_length=32)
    due_date: datetime | None = None


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    course_code: str | None = None
    subject: str | None = None
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(active|in_review|completed|archived)$")
    citation_style: str | None = None
    due_date: datetime | None = None
    notes: str | None = None


class ProjectContextCreateRequest(BaseModel):
    source_type: str = Field(pattern="^(document|file|note|research)$")
    source_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    content_excerpt: str = Field(min_length=1)
    include_in_ai_context: bool = True


class ProjectContextToggleRequest(BaseModel):
    include_in_ai_context: bool


class ProjectArtifactGenerateRequest(BaseModel):
    artifact_type: str = Field(
        pattern="^(proposal|srs|functional_requirements|non_functional_requirements|system_architecture|database_schema|test_cases|implementation_report|user_manual|final_documentation)$"
    )
    domain_summary: str = Field(min_length=5, max_length=4000)
    create_diagrams: bool = True


def _serialize_project(p: AcademicProject) -> dict[str, Any]:
    return {
        "id": p.id,
        "workspace_id": p.workspace_id,
        "owner_id": p.owner_id,
        "title": p.title,
        "course_code": p.course_code,
        "subject": p.subject,
        "description": p.description,
        "project_type": p.project_type,
        "status": p.status,
        "citation_style": p.citation_style,
        "due_date": p.due_date.isoformat() if p.due_date else None,
        "notes": p.notes,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


@router.get("")
async def list_projects(
    workspace_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AcademicProject).where(
        AcademicProject.owner_id == user.id, AcademicProject.deleted_at.is_(None)
    )
    if workspace_id:
        await ensure_workspace_access(db, workspace_id, user)
        stmt = select(AcademicProject).where(
            AcademicProject.workspace_id == workspace_id, AcademicProject.deleted_at.is_(None)
        )
    rows = (await db.execute(stmt.order_by(AcademicProject.updated_at.desc()))).scalars().all()
    return {"projects": [_serialize_project(p) for p in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.workspace_id:
        ws = await ensure_workspace_access(db, body.workspace_id, user, require_write=True)
    else:
        ws = await get_default_workspace(db, user)

    proj = AcademicProject(
        workspace_id=ws.id,
        owner_id=user.id,
        title=body.title.strip(),
        course_code=body.course_code,
        subject=body.subject,
        description=body.description,
        project_type=body.project_type,
        citation_style=body.citation_style,
        due_date=body.due_date,
    )
    db.add(proj)
    await db.flush()
    await log_audit(db, user.id, "project.create", "academic_project", proj.id)
    await db.commit()
    return {"project": _serialize_project(proj)}


@router.get("/{project_id}")
async def get_project_hub(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unified Academic Workspace Hub: returns all connected artifacts scoped strictly to this project."""
    proj = await ensure_project_access(db, project_id, user)

    docs = (
        await db.execute(
            select(Document).where(Document.project_id == proj.id, Document.deleted_at.is_(None)).order_by(Document.updated_at.desc())
        )
    ).scalars().all()
    diagrams = (
        await db.execute(
            select(Diagram).where(Diagram.project_id == proj.id, Diagram.deleted_at.is_(None)).order_by(Diagram.updated_at.desc())
        )
    ).scalars().all()
    presentations = (
        await db.execute(
            select(Presentation).where(Presentation.project_id == proj.id, Presentation.deleted_at.is_(None)).order_by(Presentation.updated_at.desc())
        )
    ).scalars().all()
    sources = (
        await db.execute(
            select(ResearchSource).where(ResearchSource.project_id == proj.id, ResearchSource.deleted_at.is_(None)).order_by(ResearchSource.created_at.desc())
        )
    ).scalars().all()
    files = (
        await db.execute(
            select(MediaAsset).where(MediaAsset.project_id == proj.id, MediaAsset.deleted_at.is_(None)).order_by(MediaAsset.created_at.desc())
        )
    ).scalars().all()
    tasks = (
        await db.execute(
            select(Task).where(Task.project_id == proj.id, Task.deleted_at.is_(None)).order_by(Task.created_at.desc())
        )
    ).scalars().all()
    context_items = (
        await db.execute(
            select(ProjectContext).where(ProjectContext.project_id == proj.id).order_by(ProjectContext.created_at.desc())
        )
    ).scalars().all()

    return {
        "project": _serialize_project(proj),
        "documents": [
            {"id": d.id, "title": d.title, "doc_type": d.doc_type, "word_count": d.word_count, "updated_at": d.updated_at.isoformat()}
            for d in docs
        ],
        "diagrams": [
            {"id": g.id, "title": g.title, "diagram_type": g.diagram_type, "engine": g.engine, "updated_at": g.updated_at.isoformat()}
            for g in diagrams
        ],
        "presentations": [
            {"id": pr.id, "title": pr.title, "theme": pr.theme, "updated_at": pr.updated_at.isoformat()}
            for pr in presentations
        ],
        "research_sources": [
            {"id": s.id, "title": s.title, "authors": s.authors, "year": s.year, "doi": s.doi, "provenance_status": s.provenance_status}
            for s in sources
        ],
        "files": [
            {"id": f.id, "filename": f.original_filename, "asset_type": f.asset_type, "mime_type": f.mime_type, "size_bytes": f.size_bytes}
            for f in files
        ],
        "tasks": [
            {"id": t.id, "title": t.title, "status": t.status, "priority": t.priority, "progress_percent": t.progress_percent}
            for t in tasks
        ],
        "context_items": [
            {
                "id": c.id,
                "source_type": c.source_type,
                "source_id": c.source_id,
                "title": c.title,
                "include_in_ai_context": c.include_in_ai_context,
                "token_estimate": c.token_estimate,
            }
            for c in context_items
        ],
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await ensure_project_access(db, project_id, user, require_write=True)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(proj, field, val)
    await log_audit(db, user.id, "project.update", "academic_project", proj.id)
    await db.commit()
    return {"project": _serialize_project(proj)}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await ensure_project_access(db, project_id, user, require_write=True)
    proj.deleted_at = datetime.now(timezone.utc)
    await log_audit(db, user.id, "project.delete", "academic_project", proj.id)
    await db.commit()
    return {"deleted": True}


@router.post("/{project_id}/context", status_code=status.HTTP_201_CREATED)
async def add_project_context(
    project_id: str,
    body: ProjectContextCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await ensure_project_access(db, project_id, user, require_write=True)
    item = ProjectContext(
        project_id=proj.id,
        owner_id=user.id,
        source_type=body.source_type,
        source_id=body.source_id,
        title=body.title.strip(),
        content_excerpt=body.content_excerpt[:20000],
        include_in_ai_context=body.include_in_ai_context,
        token_estimate=max(1, len(body.content_excerpt) // 4),
    )
    db.add(item)
    await db.commit()
    return {
        "context_item": {
            "id": item.id,
            "title": item.title,
            "source_type": item.source_type,
            "include_in_ai_context": item.include_in_ai_context,
            "token_estimate": item.token_estimate,
        }
    }


@router.patch("/{project_id}/context/{context_id}")
async def toggle_project_context(
    project_id: str,
    context_id: str,
    body: ProjectContextToggleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await ensure_project_access(db, project_id, user, require_write=True)
    item = (
        await db.execute(
            select(ProjectContext).where(
                ProjectContext.id == context_id, ProjectContext.project_id == proj.id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError("Project context item")
    item.include_in_ai_context = body.include_in_ai_context
    await db.commit()
    return {"id": item.id, "include_in_ai_context": item.include_in_ai_context}


@router.post("/{project_id}/generate-artifact", status_code=status.HTTP_201_CREATED)
async def generate_project_dev_artifact(
    project_id: str,
    body: ProjectArtifactGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Module G — Project Development Studio: builds structured SRS/Proposal/Architecture/Schema/Test docs + editable diagrams."""
    proj = await ensure_project_access(db, project_id, user, require_write=True)
    label = body.artifact_type.replace("_", " ").title()
    doc_title = f"{proj.title} — {label}"

    artifact_templates: dict[str, str] = {
        "srs": (
            f"# Software Requirements Specification (IEEE 830): {proj.title}\n\n"
            f"## 1. Introduction & System Scope\n{body.domain_summary}\n\n"
            "## 2. Functional Requirements\n"
            "| ID | Requirement | Priority | Verification |\n"
            "| --- | --- | --- | --- |\n"
            "| FR-01 | User registration, secure authentication, and role-based access control | High | Automated API & Auth Tests |\n"
            "| FR-02 | Core domain workflow execution and persistent record management | High | Integration & E2E Tests |\n"
            "| FR-03 | Reporting, search, filtering, and export capabilities | Medium | Functional Verification |\n\n"
            "## 3. Non-Functional Requirements\n"
            "- **Security**: Argon2id password hashing, TLS transport, strict authorization isolation.\n"
            "- **Performance**: P95 API response under 300ms for interactive reads.\n"
            "- **Reliability**: ACID database transactions and automated backups.\n"
            "- **Accessibility**: WCAG 2.1 AA contrast and keyboard navigation.\n\n"
            "## 4. External Interface Requirements\nRESTful JSON API, responsive web client, and relational database storage."
        ),
        "database_schema": (
            f"# Database Schema Specification: {proj.title}\n\n"
            f"## Domain Context\n{body.domain_summary}\n\n"
            "## Normalized Entities (3NF)\n"
            "| Table | Primary Key | Key Attributes | Foreign Keys |\n"
            "| --- | --- | --- | --- |\n"
            "| users | id (UUID) | email, password_hash, role, created_at | - |\n"
            "| records | id (UUID) | title, status, payload_json, updated_at | owner_id -> users.id |\n"
            "| audit_events | id (UUID) | action, actor_id, timestamp | actor_id -> users.id |\n\n"
            "## Indexing & Integrity Constraints\nUnique indexes on natural keys, foreign key cascades, and soft-delete timestamps."
        ),
        "test_cases": (
            f"# Software Testing Documentation & Test Cases: {proj.title}\n\n"
            f"## Scope\n{body.domain_summary}\n\n"
            "## Test Case Matrix\n"
            "| TC ID | Module | Scenario | Expected Result | Status |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| TC-01 | Auth | Valid user login | Returns 200 OK & active session | Ready |\n"
            "| TC-02 | Auth | Unauthorized access to private project | Returns 403 Forbidden | Ready |\n"
            "| TC-03 | Core | Create, update, and persist primary entity | Persisted in DB & returned on reload | Ready |\n"
            "| TC-04 | Export | Generate submission PDF/DOCX | Valid binary file exported | Ready |"
        ),
    }

    markdown_content = artifact_templates.get(
        body.artifact_type,
        (
            f"# {doc_title}\n\n"
            f"## 1. Project Overview\n{body.domain_summary}\n\n"
            f"## 2. Core {label} Specification\n"
            "- Define stakeholder objectives, constraints, and measurable deliverables.\n"
            "- Map architectural components, data flows, and security boundaries.\n"
            "- Validate outputs against university project assessment criteria.\n\n"
            "## 3. Traceability & Next Steps\nLink supporting Research Studio sources and Diagram Studio models to this project workspace."
        ),
    )

    doc = Document(
        workspace_id=proj.workspace_id,
        project_id=proj.id,
        owner_id=user.id,
        title=doc_title,
        doc_type="technical_documentation" if body.artifact_type != "proposal" else "project_proposal",
        citation_style=proj.citation_style,
        content_markdown=markdown_content,
        content_html=render_markdown_to_html(markdown_content),
        word_count=count_words(markdown_content),
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
            change_summary=f"Generated {label} artifact in Project Development Studio",
        )
    )

    created_diagrams = []
    if body.create_diagrams:
        diag_map = {
            "srs": ("uml_class", f"{proj.title} — Domain Class Diagram"),
            "database_schema": ("er", f"{proj.title} — ER Schema Diagram"),
            "system_architecture": ("architecture", f"{proj.title} — System Architecture"),
            "proposal": ("flowchart", f"{proj.title} — Workflow Flowchart"),
        }
        dtype, dtitle = diag_map.get(body.artifact_type, ("architecture", f"{proj.title} — {label} Diagram"))
        tpl = get_starter_diagram(dtype)
        diag = Diagram(
            workspace_id=proj.workspace_id,
            project_id=proj.id,
            owner_id=user.id,
            title=dtitle,
            diagram_type=dtype,
            engine="reactflow",
            nodes_json=tpl["nodes"],
            edges_json=tpl["edges"],
            mermaid_code=tpl["mermaid"],
            plantuml_code=tpl["plantuml"],
        )
        db.add(diag)
        await db.flush()
        created_diagrams.append({"id": diag.id, "title": diag.title, "diagram_type": diag.diagram_type})

    await log_audit(db, user.id, "project.generate_artifact", "document", doc.id, details={"artifact_type": body.artifact_type})
    await db.commit()
    return {
        "document": {"id": doc.id, "title": doc.title, "word_count": doc.word_count},
        "diagrams": created_diagrams,
    }
