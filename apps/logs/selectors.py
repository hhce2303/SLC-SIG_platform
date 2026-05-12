"""
Read-only queries for daily events.

The key business rule: events are filtered from the user's **last START SHIFT**
(activity_id = 44). This gives the operator a view scoped to their current shift.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.core.models import Site, SpecialGroup
from apps.logs.models import DailyEvent

START_SHIFT_ACTIVITY_ID = 44


def get_shift_events(user_id: int) -> QuerySet[DailyEvent]:
    """
    Return events for *user_id* from their most recent START SHIFT onward.

    If no START SHIFT is found, returns an empty queryset (the operator hasn't
    started a shift yet).
    """
    last_start_shift = (
        DailyEvent.objects
        .filter(user_id=user_id, activity_id=START_SHIFT_ACTIVITY_ID)
        .order_by("-event_datetime")
        .values_list("event_datetime", flat=True)
        .first()
    )

    if last_start_shift is None:
        return DailyEvent.objects.none()

    return (
        DailyEvent.objects
        .filter(user_id=user_id, event_datetime__gte=last_start_shift)
        .select_related("site", "activity")
        .order_by("event_datetime")
    )


def is_special_site(site_id: int) -> bool:
    """
    Check if a site belongs to a special group.

    Looks up the site's group_id and checks it against the
    daily_special_groups table.
    """
    site_group = (
        Site.objects
        .filter(pk=site_id)
        .values_list("group_id", flat=True)
        .first()
    )

    if not site_group:
        return False

    return SpecialGroup.objects.filter(group_code=site_group).exists()
