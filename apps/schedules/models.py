from __future__ import annotations

from django.db import models


class Squad(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, default="")
    color_theme = models.CharField(max_length=50, blank=True, default="")
    is_static = models.BooleanField(default=False)
    can_take_slots = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_squads"

    def __str__(self) -> str:
        return self.name


class ShiftType(models.Model):
    """Represents a shift definition (e.g. '9:00pm - 6:00am', 'OFF')."""

    name = models.CharField(max_length=100, unique=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_off = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_shift_types"

    def __str__(self) -> str:
        return self.name


class Schedule(models.Model):
    user = models.ForeignKey(
        "auth.User",
        db_column="user_id",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="schedules",
    )
    shift_date = models.DateField()
    shift_type_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sch_schedules"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "shift_date"],
                name="uq_sch_user_shift_date",
            ),
        ]

    def __str__(self) -> str:
        return f"user={self.user_id} — {self.shift_date}"


class SquadPattern(models.Model):
    """Default weekly shift pattern for a squad (day 1=Mon … 7=Sun)."""

    squad = models.ForeignKey(
        Squad,
        on_delete=models.CASCADE,
        related_name="patterns",
    )
    day_of_week = models.PositiveSmallIntegerField()  # 1-7
    shift_type_id = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "sch_squad_patterns"

    def __str__(self) -> str:
        return f"{self.squad} — day {self.day_of_week}"


class AvailableSlot(models.Model):
    slot_date = models.DateField()
    shift_type_id = models.CharField(max_length=255)
    total_slots = models.PositiveIntegerField(default=1)
    taken_slots = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_available_slots"

    def __str__(self) -> str:
        return f"{self.slot_date} — {self.shift_type_id} ({self.taken_slots}/{self.total_slots})"


class SlotClaim(models.Model):
    slot = models.ForeignKey(
        AvailableSlot,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    user = models.ForeignKey(
        "auth.User",
        db_column="user_id",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="slot_claims",
    )
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_slot_claims"

    def __str__(self) -> str:
        return f"user={self.user_id} → slot {self.slot_id}"


class CancellationRequestStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    APPROVED = "approved", "Aprobado"
    REJECTED = "rejected", "Rechazado"


class CancellationRequest(models.Model):
    slot = models.ForeignKey(
        AvailableSlot,
        on_delete=models.CASCADE,
        related_name="cancellation_requests",
    )
    user = models.ForeignKey(
        "auth.User",
        db_column="user_id",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        related_name="cancellation_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=CancellationRequestStatus.choices,
        default=CancellationRequestStatus.PENDING,
    )
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_cancellation_requests"

    def __str__(self) -> str:
        return f"user={self.user_id} — {self.status}"


class AppNotification(models.Model):
    message = models.TextField()
    is_global = models.BooleanField(default=False)
    target_user = models.ForeignKey(
        "auth.User",
        db_column="target_user_id",
        db_constraint=False,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="schedule_notifications",
    )
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sch_app_notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        target = f"user={self.target_user_id}" if self.target_user_id else "GLOBAL"
        return f"[{target}] {self.message[:60]}"
