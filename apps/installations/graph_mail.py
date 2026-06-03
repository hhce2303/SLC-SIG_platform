from __future__ import annotations

import logging
from typing import Iterable

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class GraphMailConfigError(RuntimeError):
    """Raised when Graph mail settings are incomplete."""


def _required_settings() -> dict[str, str]:
    return {
        "tenant_id": getattr(settings, "MS_GRAPH_TENANT_ID", "") or "",
        "client_id": getattr(settings, "MS_GRAPH_CLIENT_ID", "") or "",
        "client_secret": getattr(settings, "MS_GRAPH_CLIENT_SECRET", "") or "",
        "sender": getattr(settings, "MS_GRAPH_SENDER", "") or "",
    }


def is_graph_mail_configured() -> bool:
    cfg = _required_settings()
    return all(cfg.values())


def _graph_token(client: httpx.Client, tenant_id: str, client_id: str, client_secret: str) -> str:
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = client.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
    )
    response.raise_for_status()
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph token response did not include access_token")
    return token


def send_graph_mail(
    *,
    to_emails: Iterable[str],
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> bool:
    recipients = [email.strip() for email in to_emails if email and email.strip()]
    if not recipients:
        return False

    cfg = _required_settings()
    if not all(cfg.values()):
        raise GraphMailConfigError(
            "MS_GRAPH_TENANT_ID / MS_GRAPH_CLIENT_ID / MS_GRAPH_CLIENT_SECRET / MS_GRAPH_SENDER are required"
        )

    content = text_content.strip() if text_content and text_content.strip() else ""
    body_content = content or html_content
    body_type = "Text" if content else "HTML"

    with httpx.Client(timeout=20.0) as client:
        token = _graph_token(client, cfg["tenant_id"], cfg["client_id"], cfg["client_secret"])
        send_url = f"https://graph.microsoft.com/v1.0/users/{cfg['sender']}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": body_type,
                    "content": body_content,
                },
                "toRecipients": [{"emailAddress": {"address": email}} for email in recipients],
            },
            "saveToSentItems": "false",
        }
        response = client.post(
            send_url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        response.raise_for_status()

    logger.info("Graph mail sent to %s recipients", len(recipients))
    return True
