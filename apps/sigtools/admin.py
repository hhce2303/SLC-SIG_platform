"""
SIG Tools admin — registered on SigtoolsAdminSite.

Models are read-only (managed=False) and point to sigtools_beta.
Write operations are disabled; actions export or summarise data only.
"""

from __future__ import annotations

import csv
from typing import Any

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html

from apps.sigtools.models import (
    Camera,
    Device,
    Event,
    Installation,
    Role,
    Site,
    SigtoolsUser,
    UserRole,
)
from config.admin_sites import sigtools_admin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _export_csv(queryset, fields: list[str], filename: str) -> HttpResponse:
    """Generic CSV export for any queryset."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(fields)
    for obj in queryset.values_list(*fields):
        writer.writerow(obj)
    return response


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class ReadOnlyAdminMixin:
    """Disable all write operations — tables are unmanaged/read-only."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

@admin.register(Site, site=sigtools_admin)
class SiteAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = (
        "id", "name", "city", "state_code", "country_code",
        "cameras_count", "devices_down_badge", "monitored", "maintenance",
        "installation_date",
    )
    search_fields = ("name", "city", "ip_address")
    list_filter = ("country_code", "state_code", "monitored", "maintenance", "receive_notifications")
    ordering = ("name",)
    list_per_page = 50
    readonly_fields = [f.name for f in Site._meta.get_fields() if hasattr(f, "name")]

    @admin.display(description="Devices Down")
    def devices_down_badge(self, obj: Site) -> str:
        color = "red" if obj.devices_down else "green"
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color,
            obj.devices_down,
        )

    # ── Actions ──────────────────────────────────────────────────────────

    @admin.action(description="Exportar sitios a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "name", "ip_address", "city", "state_code", "country_code",
                  "timezone", "cameras_count", "total_devices", "devices_down",
                  "monitored", "maintenance", "installation_date"]
        return _export_csv(queryset, fields, "sigtools_sites.csv")

    @admin.action(description="Marcar sitios como en mantenimiento")
    def set_maintenance_on(self, request: HttpRequest, queryset: QuerySet) -> None:
        count = queryset.count()
        queryset.update(maintenance=True)
        self.message_user(request, f"{count} sitio(s) marcados como en mantenimiento.")

    @admin.action(description="Quitar modo mantenimiento")
    def set_maintenance_off(self, request: HttpRequest, queryset: QuerySet) -> None:
        count = queryset.count()
        queryset.update(maintenance=False)
        self.message_user(request, f"{count} sitio(s) fuera de mantenimiento.")

    actions = ["export_csv", "set_maintenance_on", "set_maintenance_off"]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@admin.register(SigtoolsUser, site=sigtools_admin)
class SigtoolsUserAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "name", "email", "username", "user_type", "email_verified_at", "deleted_at")
    search_fields = ("name", "email", "username")
    list_filter = ("user_type",)
    ordering = ("name",)
    list_per_page = 50
    # Never expose password or 2FA fields
    exclude = ("password", "two_factor_secret", "two_factor_recovery_codes",
               "remember_token", "profile_photo_path")

    @admin.action(description="Exportar usuarios a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "name", "email", "username", "user_type",
                  "email_verified_at", "created_at", "deleted_at"]
        return _export_csv(queryset, fields, "sigtools_users.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@admin.register(Role, site=sigtools_admin)
class RoleAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "name", "description", "user_count")
    search_fields = ("name", "description")
    ordering = ("name",)
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).prefetch_related("user_roles")

    @admin.display(description="Usuarios")
    def user_count(self, obj: Role) -> int:
        return obj.user_roles.count()

    @admin.action(description="Exportar roles a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "name", "description", "created_at"]
        return _export_csv(queryset, fields, "sigtools_roles.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# UserRole
# ---------------------------------------------------------------------------

@admin.register(UserRole, site=sigtools_admin)
class UserRoleAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "user", "role", "created_at")
    search_fields = ("user__name", "user__email", "role__name")
    list_filter = ("role",)
    ordering = ("-created_at",)
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("user", "role")

    @admin.action(description="Exportar asignaciones de roles a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "user_id", "role_id", "created_at"]
        return _export_csv(queryset, fields, "sigtools_user_roles.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

@admin.register(Device, site=sigtools_admin)
class DeviceAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "name", "code", "address", "site", "status_badge", "deleted_at")
    search_fields = ("name", "address", "site__name")
    list_filter = ("code",)
    ordering = ("site", "name")
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("site")

    STATUS_LABELS = {0: ("green", "Online"), 1: ("orange", "Warning"), 2: ("red", "Down")}

    @admin.display(description="Estado")
    def status_badge(self, obj: Device) -> str:
        color, label = self.STATUS_LABELS.get(obj.status, ("gray", f"#{obj.status}"))
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>', color, label
        )

    @admin.action(description="Exportar dispositivos a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "name", "code", "address", "site_id", "status", "notes", "deleted_at"]
        return _export_csv(queryset, fields, "sigtools_devices.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# Cameras
# ---------------------------------------------------------------------------

@admin.register(Camera, site=sigtools_admin)
class CameraAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "serial", "preowned", "exterior", "lift", "hours", "notes", "deleted_at")
    search_fields = ("serial", "notes")
    list_filter = ("preowned", "exterior", "lift")
    ordering = ("serial",)
    list_per_page = 50
    # Never expose camera credentials
    exclude = ("user", "password")

    @admin.action(description="Exportar cámaras a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "serial", "preowned", "exterior", "lift",
                  "height", "hours", "notes", "device_id", "installation_id", "deleted_at"]
        return _export_csv(queryset, fields, "sigtools_cameras.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# Installations
# ---------------------------------------------------------------------------

@admin.register(Installation, site=sigtools_admin)
class InstallationAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = (
        "id", "site", "total_cameras", "total_views", "total_hours",
        "starting_date", "limit_date", "deleted_at",
    )
    search_fields = ("site__name",)
    ordering = ("-starting_date",)
    list_per_page = 50

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("site")

    @admin.action(description="Exportar instalaciones a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "site_id", "total_cameras", "total_views",
                  "total_hours", "starting_date", "limit_date", "deleted_at"]
        return _export_csv(queryset, fields, "sigtools_installations.csv")

    actions = ["export_csv"]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@admin.register(Event, site=sigtools_admin)
class EventAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ("id", "device", "source", "status", "event_time", "notes")
    search_fields = ("device__name", "notes")
    list_filter = ("source", "status")
    date_hierarchy = "event_time"
    ordering = ("-event_time",)
    list_per_page = 100

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("device__site")

    @admin.action(description="Exportar eventos a CSV")
    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        fields = ["id", "device_id", "source", "status", "event_time", "notes"]
        return _export_csv(queryset, fields, "sigtools_events.csv")

    actions = ["export_csv"]

