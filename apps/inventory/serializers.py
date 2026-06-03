"""Inventory serializers — zero logic, only data shape."""

from __future__ import annotations

from rest_framework import serializers

from apps.inventory.models import (
    ActivityLog, Article, Group,
    MaterialsRequest, DailyReport, CableRun,
    ScopeChange, EquipmentReturn, ElevatorRental,
)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

class GroupSerializer(serializers.ModelSerializer):
    # Frontend expects camelCase keys
    iconName = serializers.CharField(source="icon_name")

    class Meta:
        model = Group
        fields = ("id", "name", "description", "iconName", "color")


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

class ArticleReadSerializer(serializers.ModelSerializer):
    groupId = serializers.CharField(source="group_id", allow_null=True)
    acquisitionDate = serializers.DateField(source="acquisition_date", allow_null=True)
    modifiedBy = serializers.CharField(source="modified_by")
    latestNote = serializers.CharField(source="latest_note")
    lastMod = serializers.DateTimeField(source="updated_at", format="%Y-%m-%dT%H:%M:%S")
    quantitySend = serializers.IntegerField(source="quantity_send", allow_null=True)
    checklistReceived = serializers.BooleanField(source="checklist_received", allow_null=True)
    checklistNotes = serializers.CharField(source="checklist_notes")
    checklistDate = serializers.DateTimeField(source="checklist_date", allow_null=True)

    class Meta:
        model = Article
        fields = (
            "id",
            "sku",
            "name",
            "sub",
            "category",
            "groupId",
            "status",
            "location",
            "acquisitionDate",
            "image",
            "serial",
            "modifiedBy",
            "latestNote",
            "lastMod",
            # dispatch fields
            "vendor",
            "quantitySend",
            "tracking",
            "observations",
            # checklist fields
            "checklistReceived",
            "checklistNotes",
            "checklistDate",
        )


class ArticleWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=200)
    sub = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.CharField(max_length=50)
    group_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    status = serializers.CharField(max_length=20, default="activo")
    location = serializers.CharField(required=False, allow_blank=True, default="")
    acquisition_date = serializers.DateField(required=False, allow_null=True, default=None)
    image = serializers.CharField(required=False, allow_blank=True, default="")
    serial = serializers.CharField(required=False, allow_blank=True, default="")
    modified_by = serializers.CharField(required=False, allow_blank=True, default="")
    latest_note = serializers.CharField(required=False, allow_blank=True, default="")
    # dispatch fields
    vendor        = serializers.CharField(required=False, allow_blank=True, default="")
    quantity_send = serializers.IntegerField(required=False, allow_null=True, default=None)
    tracking      = serializers.CharField(required=False, allow_blank=True, default="")
    observations  = serializers.CharField(required=False, allow_blank=True, default="")
    # checklist fields
    checklist_received = serializers.BooleanField(required=False, allow_null=True, default=None)
    checklist_notes    = serializers.CharField(required=False, allow_blank=True, default="")
    checklist_date     = serializers.DateTimeField(required=False, allow_null=True, default=None)


class ArticleUpdateSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=100, required=False)
    name = serializers.CharField(max_length=200, required=False)
    sub = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(max_length=50, required=False)
    group_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.CharField(max_length=20, required=False)
    location = serializers.CharField(required=False, allow_blank=True)
    acquisition_date = serializers.DateField(required=False, allow_null=True)
    image = serializers.CharField(required=False, allow_blank=True)
    serial = serializers.CharField(required=False, allow_blank=True)
    modified_by = serializers.CharField(required=False, allow_blank=True)
    latest_note = serializers.CharField(required=False, allow_blank=True)
    # dispatch fields
    vendor        = serializers.CharField(required=False, allow_blank=True)
    quantity_send = serializers.IntegerField(required=False, allow_null=True)
    tracking      = serializers.CharField(required=False, allow_blank=True)
    observations  = serializers.CharField(required=False, allow_blank=True)
    # checklist fields
    checklist_received = serializers.BooleanField(required=False, allow_null=True)
    checklist_notes    = serializers.CharField(required=False, allow_blank=True)
    checklist_date     = serializers.DateTimeField(required=False, allow_null=True)


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------

class ActivityLogReadSerializer(serializers.ModelSerializer):
    articleId = serializers.IntegerField(source="article_id")
    userId = serializers.CharField(source="user_id")

    class Meta:
        model = ActivityLog
        fields = ("id", "articleId", "action", "userId", "timestamp", "notes")


