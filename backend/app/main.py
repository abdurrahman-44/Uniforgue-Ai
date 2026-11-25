"""UNIFORGE AI FastAPI Application Entry Point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import rate_limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="UNIFORGE AI API",
        description="Complete AI-Powered Academic Productivity & Creation Ecosystem API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_and_rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not request.url.path.endswith("/health"):
            allowed, retry_after = rate_limiter.check(
                f"ip:{client_ip}",
                limit=settings.rate_limit_requests_per_minute,
                window_seconds=60,
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please slow down.",
                            "details": {"retry_after_seconds": retry_after},
                        }
                    },
                )

        # Enforce CSRF token verification on cookie-authenticated state-changing requests
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and not request.headers.get("Authorization")
            and request.cookies.get("uniforge_access_token")
        ):
            csrf_exempt = (
                "/auth/login",
                "/auth/register",
                "/auth/refresh",
                "/auth/forgot-password",
                "/auth/reset-password",
                "/auth/verify-email",
            )
            if not any(request.url.path.endswith(p) for p in csrf_exempt):
                from app.core.security import decode_token, verify_csrf_token

                csrf_header = request.headers.get("X-CSRF-Token", "")
                try:
                    token_payload = decode_token(request.cookies["uniforge_access_token"])
                    sid = str(token_payload.get("sid", ""))
                    if not sid or not verify_csrf_token(sid, csrf_header):
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": {
                                    "code": "CSRF_VALIDATION_FAILED",
                                    "message": "Missing or invalid X-CSRF-Token header for cookie-authenticated request.",
                                    "details": None,
                                }
                            },
                        )
                except Exception:
                    pass

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'"
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "tagline": "From Academic Ideas to Submission-Ready Work.",
            "api_docs": "/api/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
