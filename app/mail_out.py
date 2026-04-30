"""SMTP — mirrors backend/src/config/mailer.js (subjects + minimal HTML)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool((settings.smtp_user or "").strip() and (settings.smtp_pass or "").strip())


def get_template(template_type: str, data: dict) -> tuple[str, str] | None:
    if template_type == "login_otp":
        otp = data.get("otp", "")
        return (
            "Your Login Verification Code - IITTNiF",
            f"<p>Your login verification code is <b>{otp}</b></p><p>Valid for 10 minutes.</p>",
        )
    if template_type == "reset_otp":
        otp = data.get("otp", "")
        return (
            "Password Reset Code - IITTNiF",
            f"<p>Your password reset code is <b>{otp}</b></p><p>Valid for 15 minutes.</p>",
        )
    if template_type == "welcome_invitation":
        name = data.get("name", "User")
        email = data.get("email", "")
        password = data.get("password", "")
        login_url = data.get("loginUrl", "")
        return (
            "Your IITTNiF Admin Account - Login Credentials Inside",
            f"<p>Hello {name},</p><p>Email: {email}</p><p>Temporary password: {password}</p><p>Login: {login_url}</p>",
        )
    if template_type == "admin_activity":
        action = data.get("actionType", "comment")
        if action == "edit":
            return (
                "IITTNiF: Startup Field Updated by Admin",
                f"<p>Field {data.get('fieldLabel')} was updated.</p><p>Old: {data.get('oldValue')}</p><p>New: {data.get('newValue')}</p>",
            )
        return (
            "IITTNiF: New Admin Comment on Your Startup",
            f"<p>Admin comment on {data.get('fieldLabel', 'General')}</p><p>{data.get('commentText', '')}</p>",
        )
    return None


def send_email_with_template(to: str, template_type: str, data: dict) -> None:
    if not _configured():
        logger.warning("SMTP not configured. Skipping email %s to %s", template_type, to)
        return

    tpl = get_template(template_type, data)
    if not tpl:
        logger.error("No template found for %s", template_type)
        return

    subject, html_content = tpl

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
        logger.info("Email %s sent successfully to %s", template_type, to)
    except Exception as e:
        logger.error("Failed to send email %s to %s: %s", template_type, to, e)
