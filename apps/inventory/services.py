"""Write operations for inventory."""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.inventory.models import (
    ActivityLog, Article, CameraSpecChangeLog, Group,
    MaterialsRequest, DailyReport, CableRun,
    ScopeChange, EquipmentReturn, OperationsAssignment, ElevatorRental,
)
from apps.core.realtime import CH_INSTALLATIONS, CH_INVENTORY, publish as _rt_publish

logger = logging.getLogger(__name__)


import re as _re
_DEVICE_TAG_RE = _re.compile(r"\[device:([^\]]+)\]")


def _extract_device_id(note: str) -> str:
    """Return the device catalog ID embedded in a note tag, e.g. 'cam-42'."""
    m = _DEVICE_TAG_RE.search(note or "")
    return m.group(1) if m else ""


def _publish_article(article: Article) -> None:
    # El front escucha el evento snake_case `article_updated` (→ sig:article-updated)
    # y lo usa como disparador para re-consultar. El nombre debe coincidir exacto.
    # Se publica en ambos canales para llegar a cualquier stream que escuche el front.
    from apps.inventory.serializers import ArticleReadSerializer
    payload = [dict(ArticleReadSerializer(article).data)]
    _rt_publish(CH_INVENTORY, "article_updated", payload)
    _rt_publish(CH_INSTALLATIONS, "article_updated", payload)


def create_article(*, data: dict[str, Any]) -> Article:
    group_id = data.pop("group_id", None)
    data.setdefault("device_id", _extract_device_id(data.get("latest_note", "")))
    article = Article.objects.create(group_id=group_id, **data)
    article = Article.objects.select_related("group").get(pk=article.pk)
    _publish_article(article)
    return article


def update_article(article_id: int, *, data: dict[str, Any]) -> Article:
    article = Article.objects.get(pk=article_id)

    if "latest_note" in data:
        data["device_id"] = _extract_device_id(data["latest_note"])

    for field, value in data.items():
        setattr(article, field, value)
    article.save()

    article = Article.objects.select_related("group").get(pk=article.pk)
    _publish_article(article)
    return article


def delete_article(article_id: int) -> None:
    Article.objects.filter(pk=article_id).delete()


def log_activity(*, data: dict[str, Any]) -> ActivityLog:
    return ActivityLog.objects.create(**data)


# ===========================================================================
# Materials Request
# ===========================================================================

def create_materials_request(*, user_id: int, data: dict) -> MaterialsRequest:
    obj = MaterialsRequest.objects.create(
        site_id=data["site_id"],
        requested_by_id=user_id,
        items=data.get("items", []),
        notes=data.get("notes", ""),
    )
    from apps.inventory.serializers import MaterialsRequestReadSerializer
    _rt_publish(CH_INVENTORY, "materials_request_created",
                dict(MaterialsRequestReadSerializer(obj).data))
    return obj


def review_materials_request(request_id: int, *, reviewer_id: int, status: str, reviewer_notes: str = "") -> MaterialsRequest:
    obj = MaterialsRequest.objects.get(pk=request_id)
    obj.status = status
    obj.reviewer_id = reviewer_id
    obj.reviewed_at = timezone.now()
    obj.notes = reviewer_notes if reviewer_notes else obj.notes
    obj.save(update_fields=["status", "reviewer_id", "reviewed_at", "notes", "updated_at"])
    from apps.inventory.serializers import MaterialsRequestReadSerializer
    _rt_publish(CH_INVENTORY, "materials_request_updated",
                dict(MaterialsRequestReadSerializer(obj).data))
    return obj


# ===========================================================================
# Daily Report
# ===========================================================================

def create_daily_report(*, user_id: int, data: dict) -> DailyReport:
    dr = DailyReport.objects.create(
        site_id=data["site_id"],
        date=data["date"],
        submitted_by_id=user_id,
        q1=data.get("q1", ""),
        q2=data.get("q2", ""),
        q3=data.get("q3", ""),
        q4=data.get("q4", ""),
        q5=data.get("q5", ""),
        q6=data.get("q6", ""),
        q7=data.get("q7", ""),
        q8=data.get("q8", ""),
        q9=data.get("q9", ""),
        q10=data.get("q10", ""),
        q11=data.get("q11", ""),
    )
    from apps.inventory.serializers import DailyReportReadSerializer
    _rt_publish(CH_INVENTORY, "daily_report_created",
                dict(DailyReportReadSerializer(dr).data))
    return dr


# ===========================================================================
# Cable Run
# ===========================================================================

def create_cable_run(*, data: dict) -> CableRun:
    return CableRun.objects.create(**data)


def update_cable_run(cable_run_id: int, *, data: dict) -> CableRun:
    CableRun.objects.filter(pk=cable_run_id).update(**data)
    return CableRun.objects.get(pk=cable_run_id)


def delete_cable_run(cable_run_id: int) -> None:
    CableRun.objects.filter(pk=cable_run_id).delete()


# ===========================================================================
# Scope Change
# ===========================================================================

