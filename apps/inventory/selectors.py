"""Read-only queries for inventory."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from apps.inventory.models import (
    ActivityLog, Article, Group,
    MaterialsRequest, DailyReport, CableRun,
    ScopeChange, EquipmentReturn, OperationsAssignment, ElevatorRental,
)


def get_all_articles() -> QuerySet[Article]:
    return Article.objects.select_related("group").all()


def get_article_by_id(article_id: int) -> Article:
    return Article.objects.select_related("group").get(pk=article_id)


def get_all_groups() -> QuerySet[Group]:
    return Group.objects.all()


def get_activity_logs() -> QuerySet[ActivityLog]:
    # El serializer solo expone article_id (no accede al objeto Article),
    # así que no se necesita select_related.
    return ActivityLog.objects.order_by("-timestamp")


def get_activity_logs_for_article(article_id: int) -> QuerySet[ActivityLog]:
    return ActivityLog.objects.filter(article_id=article_id).order_by("-timestamp")


def get_dashboard_stats() -> dict[str, int]:
    result = Article.objects.aggregate(
        enAlerta=Count("id", filter=Q(status="danado")),
        enMantenimiento=Count("id", filter=Q(status="reparacion")),
        optimo=Count("id", filter=Q(status__in=["activo", "reparado"])),
        total=Count("id"),
    )
    return result


def get_articles_updated_since(since) -> QuerySet[Article]:
    return Article.objects.select_related("group").filter(updated_at__gt=since)


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


# ===========================================================================
# Materials Request
# ===========================================================================

def get_materials_requests(*, site_id: int | None = None, status: str | None = None) -> QuerySet[MaterialsRequest]:
    qs = MaterialsRequest.objects.all()
    if site_id:
        qs = qs.filter(site_id=site_id)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-created_at")


def get_materials_request_by_id(request_id: int) -> MaterialsRequest:
    return MaterialsRequest.objects.get(pk=request_id)


def get_materials_requests_updated_since(since) -> QuerySet[MaterialsRequest]:
    return MaterialsRequest.objects.filter(updated_at__gt=since)


# ===========================================================================
# Daily Report
# ===========================================================================

def get_daily_reports(*, site_id: int | None = None) -> QuerySet[DailyReport]:
    qs = DailyReport.objects.all()
    if site_id:
        qs = qs.filter(site_id=site_id)
    return qs.order_by("-date", "-created_at")


def get_daily_reports_created_since(since) -> QuerySet[DailyReport]:
    return DailyReport.objects.filter(created_at__gt=since)


# ===========================================================================
# Cable Run
# ===========================================================================

def get_cable_runs(*, site_id: int | None = None) -> QuerySet[CableRun]:
    qs = CableRun.objects.all()
    if site_id:
        qs = qs.filter(site_id=site_id)
    return qs.order_by("label")


def get_cable_run_by_id(cable_run_id: int) -> CableRun:
    return CableRun.objects.get(pk=cable_run_id)


# ===========================================================================
# Scope Change
# ===========================================================================

def get_scope_changes(*, site_id: int | None = None, status: str | None = None) -> QuerySet[ScopeChange]:
    qs = ScopeChange.objects.all()
    if site_id:
        qs = qs.filter(site_id=site_id)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-created_at")


def get_scope_change_by_id(scope_change_id: int) -> ScopeChange:
    return ScopeChange.objects.get(pk=scope_change_id)


# ===========================================================================
# Equipment Return
# ===========================================================================

def get_equipment_returns(*, site_id: int | None = None) -> QuerySet[EquipmentReturn]:
    qs = EquipmentReturn.objects.all()
    if site_id:
        qs = qs.filter(site_id=site_id)
    return qs.order_by("-created_at")


def get_equipment_return_by_id(return_id: int) -> EquipmentReturn:
    return EquipmentReturn.objects.get(pk=return_id)


# ===========================================================================
# Operations Assignment
# ===========================================================================

def get_operations_assignment(site_id: int) -> OperationsAssignment | None:
    return OperationsAssignment.objects.filter(site_id=site_id).first()


# ===========================================================================
# Elevator Rental
# ===========================================================================

def get_elevator_rental(site_id: int) -> ElevatorRental | None:
    return ElevatorRental.objects.filter(site_id=site_id).first()
