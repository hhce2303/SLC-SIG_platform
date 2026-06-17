"""
Views — orchestration only.
No business logic here; delegates to selectors (reads) and services (writes).
"""
from __future__ import annotations

import json
import time

from django.db import connections
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views import View

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import cache_utils as cu
from apps.installations import selectors, services
from apps.installations.serializers import (
    AdminPermissionSerializer,
    AdminRoleCreateSerializer,
    AdminRoleSerializer,
    AdminRoleUpdateSerializer,
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    BulkParentPayloadSerializer,
    BulkParentResultSerializer,
    CameraTypeSerializer,
    DevicePositionSerializer,
    DeviceTypeSerializer,
    InstallationCreateSerializer,
    InstallationResponseSerializer,
    InventoryExportResponseSerializer,
    InventoryExportSerializer,
    InventoryItemSerializer,
    MessageResponseSerializer,
    SetParentSerializer,
    SigProjectCancelApprovalSerializer,
    SigProjectCreateSerializer,
    SigProjectRenameSerializer,
    SigProjectRequestApprovalSerializer,
    SigProjectSerializer,
    SigProjectUpdateSerializer,
    SimpleDropdownSerializer,
    SiteCameraModelSerializer,
    SiteDashboardItemSerializer,
    SiteDeviceCatalogItemSerializer,
    SiteDeviceDispatchSerializer,
    SiteDeviceDispatchWriteSerializer,
    SiteDeviceInstallSerializer,
    SiteDeviceLogSerializer,
    SiteDeviceLogWriteSerializer,
    SiteDeviceReceiveSerializer,
    DeviceSerialWriteSerializer,
    SiteDispatchProgressSerializer,
    SiteListItemSerializer,
    SiteOnboardingResponseSerializer,
    SiteOnboardingSerializer,
    SiteProgressSerializer,
    SiteSwitchModelSerializer,
    SiteCreateSerializer,
    SiteCreateResponseSerializer,
    SiteDetailSerializer,
    SiteUpdateSerializer,
    SiteStatusEntrySerializer,
    TopologyValidateRequestSerializer,
    TopologyValidateResponseSerializer,
    BOMResponseSerializer,
    CeoDashboardResponseSerializer,
    SiteIndoorMapSerializer,
    SiteIndoorMapUploadSerializer,
    SyncPayloadSerializer,
    SyncResponseSerializer,
    UserSerializer,
    ProjectSiteListItemSerializer,
    ProjectSiteInfoSerializer,
    ProjectSiteInfoUpdateSerializer,
    ItSiteTestReadSerializer,
    ItSiteTestWriteSerializer,
    DashboardInitSerializer,
    NotificationSerializer,
)

from apps.core.permissions import has_app_permission


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class CameraModelCatalogView(APIView):
    """GET /catalog/camera-models/ — all camera models in the company catalog."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteCameraModelSerializer(many=True)})
    def get(self, request: Request) -> Response:
        data = selectors.get_camera_model_catalog()
        return Response(data, status=status.HTTP_200_OK)


class CameraCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CameraTypeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        data = selectors.get_camera_catalog()
        return Response(data, status=status.HTTP_200_OK)


class DeviceCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: DeviceTypeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        data = selectors.get_device_types()
        return Response(data, status=status.HTTP_200_OK)


class SiteCameraCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteCameraModelSerializer(many=True)})
    def get(self, request: Request, site_id: int) -> Response:
        cameras = selectors.get_site_camera_models(site_id)
        return Response(cameras, status=status.HTTP_200_OK)


class SiteSwitchCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteSwitchModelSerializer(many=True)})
    def get(self, request: Request, site_id: int) -> Response:
        switches = selectors.get_site_switch_models(site_id)
        return Response(switches, status=status.HTTP_200_OK)


class SiteDeviceCatalogView(APIView):
    """
    GET /sites/<site_id>/catalog/

    Unified device catalog for a site.  Returns all physical devices installed
    at the site in a single flat list:
      - cameras      → category="camera",   subtype=camera_type (bullet, dome, ptz, ...)
      - switches     → category="network",  subtype="switch"
      - routers      → category="network",  subtype="router"
      - PDUs         → category="power",    subtype="pdu"
      - DAs          → category="video",    subtype="da"
      - radios       → category="wireless", subtype="radio"
      - access ctrl  → category="security", subtype="access_control"

    Each entry uses the same shape; fields that don't apply to a device type are null.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteDeviceCatalogItemSerializer(many=True)})
    def get(self, request: Request, site_id: int) -> Response:
        return Response(selectors.get_site_device_catalog(site_id), status=status.HTTP_200_OK)


