"""Schedules selectors — read-only optimized queries."""

from __future__ import annotations

from datetime import date

from django.db.models import QuerySet

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


# ── Squads ─────────────────────────────────────────────────────────────────

def get_all_squads() -> QuerySet[Squad]:
    return Squad.objects.all()


def get_squad_by_id(squad_id: int) -> Squad:
    return Squad.objects.get(pk=squad_id)


# ── ShiftTypes ─────────────────────────────────────────────────────────────

def get_all_shift_types() -> QuerySet[ShiftType]:
    return ShiftType.objects.all()



# ── Schedules ──────────────────────────────────────────────────────────────

def get_schedules_by_range(
    start_date: date,
    end_date: date,
) -> QuerySet[Schedule]:
    return (
        Schedule.objects
        .filter(shift_date__gte=start_date, shift_date__lte=end_date)
    )


def get_schedule_by_user_and_date(
    user_id: int,
    shift_date: date,
) -> Schedule | None:
    return (
        Schedule.objects
        .filter(user_id=user_id, shift_date=shift_date)
        .first()
    )


# ── Squad Patterns ─────────────────────────────────────────────────────────

def get_patterns_by_squad(squad_id: int) -> QuerySet[SquadPattern]:
    return SquadPattern.objects.filter(squad_id=squad_id)


# ── Available Slots ────────────────────────────────────────────────────────

def get_slots_by_range(
    start_date: date,
    end_date: date,
) -> QuerySet[AvailableSlot]:
    return AvailableSlot.objects.filter(
        slot_date__gte=start_date,
        slot_date__lte=end_date,
    )


def get_slot_by_id(slot_id: int) -> AvailableSlot:
    return AvailableSlot.objects.get(pk=slot_id)


# ── Slot Claims ────────────────────────────────────────────────────────────

def get_all_slot_claims() -> QuerySet[SlotClaim]:
    return SlotClaim.objects.select_related("slot").all()


def get_claims_for_slot(slot_id: int) -> QuerySet[SlotClaim]:
    return SlotClaim.objects.filter(slot_id=slot_id)


# ── Cancellation Requests ─────────────────────────────────────────────────

def get_pending_cancellation_requests() -> QuerySet[CancellationRequest]:
    return (
        CancellationRequest.objects
        .select_related("slot")
        .filter(status="pending")
        .order_by("-created_at")
    )


# ── Notifications ──────────────────────────────────────────────────────────

def get_notifications(
    *,
    user_id: int | None = None,
    is_admin: bool = False,
    limit: int = 30,
) -> QuerySet[AppNotification]:
    from django.db.models import Q

    qs = AppNotification.objects.order_by("-created_at")
    if not is_admin and user_id:
        qs = qs.filter(Q(target_user_id=user_id) | Q(is_global=True))
    return qs[:limit]
