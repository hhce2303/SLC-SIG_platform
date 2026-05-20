"""
Selectors — read-only queries against sigtools_beta.
All DB access is routed via 'sigtools' alias by SigtoolsRouter.
Complex joins use raw SQL; simple lookups use the ORM.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db import connections

from apps.sigtools.models import (
    CameraModel,
    CustomerGroup,
    DeviceType,
    Installation,
    InstallationType,
    Server,
    Site,
    SigtoolsUser,
)

_DB = "sigtools"

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def get_camera_catalog() -> list[dict]:
    """
    Hierarchical camera catalog: Type → Brand → [Model].
    Uses raw SQL for the three-table join; returns a nested Python structure.
    """
    sql = """
        SELECT
            ct.id   AS type_id,  ct.name AS type_name,
            ct.description,      ct.lens_amount,
            cb.id   AS brand_id, cb.Name AS brand_name,
            cm.id   AS model_id, cm.name AS model_name
        FROM camera_types ct
        JOIN camera_models cm ON ct.id = cm.camera_type_id
        JOIN camera_brands cb ON cm.camera_brand_id = cb.id
        ORDER BY ct.name, cb.Name, cm.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    types: dict[int, dict] = {}
    for row in rows:
        t_id = row["type_id"]
        if t_id not in types:
            types[t_id] = {
                "id": t_id,
                "name": row["type_name"],
                "description": row["description"],
                "lens_amount": row["lens_amount"],
                "brands": {},
            }
        b_id = row["brand_id"]
        if b_id not in types[t_id]["brands"]:
            types[t_id]["brands"][b_id] = {
                "id": b_id,
                "name": row["brand_name"],
                "models": [],
            }
        types[t_id]["brands"][b_id]["models"].append(
            {"id": row["model_id"], "name": row["model_name"]}
        )

    result = []
    for t in types.values():
        t["brands"] = list(t["brands"].values())
        result.append(t)
    return result


def get_device_types() -> list[dict]:
    return list(
        DeviceType.objects.using(_DB)
        .order_by("device_type", "brand", "model")
        .values("id", "device_type", "brand", "model")
    )


def get_vms_catalog() -> list[str]:
    return list(
        Server.objects.using(_DB)
        .filter(deleted_at__isnull=True)
        .exclude(vms_name__isnull=True)
        .exclude(vms_name="")
        .order_by("vms_name")
        .values_list("vms_name", flat=True)
        .distinct()
    )


def get_installation_types() -> list[dict]:
    return list(
        InstallationType.objects.using(_DB)
        .order_by("name")
        .values("id", "name")
    )


