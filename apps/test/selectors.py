from django.db import connections

def get_cameras_by_site(site_id: int) -> list:
    """
    Obtiene lista única de marca y tipo de cámara para una instalación.
    cameras → camera_models → camera_brands + camera_types
    """
    with connections["sigtools"].cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT
                cb.Name  AS brand,
                ct.name  AS camera_type
            FROM cameras c
            JOIN camera_models cm ON c.camera_model_id = cm.id
            JOIN camera_brands cb ON cm.camera_brand_id = cb.id
            JOIN camera_types  ct ON cm.camera_type_id  = ct.id
            WHERE c.installation_id = %s
              AND c.deleted_at IS NULL
            ORDER BY cb.Name, ct.name
            """,
            [site_id]
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
