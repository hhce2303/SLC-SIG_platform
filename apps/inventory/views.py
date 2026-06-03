"""Inventory API views — thin orchestration layer."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.http import build_list_payload, parse_int_param
from apps.inventory import selectors, services
from apps.inventory.serializers import (
    ActivityLogReadSerializer,
    ActivityLogWriteSerializer,
    ArticleReadSerializer,
    ArticleUpdateSerializer,
    ArticleWriteSerializer,
    CamerasBySiteSerializer,
    DashboardStatsSerializer,
    GroupSerializer,
    MaterialsRequestReadSerializer,
    MaterialsRequestWriteSerializer,
    MaterialsRequestReviewSerializer,
    DailyReportReadSerializer,
    DailyReportWriteSerializer,
    CableRunReadSerializer,
    CableRunWriteSerializer,
    CableRunUpdateSerializer,
    ScopeChangeReadSerializer,
    ScopeChangeWriteSerializer,
    ScopeChangeReviewSerializer,
    EquipmentReturnReadSerializer,
    EquipmentReturnWriteSerializer,
    EquipmentReturnReceiveSerializer,
    OperationsAssignmentSerializer,
    ElevatorRentalReadSerializer,
    ElevatorRentalWriteSerializer,
)


class ArticleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_articles()
        return Response(build_list_payload(request, qs, ArticleReadSerializer))

    def post(self, request: Request) -> Response:
        ser = ArticleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        article = services.create_article(data=ser.validated_data)
        return Response(
            ArticleReadSerializer(article).data,
            status=status.HTTP_201_CREATED,
        )


class ArticleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, article_id: int) -> Response:
        from apps.inventory.models import Article
        try:
            article = selectors.get_article_by_id(article_id)
        except Article.DoesNotExist:
            return Response({"detail": "Article not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ArticleReadSerializer(article).data)

    def patch(self, request: Request, article_id: int) -> Response:
        from apps.inventory.models import Article
        ser = ArticleUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            article = services.update_article(article_id, data=ser.validated_data)
        except Article.DoesNotExist:
            return Response({"detail": "Article not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ArticleReadSerializer(article).data)

    def delete(self, request: Request, article_id: int) -> Response:
        services.delete_article(article_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_groups()
        return Response(build_list_payload(request, qs, GroupSerializer))


class ActivityLogListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        article_id = parse_int_param(request.query_params.get("article_id"), "article_id")
        if article_id is not None:
            qs = selectors.get_activity_logs_for_article(article_id)
        else:
            qs = selectors.get_activity_logs()
        return Response(build_list_payload(request, qs, ActivityLogReadSerializer))

    def post(self, request: Request) -> Response:
        ser = ActivityLogWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        log = services.log_activity(data=ser.validated_data)
        return Response(
            ActivityLogReadSerializer(log).data,
            status=status.HTTP_201_CREATED,
        )


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        stats = selectors.get_dashboard_stats()
        return Response(DashboardStatsSerializer(stats).data)


class CamerasBySiteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        cameras = selectors.get_cameras_by_site(site_id)
        data = CamerasBySiteSerializer(cameras, many=True).data
        return Response({"data": data, "total": len(data)})


async def inventory_sse_stream(request):
    """
    GET /api/v1/inventory/stream/
    Server-Sent Events: escucha el canal Redis rt:inventory.

    Eventos (publicados por services.py):
      article_updated            — Article creado/modificado (serial/estado)
      device_received            — dispositivo recibido en sitio
      device_installed           — dispositivo instalado
      site_device_updated        — despacho / cambio de serial del dispositivo
      materials_request_created  — MaterialsRequest nueva
      materials_request_updated  — MaterialsRequest revisada
      daily_report_created       — DailyReport nueva
    """
    from apps.core.realtime import CH_INVENTORY
    from apps.core.sse import sse_stream
    return await sse_stream(CH_INVENTORY, request)


# ===========================================================================
# Materials Request
# ===========================================================================

class MaterialsRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        site_id = parse_int_param(request.query_params.get("site_id"), "site_id")
        status_filter = request.query_params.get("status")
        qs = selectors.get_materials_requests(site_id=site_id, status=status_filter)
        return Response(build_list_payload(
            request, qs, MaterialsRequestReadSerializer,
            items_key="results", count_key="count",
        ))

    def post(self, request: Request) -> Response:
        ser = MaterialsRequestWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        obj = services.create_materials_request(user_id=user_id, data=ser.validated_data)
        return Response(MaterialsRequestReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class MaterialsRequestReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, request_id: int) -> Response:
        ser = MaterialsRequestReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        from apps.inventory.models import MaterialsRequest
        try:
            obj = services.review_materials_request(
                request_id,
                reviewer_id=user_id,
                status=ser.validated_data["status"],
                reviewer_notes=ser.validated_data.get("reviewer_notes", ""),
            )
        except MaterialsRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(MaterialsRequestReadSerializer(obj).data)


# ===========================================================================
# Daily Report
# ===========================================================================

class DailyReportListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        site_id = parse_int_param(request.query_params.get("site_id"), "site_id")
        qs = selectors.get_daily_reports(site_id=site_id)
        return Response(build_list_payload(
            request, qs, DailyReportReadSerializer,
            items_key="results", count_key="count",
        ))

    def post(self, request: Request) -> Response:
        ser = DailyReportWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        obj = services.create_daily_report(user_id=user_id, data=ser.validated_data)
        return Response(DailyReportReadSerializer(obj).data, status=status.HTTP_201_CREATED)


# ===========================================================================
# Cable Run
# ===========================================================================

class CableRunListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        site_id = parse_int_param(request.query_params.get("site_id"), "site_id")
        qs = selectors.get_cable_runs(site_id=site_id)
        return Response(build_list_payload(
            request, qs, CableRunReadSerializer,
            items_key="results", count_key="count",
        ))

    def post(self, request: Request) -> Response:
        ser = CableRunWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = services.create_cable_run(data=ser.validated_data)
        return Response(CableRunReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class CableRunDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, cable_run_id: int) -> Response:
        from apps.inventory.models import CableRun
        try:
            obj = selectors.get_cable_run_by_id(cable_run_id)
        except CableRun.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CableRunReadSerializer(obj).data)

    def patch(self, request: Request, cable_run_id: int) -> Response:
        from apps.inventory.models import CableRun
        ser = CableRunUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            obj = services.update_cable_run(cable_run_id, data=ser.validated_data)
        except CableRun.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CableRunReadSerializer(obj).data)

    def delete(self, request: Request, cable_run_id: int) -> Response:
        services.delete_cable_run(cable_run_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# Scope Change
# ===========================================================================

class ScopeChangeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        site_id = parse_int_param(request.query_params.get("site_id"), "site_id")
        status_filter = request.query_params.get("status")
        qs = selectors.get_scope_changes(site_id=site_id, status=status_filter)
        return Response(build_list_payload(
            request, qs, ScopeChangeReadSerializer,
            items_key="results", count_key="count",
        ))

    def post(self, request: Request) -> Response:
        ser = ScopeChangeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        obj = services.create_scope_change(user_id=user_id, data=ser.validated_data)
        return Response(ScopeChangeReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class ScopeChangeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, scope_change_id: int) -> Response:
        from apps.inventory.models import ScopeChange
        try:
            obj = selectors.get_scope_change_by_id(scope_change_id)
        except ScopeChange.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ScopeChangeReadSerializer(obj).data)

    def patch(self, request: Request, scope_change_id: int) -> Response:
        from apps.inventory.models import ScopeChange
        ser = ScopeChangeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            obj = services.update_scope_change(scope_change_id, data=ser.validated_data)
        except ScopeChange.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ScopeChangeReadSerializer(obj).data)

    def delete(self, request: Request, scope_change_id: int) -> Response:
        services.delete_scope_change(scope_change_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScopeChangeReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, scope_change_id: int) -> Response:
        ser = ScopeChangeReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        from apps.inventory.models import ScopeChange
        try:
            obj = services.review_scope_change(
                scope_change_id,
                reviewer_id=user_id,
                status=ser.validated_data["status"],
                reviewer_notes=ser.validated_data.get("reviewer_notes", ""),
            )
        except ScopeChange.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ScopeChangeReadSerializer(obj).data)


# ===========================================================================
# Equipment Return
# ===========================================================================

class EquipmentReturnListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        site_id = parse_int_param(request.query_params.get("site_id"), "site_id")
        qs = selectors.get_equipment_returns(site_id=site_id)
        return Response(build_list_payload(
            request, qs, EquipmentReturnReadSerializer,
            items_key="results", count_key="count",
        ))

    def post(self, request: Request) -> Response:
        ser = EquipmentReturnWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        obj = services.create_equipment_return(user_id=user_id, data=ser.validated_data)
        return Response(EquipmentReturnReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class EquipmentReturnDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, return_id: int) -> Response:
        from apps.inventory.models import EquipmentReturn
        try:
            obj = selectors.get_equipment_return_by_id(return_id)
        except EquipmentReturn.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(EquipmentReturnReadSerializer(obj).data)

    def delete(self, request: Request, return_id: int) -> Response:
        services.delete_equipment_return(return_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EquipmentReturnReceiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, return_id: int) -> Response:
        ser = EquipmentReturnReceiveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = getattr(request.user, "id", None)
        from apps.inventory.models import EquipmentReturn
        try:
            obj = services.receive_equipment_return(
                return_id,
                receiver_id=user_id,
                notes=ser.validated_data.get("notes", ""),
            )
        except EquipmentReturn.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(EquipmentReturnReadSerializer(obj).data)


# ===========================================================================
# Operations Assignment (singleton per site)
# ===========================================================================

class OperationsAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        obj = selectors.get_operations_assignment(site_id)
        if obj is None:
            return Response({"site_id": site_id, "data": {}})
        return Response(OperationsAssignmentSerializer({"site_id": obj.site_id, "data": obj.data}).data)

    def put(self, request: Request, site_id: int) -> Response:
        data = request.data.get("data", request.data)
        obj = services.upsert_operations_assignment(site_id, data)
        return Response(OperationsAssignmentSerializer({"site_id": obj.site_id, "data": obj.data}).data)


# ===========================================================================
# Elevator Rental (singleton per site)
# ===========================================================================

class ElevatorRentalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        obj = selectors.get_elevator_rental(site_id)
        if obj is None:
            return Response({"detail": "No elevator rental record found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ElevatorRentalReadSerializer(obj).data)

    def put(self, request: Request, site_id: int) -> Response:
        ser = ElevatorRentalWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = services.upsert_elevator_rental(site_id, ser.validated_data)
        return Response(ElevatorRentalReadSerializer(obj).data)
