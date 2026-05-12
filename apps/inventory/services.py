"""Write operations for inventory."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings
from django.utils import timezone

from apps.inventory.models import ActivityLog, Article, ArticleStatus, Group

logger = logging.getLogger(__name__)


def create_article(*, data: dict[str, Any]) -> Article:
    group_id = data.pop("group_id", None)
    article = Article.objects.create(group_id=group_id, **data)
    return Article.objects.select_related("group").get(pk=article.pk)


def update_article(article_id: int, *, data: dict[str, Any]) -> Article:
    article = Article.objects.get(pk=article_id)
    old_status = article.status

    for field, value in data.items():
        setattr(article, field, value)
    article.save()

    # Trigger Teams alert when status changes to 'danado'
    new_status = article.status
    if new_status == ArticleStatus.DANADO and old_status != ArticleStatus.DANADO:
        _send_damaged_alert(article)

    return Article.objects.select_related("group").get(pk=article.pk)


def delete_article(article_id: int) -> None:
    Article.objects.filter(pk=article_id).delete()


def log_activity(*, data: dict[str, Any]) -> ActivityLog:
    return ActivityLog.objects.create(**data)


# ---------------------------------------------------------------------------
# Teams webhook notification
# ---------------------------------------------------------------------------

def _send_damaged_alert(article: Article) -> None:
    webhook_url = getattr(settings, "TEAMS_WEBHOOK_URL", None)
    if not webhook_url:
        logger.warning("TEAMS_WEBHOOK_URL not configured, skipping damaged alert.")
        return

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "E81123",
        "summary": "Digital Curator - Alerta de Equipo Dañado",
        "title": "🚨 ¡Alerta de Equipo Dañado!",
        "text": (
            f"El artículo **{article.name}** ha sido reportado como "
            f"**DAÑADO** y requiere revisión inmediata."
        ),
        "sections": [
            {
                "activityTitle": "Detalles del Artículo",
                "facts": [
                    {"name": "Identificador / Modelo:", "value": article.name},
                    {"name": "Categoría:", "value": article.category},
                    {"name": "Número de Serie:", "value": article.serial or "N/A"},
                    {"name": "Reportado Por:", "value": article.modified_by or "Sistema"},
                ],
                "text": f"*Nota Adicional:* {article.latest_note or 'Sin notas.'}",
            }
        ],
    }

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Damaged alert sent for Article #%s", article.pk)
    except Exception:
        logger.exception("Failed to send damaged alert for Article #%s", article.pk)