class ActivityLogWriteSerializer(serializers.Serializer):
    article_id = serializers.IntegerField()
    action = serializers.CharField(max_length=100)
    user_id = serializers.CharField(max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

class DashboardStatsSerializer(serializers.Serializer):
    enAlerta = serializers.IntegerField()
    enMantenimiento = serializers.IntegerField()
    optimo = serializers.IntegerField()
    total = serializers.IntegerField()


# ---------------------------------------------------------------------------
# Cameras by site
# ---------------------------------------------------------------------------

class CamerasBySiteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    brand = serializers.CharField()
    model = serializers.CharField()
    camera_type = serializers.CharField()


# ===========================================================================
# Materials Request
# ===========================================================================

class MaterialsRequestReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialsRequest
        fields = [
            "id", "site_id", "requested_by_id", "items", "status",
            "notes", "reviewer_id", "reviewed_at", "created_at", "updated_at",
        ]


class MaterialsRequestWriteSerializer(serializers.Serializer):
    site_id          = serializers.IntegerField()
    items            = serializers.JSONField()
    notes            = serializers.CharField(allow_blank=True, default="")


class MaterialsRequestReviewSerializer(serializers.Serializer):
    status           = serializers.ChoiceField(choices=["approved", "rejected"])
    reviewer_notes   = serializers.CharField(allow_blank=True, default="")


# ===========================================================================
# Daily Report
# ===========================================================================

class DailyReportReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = [
            "id", "site_id", "date", "submitted_by_id",
            "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10", "q11",
            "created_at",
        ]


class DailyReportWriteSerializer(serializers.Serializer):
    site_id  = serializers.IntegerField()
    date     = serializers.DateField()
    q1  = serializers.CharField(allow_blank=True, default="")
    q2  = serializers.CharField(allow_blank=True, default="")
    q3  = serializers.CharField(allow_blank=True, default="")
    q4  = serializers.CharField(allow_blank=True, default="")
    q5  = serializers.CharField(allow_blank=True, default="")
    q6  = serializers.CharField(allow_blank=True, default="")
    q7  = serializers.CharField(allow_blank=True, default="")
    q8  = serializers.CharField(allow_blank=True, default="")
    q9  = serializers.CharField(allow_blank=True, default="")
    q10 = serializers.CharField(allow_blank=True, default="")
    q11 = serializers.CharField(allow_blank=True, default="")


# ===========================================================================
# Cable Run
# ===========================================================================

class CableRunReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CableRun
        fields = "__all__"


class CableRunWriteSerializer(serializers.Serializer):
    site_id       = serializers.IntegerField()
    label         = serializers.CharField(max_length=255)
    from_location = serializers.CharField(max_length=255, allow_blank=True, default="")
    to_location   = serializers.CharField(max_length=255, allow_blank=True, default="")
    cable_type    = serializers.CharField(max_length=100, allow_blank=True, default="")
    length_ft     = serializers.FloatField(allow_null=True, required=False)
    status        = serializers.ChoiceField(choices=["pending", "complete"], default="pending")
    notes         = serializers.CharField(allow_blank=True, default="")


class CableRunUpdateSerializer(serializers.Serializer):
    label         = serializers.CharField(max_length=255, required=False)
    from_location = serializers.CharField(max_length=255, allow_blank=True, required=False)
    to_location   = serializers.CharField(max_length=255, allow_blank=True, required=False)
    cable_type    = serializers.CharField(max_length=100, allow_blank=True, required=False)
    length_ft     = serializers.FloatField(allow_null=True, required=False)
    status        = serializers.ChoiceField(choices=["pending", "complete"], required=False)
    notes         = serializers.CharField(allow_blank=True, required=False)


# ===========================================================================
# Scope Change
# ===========================================================================

class ScopeChangeReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScopeChange
        fields = "__all__"


class ScopeChangeWriteSerializer(serializers.Serializer):
    site_id     = serializers.IntegerField()
    description = serializers.CharField()
    notes       = serializers.CharField(allow_blank=True, default="")


class ScopeChangeReviewSerializer(serializers.Serializer):
    status         = serializers.ChoiceField(choices=["approved", "rejected"])
    reviewer_notes = serializers.CharField(allow_blank=True, default="")


# ===========================================================================
# Equipment Return
# ===========================================================================

class EquipmentReturnReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentReturn
        fields = "__all__"


class EquipmentReturnWriteSerializer(serializers.Serializer):
    site_id      = serializers.IntegerField()
    device_name  = serializers.CharField(max_length=255)
    device_id    = serializers.CharField(max_length=255, allow_blank=True, default="")
    reason       = serializers.CharField(allow_blank=True, default="")
    qty_returned = serializers.IntegerField(default=1, min_value=1)
    notes        = serializers.CharField(allow_blank=True, default="")


class EquipmentReturnReceiveSerializer(serializers.Serializer):
    notes = serializers.CharField(allow_blank=True, default="")


# ===========================================================================
# Operations Assignment
# ===========================================================================

class OperationsAssignmentSerializer(serializers.Serializer):
    site_id    = serializers.IntegerField()
    data       = serializers.JSONField()


# ===========================================================================
# Elevator Rental
# ===========================================================================

class ElevatorRentalReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElevatorRental
        fields = "__all__"


class ElevatorRentalWriteSerializer(serializers.Serializer):
    lift_required = serializers.BooleanField(default=False)
    vendor        = serializers.CharField(max_length=255, allow_blank=True, default="")
    rental_start  = serializers.DateField(allow_null=True, required=False)
    rental_end    = serializers.DateField(allow_null=True, required=False)
    cost          = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True, required=False)
    notes         = serializers.CharField(allow_blank=True, default="")
