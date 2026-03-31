"""Async email sender — wraps aiosmtplib for password reset emails."""
from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.utils.logging import get_logger

logger = get_logger(__name__)


async def send_password_reset_email(
    *,
    to_email: str,
    reset_link: str,
    from_email: str,
    from_name: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str,
    use_tls: bool = True,
) -> None:
    """Send a password-reset email to *to_email*.

    Raises on SMTP failure so the caller can decide whether to surface the
    error to the user or swallow it (the endpoint always returns 200 to
    prevent email enumeration).
    """
    import aiosmtplib

    subject = "Reset your DocMind password"
    html_body = f"""
    <html><body>
    <p>You requested a password reset for your DocMind account.</p>
    <p>Click the link below to set a new password. It expires in <strong>1 hour</strong>.</p>
    <p><a href="{reset_link}" style="font-size:16px;color:#4f46e5;">Reset my password</a></p>
    <p>If you did not request this, you can safely ignore this email.</p>
    <hr/>
    <small>DocMind — AI-powered PDF Q&amp;A</small>
    </body></html>
    """
    text_body = (
        f"Reset your DocMind password\n\n"
        f"Click the link below (expires in 1 hour):\n{reset_link}\n\n"
        f"If you did not request this, ignore this email."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=smtp_host,
        port=smtp_port,
        username=smtp_username,
        password=smtp_password,
        start_tls=use_tls,
    )
    logger.info("Password reset email sent to %s", to_email)
