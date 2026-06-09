"""
Serializers for the Installations API.
Input validation and output shaping — no business logic here.
"""
from __future__ import annotations

from rest_framework import serializers


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class CameraModelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class CameraBrandSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    models = CameraModelSerializer(many=True)


class CameraTypeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    lens_amount = serializers.IntegerField()
    brands = CameraBrandSerializer(many=True)


class DeviceTypeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    device_type = serializers.CharField()
    brand = serializers.CharField()
    model = serializers.CharField()


class SimpleDropdownSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    role = serializers.CharField()


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

class SiteListItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    location = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)


class LogEntrySerializer(serializers.Serializer):
    date = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    user = serializers.CharField()


class SiteDashboardItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    customer_group_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    address = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)
    responsable = serializers.CharField(allow_null=True)
    it_manager = serializers.CharField(allow_null=True)
    notes = serializers.CharField(allow_null=True)
    log = LogEntrySerializer(many=True)
    log_count = serializers.IntegerField()
    total_cameras = serializers.IntegerField(allow_null=True)
    total_views = serializers.IntegerField(allow_null=True)
    starting_date = serializers.DateTimeField(allow_null=True)
    limit_date = serializers.DateTimeField(allow_null=True)


class SiteCreateSerializer(serializers.Serializer):
    # When project_site_id is provided the other fields become optional —
    # the site data is read from project_sites and promoted to sites.
    project_site_id   = serializers.IntegerField(required=False, allow_null=True)
    name              = serializers.CharField(max_length=255, required=False)
    customer_group_id = serializers.IntegerField(required=False)
    ip_address        = serializers.IPAddressField(default="0.0.0.0", required=False)
    teams_channelid   = serializers.CharField(max_length=255, default="", allow_blank=True, required=False)
    teams_teamid      = serializers.CharField(max_length=255, default="", allow_blank=True, required=False)

    def validate(self, attrs):
        if not attrs.get("project_site_id"):
            if not attrs.get("name"):
                raise serializers.ValidationError({"name": "Required when project_site_id is not provided."})
            if not attrs.get("customer_group_id"):
                raise serializers.ValidationError({"customer_group_id": "Required when project_site_id is not provided."})
        return attrs


class SiteCreateResponseSerializer(serializers.Serializer):
    site_id = serializers.IntegerField()


class SiteUpdateSerializer(serializers.Serializer):
    """
    Editable core fields on a sigtools_beta.sites row.
    All optional — PATCH applies only the provided fields; PUT behaves the
    same way (the canonical site record lives in read-only sigtools_beta, so
    there is no full-replace semantics to enforce here).
    """
    name                  = serializers.CharField(max_length=255, required=False)
    ip_address            = serializers.CharField(max_length=250, required=False, allow_null=True, allow_blank=True)
    city                  = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    state_code            = serializers.CharField(max_length=2, required=False, allow_null=True, allow_blank=True)
    country_code          = serializers.CharField(max_length=2, required=False, allow_null=True, allow_blank=True)
    address               = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    timezone              = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    monitored             = serializers.BooleanField(required=False)
    maintenance           = serializers.BooleanField(required=False)
    receive_notifications = serializers.BooleanField(required=False)
    installation_date     = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs


class SiteDetailSerializer(serializers.Serializer):
    """Read shape returned after a site update."""
    id                    = serializers.IntegerField()
    name                  = serializers.CharField()
    ip_address            = serializers.CharField(allow_null=True)
    city                  = serializers.CharField(allow_null=True)
    state_code            = serializers.CharField(allow_null=True)
    country_code          = serializers.CharField(allow_null=True)
    address               = serializers.CharField(allow_null=True)
    timezone              = serializers.CharField(allow_null=True)
    monitored             = serializers.BooleanField()
    maintenance           = serializers.BooleanField()
    receive_notifications = serializers.BooleanField()
    installation_date     = serializers.DateField(allow_null=True)
    updated_at            = serializers.DateTimeField(allow_null=True)


class SiteStatusEntrySerializer(serializers.Serializer):
    installation_id = serializers.IntegerField()
    type_name = serializers.CharField()
    status_name = serializers.CharField()


class InventoryItemSerializer(serializers.Serializer):
    category = serializers.CharField()
    brand = serializers.CharField(allow_null=True)
    model = serializers.CharField(allow_null=True)
    qty = serializers.IntegerField()


