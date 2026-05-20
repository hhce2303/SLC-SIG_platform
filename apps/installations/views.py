"""
Views — orchestration only.
No business logic here; delegates to selectors (reads) and services (writes).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
    InventoryItemSerializer,
    MessageResponseSerializer,
    SetParentSerializer,
    SigProjectCreateSerializer,
    SigProjectRenameSerializer,
    SigProjectSerializer,
    SigProjectUpdateSerializer,
    SimpleDropdownSerializer,
    SiteCameraModelSerializer,
    SiteDashboardItemSerializer,
    SiteDeviceCatalogItemSerializer,
    SiteListItemSerializer,
    SiteOnboardingResponseSerializer,
    SiteOnboardingSerializer,
    SiteSwitchModelSerializer,
    SiteCreateSerializer,
    SiteCreateResponseSerializer,
    SiteStatusEntrySerializer,
    SyncPayloadSerializer,
    SyncResponseSerializer,
    UserSerializer,
)


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
        data = selectors.get_site_device_catalog(site_id)
        return Response(data, status=status.HTTP_200_OK)


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
        data = selectors.list_sites_dashboard()
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=SiteCreateSerializer, responses={201: SiteCreateResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = SiteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        site_id = services.create_site(serializer.validated_data)
        return Response({"site_id": site_id}, status=status.HTTP_201_CREATED)


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
            installation = services.create_site_with_installation(serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
        )
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(user, status=status.HTTP_200_OK)

    @extend_schema(responses={200: MessageResponseSerializer, 404: None})
    def delete(self, request: Request, user_id: int) -> Response:
        deactivated = services.deactivate_admin_user(user_id)
        if not deactivated:
            return Response({"detail": "User not found or already inactive."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"success": True, "message": f"User {user_id} deactivated."},
            status=status.HTTP_200_OK,
        )


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
    PATCH  /api/v1/installations/admin/roles/<uuid>/ — update role metadata / permissions
    DELETE /api/v1/installations/admin/roles/<uuid>/ — delete role (rejects if is_system)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=AdminRoleUpdateSerializer, responses={200: AdminRoleSerializer})
    def patch(self, request: Request, role_id) -> Response:
        serializer = AdminRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        role = services.update_admin_role(
            role_id=str(role_id),
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
        result = services.delete_admin_role(str(role_id))
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