class CatalogByIdsView(APIView):
    """
    GET /catalog/by-ids/?ids=cam-168,cam-165

    Supplemental catalog fetch: returns enriched catalog items for specific
    device IDs (e.g. cam-168) regardless of which site they belong to.
    Used by the frontend when a project contains devices whose catalogoId is
    not covered by the current site's catalog (e.g. cameras placed in a
    previous session from a different site).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ids_param = request.query_params.get("ids", "")
        raw_ids = [i.strip() for i in ids_param.split(",") if i.strip()]
        camera_ids = []
        for raw in raw_ids:
            if raw.startswith("cam-"):
                try:
                    camera_ids.append(int(raw[4:]))
                except ValueError:
                    pass
        return Response(selectors.get_cameras_by_ids(camera_ids), status=status.HTTP_200_OK)


class SiteTopologyValidateView(APIView):
    """
    POST /sites/<site_id>/topology/validate/

    Validates a canvas network topology server-side: loop detection, PoE
    budget per switch, uplink bandwidth and port counts. The request carries
    the device specs and connections the frontend already holds in memory, so
    the browser stops running graph traversal + PoE summation on every click
    and only renders the errors this endpoint returns.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TopologyValidateRequestSerializer,
        responses={200: TopologyValidateResponseSerializer},
    )
    def post(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = TopologyValidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.validate_topology(
            serializer.validated_data["devices"],
            serializer.validated_data["connections"],
        )
        return Response(result, status=status.HTTP_200_OK)


class BomPreviewView(APIView):
    """
    POST /bom/preview/
    Pure BOM aggregation for the active canvas design (no site binding).
    Body: {devices: [{instanceId, numero, area, category, subtype, lensType, brand, name}]}
    Response: {coverage_by_area, summary, total_cameras, total_views, total_devices}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        devices = request.data.get("devices") or []
        result = selectors.get_bom_preview(devices)
        return Response(result, status=status.HTTP_200_OK)


class TopologyAnalyzeView(APIView):
    """
    POST /topology/analyze/

    Full topology analysis not tied to a specific site (the design lives in
    the SigProject JSON blob). Returns validate() result + build_tree +
    cascade aggregates + optional connection_check.

    Body: {
      devices: [{id, category, subtype, poe_draw_watts, bandwidth_mbps,
                 poe_budget_watts, uplink_mbps, port_count, ip}, ...],
      connections: [{source_id, target_id}, ...],
      check?: {source, target}        ← proposed new connection to pre-validate
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        devices = request.data.get("devices") or []
        connections_raw = request.data.get("connections") or []
        check = request.data.get("check") or None

        # Normalise connection keys: frontend sends source_id/target_id,
        # topology.py expects source/target.
        connections = [
            {"source": c.get("source_id", c.get("source", "")),
             "target": c.get("target_id", c.get("target", ""))}
            for c in connections_raw
        ]

        result = services.analyze_topology(devices, connections, check)
        return Response(result, status=status.HTTP_200_OK)


class SiteBOMView(APIView):
    """
    GET /sites/<site_id>/bom/

    Bill of Materials — device counts grouped by catalog entry via SQL
    GROUP BY (cameras + other_devices). The frontend stops iterating thousands
    of per-unit records in memory to build the hardware table.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BOMResponseSerializer})
    def get(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(selectors.get_site_bom(site_id), status=status.HTTP_200_OK)


class SiteGeocodeView(APIView):
    """
    GET /sites/<site_id>/geocode/
    Returns {lat, lng, source} for a site. If lat/lng not yet in DB, resolves
    via Nominatim and persists. Returns 404 when the site is unknown or
    geocoding fails entirely.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        result = services.geocode_site(site_id)
        if result is None:
            return Response({"detail": "Could not geocode site."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class GeocodeSearchView(APIView):
    """
    GET /geocode/search/?q=<query>&limit=<n>
    Server-side proxy for Nominatim address autocomplete. Cached 1 h.
    Returns list of {lat, lon, display_name}.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)
        limit = min(int(request.query_params.get("limit", 5) or 5), 10)
        results = services.geocode_search(query, limit)
        return Response(results, status=status.HTTP_200_OK)


class CeoDashboardView(APIView):
    """
    GET /metrics/ceo-dashboard/

    Company-wide project health analytics: per-project install progress,
    schedule usage and a health semaphore (on_track / watch / behind_schedule)
    plus an overall summary. Delay detection (keyword scan over logs/notes)
    runs DB-side, so the CEO's browser never downloads every site nor runs
    regexes over giant log fields.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CeoDashboardResponseSerializer}, tags=["metrics"])
    def get(self, request: Request) -> Response:
        return Response(selectors.get_ceo_dashboard(), status=status.HTTP_200_OK)


class SiteIndoorMapView(APIView):
    """
    GET  /sites/<site_id>/indoor-maps/  — list uploaded indoor floor-plans
    POST /sites/<site_id>/indoor-maps/  — upload one (multipart/form-data)

    The image is stored natively on MEDIA_ROOT and served by nginx at /media/,
    so the frontend stops sending giant base64-encoded payloads.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={200: SiteIndoorMapSerializer(many=True)}, tags=["indoor-maps"])
    def get(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        maps = selectors.list_indoor_maps(site_id)
        data = SiteIndoorMapSerializer(maps, many=True, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SiteIndoorMapUploadSerializer,
        responses={201: SiteIndoorMapSerializer},
        tags=["indoor-maps"],
    )
    def post(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        ser = SiteIndoorMapUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = services.create_indoor_map(
            site_id,
            ser.validated_data["image"],
            label=ser.validated_data.get("label", ""),
            uploaded_by=getattr(request.user, "id", None),
        )
        data = SiteIndoorMapSerializer(obj, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)


class SiteIndoorMapDetailView(APIView):
    """DELETE /sites/<site_id>/indoor-maps/<map_id>/ — remove an indoor map."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MessageResponseSerializer}, tags=["indoor-maps"])
    def delete(self, request: Request, site_id: int, map_id: int) -> Response:
        if not services.delete_indoor_map(site_id, map_id):
            return Response({"detail": "Indoor map not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"success": True, "message": "Indoor map deleted."},
            status=status.HTTP_200_OK,
        )


class VMSCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SimpleDropdownSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.get_vms_catalog(), status=status.HTTP_200_OK)


class InstallationTypesCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SimpleDropdownSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.get_installation_types(), status=status.HTTP_200_OK)


class CustomerGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SimpleDropdownSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.get_customer_groups(), status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UsersView(APIView):
    """
    GET /users/            → IT technicians (default)
    GET /users/<role>/     → Filter by role key
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer(many=True)})
    def get(self, request: Request, role: str = "it-technicians") -> Response:
        data = selectors.get_users_by_role(role)
        return Response(data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

class SiteListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteDashboardItemSerializer(many=True)})
    def get(self, request: Request) -> Response:
        if request.query_params.get("fresh") == "1":
            cu.invalidate("inst:sites_dashboard")
        data = selectors.list_sites_dashboard()
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=SiteCreateSerializer, responses={201: SiteCreateResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = SiteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            if data.get("project_site_id"):
                authorized_by = getattr(request.user, "id", None)
                site_id = services.promote_project_site(
                    project_site_id=data["project_site_id"],
                    authorized_by=authorized_by,
                )
            else:
                site_id = services.create_site(data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        cu.invalidate_dashboard()
        return Response({"site_id": site_id}, status=status.HTTP_201_CREATED)


class SiteTechniciansView(APIView):
    """
    GET  /sites/<site_id>/technicians/  → technicians assigned to the site
    POST /sites/<site_id>/technicians/  → replace assignment {user_ids: [..]}
    Reuses it_installation_responsibles. POST notifies the newly assigned techs.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        return Response(services.get_site_technicians(site_id=int(site_id)), status=status.HTTP_200_OK)

    def post(self, request: Request, site_id: int) -> Response:
        raw = request.data.get("user_ids", []) if isinstance(request.data, dict) else []
        try:
            user_ids = [int(u) for u in raw]
        except (TypeError, ValueError):
            return Response({"detail": "user_ids must be a list of integers."}, status=status.HTTP_400_BAD_REQUEST)
        result = services.set_site_technicians(
            site_id=int(site_id),
            user_ids=user_ids,
            assigned_by_id=getattr(request.user, "id", None),
        )
        if result is None:
            return Response({"detail": "Site has no installation."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class AssignedSitesView(APIView):
    """GET /sites/assigned/ — sites assigned to the authenticated technician."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user_id = getattr(request.user, "id", None)
        if not user_id:
            return Response([], status=status.HTTP_200_OK)
        return Response(services.list_assigned_sites(user_id=int(user_id)), status=status.HTTP_200_OK)


class SiteDeviceDetailView(APIView):
    """
    GET /sites/<site_id>/catalog/<device_id>/detail/
    Receipt/installation trace for one device (who/when/notes/photos) — for the
    Installations right-click "Installation details".
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int, device_id: str) -> Response:
        return Response(
            selectors.get_device_install_detail(site_id=int(site_id), device_id=str(device_id)),
            status=status.HTTP_200_OK,
        )


class SiteOnboardingView(APIView):
    """
    POST /onboarding/
    Creates a site and its first installation in a single atomic transaction.
    Returns the full installation record upon success.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SiteOnboardingSerializer,
        responses={201: SiteOnboardingResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SiteOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = dict(serializer.validated_data)
            payload["created_by"] = getattr(request.user, "id", None)
            installation = services.create_project_site_with_installation(payload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cu.invalidate_dashboard()
        return Response(installation, status=status.HTTP_201_CREATED)


class SiteStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteStatusEntrySerializer(many=True)})
    def get(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        data = selectors.get_site_status(site_id)
        return Response({"site_id": site_id, "installations": data}, status=status.HTTP_200_OK)


class SiteInventoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InventoryItemSerializer(many=True)})
    def get(self, request: Request, site_id: int) -> Response:
        if not selectors.get_site_or_404(site_id):
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        data = selectors.get_site_inventory(site_id)
        return Response({"site_id": site_id, "inventory": data}, status=status.HTTP_200_OK)


class SiteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteDetailSerializer})
    def get(self, request: Request, site_id: int) -> Response:
        site_data = selectors.get_site_detail(site_id)
        if site_data is None:
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(site_data, status=status.HTTP_200_OK)

    @extend_schema(request=SiteUpdateSerializer, responses={200: SiteDetailSerializer})
    def patch(self, request: Request, site_id: int) -> Response:
        return self._update(request, site_id)

    @extend_schema(request=SiteUpdateSerializer, responses={200: SiteDetailSerializer})
    def put(self, request: Request, site_id: int) -> Response:
        return self._update(request, site_id)

    def _update(self, request: Request, site_id: int) -> Response:
        serializer = SiteUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.update_site(site_id, serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if updated is None:
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated, status=status.HTTP_200_OK)

    @extend_schema(responses={200: MessageResponseSerializer})
    def delete(self, request: Request, site_id: int) -> Response:
        deleted = services.delete_site(site_id)
        if not deleted:
            return Response(
                {"detail": "Site not found or already deleted."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "message": f"Site {site_id} and its installations deleted."},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Projects (Installations)
# ---------------------------------------------------------------------------

class ProjectListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=InstallationCreateSerializer, responses={201: InstallationResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = InstallationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inst_id = services.create_installation(serializer.validated_data)
        return Response({"installation_id": inst_id}, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MessageResponseSerializer})
    def delete(self, request: Request, inst_id: int) -> Response:
        deleted = services.delete_installation(inst_id)
        if not deleted:
            return Response(
                {"detail": "Installation not found or already deleted."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "message": f"Installation {inst_id} deleted."},
            status=status.HTTP_200_OK,
        )


class ProjectDesignView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, inst_id: int) -> Response:
        if not selectors.get_installation_or_404(inst_id):
            return Response({"detail": "Installation not found."}, status=status.HTTP_404_NOT_FOUND)
        v_meta = selectors.get_installation_design(inst_id)
        return Response(
            {"installation_id": inst_id, "visual_metadata": v_meta or {}},
            status=status.HTTP_200_OK,
        )


class ProjectSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SyncPayloadSerializer, responses={200: SyncResponseSerializer})
    def post(self, request: Request, inst_id: int) -> Response:
        serializer = SyncPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            id_mapping = services.sync_installation(inst_id, serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cu.invalidate_dashboard()
        return Response({"success": True, "mapped_ids": id_mapping}, status=status.HTTP_200_OK)


class ProjectInventoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InventoryItemSerializer(many=True)})
    def get(self, request: Request, inst_id: int) -> Response:
        if not selectors.get_installation_or_404(inst_id):
            return Response({"detail": "Installation not found."}, status=status.HTTP_404_NOT_FOUND)
        data = selectors.get_installation_inventory(inst_id)
        return Response({"installation_id": inst_id, "inventory": data}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

class DevicePositionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: DevicePositionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.get_device_positions(), status=status.HTTP_200_OK)


class DeviceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MessageResponseSerializer})
    def delete(self, request: Request, item_id: int) -> Response:
        category = request.query_params.get("category", "")
        if not category:
            return Response(
                {"detail": "Query param 'category' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            deleted = services.delete_device(item_id, category)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not deleted:
            return Response(
                {"detail": "Device not found or already deleted."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "message": "Device deleted successfully."},
            status=status.HTTP_200_OK,
        )


class DeviceParentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=SetParentSerializer, responses={200: MessageResponseSerializer})
    def patch(self, request: Request, device_id: int) -> Response:
        serializer = SetParentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.set_device_parent(device_id, serializer.validated_data.get("parent_id"))
        if not updated:
            return Response({"detail": "Device not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"success": True, "message": "Parent updated."},
            status=status.HTTP_200_OK,
        )


class BulkDeviceParentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=BulkParentPayloadSerializer, responses={200: BulkParentResultSerializer})
    def post(self, request: Request, inst_id: int) -> Response:
        serializer = BulkParentPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = services.bulk_set_device_parent(
                inst_id, serializer.validated_data["assignments"]
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


# ===========================================================================
# Supabase — sig_projects
# ===========================================================================

class SigProjectListView(APIView):
    """
    GET  /api/v1/installations/sig-projects/ — list all sig_projects
    POST /api/v1/installations/sig-projects/ — create a new sig_project
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SigProjectSerializer(many=True)})
    def get(self, request: Request) -> Response:
        data = selectors.list_sig_projects()
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=SigProjectCreateSerializer, responses={201: SigProjectSerializer})
    def post(self, request: Request) -> Response:
        serializer = SigProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        project = services.create_sig_project(
            project_id=str(d["id"]) if d.get("id") else None,
            name=d["name"],
            data=d.get("data", {}),
            created_by=getattr(request.user, "id", None),
        )
        return Response(project, status=status.HTTP_201_CREATED)


