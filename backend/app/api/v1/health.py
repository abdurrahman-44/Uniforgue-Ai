"""Health check & system readiness routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.providers.ai_providers import ai_service
from app.providers.image_providers import image_provider_service
from app.providers.video_providers import video_provider_status

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    ai_status = await ai_service.status(db)
    img_status = await image_provider_service.status(db)
    vid_status = video_provider_status()

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {"connected": db_ok},
        "storage": {"backend": settings.storage_backend},
        "providers": {
            "ai": {"available": ai_status["available"], "active": ai_status["active_provider"]},
            "image": {"available": img_status["available"], "active": img_status["active_provider"]},
            "video": {
                "generative_available": vid_status["generative_video_available"],
                "local_ffmpeg_available": vid_status["local_ffmpeg_assembly_available"],
            },
        },
    }
