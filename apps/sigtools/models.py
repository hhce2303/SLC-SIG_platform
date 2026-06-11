"""
Read-only, unmanaged models that map to the sigtools_beta database.
Django never creates or migrates these tables.
"""

from django.db import models

# Tenant-owned models (tenant = customer_groups). See apps/sigtools/tenancy.py.
#   TenantDirectModel — carries its own customer_group_id column (sites + inventory).
#   TenantScopedModel — derives the tenant via a FK chain; sets tenant_path, no column.
from apps.sigtools.tenancy import TenantDirectModel, TenantScopedModel


class _SigtoolsBase(models.Model):
    """Abstract base for all sigtools_beta models."""

    class Meta:
        abstract = True
        app_label = "sigtools"
        managed = False


# ---------------------------------------------------------------------------
# Users & Roles
# ---------------------------------------------------------------------------

class Role(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "roles"

    def __str__(self):
        return self.name


class SigtoolsUser(_SigtoolsBase):
    """Maps to sigtools_beta.users (avoids conflict with Django auth.User)."""

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=255, null=True, blank=True, unique=True)
    user_type = models.IntegerField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "users"

    def __str__(self):
        return self.name


class UserRole(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        SigtoolsUser, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="user_roles",
    )
    role = models.ForeignKey(
        Role, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="user_roles",
    )
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "user_roles"

    def __str__(self):
        return f"{self.user} → {self.role}"


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

class Site(TenantDirectModel, _SigtoolsBase):
    # DIRECT: sites already has a hard customer_group_id FK in the DB.
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    ip_address = models.CharField(max_length=250)
    city = models.CharField(max_length=255, null=True, blank=True)
    state_code = models.CharField(max_length=2, null=True, blank=True)
    country_code = models.CharField(max_length=2, null=True, blank=True, default="US")
    timezone = models.CharField(max_length=50, null=True, blank=True)
    cameras_count = models.IntegerField(default=0)
    total_devices = models.IntegerField(default=0)
    devices_down = models.IntegerField(default=0)
    monitored = models.BooleanField(default=True)
    maintenance = models.BooleanField(default=True)
    receive_notifications = models.BooleanField(default=True)
    address = models.TextField(null=True, blank=True)
    installation_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "sites"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Devices & Cameras
# ---------------------------------------------------------------------------

class Device(TenantScopedModel, _SigtoolsBase):
    tenant_path = "site__customer_group_id"  # DERIVED via site
    DEVICE_CODES = [
        ("Router", "Router"),
        ("PDU", "PDU"),
        ("InterMapper", "InterMapper"),
        ("Other", "Other"),
    ]
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, choices=DEVICE_CODES)
    address = models.CharField(max_length=255)
    notes = models.CharField(max_length=255, null=True, blank=True)
    site = models.ForeignKey(
        Site, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="devices",
    )
    status = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "devices"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Camera(TenantScopedModel, _SigtoolsBase):
    tenant_path = "device__site__customer_group_id"  # DERIVED via device -> site
    id = models.BigAutoField(primary_key=True)
    serial = models.CharField(max_length=255)
    preowned = models.BooleanField(default=False)
    exterior = models.BooleanField(default=False)
    lift = models.BooleanField(default=False)
    height = models.FloatField(null=True, blank=True)
    hours = models.FloatField()
    notes = models.CharField(max_length=255, null=True, blank=True)
    device = models.ForeignKey(
        Device, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="cameras",
    )
    installation_id = models.BigIntegerField()
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "cameras"

    def __str__(self):
        return self.serial


# ---------------------------------------------------------------------------
# Installations
# ---------------------------------------------------------------------------

