"""Schedules serializers — zero logic, only data shape."""

from __future__ import annotations

from rest_framework import serializers

from apps.schedules.models import (
    AppNotification,
    AvailableSlot,
    CancellationRequest,
    Schedule,
    ShiftType,
    SlotClaim,
    Squad,
    SquadPattern,
)


# ── Squad ──────────────────────────────────────────────────────────────────

class SquadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Squad
        fields = ("id", "name", "description", "color_theme", "is_static", "can_take_slots")


# ── ShiftType ──────────────────────────────────────────────────────────────

class ShiftTypeSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format="%H:%M:%S", allow_null=True)
    end_time = serializers.TimeField(format="%H:%M:%S", allow_null=True)

    class Meta:
        model = ShiftType
        fields = ("id", "name", "start_time", "end_time", "is_off", "is_custom")



# ── Schedule ───────────────────────────────────────────────────────────────

class ScheduleReadSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField()
    shift_type_id = serializers.CharField()

    class Meta:
        model = Schedule
        fields = ("id", "user_id", "shift_date", "shift_type_id")


class ScheduleWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    shift_date = serializers.DateField()
    shift_type_id = serializers.CharField(max_length=255)


class ScheduleBulkSerializer(serializers.Serializer):
    schedules = serializers.ListField(child=ScheduleWriteSerializer())


# ── SquadPattern ───────────────────────────────────────────────────────────

class SquadPatternSerializer(serializers.ModelSerializer):
    squad_id = serializers.IntegerField()

    class Meta:
        model = SquadPattern
        fields = ("id", "squad_id", "day_of_week", "shift_type_id")


# ── AvailableSlot ──────────────────────────────────────────────────────────

class AvailableSlotReadSerializer(serializers.ModelSerializer):
    shift_type_id = serializers.CharField()

    class Meta:
        model = AvailableSlot
        fields = ("id", "slot_date", "shift_type_id", "total_slots", "taken_slots", "created_at")


class AvailableSlotWriteSerializer(serializers.Serializer):
    slot_date = serializers.DateField()
    shift_type_id = serializers.CharField(max_length=255)
    total_slots = serializers.IntegerField(min_value=1)


# ── SlotClaim ──────────────────────────────────────────────────────────────

class SlotClaimReadSerializer(serializers.ModelSerializer):
    slot_id = serializers.IntegerField()
    user_id = serializers.IntegerField()

    class Meta:
        model = SlotClaim
        fields = ("id", "slot_id", "user_id", "claimed_at")


class SlotClaimWriteSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    user_id = serializers.IntegerField()


# ── CancellationRequest ───────────────────────────────────────────────────

class CancellationRequestReadSerializer(serializers.ModelSerializer):
    slot_id = serializers.IntegerField()
    user_id = serializers.IntegerField()

    class Meta:
        model = CancellationRequest
        fields = ("id", "slot_id", "user_id", "status", "reason", "created_at")


class CancellationRequestWriteSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    user_id = serializers.IntegerField()


class CancellationRequestHandleSerializer(serializers.Serializer):
    approve = serializers.BooleanField()


# ── Notification ───────────────────────────────────────────────────────────

class NotificationReadSerializer(serializers.ModelSerializer):
    target_user_id = serializers.IntegerField(allow_null=True)

    class Meta:
        model = AppNotification
        fields = ("id", "message", "is_global", "target_user_id", "read", "created_at")


class NotificationWriteSerializer(serializers.Serializer):
    message = serializers.CharField()
    target_user_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    is_global = serializers.BooleanField(default=False)


class NotificationMarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())
