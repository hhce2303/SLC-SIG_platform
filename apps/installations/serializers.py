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


class SiteCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    customer_group_id = serializers.IntegerField()
    ip_address = serializers.IPAddressField(default="0.0.0.0")
    teams_channelid = serializers.CharField(max_length=255, default="", allow_blank=True)
    teams_teamid = serializers.CharField(max_length=255, default="", allow_blank=True)


class SiteCreateResponseSerializer(serializers.Serializer):
    site_id = serializers.IntegerField()


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
    state_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)
    teams_channelid = serializers.CharField(max_length=255, default="", allow_blank=True)
    teams_teamid = serializers.CharField(max_length=255, default="", allow_blank=True)
    # --- Installation fields ---
    it_lead_tech_id = serializers.IntegerField()
    installation_type_id = serializers.IntegerField()
    project_owner = serializers.IntegerField(required=False, allow_null=True)
    total_cameras = serializers.IntegerField(default=0, min_value=0)
    total_views = serializers.IntegerField(default=0, min_value=0)
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
    full_name = serializers.CharField(max_length=255, required=False)
    role_names = serializers.ListField(
        child=serializers.CharField(), required=False
    )

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