class Installation(TenantScopedModel, _SigtoolsBase):
    tenant_path = "site__customer_group_id"  # DERIVED via site
    id = models.BigAutoField(primary_key=True)
    site = models.ForeignKey(
        Site, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="installations",
    )
    inst_status_id = models.BigIntegerField(default=1)
    installation_type_id = models.BigIntegerField(null=True, blank=True)
    it_lead_tech_id = models.BigIntegerField(null=True, blank=True)
    project_owner = models.BigIntegerField(null=True, blank=True)
    total_cameras = models.IntegerField(null=True, blank=True, db_column="Total_cameras")
    total_views = models.IntegerField(null=True, blank=True, db_column="Total_views")
    total_hours = models.FloatField(default=0)
    starting_date = models.DateTimeField(null=True, blank=True)
    limit_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "installations"

    def __str__(self):
        return f"Installation #{self.id} — Site {self.site_id}"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class Event(TenantScopedModel, _SigtoolsBase):
    tenant_path = "device__site__customer_group_id"  # DERIVED via device -> site
    SOURCE_CHOICES = [("SIG", "SIG"), ("SLC", "SLC"), ("Other", "Other")]

    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey(
        Device, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="events",
    )
    status = models.IntegerField()
    event_time = models.DateTimeField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="SIG")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "events"
        ordering = ["-event_time"]

    def __str__(self):
        return f"Event #{self.id} [{self.source}] status={self.status}"


# ---------------------------------------------------------------------------
# Catalog models
# ---------------------------------------------------------------------------

