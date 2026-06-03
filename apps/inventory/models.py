from __future__ import annotations

from django.db import models


class ArticleStatus(models.TextChoices):
    ACTIVO = "activo", "Activo"
    REPARADO = "reparado", "Reparado"
    REPARACION = "reparacion", "En reparación"
    DANADO = "danado", "Dañado"
    COTIZACION = "cotizacion", "En Cotización"
    INSTALACION = "instalacion", "En Instalación"


class ArticleCategory(models.TextChoices):
    PERIFERICOS = "Perifericos", "Periféricos"
    ELECTRODOMESTICOS = "Electrodomesticos", "Electrodomésticos"
    MOBILIARIO = "Mobiliario", "Mobiliario"
    COMPUTADORES = "Computadores", "Computadores"
    PARTES_ELECTRONICAS = "Partes Electronicas", "Partes Electrónicas"


class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    icon_name = models.CharField(max_length=50, blank=True, default="Package")
    color = models.CharField(max_length=30, blank=True, default="#6366f1")

    class Meta:
        db_table = "inv_groups"

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    sku = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    sub = models.CharField(max_length=200, blank=True, default="")
    category = models.CharField(max_length=50, choices=ArticleCategory.choices)
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.ACTIVO,
    )
    location = models.CharField(max_length=200, blank=True, default="")
    acquisition_date = models.DateField(null=True, blank=True)
    image = models.CharField(max_length=500, blank=True, default="")
    serial = models.CharField(max_length=200, blank=True, default="")
    modified_by = models.CharField(max_length=100, blank=True, default="")
    latest_note = models.TextField(blank=True, default="")
    # Extracted from latest_note when it contains a [device:XXX] tag.
    # Indexed so catalog serial lookups are O(log n) instead of a full scan.
    device_id = models.CharField(max_length=50, blank=True, default="", db_index=True)

    # Dispatch / shipping info
    vendor        = models.CharField(max_length=255, blank=True, default="")
    quantity_send = models.IntegerField(null=True, blank=True)
    tracking      = models.CharField(max_length=500, blank=True, default="")
    observations  = models.TextField(blank=True, default="")

    # Technician receipt checklist
    checklist_received = models.BooleanField(null=True, blank=True)
    checklist_notes    = models.TextField(blank=True, default="")
    checklist_date     = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_articles"
        indexes = [
            models.Index(fields=["status"], name="inv_articles_status_idx"),
            models.Index(fields=["updated_at"], name="inv_articles_updated_at_idx"),
            models.Index(fields=["status", "updated_at"], name="inv_art_status_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"


class ActivityLog(models.Model):
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "inv_activity_logs"
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["timestamp"], name="inv_actlog_timestamp_idx")]

    def __str__(self) -> str:
        return f"{self.action} on Article #{self.article_id}"


# ── Materials Request ────────────────────────────────────────────────────────

class MaterialsRequest(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    site_id         = models.BigIntegerField(db_index=True)
    requested_by_id = models.BigIntegerField()
    items           = models.JSONField(default=list)   # [{name, qty, notes}, ...]
    status          = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    notes        = models.TextField(blank=True, default="")
    reviewer_id  = models.BigIntegerField(null=True, blank=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_materials_requests"
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["site_id", "status"], name="inv_mr_site_status_idx"),
            models.Index(fields=["created_at"], name="inv_matreq_created_at_idx"),
            models.Index(fields=["updated_at"], name="inv_matreq_updated_at_idx"),
        ]

    def __str__(self) -> str:
        return f"MaterialsRequest site={self.site_id} [{self.status}]"


# ── Daily Report ─────────────────────────────────────────────────────────────

class DailyReport(models.Model):
    site_id         = models.BigIntegerField(db_index=True)
    date            = models.DateField(db_index=True)
    submitted_by_id = models.BigIntegerField()
    q1  = models.TextField(blank=True, default="")
    q2  = models.TextField(blank=True, default="")
    q3  = models.TextField(blank=True, default="")
    q4  = models.TextField(blank=True, default="")
    q5  = models.TextField(blank=True, default="")
    q6  = models.TextField(blank=True, default="")
    q7  = models.TextField(blank=True, default="")
    q8  = models.TextField(blank=True, default="")
    q9  = models.TextField(blank=True, default="")
    q10 = models.TextField(blank=True, default="")
    q11 = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inv_daily_reports"
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["site_id", "date"], name="inv_dr_site_date_idx"),
            models.Index(fields=["created_at"], name="inv_dailyrep_created_at_idx"),
        ]

    def __str__(self) -> str:
        return f"DailyReport site={self.site_id} {self.date}"


# ── Cable Runs ───────────────────────────────────────────────────────────────

class CableRun(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("complete", "Complete"),
    ]

    site_id       = models.BigIntegerField(db_index=True)
    label         = models.CharField(max_length=255)
    from_location = models.CharField(max_length=255, blank=True, default="")
    to_location   = models.CharField(max_length=255, blank=True, default="")
    cable_type    = models.CharField(max_length=100, blank=True, default="")
    length_ft     = models.FloatField(null=True, blank=True)
    status        = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    notes      = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_cable_runs"
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["site_id"])]

    def __str__(self) -> str:
        return f"CableRun '{self.label}' site={self.site_id}"


# ── Scope Changes ────────────────────────────────────────────────────────────

class ScopeChange(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    site_id         = models.BigIntegerField(db_index=True)
    description     = models.TextField()
    status          = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    requested_by_id = models.BigIntegerField(null=True, blank=True)
    reviewed_by_id  = models.BigIntegerField(null=True, blank=True)
    reviewer_notes  = models.TextField(blank=True, default="")
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_scope_changes"
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["site_id", "status"], name="inv_sc_site_status_idx")]

    def __str__(self) -> str:
        return f"ScopeChange site={self.site_id} [{self.status}]"


# ── Equipment Returns ─────────────────────────────────────────────────────────

class EquipmentReturn(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("received", "Received"),
    ]

    site_id        = models.BigIntegerField(db_index=True)
    device_id      = models.CharField(max_length=50)
    device_name    = models.CharField(max_length=255, blank=True, default="")
    reason         = models.TextField(blank=True, default="")
    qty_returned   = models.IntegerField(null=True, blank=True)
    returned_at    = models.DateTimeField(null=True, blank=True)
    received_by_id = models.BigIntegerField(null=True, blank=True)
    status         = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    notes      = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_equipment_returns"
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["site_id"])]

    def __str__(self) -> str:
        return f"EquipReturn site={self.site_id} device={self.device_id}"


# ── Operations Assignment ─────────────────────────────────────────────────────

class OperationsAssignment(models.Model):
    """Singleton per site — operations personnel/role assignment."""

    site_id    = models.BigIntegerField(unique=True, db_index=True)
    data       = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_operations_assignment"

    def __str__(self) -> str:
        return f"OperationsAssignment site={self.site_id}"


# ── Elevator Rental ───────────────────────────────────────────────────────────

class ElevatorRental(models.Model):
    """Singleton per site — elevator/lift rental info."""

    site_id      = models.BigIntegerField(unique=True, db_index=True)
    lift_required = models.BooleanField(default=False)
    vendor       = models.CharField(max_length=255, blank=True, default="")
    rental_start = models.DateField(null=True, blank=True)
    rental_end   = models.DateField(null=True, blank=True)
    cost         = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes        = models.TextField(blank=True, default="")
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inv_elevator_rental"

    def __str__(self) -> str:
        return f"ElevatorRental site={self.site_id}"
