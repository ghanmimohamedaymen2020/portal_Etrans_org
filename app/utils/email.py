"""Utilitaire d'envoi d'e-mails."""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


def send_email(
    recipient: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> bool:
    """Envoie un e-mail via SMTP.

    Returns True si l'envoi a réussi, False sinon.
    """
    try:
        sender = current_app.config["MAIL_USERNAME"]
        password = current_app.config["MAIL_PASSWORD"]
        if not sender or not password:
            current_app.logger.error("MAIL_USERNAME ou MAIL_PASSWORD non configuré.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient

        msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(
            current_app.config["MAIL_SERVER"],
            current_app.config["MAIL_PORT"],
        ) as server:
            if current_app.config.get("MAIL_USE_TLS", True):
                server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        return True
    except Exception as exc:
        current_app.logger.error("Erreur envoi e-mail : %s", exc)
        return False
