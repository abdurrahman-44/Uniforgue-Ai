"""Diagram Studio Engine: Templates, Mermaid/PlantUML Importers, SVG/PNG/PDF Exporters."""

from __future__ import annotations

import io
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors

DIAGRAM_TEMPLATES: dict[str, dict[str, Any]] = {
    "flowchart": {
        "nodes": [
            {"id": "n1", "type": "default", "position": {"x": 80, "y": 60}, "data": {"label": "Start Research Idea", "color": "#7C3AED", "shape": "rounded"}},
            {"id": "n2", "type": "default", "position": {"x": 80, "y": 180}, "data": {"label": "Gather Verified Sources", "color": "#06B6D4", "shape": "rect"}},
            {"id": "n3", "type": "default", "position": {"x": 80, "y": 300}, "data": {"label": "Draft & Review Document", "color": "#2563EB", "shape": "rect"}},
            {"id": "n4", "type": "default", "position": {"x": 80, "y": 420}, "data": {"label": "Export Submission PDF/DOCX", "color": "#10B981", "shape": "rounded"}},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "label": "scope defined"},
            {"id": "e2-3", "source": "n2", "target": "n3", "label": "citations linked"},
            {"id": "e3-4", "source": "n3", "target": "n4", "label": "rubric verified"},
        ],
        "mermaid": "flowchart TD\n  n1([Start Research Idea]) -->|scope defined| n2[Gather Verified Sources]\n  n2 -->|citations linked| n3[Draft & Review Document]\n  n3 -->|rubric verified| n4([Export Submission PDF/DOCX])",
        "plantuml": "@startuml\nstart\n:Start Research Idea;\n:Gather Verified Sources;\n:Draft & Review Document;\n:Export Submission PDF/DOCX;\nstop\n@enduml",
    },
    "er": {
        "nodes": [
            {"id": "u", "type": "default", "position": {"x": 60, "y": 120}, "data": {"label": "STUDENT (id PK, email, name)", "color": "#7C3AED", "shape": "rect"}},
            {"id": "p", "type": "default", "position": {"x": 360, "y": 120}, "data": {"label": "PROJECT (id PK, student_id FK, title)", "color": "#06B6D4", "shape": "rect"}},
            {"id": "d", "type": "default", "position": {"x": 680, "y": 120}, "data": {"label": "DOCUMENT (id PK, project_id FK, content)", "color": "#2563EB", "shape": "rect"}},
        ],
        "edges": [
            {"id": "e-up", "source": "u", "target": "p", "label": "1 : N owns"},
            {"id": "e-pd", "source": "p", "target": "d", "label": "1 : N contains"},
        ],
        "mermaid": "erDiagram\n  STUDENT ||--o{ PROJECT : owns\n  PROJECT ||--o{ DOCUMENT : contains",
        "plantuml": "@startuml\nentity STUDENT {\n  *id : UUID\n  email : VARCHAR\n}\nentity PROJECT {\n  *id : UUID\n  title : VARCHAR\n}\nSTUDENT ||--o{ PROJECT\n@enduml",
    },
    "architecture": {
        "nodes": [
            {"id": "fe", "type": "default", "position": {"x": 60, "y": 140}, "data": {"label": "Next.js Web Client", "color": "#7C3AED", "shape": "rect"}},
            {"id": "api", "type": "default", "position": {"x": 320, "y": 140}, "data": {"label": "FastAPI Modular API", "color": "#06B6D4", "shape": "rect"}},
            {"id": "db", "type": "default", "position": {"x": 580, "y": 60}, "data": {"label": "PostgreSQL + pgvector", "color": "#2563EB", "shape": "rect"}},
            {"id": "q", "type": "default", "position": {"x": 580, "y": 220}, "data": {"label": "Redis + Celery Workers", "color": "#10B981", "shape": "rect"}},
        ],
        "edges": [
            {"id": "e1", "source": "fe", "target": "api", "label": "HTTPS / WS"},
            {"id": "e2", "source": "api", "target": "db", "label": "SQLAlchemy"},
            {"id": "e3", "source": "api", "target": "q", "label": "Async Jobs"},
        ],
        "mermaid": "graph LR\n  FE[Next.js Web Client] -->|HTTPS/WS| API[FastAPI Modular API]\n  API --> DB[(PostgreSQL + pgvector)]\n  API --> Q[Redis + Celery Workers]",
        "plantuml": "@startuml\n[Next.js Web Client] --> [FastAPI Modular API]\n[FastAPI Modular API] --> [PostgreSQL]\n[FastAPI Modular API] --> [Redis Queue]\n@enduml",
    },
    "uml_class": {
        "nodes": [
            {"id": "c1", "type": "default", "position": {"x": 80, "y": 100}, "data": {"label": "User\n+id: UUID\n+login()", "color": "#7C3AED", "shape": "rect"}},
            {"id": "c2", "type": "default", "position": {"x": 380, "y": 100}, "data": {"label": "Booking\n+id: UUID\n+confirm()", "color": "#06B6D4", "shape": "rect"}},
        ],
        "edges": [{"id": "ec1", "source": "c1", "target": "c2", "label": "creates 1..*"}],
        "mermaid": "classDiagram\n  User \"1\" --> \"*\" Booking : creates",
        "plantuml": "@startuml\nclass User {\n  +id: UUID\n  +login()\n}\nclass Booking {\n  +id: UUID\n  +confirm()\n}\nUser \"1\" --> \"*\" Booking\n@enduml",
    },
    "uml_sequence": {
        "nodes": [
            {"id": "s1", "type": "default", "position": {"x": 80, "y": 100}, "data": {"label": "Student Browser", "color": "#7C3AED", "shape": "rect"}},
            {"id": "s2", "type": "default", "position": {"x": 340, "y": 100}, "data": {"label": "Auth Service", "color": "#06B6D4", "shape": "rect"}},
            {"id": "s3", "type": "default", "position": {"x": 600, "y": 100}, "data": {"label": "Database", "color": "#10B981", "shape": "rect"}},
        ],
        "edges": [
            {"id": "es1", "source": "s1", "target": "s2", "label": "1. POST /auth/login"},
            {"id": "es2", "source": "s2", "target": "s3", "label": "2. Verify Argon2id"},
        ],
        "mermaid": "sequenceDiagram\n  Student->>AuthService: POST /auth/login\n  AuthService->>Database: Verify Argon2id hash\n  AuthService-->>Student: Set HttpOnly JWT cookies",
        "plantuml": "@startuml\nStudent -> AuthService: POST /auth/login\nAuthService -> Database: Verify Argon2id\nAuthService --> Student: JWT Cookie\n@enduml",
    },
    "mind_map": {
        "nodes": [
            {"id": "m0", "type": "default", "position": {"x": 320, "y": 180}, "data": {"label": "Central Research Theme", "color": "#7C3AED", "shape": "rounded"}},
            {"id": "m1", "type": "default", "position": {"x": 60, "y": 60}, "data": {"label": "Literature Gaps", "color": "#06B6D4", "shape": "rounded"}},
            {"id": "m2", "type": "default", "position": {"x": 580, "y": 60}, "data": {"label": "Methodology", "color": "#2563EB", "shape": "rounded"}},
            {"id": "m3", "type": "default", "position": {"x": 320, "y": 330}, "data": {"label": "Evaluation Metrics", "color": "#10B981", "shape": "rounded"}},
        ],
        "edges": [
            {"id": "em1", "source": "m0", "target": "m1", "label": ""},
            {"id": "em2", "source": "m0", "target": "m2", "label": ""},
            {"id": "em3", "source": "m0", "target": "m3", "label": ""},
        ],
        "mermaid": "mindmap\n  root((Central Research Theme))\n    Literature Gaps\n    Methodology\n    Evaluation Metrics",
        "plantuml": "@startmindmap\n* Central Research Theme\n** Literature Gaps\n** Methodology\n** Evaluation Metrics\n@endmindmap",
    },
}


