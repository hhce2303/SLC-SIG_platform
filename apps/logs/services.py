"""
Write operations for daily events.

Services handle business logic and mutations — views never touch the ORM directly.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ResourceNotFound
from apps.core.models import Activity, Site, User as DailyUser
from apps.logs.models import DailyEvent
from apps.logs.selectors import is_special_site


def create_event(
    daily_user: DailyUser,
    *,
    site_id: int,
    activity_id: int,
    quantity: int,
    camera: str | None = None,
    description: str | None = None,
) -> DailyEvent:
    """
    Create a new daily event.

    - User resolved from JWT (passed in).
    - event_datetime set server-side (now).
    - event_status: if the site belongs to a special group → 'draft' and a
      corresponding Special record is created with timezone-adjusted
      spec_datetime; otherwise → 'confirmed'.

    The event + special creation is wrapped in a single transaction so either
    both persist or neither does.
    """
    if not Site.objects.filter(pk=site_id).exists():
        raise ResourceNotFound(f"Sitio {site_id} no encontrado.")

    if not Activity.objects.filter(pk=activity_id).exists():
        raise ResourceNotFound(f"Actividad {activity_id} no encontrada.")

    is_special = is_special_site(site_id)
    event_status = "draft" if is_special else "confirmed"

    with transaction.atomic():
        event = DailyEvent.objects.create(
            user_id=daily_user.pk,
            site_id=site_id,
            activity_id=activity_id,
            event_datetime=timezone.now(),
            event_status=event_status,
            quantity=str(quantity),
            camera=camera or "",
            description=description or "",
        )

        if is_special:
            # Reload with site relation so create_special_from_event can read
            # site.site_timezone without an extra query inside the service.
            event_with_site = (
                DailyEvent.objects
                .select_related("site", "activity")
                .get(pk=event.pk)
            )
            from apps.notifications.services import create_special_from_event
            create_special_from_event(event_with_site)

    # Return event with relations for the response serializer.
    return (
        DailyEvent.objects
        .select_related("site", "activity")
        .get(pk=event.pk)
    )
