"""Authentication, Sessions, Email Verification, Password Reset & CSRF."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, log_audit, push_notification
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError, ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.models.entities import (
    AuthToken,
    User,
    UserProfile,
    UserSession,
    UserSettings,
    Workspace,
    WorkspaceMember,
)
from app.services.email_service import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    university: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    academic_level: str = Field(default="undergraduate", max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key="uniforge_access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="uniforge_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )
    response.set_cookie(
        key="uniforge_csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


def _serialize_user(user: User, profile: UserProfile | None, usettings: UserSettings | None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_verified": user.is_verified,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "profile": {
            "full_name": profile.full_name if profile else user.email.split("@")[0],
            "university": profile.university if profile else None,
            "department": profile.department if profile else None,
            "academic_level": profile.academic_level if profile else "undergraduate",
            "bio": profile.bio if profile else None,
            "country": profile.country if profile else None,
            "avatar_asset_id": profile.avatar_asset_id if profile else None,
        },
        "settings": {
            "theme": usettings.theme if usettings else "dark",
            "language": usettings.language if usettings else "en",
            "reduced_motion": usettings.reduced_motion if usettings else False,
            "default_citation_style": usettings.default_citation_style if usettings else "APA 7",
            "ai_context_opt_in": usettings.ai_context_opt_in if usettings else True,
            "storage_quota_bytes": usettings.storage_quota_bytes if usettings else settings.default_quota_bytes,
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    normalized_email = body.email.lower().strip()
    existing = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("An account with this email already exists.")

    # First registered account can optionally bootstrap admin if none exists; otherwise student
    existing_count = (await db.execute(select(User.id).limit(1))).first()
    assigned_role = "admin" if existing_count is None else "student"

    user = User(
        email=normalized_email,
        password_hash=hash_password(body.password),
        role=assigned_role,
        is_active=True,
        is_verified=False,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        full_name=body.full_name.strip(),
        university=body.university,
        department=body.department,
        academic_level=body.academic_level,
    )
    usettings = UserSettings(user_id=user.id, storage_quota_bytes=settings.default_quota_bytes)
    db.add_all([profile, usettings])

    # Default private personal workspace
    workspace = Workspace(
        owner_id=user.id,
        name=f"{body.full_name.strip().split()[0]}'s Academic Workspace",
        slug=f"workspace-{user.id[:8]}",
        description="Your private academic workspace for research, writing, and projects.",
        visibility="private",
        is_personal=True,
    )
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))

    # Verification token
    raw_verify_token = generate_opaque_token(24)
    db.add(
        AuthToken(
            user_id=user.id,
            token_type="verify_email",
            token_hash=hash_opaque_token(raw_verify_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )

    # Create session
    session = UserSession(
        user_id=user.id,
        refresh_token_hash="pending",
        user_agent=(request.headers.get("User-Agent") or "")[:500],
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(user.id, user.role, session.id)
    refresh_token = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = hash_opaque_token(refresh_token)
    csrf_token = generate_csrf_token(session.id)

    await log_audit(db, user.id, "auth.register", "user", user.id, session.ip_address)
    await push_notification(
        db,
        user.id,
        title="Welcome to UNIFORGE AI",
        message="Your free academic ecosystem is ready. Create your first project or explore the studios.",
        category="welcome",
        action_url="/dashboard",
    )
    await db.commit()
    await send_verification_email(user.email, profile.full_name, raw_verify_token)

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)
    payload: dict = {
        "user": _serialize_user(user, profile, usettings),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
        "default_workspace_id": workspace.id,
    }
    if settings.app_env != "production":
        payload["dev_verification_token"] = raw_verify_token
    return payload


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    normalized_email = body.email.lower().strip()
    user = (
        await db.execute(
            select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if user.is_suspended:
        raise ForbiddenError(f"Account suspended: {user.suspension_reason or 'Contact administrator'}")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive.")

    user.last_login_at = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user.id,
        refresh_token_hash="pending",
        user_agent=(request.headers.get("User-Agent") or "")[:500],
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(user.id, user.role, session.id)
    refresh_token = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = hash_opaque_token(refresh_token)
    csrf_token = generate_csrf_token(session.id)

    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    usettings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    await log_audit(db, user.id, "auth.login", "session", session.id, session.ip_address)
    await db.commit()

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return {
        "user": _serialize_user(user, profile, usettings),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "csrf_token": csrf_token,
    }


@router.post("/refresh")
async def refresh_session(
    body: RefreshRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    token = body.refresh_token or request.cookies.get("uniforge_refresh_token")
    if not token:
        raise UnauthorizedError("Refresh token required.")
    try:
        payload = decode_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired refresh token.")
    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type.")

    sess = (
        await db.execute(select(UserSession).where(UserSession.id == payload.get("sid")))
    ).scalar_one_or_none()
    if not sess or sess.revoked_at is not None or sess.refresh_token_hash != hash_opaque_token(token):
        raise UnauthorizedError("Session is invalid or revoked.")

    user = (
        await db.execute(select(User).where(User.id == sess.user_id, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not user or user.is_suspended:
        raise UnauthorizedError("User account unavailable.")

    new_access = create_access_token(user.id, user.role, sess.id)
    new_refresh = create_refresh_token(user.id, sess.id)
    sess.refresh_token_hash = hash_opaque_token(new_refresh)
    csrf_token = generate_csrf_token(sess.id)
    await db.commit()

    _set_auth_cookies(response, new_access, new_refresh, csrf_token)
    return {"access_token": new_access, "refresh_token": new_refresh, "csrf_token": csrf_token}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sid = getattr(request.state, "session_id", None)
    if sid:
        sess = (await db.execute(select(UserSession).where(UserSession.id == sid))).scalar_one_or_none()
        if sess:
            sess.revoked_at = datetime.now(timezone.utc)
    await log_audit(db, user.id, "auth.logout", "session", sid)
    await db.commit()
    response.delete_cookie("uniforge_access_token", path="/")
    response.delete_cookie("uniforge_refresh_token", path="/api/v1/auth")
    response.delete_cookie("uniforge_csrf_token", path="/")
    return {"message": "Logged out successfully."}


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    usettings = (await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))).scalar_one_or_none()
    return {"user": _serialize_user(user, profile, usettings)}


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    tok = (
        await db.execute(
            select(AuthToken).where(
                AuthToken.token_hash == hash_opaque_token(body.token),
                AuthToken.token_type == "verify_email",
                AuthToken.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not tok or tok.expires_at.replace(tzinfo=timezone.utc) < now:
        raise AppError("Verification token is invalid or expired.", code="INVALID_TOKEN", status_code=400)

    user = (await db.execute(select(User).where(User.id == tok.user_id))).scalar_one_or_none()
    if not user:
        raise AppError("Account not found.", code="NOT_FOUND", status_code=404)
    user.is_verified = True
    tok.used_at = now
    await log_audit(db, user.id, "auth.verify_email", "user", user.id)
    await db.commit()
    return {"verified": True, "message": "Email verified successfully."}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(
            select(User).where(User.email == body.email.lower().strip(), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    raw_token = None
    if user:
        raw_token = generate_opaque_token(24)
        db.add(
            AuthToken(
                user_id=user.id,
                token_type="reset_password",
                token_hash=hash_opaque_token(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        await log_audit(db, user.id, "auth.forgot_password", "user", user.id)
        await db.commit()
        await send_password_reset_email(user.email, raw_token)
    resp: dict = {"message": "If an account exists for that email, a password reset link has been issued."}
    if settings.app_env != "production" and raw_token:
        resp["dev_reset_token"] = raw_token
    return resp


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    tok = (
        await db.execute(
            select(AuthToken).where(
                AuthToken.token_hash == hash_opaque_token(body.token),
                AuthToken.token_type == "reset_password",
                AuthToken.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not tok or tok.expires_at.replace(tzinfo=timezone.utc) < now:
        raise AppError("Password reset token is invalid or expired.", code="INVALID_TOKEN", status_code=400)

    user = (await db.execute(select(User).where(User.id == tok.user_id))).scalar_one_or_none()
    if not user:
        raise AppError("User not found.", code="NOT_FOUND", status_code=404)
    user.password_hash = hash_password(body.new_password)
    tok.used_at = now
    # Revoke all existing sessions on password reset
    sessions = (await db.execute(select(UserSession).where(UserSession.user_id == user.id))).scalars().all()
    for s in sessions:
        s.revoked_at = now
    await log_audit(db, user.id, "auth.reset_password", "user", user.id)
    await db.commit()
    return {"message": "Password reset successfully. Please sign in again."}


@router.get("/sessions")
async def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_sid = getattr(request.state, "session_id", None)
    sessions = (
        await db.execute(
            select(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.created_at.desc())
        )
    ).scalars().all()
    return {
        "sessions": [
            {
                "id": s.id,
                "user_agent": s.user_agent,
                "ip_address": s.ip_address,
                "created_at": s.created_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "is_current": s.id == current_sid,
            }
            for s in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sess = (
        await db.execute(
            select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not sess:
        raise AppError("Session not found.", code="NOT_FOUND", status_code=404)
    sess.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"revoked": True}