class SigProjectDetailView(APIView):
    """
    GET    /api/v1/installations/sig-projects/<uuid>/ — fetch single project
    PATCH  /api/v1/installations/sig-projects/<uuid>/ — update (optimistic concurrency)
    DELETE /api/v1/installations/sig-projects/<uuid>/ — hard delete
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SigProjectSerializer, 404: None})
    def get(self, request: Request, project_id) -> Response:
        project = selectors.get_sig_project(str(project_id))
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(project, status=status.HTTP_200_OK)

    @extend_schema(request=SigProjectUpdateSerializer, responses={200: SigProjectSerializer})
    def patch(self, request: Request, project_id) -> Response:
        serializer = SigProjectUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        updated, conflict = services.update_sig_project(
            project_id=str(project_id),
            name=d["name"],
            data=d["data"],
            expected_version=d["expected_version"],
        )
        if updated is None and conflict is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if conflict is not None:
            return Response(
                {"detail": "Version conflict. Project was modified by another session.", "latest": conflict},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(updated, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 404: None})
    def delete(self, request: Request, project_id) -> Response:
        deleted = services.delete_sig_project(str(project_id))
        if not deleted:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SigProjectRenameView(APIView):
    """PATCH /api/v1/installations/sig-projects/<uuid>/name/ — rename only (no version bump)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=SigProjectRenameSerializer, responses={200: SigProjectSerializer})
    def patch(self, request: Request, project_id) -> Response:
        serializer = SigProjectRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = services.rename_sig_project(
            project_id=str(project_id),
            name=serializer.validated_data["name"],
        )
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(project, status=status.HTTP_200_OK)