def get_customer_groups() -> list[dict]:
    return list(
        CustomerGroup.objects.using(_DB)
        .order_by("name")
        .values("id", "name")
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

_VALID_ROLES = {
    "admins": "Admin",
    "project-owners": "Project Owner",
    "lead-techs": "Lead Tech",
    "developers": "Developer",
}

_IT_TECH_ROLE_ID = 4  # role_id 4 = IT Technician (by ID as in original API)


def get_users_by_role(role_key: str) -> list[dict]:
    """
    Returns users filtered by role.
    role_key can be: 'admins', 'project-owners', 'lead-techs', 'developers', 'it-technicians'
    """
    if role_key == "it-technicians":
        sql = """
            SELECT u.id, u.username, u.name, r.name AS role
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE u.deleted_at IS NULL AND r.id = %s
        """
        params = [_IT_TECH_ROLE_ID]
    else:
        role_name = _VALID_ROLES.get(role_key)
        if not role_name:
            return []
        sql = """
            SELECT u.id, u.username, u.name, r.name AS role
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE u.deleted_at IS NULL AND r.name = %s
        """
        params = [role_name]

    with connections[_DB].cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

def list_sites() -> list[dict]:
    """
    Returns all active sites ordered by name.
    Useful for discovering site IDs before filtering cameras by site.
    """
    return list(
        Site.objects.using(_DB)
        .filter(deleted_at__isnull=True)
        .order_by("name")
        .values(
            "id", "name", "city", "state_code", "country_code",
            "cameras_count", "total_devices", "monitored", "ip_address", "address",
        )
    )


def list_sites_dashboard() -> list[dict]:
    """
    Enriched site list for the frontend dashboard.

    For each site returns:
    - status:       name of the latest installation's inst_status (null if no installation)
    - responsable:  project_owner user name of the latest installation
    - it_manager:   first IT responsible user name from it_installation_responsibles
    - notes:        text of the most recent installation_note (latest created_at)
    - log:          all installation_notes as [{date, action, user}] sorted oldest→newest

    Two queries are used to avoid N+1:
    1. Main SQL — sites + latest installation + status + responsable + it_manager
    2. Notes SQL — all notes for the relevant installations in one batch
    """
    main_sql = """
        SELECT
            s.id,
            s.name,
            s.address,
            s.city,
            s.state_code,
            s.customer_group_id,
            ist.name   AS status,
            u.name     AS responsable,
            it_u.name  AS it_manager,
            i.id       AS installation_id
        FROM sites s
        LEFT JOIN (
            SELECT site_id, MAX(id) AS latest_id
            FROM installations
            WHERE deleted_at IS NULL
            GROUP BY site_id
        ) li ON s.id = li.site_id
        LEFT JOIN installations i   ON i.id            = li.latest_id
        LEFT JOIN inst_statuses ist ON i.inst_status_id = ist.id
        LEFT JOIN users u           ON i.project_owner  = u.id
        LEFT JOIN (
            SELECT installation_id, MIN(user_id) AS user_id
            FROM it_installation_responsibles
            GROUP BY installation_id
        ) itr ON itr.installation_id = i.id
        LEFT JOIN users it_u ON it_u.id = itr.user_id
        WHERE s.deleted_at IS NULL
        ORDER BY s.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(main_sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    inst_ids = [r["installation_id"] for r in rows if r["installation_id"] is not None]

    notes_by_inst: dict[int, list[dict]] = defaultdict(list)
    if inst_ids:
        placeholders = ", ".join(["%s"] * len(inst_ids))
        notes_sql = f"""
            SELECT
                n.installation_id,
                n.note,
                n.created_at,
                u.name AS user_name
            FROM installation_notes n
            LEFT JOIN users u ON n.user_note_id = u.id
            WHERE n.installation_id IN ({placeholders})
            ORDER BY n.created_at ASC
        """
        with connections[_DB].cursor() as cur:
            cur.execute(notes_sql, inst_ids)
            note_cols = [c[0] for c in cur.description]
            for note_row in [dict(zip(note_cols, r)) for r in cur.fetchall()]:
                ts = note_row["created_at"]
                notes_by_inst[note_row["installation_id"]].append({
                    "date": ts.isoformat() if ts else None,
                    "action": note_row["note"],
                    "user": note_row["user_name"] or "Unknown",
                })

    result = []
    for row in rows:
        inst_id = row["installation_id"]
        log_entries = notes_by_inst.get(inst_id, [])
        location = ", ".join(filter(None, [row.get("city"), row.get("state_code")])) or None
        result.append({
            "id": row["id"],
            "name": row["name"],
            "status": row["status"] or None,
            "address": row["address"] or None,
            "location": location,
            "responsable": row["responsable"] or None,
            "it_manager": row["it_manager"] or None,
            "notes": log_entries[-1]["action"] if log_entries else None,
            "log": log_entries,
            "customer_group_id": row["customer_group_id"],
        })
    return result


def list_cameras(
    site_id: int | None = None,
    brand: str | None = None,
    camera_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Returns cameras with full details: brand, model, type, serial, site,
    associated device address and status.
    Supports optional filters; limit is capped at 500.
    """
    limit = min(int(limit), 500)

    where_clauses = [
        "c.deleted_at IS NULL",
        "i.deleted_at IS NULL",
        "s.deleted_at IS NULL",
    ]
    params: list = []

    if site_id is not None:
        where_clauses.append("s.id = %s")
        params.append(int(site_id))

    if brand:
        where_clauses.append("cb.Name LIKE %s")
        params.append(f"%{brand}%")

    if camera_type:
        where_clauses.append("ct.name LIKE %s")
        params.append(f"%{camera_type}%")

    where_sql = " AND ".join(where_clauses)
    params.append(limit)

    sql = f"""
        SELECT
            c.id,
            c.serial,
            cb.Name          AS brand,
            cm.name          AS model,
            ct.name          AS camera_type,
            c.exterior,
            c.preowned,
            c.lift,
            c.height,
            c.hours,
            c.notes          AS camera_notes,
            d.name           AS device_name,
            d.address        AS device_address,
            d.status         AS device_status,
            s.id             AS site_id,
            s.name           AS site_name,
            s.city,
            s.state_code,
            c.installation_id
        FROM cameras c
        JOIN camera_models cm  ON c.camera_model_id = cm.id
        JOIN camera_brands cb  ON cm.camera_brand_id = cb.id
        JOIN camera_types  ct  ON cm.camera_type_id  = ct.id
        JOIN devices       d   ON c.device_id        = d.id
        JOIN installations i   ON c.installation_id  = i.id
        JOIN sites         s   ON i.site_id          = s.id
        WHERE {where_sql}
        ORDER BY s.name, ct.name, cb.Name, cm.name
        LIMIT %s
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    # Coerce booleans from MySQL tinyint(1) → Python bool
    for row in rows:
        for field in ("exterior", "preowned", "lift"):
            if row[field] is not None:
                row[field] = bool(row[field])
    return rows


def get_site_or_404(site_id: int) -> Site | None:
    return Site.objects.using(_DB).filter(pk=site_id, deleted_at__isnull=True).first()


def get_camera_model_catalog() -> list[dict]:
    """
    Flat list of every camera model registered in the company catalog.
    NOT tied to any site or physical unit — used when building a new
    installation and selecting which models to assign.

    Shape is identical to get_site_camera_models so the frontend can
    reuse the same TypeScript interface. serial and ip are always None
    because these are model definitions, not physical units.
    """
    sql = """
        SELECT
            cm.id          AS model_id,
            cm.name        AS name,
            cb.Name        AS brand,
            ct.name        AS subtype,
            ct.description AS type_desc
        FROM camera_models cm
        JOIN camera_brands cb ON cm.camera_brand_id = cb.id
        JOIN camera_types  ct ON cm.camera_type_id  = ct.id
        ORDER BY ct.name, cb.Name, cm.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    return [
        {
            "id": f"cam-{row['model_id']}",
            "name": row["name"],
            "brand": (row["brand"] or "").upper(),
            "serial": None,
            "ip": None,
            "resolution": None,
            "type": row["type_desc"],
            "category": "camera",
            "subtype": (row["subtype"] or "").lower(),
            "lensType": None,
            "rango_lente_mm": None,
            "rango_fov_grados": None,
            "poe_watts": None,
            "bandwidth_mbps": None,
        }
        for row in rows
    ]


def get_site_camera_models(site_id: int) -> list[dict]:
    """
    Returns one entry per individual camera installed at a given site.
    Each camera is identified by its own DB id and serial number.
    Fields with no DB column are returned as None so the frontend schema
    stays intact.
    """
    sql = """
        SELECT
            c.id           AS camera_id,
            c.serial       AS serial,
            cm.name        AS name,
            cb.Name        AS brand,
            ct.name        AS subtype,
            ct.description AS type_desc,
            d.address      AS ip
        FROM cameras c
        JOIN camera_models cm  ON c.camera_model_id = cm.id
        JOIN camera_brands cb  ON cm.camera_brand_id = cb.id
        JOIN camera_types  ct  ON cm.camera_type_id  = ct.id
        JOIN installations i   ON c.installation_id  = i.id
        LEFT JOIN devices  d   ON c.device_id        = d.id
        WHERE i.site_id = %s
          AND i.deleted_at IS NULL
          AND c.deleted_at IS NULL
        ORDER BY ct.name, cb.Name, cm.name, c.serial
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [int(site_id)])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    return [
        {
            "id": f"cam-{row['camera_id']}",
            "name": row["name"],
            "brand": (row["brand"] or "").upper(),
            "serial": row["serial"],
            "ip": row["ip"] or None,
            "resolution": None,
            "type": row["type_desc"],
            "category": "camera",
            "subtype": (row["subtype"] or "").lower(),
            "lensType": None,
            "rango_lente_mm": None,
            "rango_fov_grados": None,
            "poe_watts": None,
            "bandwidth_mbps": None,
        }
        for row in rows
    ]


def get_site_switch_models(site_id: int) -> list[dict]:
    """
    Returns distinct switch device-type entries installed at a given site
    in the frontend catalog format.  Fields with no DB column are None.
    Filters device_types.device_type = 'Switch' only.
    """
    sql = """
        SELECT DISTINCT
            dt.id    AS type_id,
            dt.model AS name,
            dt.brand AS brand
        FROM other_devices od
        JOIN device_types  dt ON od.device_type_id = dt.id
        JOIN installations i  ON od.installation_id = i.id
        WHERE i.site_id = %s
          AND dt.device_type = 'Switch'
          AND i.deleted_at IS NULL
          AND od.deleted_at IS NULL
        ORDER BY dt.brand, dt.model
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [int(site_id)])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    return [
        {
            "id": f"switch-{row['type_id']}",
            "name": row["name"],
            "brand": row["brand"],
            "resolution": "\u2014",
            "type": None,
            "category": "static",
            "subtype": "switch",
            "poe_watts": None,
            "bandwidth_mbps": None,
            "poe_budget_watts": None,
            "uplink_mbps": None,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Unified site device catalog
# ---------------------------------------------------------------------------

# Maps device_types.device_type → (category, subtype, id_prefix)
_OTHER_DEVICE_MAP: dict[str, tuple[str, str, str]] = {
    "Switch":         ("network",  "switch",         "switch"),
    "Router":         ("network",  "router",         "router"),
    "PDU":            ("power",    "pdu",            "pdu"),
    "DA":             ("video",    "da",             "da"),
    "RADIO":          ("wireless", "radio",          "radio"),
    "Access Control": ("security", "access_control", "ac"),
}


def get_site_device_catalog(site_id: int) -> list[dict]:
    """
    Unified device catalog for a site.

    Returns all cameras (one entry per physical unit) and all other devices
    (one entry per physical unit from other_devices) in a single flat list
    with a consistent shape.  All fields that don't apply to a given device
    type are returned as None so the frontend interface stays stable.

    Order: cameras first (sorted by subtype/brand/name), then other devices
    sorted by device_type/brand/model.
    """
    return _get_site_cameras_for_catalog(site_id) + _get_site_other_devices_for_catalog(site_id)


def _get_site_cameras_for_catalog(site_id: int) -> list[dict]:
    sql = """
        SELECT
            c.id           AS camera_id,
            c.serial       AS serial,
            cm.name        AS name,
            cb.Name        AS brand,
            ct.name        AS subtype,
            ct.description AS type_desc,
            d.address      AS ip
        FROM cameras c
        JOIN camera_models cm  ON c.camera_model_id = cm.id
        JOIN camera_brands cb  ON cm.camera_brand_id = cb.id
        JOIN camera_types  ct  ON cm.camera_type_id  = ct.id
        JOIN installations i   ON c.installation_id  = i.id
        LEFT JOIN devices  d   ON c.device_id        = d.id
        WHERE i.site_id = %s
          AND i.deleted_at IS NULL
          AND c.deleted_at IS NULL
        ORDER BY ct.name, cb.Name, cm.name, c.serial
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [int(site_id)])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    return [
        {
            "id": f"cam-{row['camera_id']}",
            "name": row["name"],
            "brand": (row["brand"] or "").upper(),
            "serial": row["serial"] or None,
            "ip": row["ip"] or None,
            "resolution": None,
            "type": row["type_desc"] or None,
            "category": "camera",
            "subtype": (row["subtype"] or "").lower(),
            "lensType": None,
            "rango_lente_mm": None,
            "rango_fov_grados": None,
            "poe_watts": None,
            "bandwidth_mbps": None,
            "poe_budget_watts": None,
            "uplink_mbps": None,
        }
        for row in rows
    ]


def _get_site_other_devices_for_catalog(site_id: int) -> list[dict]:
    sql = """
        SELECT
            od.id          AS device_id,
            od.serial      AS serial,
            dt.model       AS name,
            dt.brand       AS brand,
            dt.device_type AS device_type,
            d.address      AS ip
        FROM other_devices od
        JOIN device_types  dt ON od.device_type_id  = dt.id
        JOIN installations i  ON od.installation_id = i.id
        LEFT JOIN devices  d  ON od.device_id       = d.id
        WHERE i.site_id = %s
          AND i.deleted_at IS NULL
          AND od.deleted_at IS NULL
        ORDER BY dt.device_type, dt.brand, dt.model, od.serial
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [int(site_id)])
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    result = []
    for row in rows:
        mapping = _OTHER_DEVICE_MAP.get(row["device_type"])
        if mapping is None:
            category = "device"
            subtype = (row["device_type"] or "unknown").lower().replace(" ", "_")
            id_prefix = "device"
        else:
            category, subtype, id_prefix = mapping

        result.append({
            "id": f"{id_prefix}-{row['device_id']}",
            "name": row["name"],
            "brand": (row["brand"] or "").title(),
            "serial": row["serial"] or None,
            "ip": row["ip"] or None,
            "resolution": None,
            "type": None,
            "category": category,
            "subtype": subtype,
            "lensType": None,
            "rango_lente_mm": None,
            "rango_fov_grados": None,
            "poe_watts": None,
            "bandwidth_mbps": None,
            "poe_budget_watts": None,
            "uplink_mbps": None,
        })
    return result


def get_site_status(site_id: int) -> list[dict]:
    sql = """
        SELECT i.id AS installation_id, t.name AS type_name, s.name AS status_name
        FROM installations i
        JOIN inst_statuses s ON i.inst_status_id = s.id
        JOIN installation_types t ON i.installation_type_id = t.id
        WHERE i.site_id = %s AND i.deleted_at IS NULL
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_site_inventory(site_id: int) -> list[dict]:
    sql = """
        SELECT 'camera' AS category, cb.Name AS brand, cm.name AS model, COUNT(c.id) AS qty
        FROM installations i
        JOIN cameras c ON i.id = c.installation_id
        JOIN camera_models cm ON c.camera_model_id = cm.id
        JOIN camera_brands cb ON cm.camera_brand_id = cb.id
        WHERE i.site_id = %s AND i.deleted_at IS NULL AND c.deleted_at IS NULL
        GROUP BY cb.Name, cm.name

        UNION ALL

        SELECT 'other' AS category, dt.brand, dt.model, COUNT(od.id) AS qty
        FROM installations i
        JOIN other_devices od ON i.id = od.installation_id
        JOIN device_types dt ON od.device_type_id = dt.id
        WHERE i.site_id = %s AND i.deleted_at IS NULL AND od.deleted_at IS NULL
        GROUP BY dt.brand, dt.model

        UNION ALL

        SELECT 'core_device' AS category, 'Generic' AS brand, d.name AS model, COUNT(d.id) AS qty
        FROM devices d
        WHERE d.site_id = %s AND d.deleted_at IS NULL
        GROUP BY d.name

        UNION ALL

        SELECT 'server' AS category, 'VMS' AS brand, s.vms_name AS model, COUNT(s.id) AS qty
        FROM servers s
        WHERE s.site_id = %s AND s.deleted_at IS NULL
        GROUP BY s.vms_name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id, site_id, site_id, site_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Installations / Projects
# ---------------------------------------------------------------------------

def get_installation_or_404(inst_id: int) -> Installation | None:
    return Installation.objects.using(_DB).filter(pk=inst_id, deleted_at__isnull=True).first()


def get_installation_design(inst_id: int) -> dict | None:
    """
    Returns visual_metadata if column exists; otherwise returns empty dict.
    visual_metadata may not be present in all schema versions.
    """
    try:
        with connections[_DB].cursor() as cur:
            cur.execute(
                "SELECT visual_metadata FROM installations WHERE id = %s",
                [inst_id],
            )
            row = cur.fetchone()
        if row is None:
            return None
        import json
        raw = row[0]
        try:
            return json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (TypeError, ValueError):
            return {}
    except Exception:
        return {}


def get_installation_inventory(inst_id: int) -> list[dict]:
    sql = """
        SELECT 'camera' AS category, cb.Name AS brand, cm.name AS model, COUNT(c.id) AS qty
        FROM cameras c
        JOIN camera_models cm ON c.camera_model_id = cm.id
        JOIN camera_brands cb ON cm.camera_brand_id = cb.id
        WHERE c.installation_id = %s AND c.deleted_at IS NULL
        GROUP BY cb.Name, cm.name

        UNION ALL

        SELECT 'other' AS category, dt.brand, dt.model, COUNT(od.id) AS qty
        FROM other_devices od
        JOIN device_types dt ON od.device_type_id = dt.id
        WHERE od.installation_id = %s AND od.deleted_at IS NULL
        GROUP BY dt.brand, dt.model
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [inst_id, inst_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def get_device_positions() -> list[dict]:
    """
    Parses visual_metadata JSON from all active installations to return
    a flat list of device positions (x, y, rotation), skipping layer_id=3.
    Returns empty list if visual_metadata column does not exist.
    """
    import json
    try:
        with connections[_DB].cursor() as cur:
            cur.execute(
                "SELECT visual_metadata FROM installations WHERE deleted_at IS NULL"
            )
            rows = cur.fetchall()
    except Exception:
        return []

    items: list[dict] = []
    for (raw,) in rows:
        try:
            meta = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if not isinstance(meta, dict):
                continue
            for node in meta.get("nodes", []):
                if node.get("layer_id") == 3:
                    continue
                pos = node.get("position", {})
                rot = node.get("rotation")
                items.append({
                    "id": str(node.get("id")),
                    "x": float(pos.get("x", 0.0)),
                    "y": float(pos.get("y", 0.0)),
                    "rotation": float(rot) if rot is not None else None,
                })
        except (TypeError, ValueError, AttributeError):
            continue
    return items


# ===========================================================================
# sig_projects (default DB — sig_dailylogs MySQL, managed by Django)
# ===========================================================================

def list_sig_projects() -> list[dict]:
    """Lists all SigProject rows ordered by updated_at DESC."""
    from apps.installations.models import SigProject
    qs = SigProject.objects.values("id", "name", "updated_at", "version", "data")
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "version": row["version"],
            "data": row["data"],
        }
        for row in qs
    ]


def get_sig_project(project_id: str) -> dict | None:
    """Returns a single SigProject by UUID string, or None."""
    from apps.installations.models import SigProject
    try:
        p = SigProject.objects.get(pk=project_id)
    except SigProject.DoesNotExist:
        return None
    return {
        "id": str(p.id),
        "name": p.name,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "version": p.version,
        "data": p.data,
    }


# ===========================================================================
# Admin — sigtools_beta MySQL (app_roles, permissions, role_permissions,
#          user_app_roles, users)
# ===========================================================================

_SIGTOOLS = "sigtools"


# ---------------------------------------------------------------------------
# Admin — Users (users + user_app_roles + app_roles)
# ---------------------------------------------------------------------------

def list_admin_users() -> list[dict]:
    """
    Returns users with their assigned app_roles.
    Tables: sigtools_beta.users, user_app_roles, app_roles
    """
    sql = """
        SELECT
            u.id,
            u.name,
            u.email,
            u.username,
            u.created_at,
            CASE WHEN u.deleted_at IS NULL THEN 1 ELSE 0 END AS is_active,
            COALESCE(
                JSON_ARRAYAGG(
                    IF(ar.id IS NOT NULL,
                        JSON_OBJECT(
                            'id',          ar.id,
                            'name',        ar.name,
                            'label',       ar.label,
                            'description', ar.description,
                            'color',       ar.color,
                            'is_system',   ar.is_system
                        ),
                        NULL
                    )
                ),
                JSON_ARRAY()
            ) AS roles
        FROM users u
        LEFT JOIN user_app_roles uar ON u.id = uar.user_id
        LEFT JOIN app_roles ar ON uar.role_id = ar.id
        WHERE u.deleted_at IS NULL
        GROUP BY u.id, u.name, u.email, u.username, u.created_at, u.deleted_at
        ORDER BY u.created_at DESC
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    import json
    for row in rows:
        if row.get("created_at") is not None:
            row["created_at"] = row["created_at"].isoformat()
        # MySQL JSON_ARRAYAGG returns a string — parse it
        if isinstance(row.get("roles"), str):
            row["roles"] = json.loads(row["roles"])
        # Filter out nulls that MySQL JSON_ARRAYAGG may include
        if isinstance(row.get("roles"), list):
            row["roles"] = [r for r in row["roles"] if r is not None]
    return rows


# ---------------------------------------------------------------------------
# Admin — Roles (app_roles + role_permissions + permissions + user_count)
# ---------------------------------------------------------------------------

def list_admin_roles() -> list[dict]:
    """
    Returns app_roles with their permissions and user count.
    Tables: sigtools_beta.app_roles, role_permissions, permissions, user_app_roles
    """
    sql = """
        SELECT
            ar.id,
            ar.name,
            ar.label,
            ar.description,
            ar.color,
            ar.is_system,
            ar.created_at,
            COUNT(DISTINCT uar.user_id) AS user_count,
            COALESCE(
                JSON_ARRAYAGG(
                    IF(p.id IS NOT NULL,
                        JSON_OBJECT(
                            'id',          p.id,
                            'key',         p.`key`,
                            'label',       p.label,
                            'description', p.description,
                            'app',         p.app,
                            'category',    p.category
                        ),
                        NULL
                    )
                ),
                JSON_ARRAY()
            ) AS permissions
        FROM app_roles ar
        LEFT JOIN role_permissions rp  ON ar.id = rp.role_id
        LEFT JOIN permissions p        ON rp.permission_id = p.id
        LEFT JOIN user_app_roles uar   ON ar.id = uar.role_id
        GROUP BY ar.id, ar.name, ar.label, ar.description, ar.color, ar.is_system, ar.created_at
        ORDER BY ar.created_at ASC
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    import json
    for row in rows:
        if row.get("created_at") is not None:
            row["created_at"] = row["created_at"].isoformat()
        if isinstance(row.get("permissions"), str):
            row["permissions"] = json.loads(row["permissions"])
        if isinstance(row.get("permissions"), list):
            row["permissions"] = [p for p in row["permissions"] if p is not None]
        row["user_count"] = int(row["user_count"])
    return rows


# ---------------------------------------------------------------------------
# Admin — Permissions
# ---------------------------------------------------------------------------

def list_admin_permissions() -> list[dict]:
    """Returns all permissions ordered by app, category, label."""
    sql = """
        SELECT id, `key`, label, description, app, category
        FROM permissions
        ORDER BY app, category, label
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_admin_user(user_id: int) -> dict | None:
    """Returns a single user (with roles) from sigtools_beta, or None."""
    import json as _json

    sql = """
        SELECT
            u.id,
            u.name,
            u.email,
            u.username,
            u.created_at,
            CASE WHEN u.deleted_at IS NULL THEN 1 ELSE 0 END AS is_active,
            COALESCE(
                JSON_ARRAYAGG(
                    IF(ar.id IS NOT NULL,
                        JSON_OBJECT(
                            'id',          ar.id,
                            'name',        ar.name,
                            'label',       ar.label,
                            'description', ar.description,
                            'color',       ar.color,
                            'is_system',   ar.is_system
                        ),
                        NULL
                    )
                ),
                JSON_ARRAY()
            ) AS roles
        FROM users u
        LEFT JOIN user_app_roles uar ON u.id = uar.user_id
        LEFT JOIN app_roles ar ON uar.role_id = ar.id
        WHERE u.id = %s
        GROUP BY u.id, u.name, u.email, u.username, u.created_at, u.deleted_at
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql, [user_id])
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
    if row is None:
        return None
    d = dict(zip(cols, row))
    if d.get("created_at") is not None:
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("roles"), str):
        d["roles"] = _json.loads(d["roles"])
    if isinstance(d.get("roles"), list):
        d["roles"] = [r for r in d["roles"] if r is not None]
    return d


def fetch_admin_role(role_id: str) -> dict | None:
    """Returns a single role (with permissions + user_count) from sigtools_beta, or None."""
    import json as _json

    sql = """
        SELECT
            ar.id,
            ar.name,
            ar.label,
            ar.description,
            ar.color,
            ar.is_system,
            ar.created_at,
            COUNT(DISTINCT uar.user_id) AS user_count,
            COALESCE(
                JSON_ARRAYAGG(
                    IF(p.id IS NOT NULL,
                        JSON_OBJECT(
                            'id',          p.id,
                            'key',         p.`key`,
                            'label',       p.label,
                            'description', p.description,
                            'app',         p.app,
                            'category',    p.category
                        ),
                        NULL
                    )
                ),
                JSON_ARRAY()
            ) AS permissions
        FROM app_roles ar
        LEFT JOIN role_permissions rp  ON ar.id = rp.role_id
        LEFT JOIN permissions p        ON rp.permission_id = p.id
        LEFT JOIN user_app_roles uar   ON ar.id = uar.role_id
        WHERE ar.id = %s
        GROUP BY ar.id, ar.name, ar.label, ar.description, ar.color, ar.is_system, ar.created_at
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql, [role_id])
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
    if row is None:
        return None
    d = dict(zip(cols, row))
    if d.get("created_at") is not None:
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("permissions"), str):
        d["permissions"] = _json.loads(d["permissions"])
    if isinstance(d.get("permissions"), list):
        d["permissions"] = [p for p in d["permissions"] if p is not None]
    d["user_count"] = int(d["user_count"])
    return d