def create_scope_change(*, user_id: int, data: dict) -> ScopeChange:
    return ScopeChange.objects.create(
        site_id=data["site_id"],
        description=data["description"],
        notes=data.get("notes", ""),
        requested_by_id=user_id,
    )


def update_scope_change(scope_change_id: int, *, data: dict) -> ScopeChange:
    ScopeChange.objects.filter(pk=scope_change_id).update(**data)
    return ScopeChange.objects.get(pk=scope_change_id)


def delete_scope_change(scope_change_id: int) -> None:
    ScopeChange.objects.filter(pk=scope_change_id).delete()


def review_scope_change(scope_change_id: int, *, reviewer_id: int, status: str, reviewer_notes: str = "") -> ScopeChange:
    obj = ScopeChange.objects.get(pk=scope_change_id)
    obj.status = status
    obj.reviewed_by_id = reviewer_id
    obj.reviewer_notes = reviewer_notes
    obj.reviewed_at = timezone.now()
    obj.save(update_fields=["status", "reviewed_by_id", "reviewer_notes", "reviewed_at", "updated_at"])
    return obj


# ===========================================================================
# Equipment Return
# ===========================================================================

def create_equipment_return(*, user_id: int, data: dict) -> EquipmentReturn:
    return EquipmentReturn.objects.create(
        site_id=data["site_id"],
        device_name=data["device_name"],
        device_id=data.get("device_id", ""),
        reason=data.get("reason", ""),
        qty_returned=data.get("qty_returned", 1),
        notes=data.get("notes", ""),
    )


def receive_equipment_return(return_id: int, *, receiver_id: int, notes: str = "") -> EquipmentReturn:
    obj = EquipmentReturn.objects.get(pk=return_id)
    obj.status = "received"
    obj.received_by_id = receiver_id
    obj.returned_at = timezone.now()
    if notes:
        obj.notes = notes
    obj.save(update_fields=["status", "received_by_id", "returned_at", "notes"])
    return obj


def delete_equipment_return(return_id: int) -> None:
    EquipmentReturn.objects.filter(pk=return_id).delete()


# ===========================================================================
# Operations Assignment
# ===========================================================================

def upsert_operations_assignment(site_id: int, data: dict) -> OperationsAssignment:
    obj, _ = OperationsAssignment.objects.update_or_create(site_id=site_id, defaults={"data": data})
    return obj


# ===========================================================================
# Elevator Rental
# ===========================================================================

def upsert_elevator_rental(site_id: int, data: dict) -> ElevatorRental:
    allowed = {"lift_required", "vendor", "rental_start", "rental_end", "cost", "notes"}
    defaults = {k: v for k, v in data.items() if k in allowed}
    obj, _ = ElevatorRental.objects.update_or_create(site_id=site_id, defaults=defaults)
    return obj


# ===========================================================================
# Camera Spec (writes into sigtools_beta.camera_models — first inventory
# cross-app import into apps.sigtools; see docs/db/camera_models_schema.md)
# ===========================================================================

def update_camera_spec(
    *, camera_model_id: int, rango_lente_mm: list, rango_fov_grados: list, changed_by_id: int,
) -> dict:
    from apps.core import cache_utils as cu
    from apps.installations.selectors import CAMERA_CATALOG_CACHE_KEY, CAMERA_MODEL_CATALOG_CACHE_KEY
    from apps.sigtools.models import CameraBrand, CameraModel

    # Primary effect first — this write must land before anything best-effort below.
    obj = CameraModel.objects.get(pk=camera_model_id)
    obj.rango_lente_mm = rango_lente_mm
    obj.rango_fov_grados = rango_fov_grados
    obj.save(update_fields=["rango_lente_mm", "rango_fov_grados"])

    cu.invalidate(CAMERA_MODEL_CATALOG_CACHE_KEY, CAMERA_CATALOG_CACHE_KEY)

    # camera_brand_id has no real DB constraint (apps/sigtools/models.py) — a
    # dangling brand must not turn a successful spec update into a 500.
    try:
        brand = CameraBrand.objects.get(pk=obj.camera_brand_id).name
    except CameraBrand.DoesNotExist:
        brand = None

    # Audit trail lives in a different database (default) than CameraModel
    # (sigtools) — no shared transaction is possible across the two, so this
    # is intentionally best-effort and must never fail the request.
    try:
        CameraSpecChangeLog.objects.create(
            camera_model_id=camera_model_id,
            rango_lente_mm=rango_lente_mm,
            rango_fov_grados=rango_fov_grados,
            changed_by_id=changed_by_id,
        )
    except Exception:
        logger.warning(
            "update_camera_spec: failed to write CameraSpecChangeLog for camera_model_id=%s",
            camera_model_id, exc_info=True,
        )

    return {
        "camera_model_id": camera_model_id,
        "name": obj.name,
        "brand": brand,
        "rango_lente_mm": rango_lente_mm,
        "rango_fov_grados": rango_fov_grados,
    }