class SiteCameraModelSerializer(serializers.Serializer):
    """Matches the frontend mock catalog shape exactly."""
    id = serializers.CharField()
    name = serializers.CharField()
    brand = serializers.CharField()
    serial = serializers.CharField(allow_null=True)
    ip = serializers.CharField(allow_null=True)
    resolution = serializers.CharField(allow_null=True)
    type = serializers.CharField(allow_null=True)
    category = serializers.CharField()
    subtype = serializers.CharField()
    lensType = serializers.CharField(allow_null=True)
    rango_lente_mm = serializers.ListField(child=serializers.FloatField(), allow_null=True)
    rango_fov_grados = serializers.ListField(child=serializers.FloatField(), allow_null=True)
    poe_watts = serializers.FloatField(allow_null=True)
    bandwidth_mbps = serializers.FloatField(allow_null=True)


class SiteSwitchModelSerializer(serializers.Serializer):
    """Matches the frontend mock switch catalog shape exactly."""
    id = serializers.CharField()
    name = serializers.CharField()
    brand = serializers.CharField()
    resolution = serializers.CharField(allow_null=True)
    type = serializers.CharField(allow_null=True)
    category = serializers.CharField()
    subtype = serializers.CharField()
    poe_watts = serializers.FloatField(allow_null=True)
    bandwidth_mbps = serializers.FloatField(allow_null=True)
    poe_budget_watts = serializers.FloatField(allow_null=True)
    uplink_mbps = serializers.FloatField(allow_null=True)


class SiteDeviceCatalogItemSerializer(serializers.Serializer):
    """
    Unified shape for all device types in a site catalog.
    Superset of SiteCameraModelSerializer and SiteSwitchModelSerializer.
    Fields that don't apply to a given device type are null.
    """
    id = serializers.CharField()
    name = serializers.CharField()
    brand = serializers.CharField()
    serial = serializers.CharField(allow_null=True)
    ip = serializers.CharField(allow_null=True)
    resolution = serializers.CharField(allow_null=True)
    type = serializers.CharField(allow_null=True)
    category = serializers.CharField()
    subtype = serializers.CharField()
    lensType = serializers.CharField(allow_null=True)
    rango_lente_mm = serializers.ListField(child=serializers.FloatField(), allow_null=True)
    rango_fov_grados = serializers.ListField(child=serializers.FloatField(), allow_null=True)
    poe_watts = serializers.FloatField(allow_null=True)
    bandwidth_mbps = serializers.FloatField(allow_null=True)
    poe_budget_watts = serializers.FloatField(allow_null=True)
    uplink_mbps = serializers.FloatField(allow_null=True)
    # Dispatch overlay fields (null when no dispatch record exists)
    vendor            = serializers.CharField(allow_null=True, allow_blank=True)
    qty_sent          = serializers.IntegerField(allow_null=True)
    tracking          = serializers.CharField(allow_null=True, allow_blank=True)
    observations      = serializers.CharField(allow_null=True, allow_blank=True)
    dispatched_at     = serializers.DateTimeField(allow_null=True)
    qty_received      = serializers.IntegerField(allow_null=True)
    received_at       = serializers.DateTimeField(allow_null=True)
    receipt_photo_url = serializers.CharField(allow_null=True, allow_blank=True)
    installed         = serializers.BooleanField(default=False)
    installed_at      = serializers.DateTimeField(allow_null=True)
    install_photo_url = serializers.CharField(allow_null=True, allow_blank=True)
    # Camera view assignment (null for non-camera devices)
    view_name         = serializers.CharField(allow_null=True)
    # Physical install status derived from the dispatch overlay
    # (installed → received → none). Lets the frontend stop guessing from
    # device-name strings (e.g. matching "CAM 3").
    physical_status   = serializers.ChoiceField(
        choices=["installed", "received", "none"], default="none",
    )


# ---------------------------------------------------------------------------
# Topology validation (POST /sites/<id>/topology/validate/)
# ---------------------------------------------------------------------------

class TopologyDeviceSerializer(serializers.Serializer):
    """A node in the canvas graph plus the catalog specs the frontend holds."""
    id               = serializers.CharField()
    type             = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    poe_draw_watts   = serializers.FloatField(required=False, allow_null=True)
    poe_budget_watts = serializers.FloatField(required=False, allow_null=True)
    bandwidth_mbps   = serializers.FloatField(required=False, allow_null=True)
    uplink_mbps      = serializers.FloatField(required=False, allow_null=True)
    port_count       = serializers.IntegerField(required=False, allow_null=True)


class TopologyConnectionSerializer(serializers.Serializer):
    source         = serializers.CharField()
    target         = serializers.CharField()
    type           = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    bandwidth_mbps = serializers.FloatField(required=False, allow_null=True)


