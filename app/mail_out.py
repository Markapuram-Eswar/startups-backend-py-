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
        logger.warning("Skipping email %s to %s (SMTP not configured)", template_type, to)
        return
    t = get_template(template_type, data)
    if not t:
        raise ValueError(f"Template type {template_type!r} not found")
    subject, html = t
    host = settings.smtp_host
    port = int(settings.smtp_port)
    user = (settings.smtp_user or "").strip()
    password = (settings.smtp_pass or "").strip()
    from_email = (settings.smtp_from_email or user).strip()
    from_name = (settings.smtp_from_name or "IITTNiF").strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    text_fallback = f"OTP/Code: {data.get('otp', '')}"
    msg.attach(MIMEText(text_fallback, "plain"))

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(from_email, [to], msg.as_string())
    logger.info("Mail sent to %s (%s)", to, template_type)
