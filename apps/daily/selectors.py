from django.db import connections

DISPATCH_ACTIVITY_ID = 23  # daily_activities.ID_Activity = 23 (Dispatched)


def get_police_dispatch_events(limit: int = 50) -> list[dict]:
    """
    Returns daily_events rows where ID_activity = 23 (Dispatched),
    ordered by most recent first.
    DB: sig_dailylogs (default)
    """
    with connections["default"].cursor() as cur:
        cur.execute(
            """
            SELECT
                e.ID_event        AS id,
                e.event_datetime  AS datetime,
                e.ID_site         AS siteId,
                e.event_quantity  AS quantity,
                e.event_camera    AS camera,
                e.event_description AS description,
                e.ID_user         AS userId,
                e.event_status    AS status
            FROM daily_events e
            WHERE e.ID_activity = %s
            ORDER BY e.event_datetime DESC
            LIMIT %s
            """,
            [DISPATCH_ACTIVITY_ID, limit],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
