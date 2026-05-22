"""
Installations models.

SigProject      — managed=True, sig_dailylogs
SiteDeviceDispatch — dispatch/receipt/install overlay per (site, device)
SiteDeviceLog   — activity log per (site, device)
AppRole         — application-level roles (admin panel)
AppPermission   — granular permission keys (app.category.action)
AppRolePermission — M2M role ↔ permission
UserAppRole     — assigns AppRoles to sigtools_beta users by user_id
"""
from __future__ import annotations

import uuid

from django.db import models


class SigProject(models.Model):
    """
    Canvas design project — stores map layout JSON.
    owner_id references the bigint PK of sigtools_beta.users (cross-DB,
    so no FK constraint — stored as plain IntegerField).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    data = models.JSONField(
        default=dict,
        help_text='Canvas payload: {"sitios": [], "devices": [], "enlaces": [], "drawings": []}',
    )
    version = models.IntegerField(default=1)
    owner_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "sig_projects"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


# ── Dispatch / Receipt / Install tracking ────────────────────────────────────

class SiteDeviceDispatch(models.Model):
    """
    Overlay table that tracks dispatch → receipt → installation state
    for every device at a site.  Written in sig_dailylogs (managed=True)
    because sigtools_beta is read-only.
    """

    site_id   = models.BigIntegerField(db_index=True)
    device_id = models.CharField(max_length=50, db_index=True)  # e.g. "cam-123", "switch-456"

    # Dispatch info (filled by inventory personnel on desktop)
    vendor        = models.CharField(max_length=255, blank=True, default="")
    qty_sent      = models.IntegerField(null=True, blank=True)
    tracking      = models.CharField(max_length=500, blank=True, default="")
    observations  = models.TextField(blank=True, default="")
    dispatched_at = models.DateTimeField(null=True, blank=True)

    # Receipt info (filled by technician on mobile)
    qty_received      = models.IntegerField(null=True, blank=True)
    received_at       = models.DateTimeField(null=True, blank=True)
    receipt_notes     = models.TextField(blank=True, default="")
    receipt_photo_url = models.TextField(blank=True, default="")  # Cloudinary URL

    # Installation info (filled by technician on mobile)
    installed         = models.BooleanField(default=False)
    installed_at      = models.DateTimeField(null=True, blank=True)
    install_notes     = models.TextField(blank=True, default="")
    install_photo_url = models.TextField(blank=True, default="")  # Cloudinary URL — evidence

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "site_device_dispatch"
        unique_together = ("site_id", "device_id")

    def __str__(self):
        return f"Dispatch site={self.site_id} device={self.device_id}"


class SiteDeviceLog(models.Model):
    """Activity log for a specific device at a site."""

    site_id   = models.BigIntegerField(db_index=True)
    device_id = models.CharField(max_length=50, db_index=True)
    action    = models.CharField(max_length=100)
    user_id   = models.BigIntegerField(null=True, blank=True)
    notes     = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "installations"
        db_table = "site_device_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} — site={self.site_id} device={self.device_id}"


# ── Role / Permission system (Admin Panel) ───────────────────────────────────

class AppRole(models.Model):
    """
    Application-level role.  Lives in sigtools_beta (managed=False — Django does
    not create or migrate this table; raw-SQL admin code owns it).
    """

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    is_system   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "app_roles"
        managed = False

    def __str__(self):
        return self.name


class AppPermission(models.Model):
    """
    Granular permission key (app.category.action).  Lives in sigtools_beta
    (managed=False).
    """

    key         = models.CharField(max_length=100, unique=True)
    app         = models.CharField(max_length=50)
    category    = models.CharField(max_length=50)
    action      = models.CharField(max_length=50)
    description = models.TextField(blank=True, default="")

    class Meta:
        app_label = "installations"
        db_table = "app_permissions"
        managed = False

    def __str__(self):
        return self.key


class AppRolePermission(models.Model):
    """M2M AppRole ↔ AppPermission.  Lives in sigtools_beta (managed=False)."""

    role       = models.ForeignKey(AppRole, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(AppPermission, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        app_label = "installations"
        db_table = "app_role_permissions"
        managed = False
        unique_together = ("role", "permission")


class UserAppRole(models.Model):
    """
    Assigns AppRoles to users by sigtools_beta user_id.  Lives in sigtools_beta
    (managed=False).
    """

    user_id = models.BigIntegerField(db_index=True)
    role    = models.ForeignKey(AppRole, on_delete=models.CASCADE, related_name="user_roles")

    class Meta:
        app_label = "installations"
        db_table = "user_app_roles"
        managed = False
        unique_together = ("user_id", "role")
