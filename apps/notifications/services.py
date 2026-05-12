"""
Business logic for notifications (specials).

Rules:
- create_special_from_event: converts a draft DailyEvent to a Special, applying
  the site's timezone offset to spec_datetime so supervisors see local time.
- mark_special: sets spec_status, spec_marked_at=now(), spec_marked_by=supervisor_id.
- unmark_special: clears all three fields (status=None).
- select_for_update() prevents concurrent mark races on the same row.

Timezone adjustment rationale:
  event_datetime is stored in UTC (Django USE_TZ=True).
  spec_datetime must reflect the site's local time so supervisors see events at
  "site clock" time, matching legacy desktop app behavior.
  Technique: add the offset hours to the UTC datetime. Django stores the
  resulting value as-is in MySQL DATETIME (no TZ stored in the column), so the
  DB value equals the local time of the site. The API response always includes
  site_timezone so the frontend can display it correctly.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Special
from apps.notifications.selectors import get_on_duty_supervisor_id, get_timezone_offset_for_site

if TYPE_CHECKING:
    from apps.logs.models import DailyEvent


def create_special_from_event(event: "DailyEvent") -> Special:
    """
    Convert a draft DailyEvent to a Special record.

    Called by logs.services.create_event immediately after a draft event is
    persisted. The caller must pass an event with ``site`` already
    select_related (no extra query needed here).

    Timezone adjustment:
        spec_datetime = event_datetime + timedelta(hours=site_tz_offset)

    supervisor is left NULL at creation — supervisor assignment is a
    separate step (auto-assign via ranges or manual assignment).
    """
    offset = get_timezone_offset_for_site(event.site.site_timezone)
    # offset is relative to Colombia (UTC-5).
    # To convert UTC → site local: UTC + (offset − 5).
    # e.g. ET summer: offset=+1 → UTC − 4 = ET local (UTC-4)
    # The result stays UTC-aware; the NUMERIC value equals site local time.
    # The serializer returns it without a Z suffix so the frontend displays
    # the value as-is (no second UTC→local browser conversion).
    COLOMBIA_UTC_OFFSET = -5
    spec_datetime = event.event_datetime + timedelta(hours=offset + COLOMBIA_UTC_OFFSET)

    supervisor_id = get_on_duty_supervisor_id()
    if supervisor_id is None:
        raise ValueError(
            "No supervisor found to assign the special. "
            "Ensure at least one Supervisor user exists."
        )

    return Special.objects.create(
        event_id=event.pk,
        site_id=event.site_id,
        activity_id=event.activity_id,
        user_id=event.user_id,
        supervisor_id=supervisor_id,
        spec_datetime=spec_datetime,
        spec_quantity=event.quantity,
        spec_camera=event.camera,
        spec_description=event.description,
        spec_status=None,
        spec_marked_at=None,
        spec_marked_by=None,
    )


def mark_special(
    special_id: int,
    status: str | None,
    marked_by_id: int,
) -> Special:
    """
    Mark or unmark a special.

    Args:
        special_id:    PK of the Special row.
        status:        'done' | 'flagged' to mark, None to unmark.
        marked_by_id:  daily_user PK of the supervisor performing the action.

    Returns:
        The updated Special instance (not re-fetched — caller handles serialization).

    Raises:
        Special.DoesNotExist: propagated to view for 404 handling.
    """
    with transaction.atomic():
        special = Special.objects.select_for_update().get(pk=special_id)

        if status is None:
            special.spec_status = None
            special.spec_marked_at = None
            special.spec_marked_by = None
        else:
            special.spec_status = status
            special.spec_marked_at = timezone.now()
            special.spec_marked_by = marked_by_id

        special.save(update_fields=["spec_status", "spec_marked_at", "spec_marked_by"])

    return special
