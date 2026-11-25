"""Security primitives: Argon2id hashing, JWT, CSRF, HMAC signed URLs, secret encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# Argon2id configuration following OWASP recommendations
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except Exception:
        return True


def create_access_token(
    subject: str,
    role: str,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "sid": session_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(12),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_csrf_token(session_id: str) -> str:
    nonce = secrets.token_hex(16)
    msg = f"{session_id}:{nonce}".encode("utf-8")
    sig = hmac.new(settings.csrf_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def verify_csrf_token(session_id: str, token: str) -> bool:
    if not token or "." not in token:
        return False
    nonce, provided_sig = token.split(".", 1)
    msg = f"{session_id}:{nonce}".encode("utf-8")
    expected_sig = hmac.new(
        settings.csrf_secret.encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(provided_sig, expected_sig)


def create_signed_download_token(asset_id: str, user_id: str, ttl_seconds: int = 900) -> tuple[str, int]:
    expires = int(time.time()) + ttl_seconds
    msg = f"{asset_id}:{user_id}:{expires}".encode("utf-8")
    sig = hmac.new(settings.secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return sig, expires


def verify_signed_download_token(asset_id: str, user_id: str, expires: int, sig: str) -> bool:
    if expires < int(time.time()):
        return False
    msg = f"{asset_id}:{user_id}:{expires}".encode("utf-8")
    expected = hmac.new(settings.secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _get_fernet() -> Fernet:
    if settings.encryption_key:
        raw_key = settings.encryption_key.encode("utf-8")
        try:
            return Fernet(raw_key)
        except Exception:
            pass
    # Derive deterministic 32-byte Fernet key from secret_key for local/dev consistency
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}{'*' * (len(secret) - 8)}{secret[-4:]}"
