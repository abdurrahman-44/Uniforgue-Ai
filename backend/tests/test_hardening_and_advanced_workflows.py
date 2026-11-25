"""Production hardening tests: CSRF, Password Reset, Semantic Retrieval, Embedded Figures, Jobs & Video Merge."""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient
from PIL import Image

from app.models.entities import ProjectContext
from app.services.retrieval_service import rank_project_context


def _sample_png_bytes() -> bytes:
    img = Image.new("RGB", (160, 100), color=(15, 23, 42))
    for x in range(20, 140):
        for y in range(20, 80):
            img.putpixel((x, y), (34, 211, 238))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_csrf_enforcement_and_password_reset_revokes_sessions(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "csrf_user@uniforge.edu",
            "password": "InitialPassword123!",
            "full_name": "Security Tester",
        },
    )
    assert reg.status_code == 201
    data = reg.json()
    csrf_token = data["csrf_token"]
    old_access = data["access_token"]

    # Cookie-only mutation WITHOUT X-CSRF-Token must be rejected with 403 CSRF_VALIDATION_FAILED
    bad_cookie_req = await client.post(
        "/api/v1/tasks",
        json={"title": "Blocked without CSRF"},
    )
    assert bad_cookie_req.status_code == 403
    assert bad_cookie_req.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"

    # Cookie-only mutation WITH valid X-CSRF-Token succeeds
    good_cookie_req = await client.post(
        "/api/v1/tasks",
        headers={"X-CSRF-Token": csrf_token},
        json={"title": "Allowed with valid CSRF"},
    )
    assert good_cookie_req.status_code == 201

    # Forgot password -> reset password -> old session revoked
    forgot = await client.post("/api/v1/auth/forgot-password", json={"email": "csrf_user@uniforge.edu"})
    assert forgot.status_code == 200
    reset_token = forgot.json()["dev_reset_token"]

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "NewSecurePassword456!"},
    )
    assert reset.status_code == 200

    # Prior Bearer token must now be rejected (session revoked)
    stale_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access}"})
    assert stale_me.status_code == 401

    # Login with new password works
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "csrf_user@uniforge.edu", "password": "NewSecurePassword456!"},
    )
    assert new_login.status_code == 200


def test_semantic_project_context_ranking_prefers_relevant_chunk():
    items = [
        ProjectContext(
            project_id="p1",
            owner_id="u1",
            source_type="note",
            title="UI Color Palette",
            content_excerpt="Use deep navy background and electric violet accents for glassmorphism.",
            include_in_ai_context=True,
        ),
        ProjectContext(
            project_id="p1",
            owner_id="u1",
            source_type="document",
            title="PostgreSQL Locking",
            content_excerpt="Row-level locking prevents seat double bookings during peak bus reservation traffic.",
            include_in_ai_context=True,
        ),
    ]
    ranked = rank_project_context("How do row-level locks prevent bus double bookings?", items, top_k=2)
    assert ranked[0][0].title == "PostgreSQL Locking"
    assert ranked[0][1] > ranked[1][1]


@pytest.mark.asyncio
async def test_document_embedded_figure_pdf_docx_and_video_trim_merge_and_jobs(client: AsyncClient):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "media_scholar@uniforge.edu",
            "password": "StrongPassword123!",
            "full_name": "Media Scholar",
        },
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # 1. Upload image and embed in Document -> export DOCX (contains word/media/) & PDF
    up_img = await client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("arch.png", _sample_png_bytes(), "image/png")},
    )
    assert up_img.status_code == 201
    img_id = up_img.json()["file"]["id"]

    doc = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Embedded Figure Thesis",
            "content_markdown": f"# System Design\n\n![Figure 1: Campus Architecture](asset://{img_id})\n\nEnd of section.",
            "use_template": False,
        },
    )
    assert doc.status_code == 201
    doc_id = doc.json()["document"]["id"]

    docx_resp = await client.get(f"/api/v1/documents/{doc_id}/export?format=docx", headers=headers)
    assert docx_resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(docx_resp.content)) as zf:
        assert any(name.startswith("word/media/") for name in zf.namelist())

    pdf_resp = await client.get(f"/api/v1/documents/{doc_id}/export?format=pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")

    # 2. Assemble 2 short MP4 clips -> trim -> merge -> verify jobs endpoint
    v1 = await client.post(
        "/api/v1/videos/assemble",
        headers=headers,
        json={
            "title": "Clip One",
            "scenes": [{"title": "Intro", "narration": "Scene one", "duration_seconds": 2.0, "image_asset_id": img_id}],
        },
    )
    assert v1.status_code == 201
    v1_id = v1.json()["video"]["id"]
    job_id = v1.json()["job_id"]

    job_status = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_status.status_code == 200
    assert job_status.json()["job"]["status"] == "completed"
    assert len(job_status.json()["job"]["events"]) >= 1

    trimmed = await client.post(
        "/api/v1/videos/trim",
        headers=headers,
        json={"asset_id": v1_id, "start_seconds": 0.0, "end_seconds": 1.2},
    )
    assert trimmed.status_code == 201
    v2_id = trimmed.json()["video"]["id"]

    merged = await client.post(
        "/api/v1/videos/merge",
        headers=headers,
        json={"asset_ids": [v1_id, v2_id], "title": "Combined Lecture"},
    )
    assert merged.status_code == 201
    dl = await client.get(merged.json()["video"]["download_url"])
    assert dl.status_code == 200
    assert b"ftyp" in dl.content[:32]
