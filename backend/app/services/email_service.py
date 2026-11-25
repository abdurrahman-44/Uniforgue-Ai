"""SMTP Email Delivery Service with graceful dev logging when SMTP is unconfigured."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("uniforge.email")


def _send_smtp_sync(to_email: str, subject: str, body_text: str, body_html: str) -> bool:
    if not settings.smtp_host:
        logger.info("email_dev_mode to=%s subject=%s (SMTP_HOST not configured)", to_email, subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    return True


async def send_verification_email(to_email: str, full_name: str, token: str) -> bool:
    verify_url = f"{settings.app_url.rstrip('/')}/verify-email?token={token}"
    subject = "Verify your UNIFORGE AI academic account"
    body_text = (
        f"Hello {full_name},\n\n"
        f"Welcome to UNIFORGE AI. Please verify your email address by visiting:\n{verify_url}\n\n"
        "This link expires in 24 hours."
    )
    body_html = (
        f"<p>Hello <strong>{full_name}</strong>,</p>"
        "<p>Welcome to <strong>UNIFORGE AI</strong> — your free academic productivity ecosystem.</p>"
        f'<p><a href="{verify_url}">Verify Email Address</a></p>'
        "<p>This link expires in 24 hours.</p>"
    )
    try:
        return await asyncio.to_thread(_send_smtp_sync, to_email, subject, body_text, body_html)
    except Exception as exc:
        logger.warning("email_delivery_failed type=verification error=%s", type(exc).__name__)
        return False


async def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_url = f"{settings.app_url.rstrip('/')}/reset-password?token={token}"
    subject = "Reset your UNIFORGE AI password"
    body_text = (
        "You requested a password reset for your UNIFORGE AI account.\n\n"
        f"Reset your password here (expires in 1 hour):\n{reset_url}\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    body_html = (
        "<p>You requested a password reset for your <strong>UNIFORGE AI</strong> account.</p>"
        f'<p><a href="{reset_url}">Reset Password</a> (valid for 1 hour)</p>'
        "<p>If you did not request this, you can safely ignore this email.</p>"
    )
    try:
        return await asyncio.to_thread(_send_smtp_sync, to_email, subject, body_text, body_html)
    except Exception as exc:
        logger.warning("email_delivery_failed type=password_reset error=%s", type(exc).__name__)
        return False
