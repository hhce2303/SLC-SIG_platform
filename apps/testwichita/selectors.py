"""Selectors — read operations for test endpoint."""

from django.db import connections


def get_cameras_for_site(site_id: int) -> list[dict]:
    """Get cameras for a specific site ID from sigtools DB."""
    with connections["sigtools"].cursor() as cur:
        cur.execute(
            """
            SELECT 
                id, 
                serial, 
                brand, 
                model, 
                camera_type, 
                ip_address, 
                status
            FROM cameras
            WHERE site_id = %s
            LIMIT 100
            """,
            [site_id],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
