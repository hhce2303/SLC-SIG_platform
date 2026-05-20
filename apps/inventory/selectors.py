"""Read-only queries for inventory."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.inventory.models import ActivityLog, Article, Group


def get_all_articles() -> QuerySet[Article]:
    return Article.objects.select_related("group").all()


def get_article_by_id(article_id: int) -> Article:
    return Article.objects.select_related("group").get(pk=article_id)


def get_all_groups() -> QuerySet[Group]:
    return Group.objects.all()


def get_activity_logs() -> QuerySet[ActivityLog]:
    return ActivityLog.objects.select_related("article").all()


def get_activity_logs_for_article(article_id: int) -> QuerySet[ActivityLog]:
    return ActivityLog.objects.filter(article_id=article_id).order_by("-timestamp")


def get_dashboard_stats() -> dict[str, int]:
    articles = Article.objects.all()
    return {
        "enAlerta": articles.filter(status="danado").count(),
        "enMantenimiento": articles.filter(status="reparacion").count(),
        "optimo": articles.filter(status__in=["activo", "reparado"]).count(),
        "total": articles.count(),
    }


def get_cameras_by_site(site_id: int) -> list[dict]:
    """Obtiene cámaras de un sitio: id, brand, model, camera_type."""
    from django.db import connections

    with connections["default"].cursor() as cur:
        cur.execute(
            """
            SELECT id, brand, model, camera_type
            FROM cameras
            WHERE site_id = %s
            """,
            [site_id],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
