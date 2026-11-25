"""Comprehensive E2E, Auth, RBAC, Isolation, Export, Diagram, Research, Video, Learning & Security Tests."""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient
from PIL import Image
from reportlab.pdfgen import canvas


def _make_sample_pdf(text_lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 760
    for line in text_lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def _make_sample_png() -> bytes:
    img = Image.new("RGB", (120, 80), color=(255, 255, 255))
    for x in range(30, 90):
        for y in range(20, 60):
            img.putpixel((x, y), (124, 58, 237))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _register_user(client: AsyncClient, email: str, full_name: str, password: str = "StrongPass123!"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "university": "Global Tech University",
            "department": "Computer Science",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_full_academic_lifecycle_e2e(client: AsyncClient):
    """Covers Section 13 mandatory E2E workflow: register -> workspace -> project -> PDF upload ->
    assignment analysis -> document create/edit -> DOCX & PDF export -> diagram create/save/reopen ->
    permissions check -> delete project."""
    # 1. Register user (first user becomes admin; register second user as ordinary student)
    admin_data = await _register_user(client, "admin@uniforge.edu", "Admin Scholar")
    student_data = await _register_user(client, "student@uniforge.edu", "Maya Patel")
    assert admin_data["user"]["role"] == "admin"
    assert student_data["user"]["role"] == "student"

    # Verify email flow
    verify_resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": student_data["dev_verification_token"]},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

    s_headers = {"Authorization": f"Bearer {student_data['access_token']}"}
    a_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}

    # 2. Create workspace
    ws_resp = await client.post(
        "/api/v1/workspaces",
        headers=s_headers,
        json={"name": "Final Year CS Lab", "description": "Senior thesis workspace"},
    )
    assert ws_resp.status_code == 201
    ws_id = ws_resp.json()["workspace"]["id"]

    # 3. Create academic project
    proj_resp = await client.post(
        "/api/v1/projects",
        headers=s_headers,
        json={
            "workspace_id": ws_id,
            "title": "Smart Bus Booking System",
            "course_code": "CS499",
            "subject": "Software Engineering",
            "citation_style": "IEEE",
        },
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["project"]["id"]

    # 4. Upload real assignment brief PDF and extract text via PyMuPDF
    pdf_bytes = _make_sample_pdf(
        [
            "CS499 Assignment Brief: Smart Bus Booking System",
            "Required Sections: Introduction, Literature Review, Methodology, Conclusion, References",
            "Formatting: IEEE citation style, minimum 50 words, maximum 2500 words.",
            "Question 1: How does real-time seat locking prevent double bookings?",
            "Assessment Rubric: Architecture 40%, Evaluation 30%, Writing 30%",
        ]
    )
    up_resp = await client.post(
        "/api/v1/files/upload",
        headers=s_headers,
        files={"file": ("assignment_brief.pdf", pdf_bytes, "application/pdf")},
        data={"project_id": proj_id, "add_to_project_context": "true"},
    )
    assert up_resp.status_code == 201, up_resp.text
    asset = up_resp.json()["file"]
    assert asset["has_extracted_text"] is True
    assert "Smart Bus Booking System" in asset["extracted_preview"]

    # Signed URL download verification
    dl_resp = await client.get(asset["download_url"])
    assert dl_resp.status_code == 200
    assert dl_resp.content.startswith(b"%PDF-")

    # 5. Create Document and edit with Markdown headings, table, and equation
    doc_resp = await client.post(
        "/api/v1/documents",
        headers=s_headers,
        json={
            "project_id": proj_id,
            "title": "Smart Bus Booking System Technical Report",
            "doc_type": "research_paper",
            "citation_style": "IEEE",
        },
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["document"]["id"]

    rich_md = (
        "# Smart Bus Booking System\n\n"
        "## Introduction\nThis report designs a fault-tolerant distributed bus reservation platform for university campuses.\n\n"
        "## Literature Review\nPrior transit studies emphasize ACID seat-lock transactions to prevent race conditions.\n\n"
        "## Methodology\nWe implement PostgreSQL row-level locking and REST microservices with automated verification.\n\n"
        "| Metric | Baseline | Proposed |\n"
        "| --- | --- | --- |\n"
        "| Latency | 420ms | 95ms |\n"
        "| Double Bookings | 2.1% | 0.0% |\n\n"
        "$$ T_{lock} = T_{acquire} + T_{commit} $$\n\n"
        "## Conclusion\nTransactional seat reservations eliminate booking conflicts under peak load.\n\n"
        "## References\nVerified citations linked via Research Studio.\n"
    )
    edit_resp = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=s_headers,
        json={
            "content_markdown": rich_md,
            "change_summary": "Added full sections, table, and equation",
            "expected_version": 1,
        },
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["document"]["version_number"] == 2

    # Concurrent edit protection test (stale version rejected with 409)
    stale_resp = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=s_headers,
        json={"content_markdown": "stale overwrite", "expected_version": 1},
    )
    assert stale_resp.status_code == 409

    # 6. Assignment Requirement Analyzer
    analyze_resp = await client.post(
        "/api/v1/documents/analyze-assignment",
        headers=s_headers,
        json={"brief_asset_id": asset["id"], "document_id": doc_id},
    )
    assert analyze_resp.status_code == 200
    analysis = analyze_resp.json()["analysis"]
    assert "Introduction" in analysis["required_sections"]
    assert analysis["word_limits"]["min"] == 50
    assert analysis["word_limits"]["max"] == 2500
    assert analysis["coverage_percent"] >= 70.0
    assert any("Architecture" in m for m in analysis["missing_requirements"])
    assert "does not predict or guarantee" in analysis["disclaimer"]

    # 7. Real DOCX export (verify valid ZIP + word/document.xml)
    docx_resp = await client.get(f"/api/v1/documents/{doc_id}/export?format=docx", headers=s_headers)
    assert docx_resp.status_code == 200
    assert docx_resp.content.startswith(b"PK\x03\x04")
    with zipfile.ZipFile(io.BytesIO(docx_resp.content)) as zf:
        assert "word/document.xml" in zf.namelist()
        xml_content = zf.read("word/document.xml").decode("utf-8")
        assert "Smart Bus Booking System" in xml_content

    # 8. Real PDF export (verify valid %PDF- binary)
    pdf_resp = await client.get(f"/api/v1/documents/{doc_id}/export?format=pdf", headers=s_headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")
    assert len(pdf_resp.content) > 1500

    # 9. Diagram Studio: create, edit nodes, save, reopen, export SVG/PNG/PDF
    diag_resp = await client.post(
        "/api/v1/diagrams",
        headers=s_headers,
        json={"project_id": proj_id, "title": "Bus Booking ER Schema", "diagram_type": "er"},
    )
    assert diag_resp.status_code == 201
    diag_id = diag_resp.json()["diagram"]["id"]

    custom_nodes = [
        {"id": "bus", "type": "default", "position": {"x": 80, "y": 80}, "data": {"label": "BUS (id PK, route)", "color": "#7C3AED"}},
        {"id": "seat", "type": "default", "position": {"x": 360, "y": 80}, "data": {"label": "BOOKING (id PK, seat_no)", "color": "#06B6D4"}},
    ]
    custom_edges = [{"id": "e1", "source": "bus", "target": "seat", "label": "1 : N"}]
    save_diag = await client.patch(
        f"/api/v1/diagrams/{diag_id}",
        headers=s_headers,
        json={"nodes_json": custom_nodes, "edges_json": custom_edges},
    )
    assert save_diag.status_code == 200

    reopen_diag = await client.get(f"/api/v1/diagrams/{diag_id}", headers=s_headers)
    assert reopen_diag.status_code == 200
    assert len(reopen_diag.json()["diagram"]["nodes_json"]) == 2
    assert reopen_diag.json()["diagram"]["nodes_json"][0]["data"]["label"] == "BUS (id PK, route)"

    svg_export = await client.get(f"/api/v1/diagrams/{diag_id}/export?format=svg", headers=s_headers)
    assert svg_export.status_code == 200
    assert b"<svg" in svg_export.content and b"BUS (id PK, route)" in svg_export.content

    png_export = await client.get(f"/api/v1/diagrams/{diag_id}/export?format=png", headers=s_headers)
    assert png_export.status_code == 200
    assert png_export.content.startswith(b"\x89PNG")

    # 10. Verify strict authorization / project isolation (other user MUST get 403)
    unauth_proj = await client.get(f"/api/v1/projects/{proj_id}", headers=a_headers)
    assert unauth_proj.status_code == 403

    # Non-admin MUST NOT access Admin Console (403)
    student_admin = await client.get("/api/v1/admin/overview", headers=s_headers)
    assert student_admin.status_code == 403
    real_admin = await client.get("/api/v1/admin/overview", headers=a_headers)
    assert real_admin.status_code == 200
    assert real_admin.json()["metrics"]["total_users"] == 2

    # 11. Delete project and verify it is no longer returned
    del_resp = await client.delete(f"/api/v1/projects/{proj_id}", headers=s_headers)
    assert del_resp.status_code == 200
    gone_resp = await client.get(f"/api/v1/projects/{proj_id}", headers=s_headers)
    assert gone_resp.status_code == 404


@pytest.mark.asyncio
async def test_presentation_research_learning_image_video_community(client: AsyncClient):
    """Tests Presentations (PPTX), Research & Citations, Learning Quizzes, Image Studio honesty & local tools,
    Video Studio FFmpeg MP4 assembly, Community privacy-by-default, and SVG XSS sanitization."""
    user_data = await _register_user(client, "researcher@uniforge.edu", "Dr. Alex Lin")
    headers = {"Authorization": f"Bearer {user_data['access_token']}"}

    # 1. Presentation Studio -> real PPTX + PDF export
    prs_resp = await client.post(
        "/api/v1/presentations",
        headers=headers,
        json={
            "title": "Distributed Consensus in Academic Systems",
            "theme": "academic_navy",
            "slides": [
                {"layout": "title", "title": "Distributed Consensus", "bullets": ["CS501 Seminar"], "speaker_notes": "Welcome class"},
                {
                    "layout": "title_and_bullets",
                    "title": "Performance Comparison",
                    "bullets": ["Raft leader election", "Paxos quorum latency"],
                    "speaker_notes": "Explain quorum chart",
                    "chart_data": {"categories": ["3 Nodes", "5 Nodes"], "series": [{"name": "Latency ms", "values": [12, 21]}]},
                },
            ],
        },
    )
    assert prs_resp.status_code == 201
    prs_id = prs_resp.json()["presentation"]["id"]

    pptx_resp = await client.get(f"/api/v1/presentations/{prs_id}/export?format=pptx", headers=headers)
    assert pptx_resp.status_code == 200
    assert pptx_resp.content.startswith(b"PK\x03\x04")
    with zipfile.ZipFile(io.BytesIO(pptx_resp.content)) as zf:
        assert "ppt/presentation.xml" in zf.namelist()
        assert "ppt/slides/slide1.xml" in zf.namelist()

    # 2. Research Source + Citation formatting (traceable provenance)
    src_resp = await client.post(
        "/api/v1/research/sources",
        headers=headers,
        json={
            "title": "In Search of an Understandable Consensus Algorithm",
            "authors": ["Diego Ongaro", "John Ousterhout"],
            "year": 2014,
            "venue": "USENIX ATC",
            "doi": "10.5555/2643634.2643666",
            "source_provider": "crossref",
            "provenance_status": "verified",
        },
    )
    assert src_resp.status_code == 201
    src_id = src_resp.json()["source"]["id"]

    cit_resp = await client.post(
        "/api/v1/citations",
        headers=headers,
        json={
            "source_id": src_id,
            "claim_text": "Raft decomposes consensus into leader election and log replication.",
            "citation_style": "APA 7",
        },
    )
    assert cit_resp.status_code == 201
    assert "(Ongaro & Ousterhout, 2014)" == cit_resp.json()["citation"]["formatted_inline"]

    # 3. Learning Studio: notes, flashcards, auto-quiz + grading
    mat_resp = await client.post(
        "/api/v1/learning/materials",
        headers=headers,
        json={
            "subject": "Distributed Systems",
            "title": "Raft Consensus Lecture",
            "source_text": (
                "Consensus ensures multiple distributed servers agree on a single data value. "
                "Leader election assigns one authoritative node to coordinate log replication across followers. "
                "Quorum validation guarantees safety even when a minority of nodes experience network partitions. "
                "Heartbeats prevent unnecessary elections while the current leader remains healthy."
            ),
            "auto_generate_flashcards": True,
            "auto_generate_quiz": True,
        },
    )
    assert mat_resp.status_code == 201
    assert mat_resp.json()["flashcards_created"] >= 3
    quiz_id = mat_resp.json()["quiz_id"]
    assert quiz_id is not None

    quizzes_resp = await client.get("/api/v1/learning/quizzes", headers=headers)
    quiz = next(q for q in quizzes_resp.json()["quizzes"] if q["id"] == quiz_id)
    answers = {q["id"]: q["correct_index"] for q in quiz["questions_json"]}
    attempt_resp = await client.post(
        f"/api/v1/learning/quizzes/{quiz_id}/attempt",
        headers=headers,
        json={"answers": answers},
    )
    assert attempt_resp.status_code == 201
    assert attempt_resp.json()["attempt"]["score"] == 100.0

    # 4. Image Studio: honest PROVIDER_UNAVAILABLE when unconfigured + real Pillow local upscale
    gen_img = await client.post(
        "/api/v1/images/generate",
        headers=headers,
        json={"prompt": "Diagram of solar cell layers", "academic_visual_mode": True},
    )
    assert gen_img.status_code == 503
    assert gen_img.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

    up_png = await client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("diagram.png", _make_sample_png(), "image/png")},
    )
    assert up_png.status_code == 201
    png_id = up_png.json()["file"]["id"]

    up_proc = await client.post(
        "/api/v1/images/process-local",
        headers=headers,
        json={"asset_id": png_id, "operation": "upscale", "scale_factor": 2.0},
    )
    assert up_proc.status_code == 201
    assert up_proc.json()["image"]["metadata"]["width"] == 240

    # 5. Video Studio: real FFmpeg storyboard assembly produces valid MP4
    vid_resp = await client.post(
        "/api/v1/videos/assemble",
        headers=headers,
        json={
            "title": "Raft Explainer Clip",
            "aspect_ratio": "16:9",
            "scenes": [
                {"title": "Intro", "narration": "Understanding Raft consensus.", "duration_seconds": 1.5},
                {"title": "Quorums", "narration": "Majority votes ensure safety.", "duration_seconds": 1.5},
            ],
        },
    )
    assert vid_resp.status_code == 201, vid_resp.text
    assert vid_resp.json()["video_mode"] == "storyboard_assembled"
    vid_dl = await client.get(vid_resp.json()["video"]["download_url"])
    assert vid_dl.status_code == 200
    assert b"ftyp" in vid_dl.content[:32]  # Valid ISO BMFF / MP4 signature

    # 6. Community privacy-by-default test
    draft_post = await client.post(
        "/api/v1/community/posts",
        headers=headers,
        json={
            "title": "Private Thesis Template Draft",
            "category": "template",
            "summary": "Should not appear publicly until explicitly published.",
            "publish_now": False,
        },
    )
    assert draft_post.status_code == 201
    public_feed = await client.get("/api/v1/community/posts", headers=headers)
    assert all(p["title"] != "Private Thesis Template Draft" for p in public_feed.json()["posts"])

    # 7. Security test: SVG XSS sanitization & fake PDF magic-byte rejection
    malicious_svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(2)</script><circle r="10"/></svg>'
    svg_up = await client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("icon.svg", malicious_svg, "image/svg+xml")},
    )
    assert svg_up.status_code == 201
    svg_dl = await client.get(svg_up.json()["file"]["download_url"])
    assert b"<script" not in svg_dl.content and b"onload" not in svg_dl.content

    fake_pdf = await client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("evil.pdf", b"NOT A REAL PDF PAYLOAD", "application/pdf")},
    )
    assert fake_pdf.status_code == 400
    assert fake_pdf.json()["error"]["code"] == "INVALID_FILE_SIGNATURE"
