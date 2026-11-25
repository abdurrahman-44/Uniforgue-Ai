"""Secure File & Object Storage Service (Local + S3/MinIO) with validation & text extraction."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
from docx import Document as DocxDocument
from pptx import Presentation as PptxPresentation
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.entities import MediaAsset, UserSettings

ALLOWED_EXTENSIONS: dict[str, tuple[str, str]] = {
    ".pdf": ("application/pdf", "file"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "file"),
    ".txt": ("text/plain", "file"),
    ".md": ("text/markdown", "file"),
    ".png": ("image/png", "image"),
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".webp": ("image/webp", "image"),
    ".svg": ("image/svg+xml", "image"),
    ".mp4": ("video/mp4", "video"),
    ".mp3": ("audio/mpeg", "audio"),
    ".wav": ("audio/wav", "audio"),
    ".srt": ("application/x-subrip", "file"),
}

MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".docx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
}


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    clean = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return clean[:180] or "upload.bin"


def sanitize_svg(raw_bytes: bytes) -> bytes:
    """Strip executable scripts and unsafe handlers from SVG uploads."""
    text = raw_bytes.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", text)
    text = re.sub(r"(?is)<foreignObject.*?>.*?</foreignObject>", "", text)
    text = re.sub(r"(?i)\son[a-z]+\s*=\s*(['\"]).*?\1", "", text)
    text = re.sub(r"(?i)javascript:", "", text)
    return text.encode("utf-8")


def validate_file_bytes(filename: str, content: bytes) -> tuple[str, str, bytes]:
    """Validate extension, size, magic bytes, and sanitize SVGs."""
    if not content:
        raise AppError("Uploaded file is empty.", code="EMPTY_FILE", status_code=400)
    if len(content) > settings.max_upload_bytes:
        raise AppError(
            f"File exceeds maximum upload limit of {settings.max_upload_size_mb} MB.",
            code="FILE_TOO_LARGE",
            status_code=413,
        )

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(
            f"Unsupported file format '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS.keys()))}",
            code="UNSUPPORTED_FILE_TYPE",
            status_code=400,
        )

    sigs = MAGIC_SIGNATURES.get(ext)
    if sigs and not any(content.startswith(sig) for sig in sigs):
        raise AppError(
            f"File contents do not match declared {ext} file signature.",
            code="INVALID_FILE_SIGNATURE",
            status_code=400,
        )

    if ext == ".svg":
        content = sanitize_svg(content)

    mime_type, asset_type = ALLOWED_EXTENSIONS[ext]
    return mime_type, asset_type, content


def extract_text_from_file(filename: str, content: bytes) -> str | None:
    """Extract readable text from PDF, DOCX, PPTX, TXT, and Markdown files."""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            with fitz.open(stream=content, filetype="pdf") as doc:
                parts = [page.get_text("text") for page in doc]
            return "\n".join(parts).strip()
        if ext == ".docx":
            doc = DocxDocument(io.BytesIO(content))
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for tbl in doc.tables:
                for row in tbl.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(parts).strip()
        if ext == ".pptx":
            prs = PptxPresentation(io.BytesIO(content))
            parts = []
            for idx, slide in enumerate(prs.slides, start=1):
                slide_texts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())
                if slide_texts:
                    parts.append(f"[Slide {idx}]\n" + "\n".join(slide_texts))
            return "\n\n".join(parts).strip()
        if ext in {".txt", ".md", ".srt"}:
            return content.decode("utf-8", errors="replace").strip()
    except Exception:
        return None
    return None


class StorageService:
    """Unified storage service supporting local disk (dev) and S3/MinIO (production)."""

    def _s3_client(self):
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def put_bytes(self, storage_key: str, content: bytes, content_type: str) -> str:
        if settings.storage_backend == "s3" and settings.s3_access_key:
            client = self._s3_client()
            client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=storage_key,
                Body=content,
                ContentType=content_type,
            )
            return "s3"
        dest = settings.storage_root / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return "local"

    def get_bytes(self, storage_key: str, backend: str = "local") -> bytes:
        if backend == "s3" and settings.s3_access_key:
            client = self._s3_client()
            obj = client.get_object(Bucket=settings.s3_bucket_name, Key=storage_key)
            return obj["Body"].read()
        target = settings.storage_root / storage_key
        if not target.exists():
            raise AppError("Stored file payload not found.", code="STORAGE_MISSING", status_code=404)
        return target.read_bytes()

    def delete_object(self, storage_key: str, backend: str = "local") -> None:
        try:
            if backend == "s3" and settings.s3_access_key:
                client = self._s3_client()
                client.delete_object(Bucket=settings.s3_bucket_name, Key=storage_key)
            else:
                target = settings.storage_root / storage_key
                if target.exists():
                    target.unlink()
        except Exception:
            pass

    async def check_quota(self, db: AsyncSession, user_id: str, additional_bytes: int) -> None:
        settings_row = (
            await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        ).scalar_one_or_none()
        quota = settings_row.storage_quota_bytes if settings_row else settings.default_quota_bytes
        used = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
                        MediaAsset.owner_id == user_id,
                        MediaAsset.deleted_at.is_(None),
                    )
                )
            ).scalar()
            or 0
        )
        if used + additional_bytes > quota:
            raise AppError(
                f"Storage quota exceeded ({used // (1024*1024)} MB / {quota // (1024*1024)} MB).",
                code="STORAGE_QUOTA_EXCEEDED",
                status_code=413,
            )

    async def save_asset(
        self,
        db: AsyncSession,
        owner_id: str,
        filename: str,
        content: bytes,
        workspace_id: str | None = None,
        project_id: str | None = None,
        asset_type_override: str | None = None,
        metadata: dict | None = None,
    ) -> MediaAsset:
        mime_type, inferred_type, clean_content = validate_file_bytes(filename, content)
        await self.check_quota(db, owner_id, len(clean_content))

        safe_name = sanitize_filename(filename)
        storage_key = f"{owner_id}/{uuid.uuid4().hex}_{safe_name}"
        backend_used = self.put_bytes(storage_key, clean_content, mime_type)
        sha256_hash = hashlib.sha256(clean_content).hexdigest()
        extracted = extract_text_from_file(safe_name, clean_content)

        asset = MediaAsset(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            filename=safe_name,
            original_filename=filename[:255],
            mime_type=mime_type,
            asset_type=asset_type_override or inferred_type,
            size_bytes=len(clean_content),
            storage_backend=backend_used,
            storage_key=storage_key,
            sha256_hash=sha256_hash,
            extracted_text=extracted,
            extra_metadata=metadata or {},
        )
        db.add(asset)
        await db.flush()
        return asset


storage_service = StorageService()