class SigProjectRequestApprovalView(APIView):
    """POST /api/v1/installations/sig-projects/<uuid>/request-approval/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=SigProjectRequestApprovalSerializer, responses={200: SigProjectSerializer})
    def post(self, request: Request, project_id) -> Response:
        serializer = SigProjectRequestApprovalSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        project = services.request_sig_project_approval(
            project_id=str(project_id),
            requested_by=getattr(request.user, "id", None),
            note=serializer.validated_data.get("note", ""),
        )
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(project, status=status.HTTP_200_OK)


class SigProjectCancelApprovalView(APIView):
    """POST /api/v1/installations/sig-projects/<uuid>/cancel-approval-request/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=SigProjectCancelApprovalSerializer, responses={200: SigProjectSerializer})
    def post(self, request: Request, project_id) -> Response:
        serializer = SigProjectCancelApprovalSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        project = services.cancel_sig_project_approval(
            project_id=str(project_id),
            requested_by=getattr(request.user, "id", None),
            note=serializer.validated_data.get("note", ""),
        )
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(project, status=status.HTTP_200_OK)


class SigProjectPresentationLinkView(APIView):
    """
    Manage the read-only client "guest link" for a project (auth required).
      POST   /sig-projects/<uuid>/presentation-link/  → generate/return token
      DELETE /sig-projects/<uuid>/presentation-link/  → revoke (token → NULL)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_id) -> Response:
        pricing = request.data.get("pricing") if isinstance(request.data, dict) else None
        token = services.set_sig_project_presentation_token(
            project_id=str(project_id), pricing=pricing
        )
        if token is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"token": token, "path": f"/presentation/{token}"},
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, project_id) -> Response:
        ok = services.revoke_sig_project_presentation_token(project_id=str(project_id))
        if not ok:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PresentationDetailView(APIView):
    """
    PUBLIC, unauthenticated read-only view of a shared project.
      GET /api/v1/installations/presentation/<token>/
    Returns a sanitized payload (name + sitios + devices + drawings) or 404.
    """

    authentication_classes = []  # truly public — don't let cookie auth reject
    permission_classes = [AllowAny]

    def get(self, request: Request, token) -> Response:
        data = services.get_sig_project_presentation(token=str(token))
        if data is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(data, status=status.HTTP_200_OK)


class PresentationSignView(APIView):
    """
    PUBLIC, unauthenticated endpoint to record a client's electronic signature
    on the proposal (ESIGN/UETA). The guest-link token is the authorization.
      POST /api/v1/installations/presentation/<token>/sign/
    Body: {signerName, signatureDataUrl, total, currency, governingState, ...}
    Returns 200 on success, 404 if the token is invalid/revoked or payload bad.
    """

    authentication_classes = []  # truly public — don't let cookie auth reject
    permission_classes = [AllowAny]

    def post(self, request: Request, token) -> Response:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")) or None
        ua = request.META.get("HTTP_USER_AGENT", "")
        ok = services.save_sig_project_presentation_signature(
            token=str(token),
            signature=request.data if isinstance(request.data, dict) else {},
            ip=ip,
            user_agent=ua,
        )
        if not ok:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": "signed"}, status=status.HTTP_200_OK)


class PresentationUploadSignedView(APIView):
    """
    PUBLIC, unauthenticated endpoint to upload a manually-signed copy of the
    agreement (PDF/image). The guest-link token is the authorization.
      POST /api/v1/installations/presentation/<token>/upload-signed/  (multipart)
    Field: file (pdf/png/jpg, ≤10 MB), optional signerName. Returns {url} or 404.
    """

    authentication_classes = []  # truly public — don't let cookie auth reject
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, token) -> Response:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")) or None
        ua = request.META.get("HTTP_USER_AGENT", "")
        url = services.save_sig_project_presentation_uploaded_doc(
            token=str(token),
            file=request.FILES.get("file"),
            signer_name=request.data.get("signerName", ""),
            ip=ip,
            user_agent=ua,
        )
        if url is None:
            return Response(
                {"detail": "Invalid token or file."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"url": url}, status=status.HTTP_200_OK)


# ===========================================================================
# Supabase — Admin
# ===========================================================================

class AdminUsersView(APIView):
    """
    GET  /api/v1/installations/admin/users/ — list all users with roles
    POST /api/v1/installations/admin/users/ — create a new user
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminUserSerializer(many=True)})
    def get(self, request: Request) -> Response:
        users = selectors.list_admin_users()
        return Response(users, status=status.HTTP_200_OK)

    @extend_schema(request=AdminUserCreateSerializer, responses={201: AdminUserSerializer})
    def post(self, request: Request) -> Response:
        serializer = AdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        user = services.create_admin_user(
            username=d["username"],
            password=d["password"],
            full_name=d["full_name"],
            role_names=d.get("role_names", []),
        )
        return Response(user, status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    """
    PATCH  /api/v1/installations/admin/users/<id>/ — update user profile / roles
    DELETE /api/v1/installations/admin/users/<id>/ — soft-delete (deactivate)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=AdminUserUpdateSerializer, responses={200: AdminUserSerializer})
    def patch(self, request: Request, user_id: int) -> Response:
        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        user = services.update_admin_user(
            user_id=user_id,
            full_name=d.get("full_name"),
            role_names=d.get("role_names"),
            is_active=d.get("is_active"),
        )
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(user, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None, 404: None})
    def delete(self, request: Request, user_id: int) -> Response:
        deactivated = services.deactivate_admin_user(user_id)
        if not deactivated:
            return Response({"detail": "User not found or already inactive."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRolesView(APIView):
    """
    GET  /api/v1/installations/admin/roles/ — list roles with permissions + user_count
    POST /api/v1/installations/admin/roles/ — create a new role
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminRoleSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.list_admin_roles(), status=status.HTTP_200_OK)

    @extend_schema(request=AdminRoleCreateSerializer, responses={201: AdminRoleSerializer})
    def post(self, request: Request) -> Response:
        serializer = AdminRoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        role = services.create_admin_role(
            name=d["name"],
            label=d["label"],
            description=d.get("description", ""),
            color=d.get("color", "#6366f1"),
            permission_keys=d.get("permission_keys", []),
        )
        return Response(role, status=status.HTTP_201_CREATED)