def get_starter_diagram(diagram_type: str) -> dict[str, Any]:
    key = diagram_type.lower()
    if key in DIAGRAM_TEMPLATES:
        return DIAGRAM_TEMPLATES[key]
    if "er" in key:
        return DIAGRAM_TEMPLATES["er"]
    if "arch" in key or "network" in key or "dfd" in key:
        return DIAGRAM_TEMPLATES["architecture"]
    if "class" in key:
        return DIAGRAM_TEMPLATES["uml_class"]
    if "seq" in key:
        return DIAGRAM_TEMPLATES["uml_sequence"]
    if "mind" in key or "concept" in key or "org" in key:
        return DIAGRAM_TEMPLATES["mind_map"]
    return DIAGRAM_TEMPLATES["flowchart"]


def parse_mermaid_to_graph(mermaid_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse Mermaid flowchart/graph definitions into editable React Flow nodes and edges."""
    nodes_map: dict[str, str] = {}
    edges: list[dict[str, Any]] = []
    edge_pattern = re.compile(
        r"([A-Za-z0-9_]+)(?:\[([^\]]+)\]|\(([^)]+)\))?\s*-->(?:\|([^|]+)\|)?\s*([A-Za-z0-9_]+)(?:\[([^\]]+)\]|\(([^)]+)\))?"
    )
    for line in (mermaid_code or "").splitlines():
        m = edge_pattern.search(line.strip())
        if not m:
            continue
        src_id = m.group(1)
        src_label = (m.group(2) or m.group(3) or nodes_map.get(src_id) or src_id).strip("()[] ")
        edge_label = (m.group(4) or "").strip()
        tgt_id = m.group(5)
        tgt_label = (m.group(6) or m.group(7) or nodes_map.get(tgt_id) or tgt_id).strip("()[] ")
        nodes_map[src_id] = src_label
        nodes_map[tgt_id] = tgt_label
        edges.append(
            {"id": f"e-{src_id}-{tgt_id}-{len(edges)}", "source": src_id, "target": tgt_id, "label": edge_label}
        )

    nodes: list[dict[str, Any]] = []
    for idx, (nid, label) in enumerate(nodes_map.items()):
        nodes.append(
            {
                "id": nid,
                "type": "default",
                "position": {"x": 80 + (idx % 3) * 260, "y": 80 + (idx // 3) * 140},
                "data": {"label": label, "color": "#7C3AED" if idx == 0 else "#06B6D4", "shape": "rect"},
            }
        )
    return nodes, edges


def _compute_bounds(nodes: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    if not nodes:
        return 0, 0, 900, 500
    xs = [float((n.get("position") or {}).get("x", 80)) for n in nodes]
    ys = [float((n.get("position") or {}).get("y", 80)) for n in nodes]
    min_x, max_x = min(xs) - 60, max(xs) + 280
    min_y, max_y = min(ys) - 60, max(ys) + 140
    return min_x, min_y, max(900, max_x - min_x), max(500, max_y - min_y)


def export_diagram_svg(title: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bytes:
    """Render stored editable diagram nodes and edges as clean standalone SVG."""
    min_x, min_y, width, height = _compute_bounds(nodes)
    node_centers: dict[str, tuple[float, float]] = {}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#22D3EE"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#0A1024"/>',
        f'<text x="24" y="34" fill="#F8FAFC" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="700">{title.replace("&", "&amp;").replace("<", "&lt;")}</text>',
    ]

    for n in nodes:
        pos = n.get("position") or {}
        x = float(pos.get("x", 80)) - min_x
        y = float(pos.get("y", 80)) - min_y + 24
        node_centers[str(n["id"])] = (x + 100, y + 32)

    for e in edges:
        src = node_centers.get(str(e.get("source")))
        tgt = node_centers.get(str(e.get("target")))
        if not src or not tgt:
            continue
        parts.append(
            f'<line x1="{src[0]:.1f}" y1="{src[1]:.1f}" x2="{tgt[0]:.1f}" y2="{tgt[1]:.1f}" stroke="#22D3EE" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        lbl = str(e.get("label") or "").strip()
        if lbl:
            mx, my = (src[0] + tgt[0]) / 2, (src[1] + tgt[1]) / 2 - 6
            safe_lbl = lbl.replace("&", "&amp;").replace("<", "&lt;")
            parts.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" fill="#CBD5E1" font-family="Inter, Arial, sans-serif" font-size="11">{safe_lbl}</text>'
            )

    for n in nodes:
        pos = n.get("position") or {}
        data = n.get("data") or {}
        x = float(pos.get("x", 80)) - min_x
        y = float(pos.get("y", 80)) - min_y + 24
        color = str(data.get("color") or "#7C3AED")
        rx = "18" if data.get("shape") == "rounded" else "8"
        label = str(data.get("label") or n.get("id")).replace("&", "&amp;").replace("<", "&lt;")
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="200" height="64" rx="{rx}" fill="#111936" stroke="{color}" stroke-width="2.5"/>'
        )
        parts.append(
            f'<text x="{x + 100:.1f}" y="{y + 37:.1f}" text-anchor="middle" fill="#F8FAFC" font-family="Inter, Arial, sans-serif" font-size="13" font-weight="600">{label[:32]}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts).encode("utf-8")


def export_diagram_png(title: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bytes:
    """Render stored editable diagram nodes and edges as a crisp PNG image via Pillow."""
    min_x, min_y, width, height = _compute_bounds(nodes)
    w, h = int(width), int(height)
    img = Image.new("RGB", (w, h), "#0A1024")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_node = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font_title = ImageFont.load_default()
        font_node = ImageFont.load_default()

    draw.text((24, 16), title, fill="#F8FAFC", font=font_title)
    centers: dict[str, tuple[float, float]] = {}
    for n in nodes:
        pos = n.get("position") or {}
        x = float(pos.get("x", 80)) - min_x
        y = float(pos.get("y", 80)) - min_y + 24
        centers[str(n["id"])] = (x + 100, y + 32)

    for e in edges:
        src = centers.get(str(e.get("source")))
        tgt = centers.get(str(e.get("target")))
        if src and tgt:
            draw.line([src, tgt], fill="#22D3EE", width=2)
            lbl = str(e.get("label") or "").strip()
            if lbl:
                draw.text(((src[0] + tgt[0]) / 2, (src[1] + tgt[1]) / 2 - 12), lbl, fill="#CBD5E1", font=font_node)

    for n in nodes:
        pos = n.get("position") or {}
        data = n.get("data") or {}
        x = float(pos.get("x", 80)) - min_x
        y = float(pos.get("y", 80)) - min_y + 24
        stroke = str(data.get("color") or "#7C3AED")
        draw.rounded_rectangle([x, y, x + 200, y + 64], radius=10, fill="#111936", outline=stroke, width=2)
        label = str(data.get("label") or n.get("id"))[:28]
        draw.text((x + 14, y + 24), label, fill="#F8FAFC", font=font_node)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def export_diagram_pdf(title: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bytes:
    """Render stored editable diagram as a vector PDF via ReportLab."""
    min_x, min_y, width, height = _compute_bounds(nodes)
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#0A1024"), strokeColor=None))
    drawing.add(String(24, height - 30, title, fontName="Helvetica-Bold", fontSize=16, fillColor=colors.white))

    centers: dict[str, tuple[float, float]] = {}
    for n in nodes:
        pos = n.get("position") or {}
        x = float(pos.get("x", 80)) - min_x
        y = height - (float(pos.get("y", 80)) - min_y + 100)
        centers[str(n["id"])] = (x + 100, y + 32)

    for e in edges:
        src = centers.get(str(e.get("source")))
        tgt = centers.get(str(e.get("target")))
        if src and tgt:
            drawing.add(Line(src[0], src[1], tgt[0], tgt[1], strokeColor=colors.HexColor("#22D3EE"), strokeWidth=1.8))

    for n in nodes:
        pos = n.get("position") or {}
        data = n.get("data") or {}
        x = float(pos.get("x", 80)) - min_x
        y = height - (float(pos.get("y", 80)) - min_y + 100)
        stroke_hex = str(data.get("color") or "#7C3AED")
        try:
            sc = colors.HexColor(stroke_hex)
        except Exception:
            sc = colors.HexColor("#7C3AED")
        drawing.add(Rect(x, y, 200, 64, rx=8, ry=8, fillColor=colors.HexColor("#111936"), strokeColor=sc, strokeWidth=2))
        label = str(data.get("label") or n.get("id"))[:30]
        drawing.add(String(x + 12, y + 27, label, fontName="Helvetica", fontSize=11, fillColor=colors.white))

    return renderPDF.drawToString(drawing)
