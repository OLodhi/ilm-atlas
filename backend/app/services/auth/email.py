import html
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def _init_resend():
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key


async def send_verification_email(to_email: str, token: str, display_name: str | None = None) -> bool:
    """Send email verification link."""
    _init_resend()
    name = html.escape(display_name or "there")
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Verify your Ilm Atlas account",
            "html": f"""
                <h2>Assalamu Alaikum {name},</h2>
                <p>Welcome to Ilm Atlas! Please verify your email address by clicking the link below:</p>
                <p><a href="{verify_url}">Verify Email Address</a></p>
                <p>This link expires in {settings.email_verification_expire_hours} hours.</p>
                <p>If you didn't create an account, you can safely ignore this email.</p>
                <br>
                <p>Ilm Atlas Team</p>
            """,
        })
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email[:3] + "***")
        return False


async def send_password_reset_email(to_email: str, token: str, display_name: str | None = None) -> bool:
    """Send password reset link."""
    _init_resend()
    name = html.escape(display_name or "there")
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    try:
        resend.Emails.send({
            "from": settings.email_from,
            "to": [to_email],
            "subject": "Reset your Ilm Atlas password",
            "html": f"""
                <h2>Assalamu Alaikum {name},</h2>
                <p>We received a request to reset your password. Click the link below:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>This link expires in {settings.password_reset_expire_hours} hour(s).</p>
                <p>If you didn't request this, you can safely ignore this email.</p>
                <br>
                <p>Ilm Atlas Team</p>
            """,
        })
        return True
    except Exception:
        logger.exception("Failed to send password reset email to %s", to_email[:3] + "***")
        return False