class AdminRoleDetailView(APIView):
    """
    PATCH  /api/v1/installations/admin/roles/<int>/ — update role metadata / permissions
    DELETE /api/v1/installations/admin/roles/<int>/ — delete role (rejects if is_system)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=AdminRoleUpdateSerializer, responses={200: AdminRoleSerializer})
    def patch(self, request: Request, role_id) -> Response:
        serializer = AdminRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        role = services.update_admin_role(
            role_id=role_id,
            label=d.get("label"),
            description=d.get("description"),
            color=d.get("color"),
            permission_keys=d.get("permission_keys"),
        )
        if role is None:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(role, status=status.HTTP_200_OK)

    @extend_schema(responses={200: MessageResponseSerializer, 404: None, 409: None})
    def delete(self, request: Request, role_id) -> Response:
        result = services.delete_admin_role(role_id)
        if result is False:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)
        if result == "system":
            return Response(
                {"detail": "System roles cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {"success": True, "message": f"Role {role_id} deleted."},
            status=status.HTTP_200_OK,
        )


class AdminPermissionsView(APIView):
    """GET /api/v1/installations/admin/permissions/ — all permissions."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminPermissionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        return Response(selectors.list_admin_permissions(), status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Dispatch / Receipt / Installation views
# ---------------------------------------------------------------------------

