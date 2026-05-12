"""Schedules services — write operations & business logic."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.db.models import F

from apps.schedules.models import (
    AppNotification,
    AvailableSlot,
    CancellationRequest,
    CancellationRequestStatus,
    Schedule,
    SlotClaim,
    Squad,
    SquadPattern,
)


# ── Squads ─────────────────────────────────────────────────────────────────

def toggle_squad_eligibility(squad_id: int) -> Squad:
    squad = Squad.objects.get(pk=squad_id)
    squad.can_take_slots = not squad.can_take_slots
    squad.save(update_fields=["can_take_slots"])
    return squad


# ── Schedules ──────────────────────────────────────────────────────────────

def upsert_schedule(
    *,
    user_id: int,
    shift_date: date,
    shift_type_id: str,
) -> Schedule:
    schedule, _ = Schedule.objects.update_or_create(
        user_id=user_id,
        shift_date=shift_date,
        defaults={"shift_type_id": shift_type_id},
    )
    return schedule


def upsert_schedules_bulk(payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        if (
            not payload.get("user_id")
            or not payload.get("shift_date")
            or not payload.get("shift_type_id")
        ):
            continue
        Schedule.objects.update_or_create(
            user_id=payload["user_id"],
            shift_date=payload["shift_date"],
            defaults={"shift_type_id": payload["shift_type_id"]},
        )


def delete_schedules_by_range(start_date: date, end_date: date) -> int:
    count, _ = (
        Schedule.objects
        .filter(shift_date__gte=start_date, shift_date__lte=end_date)
        .delete()
    )
    return count


def delete_schedule_by_id(schedule_id: int) -> None:
    Schedule.objects.filter(pk=schedule_id).delete()


def delete_schedule_by_user_and_date(
    user_id: int,
    shift_date: date,
) -> None:
    Schedule.objects.filter(
        user_id=user_id,
        shift_date=shift_date,
    ).delete()


# ── Available Slots ────────────────────────────────────────────────────────

def create_available_slot(
    *,
    slot_date: date,
    shift_type_id: str,
    total_slots: int,
) -> AvailableSlot:
    return AvailableSlot.objects.create(
        slot_date=slot_date,
        shift_type_id=shift_type_id,
        total_slots=total_slots,
        taken_slots=0,
    )


def delete_available_slot(slot_id: int) -> None:
    AvailableSlot.objects.filter(pk=slot_id).delete()


# ── Slot Claims ────────────────────────────────────────────────────────────

@transaction.atomic
def claim_slot(*, slot_id: int, user_id: int) -> SlotClaim:
    slot = AvailableSlot.objects.select_for_update().get(pk=slot_id)
    if slot.taken_slots >= slot.total_slots:
        raise ValueError("No hay cupos disponibles para este turno.")

    claim = SlotClaim.objects.create(slot_id=slot_id, user_id=user_id)
    slot.taken_slots = F("taken_slots") + 1
    slot.save(update_fields=["taken_slots"])
    return claim


@transaction.atomic
def unclaim_slot(*, slot_id: int, user_id: int) -> None:
    deleted, _ = SlotClaim.objects.filter(
        slot_id=slot_id,
        user_id=user_id,
    ).delete()
    if deleted:
        AvailableSlot.objects.filter(pk=slot_id).update(
            taken_slots=F("taken_slots") - 1,
        )


# ── Cancellation Requests ─────────────────────────────────────────────────

def create_cancellation_request(*, slot_id: int, user_id: int) -> CancellationRequest:
    if CancellationRequest.objects.filter(
        slot_id=slot_id,
        user_id=user_id,
        status=CancellationRequestStatus.PENDING,
    ).exists():
        raise ValueError("Ya tienes una solicitud pendiente para este turno.")

    return CancellationRequest.objects.create(
        slot_id=slot_id,
        user_id=user_id,
        status=CancellationRequestStatus.PENDING,
    )


@transaction.atomic
def handle_cancellation_request(request_id: int, *, approve: bool) -> CancellationRequest:
    cr = CancellationRequest.objects.select_for_update().get(pk=request_id)
    cr.status = (
        CancellationRequestStatus.APPROVED if approve
        else CancellationRequestStatus.REJECTED
    )
    cr.save(update_fields=["status"])

    if approve:
        unclaim_slot(slot_id=cr.slot_id, user_id=cr.user_id)

    return cr


# ── Notifications ──────────────────────────────────────────────────────────

def create_notification(
    *,
    message: str,
    target_user_id: int | None = None,
    is_global: bool = False,
) -> AppNotification:
    return AppNotification.objects.create(
        message=message,
        target_user_id=target_user_id,
        is_global=is_global,
        read=False,
    )


def mark_notifications_as_read(notification_ids: list[int]) -> int:
    if not notification_ids:
        return 0
    return AppNotification.objects.filter(pk__in=notification_ids).update(read=True)
