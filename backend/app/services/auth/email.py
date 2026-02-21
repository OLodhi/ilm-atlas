import html
import logging

import resend

from app.config import settings
from app.services.auth.email_templates import password_reset_email, verification_email

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
            "html": verification_email(name, verify_url, settings.email_verification_expire_hours),
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
            "html": password_reset_email(name, reset_url, settings.password_reset_expire_hours),
        })
        return True
    except Exception:
        logger.exception("Failed to send password reset email to %s", to_email[:3] + "***")
        return False