class SiteDeviceDispatchView(APIView):
    """PATCH /sites/<site_id>/catalog/<device_id>/ — upsert dispatch fields."""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, site_id: int, device_id: str) -> Response:
        ser = SiteDeviceDispatchWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dispatch = services.upsert_device_dispatch(
            site_id,
            device_id,
            actor_user_id=getattr(request.user, "id", None),
            **ser.validated_data,
        )
        services.log_device_activity(
            site_id, device_id, "dispatch_updated",
            getattr(request.user, "id", None),
            f"Dispatch info updated: qty_sent={dispatch.qty_sent}",
        )
        return Response(SiteDeviceDispatchSerializer(dispatch).data, status=status.HTTP_200_OK)


class SiteDeviceReceiveView(APIView):
    """POST /sites/<site_id>/catalog/<device_id>/receive/ — confirm receipt."""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, site_id: int, device_id: str) -> Response:
        ser = SiteDeviceReceiveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        dispatch = services.confirm_device_receipt(
            site_id, device_id,
            qty_received=d["qty_received"],
            receipt_notes=d.get("receipt_notes", ""),
            receipt_photo_url=d.get("receipt_photo_url", ""),
        )
        services.log_device_activity(
            site_id, device_id, "receipt_confirmed",
            getattr(request.user, "id", None),
            f"Received {dispatch.qty_received} units",
        )
        return Response(SiteDeviceDispatchSerializer(dispatch).data, status=status.HTTP_200_OK)


class SiteDeviceInstallView(APIView):
    """POST /sites/<site_id>/catalog/<device_id>/install/ — mark as installed."""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, site_id: int, device_id: str) -> Response:
        ser = SiteDeviceInstallSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        dispatch = services.mark_device_installed(
            site_id, device_id,
            install_notes=d.get("install_notes", ""),
            install_photo_url=d.get("install_photo_url", ""),
        )
        services.log_device_activity(
            site_id, device_id, "device_installed",
            getattr(request.user, "id", None),
            d.get("install_notes", ""),
        )
        return Response(SiteDeviceDispatchSerializer(dispatch).data, status=status.HTTP_200_OK)


