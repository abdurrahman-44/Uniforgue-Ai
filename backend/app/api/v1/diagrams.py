"""Module H — Diagram Studio (Interactive React Flow + Mermaid/PlantUML + Real SVG/PNG/PDF Export)."""

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
from app.models.entities import Diagram, User
from app.services.diagram_service import (
    DIAGRAM_TEMPLATES,
    export_diagram_pdf,
    export_diagram_png,
    export_diagram_svg,
    get_starter_diagram,
    parse_mermaid_to_graph,
)

router = APIRouter(prefix="/diagrams", tags=["Diagram Studio"])


class DiagramCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    diagram_type: str = Field(default="flowchart", max_length=64)
    engine: str = Field(default="reactflow", pattern="^(reactflow|mermaid|plantuml)$")
    project_id: str | None = None
    nodes_json: list[dict[str, Any]] | None = None
    edges_json: list[dict[str, Any]] | None = None
    mermaid_code: str | None = None
    plantuml_code: str | None = None


class DiagramUpdateRequest(BaseModel):
    title: str | None = None
    diagram_type: str | None = None
    engine: str | None = None
    nodes_json: list[dict[str, Any]] | None = None
    edges_json: list[dict[str, Any]] | None = None
    mermaid_code: str | None = None
    plantuml_code: str | None = None
    viewport_json: dict[str, Any] | None = None


class DiagramImportMermaidRequest(BaseModel):
    mermaid_code: str = Field(min_length=5)


def _serialize_diagram(g: Diagram) -> dict[str, Any]:
    return {
        "id": g.id,
        "workspace_id": g.workspace_id,
        "project_id": g.project_id,
        "title": g.title,
        "diagram_type": g.diagram_type,
        "engine": g.engine,
        "nodes_json": g.nodes_json,
        "edges_json": g.edges_json,
        "mermaid_code": g.mermaid_code,
        "plantuml_code": g.plantuml_code,
        "viewport_json": g.viewport_json,
        "created_at": g.created_at.isoformat(),
        "updated_at": g.updated_at.isoformat(),
    }


@router.get("/templates")
async def list_diagram_templates():
    return {
        "types": list(DIAGRAM_TEMPLATES.keys()),
        "supported_diagram_types": [
            "flowchart",
            "uml_use_case",
            "uml_activity",
            "uml_sequence",
            "uml_class",
            "er",
            "dfd",
            "network",
            "mind_map",
            "concept_map",
            "org_chart",
            "architecture",
        ],
    }


@router.get("")
async def list_diagrams(
    project_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Diagram).where(Diagram.owner_id == user.id, Diagram.deleted_at.is_(None))
    if project_id:
        await ensure_project_access(db, project_id, user)
        stmt = stmt.where(Diagram.project_id == project_id)
    rows = (await db.execute(stmt.order_by(Diagram.updated_at.desc()))).scalars().all()
    return {
        "diagrams": [
            {
                "id": g.id,
                "project_id": g.project_id,
                "title": g.title,
                "diagram_type": g.diagram_type,
                "engine": g.engine,
                "node_count": len(g.nodes_json or []),
                "edge_count": len(g.edges_json or []),
                "updated_at": g.updated_at.isoformat(),
            }
            for g in rows
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_diagram(
    body: DiagramCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    starter = get_starter_diagram(body.diagram_type)
    nodes = body.nodes_json if body.nodes_json is not None else starter["nodes"]
    edges = body.edges_json if body.edges_json is not None else starter["edges"]
    mermaid = body.mermaid_code if body.mermaid_code is not None else starter["mermaid"]
    plantuml = body.plantuml_code if body.plantuml_code is not None else starter["plantuml"]

    diag = Diagram(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        title=body.title.strip(),
        diagram_type=body.diagram_type,
        engine=body.engine,
        nodes_json=nodes,
        edges_json=edges,
        mermaid_code=mermaid,
        plantuml_code=plantuml,
    )
    db.add(diag)
    await db.flush()
    await log_audit(db, user.id, "diagram.create", "diagram", diag.id)
    await db.commit()
    return {"diagram": _serialize_diagram(diag)}


@router.get("/{diagram_id}")
async def get_diagram(
    diagram_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    diag = (
        await db.execute(
            select(Diagram).where(
                Diagram.id == diagram_id, Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise NotFoundError("Diagram")
    return {"diagram": _serialize_diagram(diag)}


@router.patch("/{diagram_id}")
async def update_diagram(
    diagram_id: str,
    body: DiagramUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    diag = (
        await db.execute(
            select(Diagram).where(
                Diagram.id == diagram_id, Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise NotFoundError("Diagram")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(diag, k, v)
    await db.commit()
    return {"diagram": _serialize_diagram(diag)}


@router.post("/{diagram_id}/import-mermaid")
async def import_mermaid(
    diagram_id: str,
    body: DiagramImportMermaidRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    diag = (
        await db.execute(
            select(Diagram).where(
                Diagram.id == diagram_id, Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise NotFoundError("Diagram")
    nodes, edges = parse_mermaid_to_graph(body.mermaid_code)
    diag.mermaid_code = body.mermaid_code
    if nodes:
        diag.nodes_json = nodes
        diag.edges_json = edges
    await db.commit()
    return {"diagram": _serialize_diagram(diag)}


@router.get("/{diagram_id}/export")
async def export_diagram(
    diagram_id: str,
    format: str = Query(default="svg", pattern="^(svg|png|pdf)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    diag = (
        await db.execute(
            select(Diagram).where(
                Diagram.id == diagram_id, Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise NotFoundError("Diagram")

    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in diag.title)[:80] or "diagram"
    if format == "svg":
        raw = export_diagram_svg(diag.title, diag.nodes_json, diag.edges_json)
        media_type = "image/svg+xml"
    elif format == "png":
        raw = export_diagram_png(diag.title, diag.nodes_json, diag.edges_json)
        media_type = "image/png"
    else:
        raw = export_diagram_pdf(diag.title, diag.nodes_json, diag.edges_json)
        media_type = "application/pdf"

    return Response(
        content=raw,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_slug}.{format}"'},
    )


@router.delete("/{diagram_id}")
async def delete_diagram(
    diagram_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    diag = (
        await db.execute(
            select(Diagram).where(
                Diagram.id == diagram_id, Diagram.owner_id == user.id, Diagram.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not diag:
        raise NotFoundError("Diagram")
    diag.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"deleted": True}