class TopologyValidateRequestSerializer(serializers.Serializer):
    devices     = TopologyDeviceSerializer(many=True)
    connections = TopologyConnectionSerializer(many=True, default=list)


class TopologyErrorSerializer(serializers.Serializer):
    code      = serializers.CharField()   # loop_detected | poe_budget_exceeded | bandwidth_exceeded | ports_exceeded
    message   = serializers.CharField()
    device_id = serializers.CharField(required=False, allow_null=True)
    nodes     = serializers.ListField(child=serializers.CharField(), required=False)


class TopologySwitchStatSerializer(serializers.Serializer):
    device_id           = serializers.CharField()
    poe_used_watts      = serializers.FloatField()
    poe_budget_watts    = serializers.FloatField(allow_null=True)
    poe_remaining_watts = serializers.FloatField(allow_null=True)
    bandwidth_used_mbps = serializers.FloatField()
    uplink_mbps         = serializers.FloatField(allow_null=True)
    ports_used          = serializers.IntegerField()
    port_count          = serializers.IntegerField(allow_null=True)


class TopologyValidateResponseSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
    errors   = TopologyErrorSerializer(many=True)
    switches = TopologySwitchStatSerializer(many=True)


# ---------------------------------------------------------------------------
# Bill of Materials (GET /sites/<id>/bom/)
# ---------------------------------------------------------------------------

class BOMItemSerializer(serializers.Serializer):
    category  = serializers.CharField()
    subtype   = serializers.CharField()
    brand     = serializers.CharField(allow_null=True, allow_blank=True)
    name      = serializers.CharField()
    qty       = serializers.IntegerField()
    is_camera = serializers.BooleanField()


class BOMResponseSerializer(serializers.Serializer):
    site_id             = serializers.IntegerField()
    total_cameras       = serializers.IntegerField()
    total_other_devices = serializers.IntegerField()
    total_devices       = serializers.IntegerField()
    items               = BOMItemSerializer(many=True)


# ---------------------------------------------------------------------------
# CEO dashboard (GET /metrics/ceo-dashboard/)
# ---------------------------------------------------------------------------

class CeoDashboardProjectSerializer(serializers.Serializer):
    site_id           = serializers.IntegerField()
    site_name         = serializers.CharField()
    customer_group_id = serializers.IntegerField(allow_null=True)
    customer_group    = serializers.CharField(allow_null=True)
    status            = serializers.CharField(allow_null=True)
    project_owner     = serializers.CharField(allow_null=True)
    starting_date     = serializers.DateTimeField(allow_null=True)
    limit_date        = serializers.DateTimeField(allow_null=True)
    total_devices     = serializers.IntegerField()
    installed         = serializers.IntegerField()
    progress_pct      = serializers.FloatField()
    time_used_pct     = serializers.FloatField(allow_null=True)
    has_delay_alerts  = serializers.BooleanField()
    health            = serializers.ChoiceField(choices=["on_track", "watch", "behind_schedule"])


class CeoDashboardSummarySerializer(serializers.Serializer):
    total_projects       = serializers.IntegerField()
    on_track             = serializers.IntegerField()
    watch                = serializers.IntegerField()
    behind_schedule      = serializers.IntegerField()
    total_devices        = serializers.IntegerField()
    total_installed      = serializers.IntegerField()
    overall_progress_pct = serializers.FloatField()


class CeoDashboardResponseSerializer(serializers.Serializer):
    summary  = CeoDashboardSummarySerializer()
    projects = CeoDashboardProjectSerializer(many=True)


# ---------------------------------------------------------------------------
# Indoor maps (POST/GET /sites/<id>/indoor-maps/)
# ---------------------------------------------------------------------------

class SiteIndoorMapUploadSerializer(serializers.Serializer):
    """multipart/form-data upload of an indoor floor-plan."""
    ALLOWED_CONTENT_TYPES = {
        "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "application/pdf",
    }
    MAX_BYTES = 50 * 1024 * 1024  # keep in sync with nginx client_max_body_size

    image = serializers.FileField()
    label = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_image(self, f):
        ct = (getattr(f, "content_type", "") or "").lower()
        if ct not in self.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"Unsupported file type '{ct}'. Allowed: PNG, JPEG, WebP, GIF, PDF."
            )
        size = getattr(f, "size", 0) or 0
        if size > self.MAX_BYTES:
            raise serializers.ValidationError(
                f"File too large ({size} bytes). Max {self.MAX_BYTES} bytes."
            )
        return f