class CustomerGroup(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    acronym = models.CharField(max_length=10, null=True, blank=True)
    receive_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "customer_groups"

    def __str__(self):
        return self.name


class InstallationType(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "installation_types"

    def __str__(self):
        return self.name


class InstallationStatus(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "inst_statuses"

    def __str__(self):
        return self.name


class CameraType(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, null=True, blank=True)
    lens_amount = models.IntegerField()
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "camera_types"

    def __str__(self):
        return self.name


class CameraBrand(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, db_column="Name")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "camera_brands"

    def __str__(self):
        return self.name


class CameraModel(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    camera_type = models.ForeignKey(
        CameraType, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="camera_models",
    )
    camera_brand = models.ForeignKey(
        CameraBrand, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="camera_models",
    )
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "camera_models"

    def __str__(self):
        return self.name


class DeviceType(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    device_type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "device_types"

    def __str__(self):
        return f"{self.brand} {self.model}"


class OtherDevice(TenantScopedModel, _SigtoolsBase):
    tenant_path = "installation__site__customer_group_id"  # DERIVED via installation -> site
    id = models.BigAutoField(primary_key=True)
    # installation_id was a bare BigIntegerField; declared as a soft FK (same
    # column) so the tenant_path can traverse installation -> site. The `_id`
    # attribute (installation_id) still works for existing callers.
    installation = models.ForeignKey(
        "sigtools.Installation", on_delete=models.DO_NOTHING,
        db_constraint=False, db_column="installation_id",
        db_index=True, related_name="+",
    )
    device_type_id = models.BigIntegerField()
    device_id = models.BigIntegerField()
    serial = models.CharField(max_length=255)
    hours = models.FloatField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "other_devices"

    def __str__(self):
        return f"OtherDevice #{self.id}"


class Server(TenantScopedModel, _SigtoolsBase):
    tenant_path = "site__customer_group_id"  # DERIVED via site
    SYSTEM_CHOICES = [
        ("Arteco", "Arteco"),
        ("ICRealtime", "ICRealtime"),
        ("Other", "Other"),
    ]
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    site = models.ForeignKey(
        Site, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="servers",
    )
    system = models.CharField(max_length=20, choices=SYSTEM_CHOICES, db_column="system")
    vms_name = models.CharField(max_length=255, null=True, blank=True)
    vms_version = models.CharField(max_length=255, null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)
    notes = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "servers"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Supabase-mirrored tables (created 2026-05-10)
# Omitted: profiles, user_roles (Supabase), sig_projects — all have auth.users FK
# Omitted: roles → renamed to app_roles to avoid collision with sigtools_beta.roles
# ---------------------------------------------------------------------------

class Company(_SigtoolsBase):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    logo_url = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "companies"

    def __str__(self):
        return self.name


class ArticleGroup(TenantDirectModel, _SigtoolsBase):
    """Maps to sigtools_beta.`groups` (Supabase article grouping). DIRECT (inventory)."""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    icon_name = models.TextField(null=True, blank=True)
    color = models.TextField(null=True, blank=True)
    company = models.ForeignKey(
        Company, on_delete=models.DO_NOTHING,
        db_constraint=False, null=True, blank=True, related_name="groups",
    )

    class Meta(_SigtoolsBase.Meta):
        db_table = "groups"

    def __str__(self):
        return self.name


class Article(TenantScopedModel, _SigtoolsBase):
    # DERIVED: physical unit tracked per site. Tenant via site -> customer_group.
    # Each Article is a unique, trackeable asset (stock item); it is NOT a shared
    # catalog entry — hence scoped to a site, not to the customer group directly.
    tenant_path = "site__customer_group_id"

    id = models.BigAutoField(primary_key=True)
    sku = models.CharField(max_length=255, unique=True)
    name = models.TextField()
    sub = models.TextField(null=True, blank=True)
    category = models.TextField()
    group = models.ForeignKey(
        ArticleGroup, on_delete=models.DO_NOTHING,
        db_constraint=False, null=True, blank=True, related_name="articles",
    )
    site = models.ForeignKey(
        "sigtools.Site", on_delete=models.DO_NOTHING,
        db_constraint=False, null=True, blank=True,
        db_column="site_id", related_name="articles",
    )
    status = models.TextField(default="activo")
    location = models.TextField(null=True, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    image = models.TextField(null=True, blank=True)
    last_mod = models.DateTimeField(auto_now=True)
    serial = models.TextField()
    modified_by = models.TextField(null=True, blank=True)
    latest_note = models.TextField(null=True, blank=True)
    vendor = models.TextField(null=True, blank=True)
    quantity_send = models.IntegerField(null=True, blank=True)
    tracking = models.TextField(null=True, blank=True)
    observations = models.TextField(null=True, blank=True)
    checklist_received = models.BooleanField(null=True, blank=True)
    checklist_notes = models.TextField(null=True, blank=True)
    checklist_date = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "articles"

    def __str__(self):
        return f"{self.sku} — {self.name}"


class ActivityLog(TenantScopedModel, _SigtoolsBase):
    # DERIVED: follows the article's site. No column added — tenant resolved via
    # article -> site -> customer_group (3-level join, no redundancy).
    tenant_path = "article__site__customer_group_id"

    id = models.BigAutoField(primary_key=True)
    article = models.ForeignKey(
        Article, on_delete=models.DO_NOTHING,
        db_constraint=False, null=True, blank=True, related_name="activity_logs",
    )
    action = models.TextField()
    user_id = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "activity_logs"

    def __str__(self):
        return f"{self.action} @ {self.timestamp}"


class AppRole(_SigtoolsBase):
    """Maps to sigtools_beta.app_roles (Supabase `roles` renamed to avoid collision)."""
    id = models.CharField(max_length=36, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    label = models.TextField()
    description = models.TextField(null=True, blank=True)
    color = models.TextField(null=True, blank=True, default="#64748b")
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "app_roles"

    def __str__(self):
        return self.label


class Permission(_SigtoolsBase):
    id = models.CharField(max_length=36, primary_key=True)
    key = models.CharField(max_length=255, unique=True)
    label = models.TextField()
    description = models.TextField(null=True, blank=True)
    app = models.TextField(default="installations")
    category = models.TextField(default="general")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "permissions"

    def __str__(self):
        return self.key


class RolePermission(_SigtoolsBase):
    """Junction table: app_roles ↔ permissions."""
    role = models.ForeignKey(
        AppRole, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="role_permissions",
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.DO_NOTHING,
        db_constraint=False, related_name="role_permissions",
    )

    class Meta(_SigtoolsBase.Meta):
        db_table = "role_permissions"
        unique_together = [("role", "permission")]

    def __str__(self):
        return f"{self.role} → {self.permission}"


class UserAppRole(_SigtoolsBase):
    """
    Junction table: sigtools_beta.users ↔ app_roles.
    Created 2026-05-10 — allows assigning application-level roles (admin, designer, etc.)
    to users independently of the internal sigtools `roles` table.
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        SigtoolsUser, on_delete=models.DO_NOTHING,
        db_column="user_id", db_constraint=False, related_name="app_roles",
    )
    role = models.ForeignKey(
        AppRole, on_delete=models.DO_NOTHING,
        db_column="role_id", db_constraint=False, related_name="user_app_roles",
    )
    granted_at = models.DateTimeField(null=True, blank=True)

    class Meta(_SigtoolsBase.Meta):
        db_table = "user_app_roles"
        unique_together = [("user", "role")]

    def __str__(self):
        return f"{self.user} → {self.role}"
