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
# Sync
# ---------------------------------------------------------------------------

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
