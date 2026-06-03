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
    created_by = models.BigIntegerField(null=True, blank=True)
    approval_requested_by = models.BigIntegerField(null=True, blank=True)
    approval_status = models.CharField(max_length=30, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "sig_projects"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["updated_at"], name="sig_projects_updated_at_idx")]

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
        indexes = [models.Index(fields=["updated_at"], name="site_dispatch_updated_at_idx")]

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
        indexes = [models.Index(fields=["created_at"], name="site_devlog_created_at_idx")]

    def __str__(self):
        return f"{self.action} — site={self.site_id} device={self.device_id}"


# ── Project Sites (pre-verification staging — sigtools_beta, managed=False) ──

class ProjectSite(models.Model):
    """
    Staging table for sites that haven't passed verification yet.
    Lives in sigtools_beta (managed=False — DDL owned by create_project_sites_table command).
    Mirrors the columns of `sites` that are known at onboarding time.
    """

    customer_group_id      = models.BigIntegerField()
    it_backup_id           = models.BigIntegerField(null=True, blank=True)
    it_responsible_id      = models.BigIntegerField(null=True, blank=True)
    name                   = models.CharField(max_length=255)
    ip_address             = models.CharField(max_length=250, null=True, blank=True, default="0.0.0.0")
    state_code             = models.CharField(max_length=2, null=True, blank=True, default="FL")
    country_code           = models.CharField(max_length=2, null=True, blank=True, default="US")
    city                   = models.CharField(max_length=255, null=True, blank=True)
    address                = models.TextField(null=True, blank=True)
    dealership_info        = models.TextField(null=True, blank=True)
    map_path               = models.TextField(null=True, blank=True)
    lat                    = models.FloatField(null=True, blank=True)
    lon                    = models.FloatField(null=True, blank=True, db_column="long")
    circuit_is_https       = models.IntegerField(null=True, blank=True, default=0)
    circuit_status         = models.IntegerField(null=True, blank=True, default=3)
    site_subdomain         = models.CharField(max_length=255, null=True, blank=True)
    site_subdomain_status  = models.CharField(max_length=10, default="none")
    monitored              = models.BooleanField(default=True)
    maintenance            = models.BooleanField(default=True)
    rental                 = models.BooleanField(default=True)
    installation_date      = models.DateField(null=True, blank=True)
    site_status_id         = models.BigIntegerField(null=True, blank=True, default=1)
    site_id                = models.BigIntegerField(null=True, blank=True)
    cameras_count          = models.IntegerField(default=0)
    preowned_cameras_count = models.IntegerField(default=0)
    exterior_cameras_count = models.IntegerField(default=0)
    teams_channelid        = models.CharField(max_length=255, blank=True, default="")
    teams_teamid           = models.CharField(max_length=255, blank=True, default="")
    timezone               = models.CharField(max_length=50, null=True, blank=True, default="America/New_York")
    verification_status    = models.CharField(max_length=20, default="pending")
    created_by             = models.BigIntegerField(null=True, blank=True)
    approval_requested_by  = models.BigIntegerField(null=True, blank=True)
    verified_by            = models.BigIntegerField(null=True, blank=True)
    verified_at            = models.DateTimeField(null=True, blank=True)
    authorized_by          = models.BigIntegerField(null=True, blank=True)
    authorized_at          = models.DateTimeField(null=True, blank=True)
    rejection_reason       = models.TextField(null=True, blank=True)
    created_at             = models.DateTimeField(null=True, blank=True)
    updated_at             = models.DateTimeField(null=True, blank=True)
    deleted_at             = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "installations"
        db_table = "project_sites"
        managed = False

    def __str__(self):
        return self.name


# ── Role / Permission system (Admin Panel) ───────────────────────────────────

class AppRole(models.Model):
    """
    Application-level role.  Lives in sigtools_beta (managed=False — Django does
    not create or migrate this table; raw-SQL admin code owns it).
    """

    id          = models.AutoField(primary_key=True)
    name        = models.CharField(max_length=100, unique=True)
    label       = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    color       = models.CharField(max_length=50, blank=True, default="")
    is_system   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

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
        db_table = "role_permissions"
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


# ── IT Analytic Test Report ──────────────────────────────────────────────────

class ItSiteTest(models.Model):
    """IT Analytic Test Report — one record per site (upserted, managed=True)."""

    site_id      = models.BigIntegerField(unique=True, db_index=True)
    references   = models.JSONField(default=list)
    camera_flags = models.JSONField(default=list)
    checklist    = models.JSONField(default=list)   # 12 structured items
    grade        = models.CharField(max_length=20, blank=True, default="")
    summary      = models.TextField(blank=True, default="")
    delays       = models.JSONField(default=list)
    attachments  = models.JSONField(default=list)
    date         = models.DateField(null=True, blank=True)
    start_time   = models.TimeField(null=True, blank=True)
    end_time     = models.TimeField(null=True, blank=True)
    technicians  = models.JSONField(default=list)
    it_personnel = models.CharField(max_length=255, blank=True, default="")
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "it_site_tests"

    def __str__(self):
        return f"IT Test — site={self.site_id}"


# ── Site Project Info overlay ────────────────────────────────────────────────

class SiteProjectInfo(models.Model):
    """
    Extra project-logistics overlay for a site (stored in sig_dailylogs).
    Supplements the project_sites row in sigtools_beta which carries
    hotel/flight_details; this table adds fields that don't fit there.
    """

    site_id        = models.BigIntegerField(unique=True, db_index=True)
    check_in       = models.DateField(null=True, blank=True)
    check_out      = models.DateField(null=True, blank=True)
    paylocity_code = models.CharField(max_length=50, blank=True, default="")
    extra_notes    = models.TextField(blank=True, default="")
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "installations"
        db_table = "site_project_info"

    def __str__(self):
        return f"ProjectInfo — site={self.site_id}"


# ── In-app notifications ─────────────────────────────────────────────────────

class Notification(models.Model):
    """
    In-app notification for a sigtools_beta user.
    recipient_id references sigtools_beta.users (cross-DB, no FK).
    """

    TYPE_APPROVAL_REQUEST  = "approval_request"
    TYPE_APPROVAL_APPROVED = "approval_approved"
    TYPE_APPROVAL_REJECTED = "approval_rejected"
    TYPE_ONBOARDING        = "onboarding"
    TYPE_INVENTORY_DISPATCH = "inventory_dispatch"
    TYPE_SYSTEM            = "system"

    TYPE_CHOICES = [
        (TYPE_APPROVAL_REQUEST,   "Approval Request"),
        (TYPE_APPROVAL_APPROVED,  "Approval Approved"),
        (TYPE_APPROVAL_REJECTED,  "Approval Rejected"),
        (TYPE_ONBOARDING,         "Onboarding"),
        (TYPE_INVENTORY_DISPATCH, "Inventory Dispatch"),
        (TYPE_SYSTEM,             "System"),
    ]

    recipient_id       = models.BigIntegerField(db_index=True)
    title              = models.CharField(max_length=255)
    message            = models.TextField()
    type               = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    is_read            = models.BooleanField(default=False, db_index=True)
    related_project_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at         = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "installations"
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_id", "is_read"], name="notif_recipient_unread_idx"),
        ]

    def __str__(self):
        return f"[{self.type}] → user={self.recipient_id}: {self.title}"
