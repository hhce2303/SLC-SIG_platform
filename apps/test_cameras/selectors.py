"""Read-only queries for test cameras from default DB."""

from __future__ import annotations

from django.db import connections


def get_cameras_by_site(site_id: int) -> list[dict]:
    """Fetch cameras for a specific site from default DB (sig_dailylogs)."""
    with connections["default"].cursor() as cur:
        cur.execute(
            """
            SELECT 
                id, brand, model, camera_type
            FROM cameras
            WHERE site_id = %s
            """,
            [site_id],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
