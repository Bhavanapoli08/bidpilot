"""
Best-effort transactional email via SMTP.

Email is an enhancement to in-app notifications, never a hard dependency: if SMTP
isn't configured the call logs and returns False rather than raising, so alert
creation always succeeds.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send a single email. Returns True on success, False (logged) otherwise."""
    if not is_configured():
        logger.info("SMTP not configured; skipping email to %s (%s)", to, subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:  # noqa: BLE001 - email must never break the caller
        logger.warning("Email to %s failed: %s", to, e)
        return False