class SiteDeviceSerialView(APIView):
    """PATCH /sites/<site_id>/catalog/<device_id>/serial/ — update device serial."""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, site_id: int, device_id: str) -> Response:
        ser = DeviceSerialWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.update_device_serial(site_id, device_id, ser.validated_data["serial"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response({"device_id": device_id, "serial": ser.validated_data["serial"]}, status=status.HTTP_200_OK)


class SiteDeviceLogsView(APIView):
    """GET/POST /sites/<site_id>/catalog/<device_id>/logs/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int, device_id: str) -> Response:
        logs = selectors.get_device_logs(site_id, device_id)
        data = SiteDeviceLogSerializer(logs, many=True).data
        return Response({"data": data, "total": len(data)}, status=status.HTTP_200_OK)

    def post(self, request: Request, site_id: int, device_id: str) -> Response:
        ser = SiteDeviceLogWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        log = services.log_device_activity(
            site_id, device_id,
            action=ser.validated_data["action"],
            user_id=ser.validated_data.get("user_id") or getattr(request.user, "id", None),
            notes=ser.validated_data.get("notes", ""),
        )
        return Response(SiteDeviceLogSerializer(log).data, status=status.HTTP_201_CREATED)


class SiteProgressView(APIView):
    """GET /sites/<site_id>/progress/ — dispatched/received/installed counts."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, site_id: int) -> Response:
        catalog = selectors.get_site_device_catalog(site_id)
        total = len(catalog)
        data = selectors.get_site_progress(site_id, total)
        return Response(SiteProgressSerializer(data).data, status=status.HTTP_200_OK)


class SitesDispatchProgressView(APIView):
    """GET /sites/dispatch-progress/ — batch dispatch progress for all sites."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SiteDispatchProgressSerializer(many=True)})
    def get(self, request: Request) -> Response:
        raw_ids = request.query_params.get("site_ids")
        site_ids = None
        if raw_ids:
            try:
                site_ids = [int(x) for x in raw_ids.split(",") if x.strip()]
            except ValueError:
                return Response({"detail": "site_ids must be comma-separated integers."}, status=status.HTTP_400_BAD_REQUEST)
        data = selectors.get_all_sites_dispatch_progress(site_ids)
        return Response(SiteDispatchProgressSerializer(data, many=True).data, status=status.HTTP_200_OK)


class InventoryExportView(APIView):
    """
    POST /inventory/export/
    Takes the full canvas snapshot and upserts cameras / other_devices for an
    installation. Safe to call multiple times — devices already in visual_metadata
    are skipped, only new canvas devices are created.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(request=InventoryExportSerializer, responses={200: InventoryExportResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = InventoryExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = services.export_inventory_from_canvas(
                payload=d,
                installation_id=d.get("installation_id"),
                site_id=d.get("site_id"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cu.invalidate_dashboard()
        return Response(result, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# SSE stream for real-time installation updates
# ---------------------------------------------------------------------------

async def installations_sse_stream(request):
    """
    GET /api/v1/installations/stream/
    Server-Sent Events: escucha el canal Redis rt:installations.

    Eventos (publicados por services.py y run_realtime_poller):
      dispatch_updated      — SiteDeviceDispatch cambió
      activity_logged       — SiteDeviceLog creado
      site_updated          — sites/project_sites en sigtools
      project_updated       — installations en sigtools
      device_status_changed — cameras/other_devices en sigtools
      article_updated       — articles en sigtools
    """
    from apps.core.realtime import CH_INSTALLATIONS
    from apps.core.sse import sse_stream
    return await sse_stream(CH_INSTALLATIONS, request)


async def projects_sse_stream(request):
    """
    GET /api/v1/installations/projects/stream/
    Server-Sent Events: bus UNIFICADO del front-end. Multiplexa los 3 canales
    Redis en una sola conexión EventSource (el front se conecta solo a este
    endpoint vía syncBus.ts), así recibe TODOS los eventos:

      rt:projects      → project_updated/created/deleted, installation_updated, project_site_updated
      rt:installations → dispatch_updated, site_updated, device_status_changed,
                         device_received, device_installed, activity_logged
      rt:inventory     → article_updated
    """
    from apps.core.realtime import CH_INSTALLATIONS, CH_INVENTORY, CH_PROJECTS
    from apps.core.sse import sse_stream
    return await sse_stream([CH_PROJECTS, CH_INSTALLATIONS, CH_INVENTORY], request)


# ---------------------------------------------------------------------------
# Project Sites (staging)
# ---------------------------------------------------------------------------

class DashboardInitView(APIView):
    """
    GET /api/v1/installations/dashboard-init/

    Unified first-load payload: combines sites, project_sites, and
    dispatch_progress into a single round-trip.  Eliminates 2 extra HTTP
    requests on high-latency LAN connections.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: DashboardInitSerializer})
    def get(self, request: Request) -> Response:
        if request.query_params.get("fresh") == "1":
            cu.invalidate_dashboard()
        data = selectors.get_dashboard_init()
        return Response(data, status=status.HTTP_200_OK)


class ProjectSiteListView(APIView):
    """GET /api/v1/installations/project-sites/ — list all staging sites."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProjectSiteListItemSerializer(many=True)}, tags=["project-sites"])
    def get(self, request: Request) -> Response:
        return Response(selectors.list_project_sites(), status=status.HTTP_200_OK)


class ProjectSiteInfoView(APIView):
    """
    GET  /api/v1/installations/sites/<id>/info/ — extended project site info
    PATCH /api/v1/installations/sites/<id>/info/ — update editable fields
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProjectSiteInfoSerializer}, tags=["project-sites"])
    def get(self, request: Request, site_id: int) -> Response:
        info = selectors.get_project_site_info(site_id)
        if info is None:
            return Response({"detail": "Project site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(info, status=status.HTTP_200_OK)

    @extend_schema(
        request=ProjectSiteInfoUpdateSerializer,
        responses={200: ProjectSiteInfoSerializer},
        tags=["project-sites"],
    )
    def patch(self, request: Request, site_id: int) -> Response:
        serializer = ProjectSiteInfoUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.update_project_site_info(site_id, serializer.validated_data)
        if updated is None:
            return Response({"detail": "Project site not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated, status=status.HTTP_200_OK)

    @extend_schema(
        request=ProjectSiteInfoUpdateSerializer,
        responses={200: ProjectSiteInfoSerializer},
        tags=["project-sites"],
    )
    def put(self, request: Request, site_id: int) -> Response:
        # Same partial-upsert semantics as PATCH; exposed so PUT no longer 405s.
        return self.patch(request, site_id)


class ItSiteTestView(APIView):
    """
    GET  /api/v1/installations/sites/<site_id>/it-test/  — requires installations.ittest.view
    PUT  /api/v1/installations/sites/<site_id>/it-test/  — requires installations.ittest.edit
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ItSiteTestReadSerializer}, tags=["it-test"])
    def get(self, request: Request, site_id: int) -> Response:
        if not has_app_permission(request.user, "installations.ittest.view"):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        tech_info = selectors.get_site_tech_info(site_id)
        if tech_info is None:
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        it_test = selectors.get_it_test_for_site(site_id)
        payload = {
            "site_id":    site_id,
            "site_name":  tech_info.get("name"),
            "ip_address": tech_info.get("ip_address"),
            "timezone":   tech_info.get("timezone"),
            "location":   tech_info.get("location"),
            "references":   it_test.references   if it_test else [],
            "camera_flags": it_test.camera_flags  if it_test else [],
            "checklist":    it_test.checklist      if it_test else [],
            "grade":        it_test.grade          if it_test else "",
            "summary":      it_test.summary        if it_test else "",
            "delays":       it_test.delays         if it_test else [],
            "attachments":  it_test.attachments    if it_test else [],
            "date":         it_test.date           if it_test else None,
            "start_time":   it_test.start_time     if it_test else None,
            "end_time":     it_test.end_time       if it_test else None,
            "technicians":  it_test.technicians    if it_test else [],
            "it_personnel": it_test.it_personnel   if it_test else "",
            "created_at":   it_test.created_at     if it_test else None,
            "updated_at":   it_test.updated_at     if it_test else None,
        }
        serializer = ItSiteTestReadSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=ItSiteTestWriteSerializer,
        responses={200: ItSiteTestReadSerializer},
        tags=["it-test"],
    )
    def put(self, request: Request, site_id: int) -> Response:
        if not has_app_permission(request.user, "installations.ittest.edit"):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        tech_info = selectors.get_site_tech_info(site_id)
        if tech_info is None:
            return Response({"detail": "Site not found."}, status=status.HTTP_404_NOT_FOUND)
        write_ser = ItSiteTestWriteSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        it_test = services.upsert_it_test(site_id, write_ser.validated_data)
        payload = {
            "site_id":    site_id,
            "site_name":  tech_info.get("name"),
            "ip_address": tech_info.get("ip_address"),
            "timezone":   tech_info.get("timezone"),
            "location":   tech_info.get("location"),
            "references":   it_test.references,
            "camera_flags": it_test.camera_flags,
            "checklist":    it_test.checklist,
            "grade":        it_test.grade,
            "summary":      it_test.summary,
            "delays":       it_test.delays,
            "attachments":  it_test.attachments,
            "date":         it_test.date,
            "start_time":   it_test.start_time,
            "end_time":     it_test.end_time,
            "technicians":  it_test.technicians,
            "it_personnel": it_test.it_personnel,
            "created_at":   it_test.created_at,
            "updated_at":   it_test.updated_at,
        }
        serializer = ItSiteTestReadSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationListView(APIView):
    """
    GET  /api/v1/installations/notifications/
        Returns all notifications for request.user, ordered by most recent.
        Query param: ?unread_only=true to filter unread only.
    """

    def get(self, request):
        unread_only = request.query_params.get("unread_only", "").lower() in ("1", "true", "yes")
        notifications = selectors.list_notifications(
            recipient_id=request.user.id,
            unread_only=unread_only,
        )
        unread_count = selectors.count_unread_notifications(request.user.id)
        serializer = NotificationSerializer(notifications, many=True)
        return Response({"results": serializer.data, "unreadCount": unread_count})


class NotificationMarkReadView(APIView):
    """
    POST /api/v1/installations/notifications/<pk>/read/
        Marks a single notification as read for request.user.
    """

    def post(self, request, pk: int):
        found = services.mark_notification_read(
            notification_id=pk,
            recipient_id=request.user.id,
        )
        if not found:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "Marked as read."})


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/installations/notifications/read-all/
        Marks all notifications for request.user as read.
    """

    def post(self, request):
        count = services.mark_all_notifications_read(recipient_id=request.user.id)
        return Response({"detail": f"{count} notification(s) marked as read.", "count": count})