class SiteIndoorMapSerializer(serializers.Serializer):
    """Read shape for an uploaded indoor map (returns an absolute URL)."""
    id           = serializers.IntegerField()
    site_id      = serializers.IntegerField()
    label        = serializers.CharField(allow_blank=True)
    url          = serializers.SerializerMethodField()
    content_type = serializers.CharField(allow_blank=True)
    size_bytes   = serializers.IntegerField()
    uploaded_by  = serializers.IntegerField(allow_null=True)
    created_at   = serializers.DateTimeField()

    def get_url(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request is not None else url


# ---------------------------------------------------------------------------
# Installations / Projects
# ---------------------------------------------------------------------------

class InstallationCreateSerializer(serializers.Serializer):
    site_id = serializers.IntegerField()
    it_lead_tech_id = serializers.IntegerField()
    installation_type_id = serializers.IntegerField()


class InstallationResponseSerializer(serializers.Serializer):
    installation_id = serializers.IntegerField()


class MessageResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()


# ---------------------------------------------------------------------------
# Site Onboarding (site + installation in one request)
# ---------------------------------------------------------------------------

class SiteOnboardingSerializer(serializers.Serializer):
    # --- Site fields ---
    name = serializers.CharField(max_length=255)
    customer_group_id = serializers.IntegerField()
    ip_address = serializers.IPAddressField(default="0.0.0.0")
    address = serializers.CharField(max_length=512, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    state_code = serializers.CharField(max_length=2, required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(max_length=2, required=False, allow_blank=True, allow_null=True)
    teams_channelid = serializers.CharField(max_length=255, default="", allow_blank=True)
    teams_teamid = serializers.CharField(max_length=255, default="", allow_blank=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    # --- Installation fields ---
    it_lead_tech_id = serializers.IntegerField()
    installation_type_id = serializers.IntegerField()
    project_owner = serializers.IntegerField(required=False, allow_null=True)
    total_cameras = serializers.IntegerField(default=0, min_value=0)
    total_views = serializers.IntegerField(default=0, min_value=0)
    total_devices_planned = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    starting_date = serializers.DateTimeField(required=False, allow_null=True)
    limit_date = serializers.DateTimeField(required=False, allow_null=True)


class SiteOnboardingResponseSerializer(serializers.Serializer):
    installation_id = serializers.IntegerField()
    site_id = serializers.IntegerField()
    site_name = serializers.CharField()
    status = serializers.CharField()
    project_owner = serializers.IntegerField(allow_null=True)
    project_owner_name = serializers.CharField(allow_null=True)
    it_lead_tech_id = serializers.IntegerField(allow_null=True)
    it_lead_tech_name = serializers.CharField(allow_null=True)
    installation_type_id = serializers.IntegerField()
    installation_type = serializers.CharField(allow_null=True)
    total_cameras = serializers.IntegerField(allow_null=True)
    total_views = serializers.IntegerField(allow_null=True)
    starting_date = serializers.DateTimeField(allow_null=True)
    limit_date = serializers.DateTimeField(allow_null=True)
    total_hours = serializers.FloatField()
    created_at = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# Inventory export (canvas → DB)
# ---------------------------------------------------------------------------

class SitioExportSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    nombre = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    zoom = serializers.IntegerField(required=False, allow_null=True)


class DeviceExportSerializer(serializers.Serializer):
    instanceId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    catalogoId = serializers.CharField(required=False, allow_null=True)
    category = serializers.CharField(default="other")
    networkDeviceId = serializers.IntegerField(required=False, allow_null=True)
    area = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    view_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    numero = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        view_name = attrs.get("view_name")
        if not view_name:
            view_name = attrs.get("numero")

        if isinstance(view_name, str):
            view_name = view_name.strip() or None

        attrs["view_name"] = view_name
        return attrs


class InventoryExportSerializer(serializers.Serializer):
    site_id = serializers.IntegerField(required=False, allow_null=True)
    installation_id = serializers.IntegerField(required=False, allow_null=True)
    sitio = SitioExportSerializer(required=False, allow_null=True)
    projectName = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    devices = DeviceExportSerializer(many=True, default=list)
    indoorDevices = DeviceExportSerializer(many=True, default=list)
    enlaces = serializers.ListField(child=serializers.DictField(), default=list)
    drawings = serializers.ListField(child=serializers.DictField(), default=list)


class InventoryExportResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    site_id = serializers.IntegerField()
    installation_id = serializers.IntegerField()
    created_cameras = serializers.IntegerField()
    created_other_devices = serializers.IntegerField()



class HardwareAddedSerializer(serializers.Serializer):
    temp_id = serializers.CharField()
    category = serializers.ChoiceField(choices=["camera", "core_device", "other", "server"])
    type_id = serializers.CharField(allow_null=True, required=False, default=None)
    model_id = serializers.IntegerField(allow_null=True, required=False, default=None)
    network_device_id = serializers.IntegerField(allow_null=True, required=False, default=None)
    layer_id = serializers.IntegerField(allow_null=True, required=False, default=None)


class HardwareRemovedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    category = serializers.ChoiceField(choices=["camera", "core_device", "other", "server"])


class PhysicalChangesSerializer(serializers.Serializer):
    added = HardwareAddedSerializer(many=True, default=list)
    removed = HardwareRemovedSerializer(many=True, default=list)


class SyncPayloadSerializer(serializers.Serializer):
    layer_id = serializers.IntegerField()
    visual_metadata = serializers.DictField(child=serializers.JSONField(), default=dict)
    physical_changes = PhysicalChangesSerializer(default=dict)


class SyncResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    mapped_ids = serializers.DictField(child=serializers.IntegerField())


# ---------------------------------------------------------------------------
# Device hierarchy
# ---------------------------------------------------------------------------

class SetParentSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField(allow_null=True, required=False, default=None)


class BulkParentAssignmentSerializer(serializers.Serializer):
    device_id = serializers.IntegerField()
    category = serializers.ChoiceField(choices=["camera", "other", "core_device"])
    parent_id = serializers.IntegerField(allow_null=True, required=False, default=None)


class BulkParentPayloadSerializer(serializers.Serializer):
    assignments = BulkParentAssignmentSerializer(many=True)


class BulkParentResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    skipped = serializers.ListField(child=serializers.CharField())


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

class DevicePositionSerializer(serializers.Serializer):
    id = serializers.CharField()
    x = serializers.FloatField()
    y = serializers.FloatField()
    rotation = serializers.FloatField(allow_null=True)


# ===========================================================================
# sig_projects (default DB)
# ===========================================================================

class SigProjectSerializer(serializers.Serializer):
    """Output shape for a single sig_project row."""
    id = serializers.CharField()
    name = serializers.CharField()
    updated_at = serializers.CharField(allow_null=True)
    version = serializers.IntegerField()
    created_by = serializers.IntegerField(allow_null=True)
    created_by_name = serializers.CharField(allow_null=True)
    approval_status = serializers.CharField()
    approval_requested_by = serializers.IntegerField(allow_null=True)
    approval_requested_by_name = serializers.CharField(allow_null=True)
    data = serializers.JSONField()


# ===========================================================================
# Admin — sigtools_beta (app_roles, permissions, users)
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared nested pieces
# ---------------------------------------------------------------------------

class AdminPermissionNestedSerializer(serializers.Serializer):
    """Permission nested inside a Role."""
    id = serializers.CharField()
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    app = serializers.CharField()
    category = serializers.CharField()


class AdminRoleNestedSerializer(serializers.Serializer):
    """Role nested inside a User."""
    id = serializers.CharField()
    name = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True)
    is_system = serializers.BooleanField()


# ---------------------------------------------------------------------------
# Admin — Users (sigtools_beta.users + user_app_roles + app_roles)
# ---------------------------------------------------------------------------

class AdminUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    username = serializers.CharField(allow_null=True)
    email = serializers.EmailField()
    is_active = serializers.BooleanField()
    created_at = serializers.CharField(allow_null=True)
    roles = AdminRoleNestedSerializer(many=True)


# ---------------------------------------------------------------------------
# Admin — Roles (sigtools_beta.app_roles + role_permissions + permissions)
# ---------------------------------------------------------------------------

class AdminRoleSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True)
    is_system = serializers.BooleanField()
    user_count = serializers.IntegerField()
    permissions = AdminPermissionNestedSerializer(many=True)


# ---------------------------------------------------------------------------
# Admin — Permissions (sigtools_beta.permissions)
# ---------------------------------------------------------------------------

class AdminPermissionSerializer(serializers.Serializer):
    id = serializers.CharField()
    key = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    app = serializers.CharField()
    category = serializers.CharField()


# ===========================================================================
# sig_projects — write (input serializers)
# ===========================================================================

class SigProjectCreateSerializer(serializers.Serializer):
    """POST /sig-projects/ — frontend may supply its own UUID."""
    id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=255)
    data = serializers.JSONField(default=dict)


class SigProjectUpdateSerializer(serializers.Serializer):
    """PATCH /sig-projects/<uuid>/ — full update with optimistic concurrency."""
    name = serializers.CharField(max_length=255)
    data = serializers.JSONField()
    expected_version = serializers.IntegerField(min_value=1)


class SigProjectRenameSerializer(serializers.Serializer):
    """PATCH /sig-projects/<uuid>/name/ — rename only, no version bump."""
    name = serializers.CharField(max_length=255)


class SigProjectRequestApprovalSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class SigProjectCancelApprovalSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


# ===========================================================================
# Admin — users — write (input serializers)
# ===========================================================================

class AdminUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(max_length=255)
    role_names = serializers.ListField(
        child=serializers.CharField(), default=list, required=False
    )


class AdminUserUpdateSerializer(serializers.Serializer):
    full_name  = serializers.CharField(max_length=255, required=False)
    is_active  = serializers.BooleanField(required=False)
    role_names = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs


# ===========================================================================
# Admin — roles — write (input serializers)
# ===========================================================================

class AdminRoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    label = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, default="")
    color = serializers.CharField(max_length=30, default="#6366f1")
    permission_keys = serializers.ListField(
        child=serializers.CharField(), default=list, required=False
    )


class AdminRoleUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    color = serializers.CharField(max_length=30, required=False)
    permission_keys = serializers.ListField(
        child=serializers.CharField(), required=False
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        return attrs


# ---------------------------------------------------------------------------
# Dispatch / Receipt / Installation serializers
# ---------------------------------------------------------------------------

class SiteDeviceDispatchSerializer(serializers.Serializer):
    id                = serializers.IntegerField(read_only=True)
    site_id           = serializers.IntegerField()
    device_id         = serializers.CharField()
    vendor            = serializers.CharField(allow_blank=True)
    qty_sent          = serializers.IntegerField(allow_null=True)
    tracking          = serializers.CharField(allow_blank=True)
    observations      = serializers.CharField(allow_blank=True)
    dispatched_at     = serializers.DateTimeField(allow_null=True)
    qty_received      = serializers.IntegerField(allow_null=True)
    received_at       = serializers.DateTimeField(allow_null=True)
    receipt_notes     = serializers.CharField(allow_blank=True)
    receipt_photo_url = serializers.CharField(allow_blank=True)
    installed         = serializers.BooleanField()
    installed_at      = serializers.DateTimeField(allow_null=True)
    install_notes     = serializers.CharField(allow_blank=True)
    install_photo_url = serializers.CharField(allow_blank=True)
    updated_at        = serializers.DateTimeField(read_only=True)


class SiteDeviceDispatchWriteSerializer(serializers.Serializer):
    vendor        = serializers.CharField(max_length=255, allow_blank=True, required=False)
    quantity_send = serializers.IntegerField(allow_null=True, required=False)  # frontend name
    tracking      = serializers.CharField(max_length=500, allow_blank=True, required=False)
    observations  = serializers.CharField(allow_blank=True, required=False)
    dispatched_at = serializers.DateTimeField(allow_null=True, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided.")
        # Map frontend name to model field name
        if 'quantity_send' in attrs:
            attrs['qty_sent'] = attrs.pop('quantity_send')
        return attrs


class SiteDeviceReceiveSerializer(serializers.Serializer):
    qty_received      = serializers.IntegerField(min_value=0)
    receipt_notes     = serializers.CharField(allow_blank=True, default="")
    receipt_photo_url = serializers.CharField(allow_blank=True, default="")


class SiteDeviceInstallSerializer(serializers.Serializer):
    install_notes     = serializers.CharField(allow_blank=True, default="")
    install_photo_url = serializers.CharField(allow_blank=True, default="")


class SiteDeviceLogSerializer(serializers.Serializer):
    id         = serializers.IntegerField(read_only=True)
    site_id    = serializers.IntegerField()
    device_id  = serializers.CharField()
    action     = serializers.CharField()
    user_id    = serializers.IntegerField(allow_null=True)
    notes      = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class SiteDeviceLogWriteSerializer(serializers.Serializer):
    action  = serializers.CharField(max_length=100)
    notes   = serializers.CharField(allow_blank=True, default="")
    user_id = serializers.IntegerField(allow_null=True, required=False)


class SiteProgressSerializer(serializers.Serializer):
    total         = serializers.IntegerField()
    dispatched    = serializers.IntegerField()
    received      = serializers.IntegerField()
    installed     = serializers.IntegerField()
    pct_dispatched = serializers.FloatField()
    pct_received   = serializers.FloatField()
    pct_installed  = serializers.FloatField()


class DeviceSerialWriteSerializer(serializers.Serializer):
    serial = serializers.CharField(max_length=255)


class SiteDispatchProgressSerializer(serializers.Serializer):
    site_id        = serializers.IntegerField()
    site_name      = serializers.CharField(allow_null=True)
    total_cameras  = serializers.IntegerField()
    total_devices  = serializers.IntegerField()
    total          = serializers.IntegerField()   # alias for total_devices
    dispatched     = serializers.IntegerField()
    received       = serializers.IntegerField()
    installed      = serializers.IntegerField()
    pct_dispatched = serializers.FloatField()
    pct_received   = serializers.FloatField()
    pct_installed  = serializers.FloatField()


# ---------------------------------------------------------------------------
# Project Sites
# ---------------------------------------------------------------------------

class ProjectSiteListItemSerializer(serializers.Serializer):
    id                   = serializers.IntegerField()
    name                 = serializers.CharField()
    city                 = serializers.CharField(allow_null=True)
    state_code           = serializers.CharField(allow_null=True)
    country_code         = serializers.CharField(allow_null=True)
    verification_status  = serializers.CharField()
    created_by           = serializers.IntegerField(allow_null=True)
    created_by_name      = serializers.CharField(allow_null=True)
    approval_requested_by = serializers.IntegerField(allow_null=True)
    approval_requested_by_name = serializers.CharField(allow_null=True)
    rejection_reason     = serializers.CharField(allow_null=True)
    created_at           = serializers.DateTimeField(allow_null=True)
    updated_at           = serializers.DateTimeField(allow_null=True)
    installation_id      = serializers.IntegerField(allow_null=True)
    it_lead_tech_id      = serializers.IntegerField(allow_null=True)
    it_lead_tech_name    = serializers.CharField(allow_null=True)
    project_owner        = serializers.IntegerField(allow_null=True)
    project_owner_name   = serializers.CharField(allow_null=True)
    installation_type    = serializers.CharField(allow_null=True)
    total_cameras        = serializers.IntegerField(allow_null=True)
    starting_date        = serializers.DateTimeField(allow_null=True)
    limit_date           = serializers.DateTimeField(allow_null=True)


class ProjectSiteInfoSerializer(serializers.Serializer):
    id                   = serializers.IntegerField()
    name                 = serializers.CharField()
    city                 = serializers.CharField(allow_null=True)
    state_code           = serializers.CharField(allow_null=True)
    country_code         = serializers.CharField(allow_null=True)
    address              = serializers.CharField(allow_null=True)
    ip_address           = serializers.CharField(allow_null=True)
    lat                  = serializers.FloatField(allow_null=True)
    lng                  = serializers.FloatField(allow_null=True)
    verification_status  = serializers.CharField()
    created_by           = serializers.IntegerField(allow_null=True)
    created_by_name      = serializers.CharField(allow_null=True)
    approval_requested_by = serializers.IntegerField(allow_null=True)
    approval_requested_by_name = serializers.CharField(allow_null=True)
    rejection_reason     = serializers.CharField(allow_null=True)
    verified_by          = serializers.IntegerField(allow_null=True)
    verified_at          = serializers.DateTimeField(allow_null=True)
    authorized_by        = serializers.IntegerField(allow_null=True)
    authorized_at        = serializers.DateTimeField(allow_null=True)
    contract_value       = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    hotel                = serializers.CharField(allow_null=True)
    flight_details       = serializers.CharField(allow_null=True)
    teams_channelid      = serializers.CharField(allow_null=True)
    teams_teamid         = serializers.CharField(allow_null=True)
    created_at           = serializers.DateTimeField(allow_null=True)
    updated_at           = serializers.DateTimeField(allow_null=True)
    installation_id      = serializers.IntegerField(allow_null=True)
    it_lead_tech_id      = serializers.IntegerField(allow_null=True)
    it_lead_tech_name    = serializers.CharField(allow_null=True)
    project_owner        = serializers.IntegerField(allow_null=True)
    project_owner_name   = serializers.CharField(allow_null=True)
    installation_type    = serializers.CharField(allow_null=True)
    total_cameras        = serializers.IntegerField(allow_null=True)
    starting_date        = serializers.DateTimeField(allow_null=True)
    limit_date           = serializers.DateTimeField(allow_null=True)
    # Overlay fields from SiteProjectInfo (default DB)
    check_in             = serializers.DateField(allow_null=True)
    check_out            = serializers.DateField(allow_null=True)
    paylocity_code       = serializers.CharField(allow_null=True)
    extra_notes          = serializers.CharField(allow_null=True)


class ProjectSiteInfoUpdateSerializer(serializers.Serializer):
    name                 = serializers.CharField(max_length=255, required=False)
    city                 = serializers.CharField(max_length=255, required=False, allow_null=True)
    state_code           = serializers.CharField(max_length=2, required=False, allow_null=True)
    country_code         = serializers.CharField(max_length=2, required=False, allow_null=True)
    address              = serializers.CharField(required=False, allow_null=True)
    ip_address           = serializers.CharField(max_length=250, required=False, allow_null=True)
    contract_value       = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    hotel                = serializers.CharField(required=False, allow_null=True)
    flight_details       = serializers.CharField(required=False, allow_null=True)
    it_lead_tech_id      = serializers.IntegerField(required=False, allow_null=True)
    project_owner        = serializers.IntegerField(required=False, allow_null=True)
    installation_type_id = serializers.IntegerField(required=False, allow_null=True)
    total_cameras        = serializers.IntegerField(required=False, allow_null=True)
    starting_date        = serializers.DateTimeField(required=False, allow_null=True)
    limit_date           = serializers.DateTimeField(required=False, allow_null=True)
    # Overlay fields (stored in SiteProjectInfo default DB)
    check_in             = serializers.DateField(required=False, allow_null=True)
    check_out            = serializers.DateField(required=False, allow_null=True)
    paylocity_code       = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    extra_notes          = serializers.CharField(required=False, allow_null=True, allow_blank=True)


# ===========================================================================
# IT Test
# ===========================================================================

class ItSiteTestReadSerializer(serializers.Serializer):
    """GET /api/v1/installations/sites/<site_id>/it-test/"""
    # Site context (from sigtools_beta.sites)
    site_id        = serializers.IntegerField()
    site_name      = serializers.CharField(allow_null=True)
    ip_address     = serializers.CharField(allow_null=True)
    timezone       = serializers.CharField(allow_null=True)
    location       = serializers.CharField(allow_null=True)
    # ItSiteTest fields
    references     = serializers.JSONField()
    camera_flags   = serializers.JSONField()
    checklist      = serializers.JSONField()
    grade          = serializers.CharField(allow_null=True, allow_blank=True)
    summary        = serializers.CharField(allow_null=True, allow_blank=True)
    delays         = serializers.JSONField()
    attachments    = serializers.JSONField()
    date           = serializers.DateField(allow_null=True)
    start_time     = serializers.TimeField(allow_null=True)
    end_time       = serializers.TimeField(allow_null=True)
    technicians    = serializers.JSONField()
    it_personnel   = serializers.CharField(allow_null=True, allow_blank=True)
    created_at     = serializers.DateTimeField(allow_null=True)
    updated_at     = serializers.DateTimeField(allow_null=True)


class ItSiteTestWriteSerializer(serializers.Serializer):
    """PUT /api/v1/installations/sites/<site_id>/it-test/"""
    references   = serializers.JSONField(required=False, default=list)
    camera_flags = serializers.JSONField(required=False, default=list)
    checklist    = serializers.JSONField(required=False, default=list)
    grade        = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    summary      = serializers.CharField(required=False, allow_blank=True, default="")
    delays       = serializers.JSONField(required=False, default=list)
    attachments  = serializers.JSONField(required=False, default=list)
    date         = serializers.DateField(required=False, allow_null=True)
    start_time   = serializers.TimeField(required=False, allow_null=True)
    end_time     = serializers.TimeField(required=False, allow_null=True)
    technicians  = serializers.JSONField(required=False, default=list)
    it_personnel = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Dashboard init — unified first-load payload
# ---------------------------------------------------------------------------

class DashboardInitSerializer(serializers.Serializer):
    """
    Single-call response for InstallationsDashboard first render.
    Combines sites, project_sites, and dispatch_progress into one payload.
    """
    sites             = SiteDashboardItemSerializer(many=True)
    project_sites     = ProjectSiteListItemSerializer(many=True)
    dispatch_progress = SiteDispatchProgressSerializer(many=True)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationSerializer(serializers.Serializer):
    id                 = serializers.IntegerField()
    title              = serializers.CharField()
    message            = serializers.CharField()
    type               = serializers.CharField()
    isRead             = serializers.BooleanField(source="is_read")
    relatedProjectId   = serializers.CharField(source="related_project_id", allow_null=True)
    createdAt          = serializers.CharField(source="created_at")
