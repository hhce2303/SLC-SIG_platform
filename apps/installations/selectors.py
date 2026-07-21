"""
Selectors — read-only queries against sigtools_beta.
All DB access is routed via 'sigtools' alias by SigtoolsRouter.
Complex joins use raw SQL; simple lookups use the ORM.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from django.db import connections

from apps.core import cache_utils as cu
from apps.installations.catalog_enrichment import enrich_catalog_item, enrich_camera_item, enrich_network_item
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

logger = logging.getLogger(__name__)

_DB = "sigtools"


def _parse_json_range(value: Any) -> list[float] | None:
    """
    camera_models.rango_lente_mm / rango_fov_grados are JSON columns holding
    [min, max]. Raw cursors return JSON columns as text, not as parsed Python
    objects — normalize both cases here. None/empty stays None so
    enrich_camera_item falls back to the DEFAULT_CAM_SPECS default.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def get_camera_catalog() -> list[dict]:
    """
    Hierarchical camera catalog: Type → Brand → [Model].
    Uses raw SQL for the three-table join; returns a nested Python structure.
    """
    return cu.cached("inst:catalog:camera_catalog", _compute_camera_catalog, cu.TTL_CATALOG)


def _compute_camera_catalog() -> list[dict]:
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
    def _compute():
        rows = list(
            DeviceType.objects.using(_DB)
            .order_by("device_type", "brand", "model")
            .values("id", "device_type", "brand", "model")
        )
        return [
            enrich_network_item({
                "id": f"dev-{row['id']}",
                "name": row.get("model") or row.get("device_type") or "",
                "brand": row.get("brand") or "",
                "subtype": (row.get("device_type") or "").lower(),
                "category": "static",
                "isExistingInventory": False,
            })
            for row in rows
        ]
    return cu.cached("inst:catalog:device_types:v2", _compute, cu.TTL_CATALOG)


def get_vms_catalog() -> list[str]:
    def _compute():
        return list(
            Server.objects.using(_DB)
            .filter(deleted_at__isnull=True)
            .exclude(vms_name__isnull=True)
            .exclude(vms_name="")
            .order_by("vms_name")
            .values_list("vms_name", flat=True)
            .distinct()
        )
    return cu.cached("inst:catalog:vms", _compute, cu.TTL_CATALOG)


def get_installation_types() -> list[dict]:
    def _compute():
        return list(
            InstallationType.objects.using(_DB)
            .order_by("name")
            .values("id", "name")
        )
    return cu.cached("inst:catalog:installation_types", _compute, cu.TTL_CATALOG)


def get_customer_groups() -> list[dict]:
    def _compute():
        return list(
            CustomerGroup.objects.using(_DB)
            .order_by("name")
            .values("id", "name")
        )
    return cu.cached("inst:catalog:customer_groups", _compute, cu.TTL_CATALOG)


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
# Project Sites (staging — pre-verification)
# ---------------------------------------------------------------------------

def list_project_sites() -> list[dict]:
    """
    Returns all non-deleted project_sites (staging) ordered by created_at DESC,
    enriched with installation info (lead tech, project owner, type, dates).
    Cacheado (TTL corto) — el SSE empuja cambios en vivo y las escrituras invalidan.
    """
    return cu.cached("inst:project_sites", _compute_project_sites, cu.TTL_DASHBOARD)


def _compute_project_sites() -> list[dict]:
    sql = """
        SELECT
            ps.id,
            ps.name,
            ps.city,
            ps.state_code,
            ps.country_code,
            ps.verification_status,
            ps.created_by,
            u_created.name    AS created_by_name,
            ps.approval_requested_by,
            u_req.name        AS approval_requested_by_name,
            ps.rejection_reason,
            ps.created_at,
            ps.updated_at,
            i.id              AS installation_id,
            i.it_lead_tech_id,
            u_tech.name       AS it_lead_tech_name,
            i.project_owner,
            u_own.name        AS project_owner_name,
            it.name           AS installation_type,
            i.Total_cameras   AS total_cameras,
            i.starting_date,
            i.limit_date
        FROM project_sites ps
        LEFT JOIN (
            SELECT site_id, MAX(id) AS latest_id
            FROM installations WHERE deleted_at IS NULL GROUP BY site_id
        ) li ON li.site_id = ps.id
        LEFT JOIN installations i        ON i.id = li.latest_id
        LEFT JOIN users u_tech           ON u_tech.id = i.it_lead_tech_id
        LEFT JOIN users u_own            ON u_own.id  = i.project_owner
        LEFT JOIN users u_created        ON u_created.id = ps.created_by
        LEFT JOIN users u_req            ON u_req.id     = ps.approval_requested_by
        LEFT JOIN installation_types it  ON it.id     = i.installation_type_id
        WHERE ps.deleted_at IS NULL
        ORDER BY ps.created_at DESC
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_project_site_info(site_id: int) -> dict | None:
    """
    Returns full project_site info including extended fields.
    Looks up by project_sites.id first, then by project_sites.site_id
    (covers legacy sites already promoted to the sites table).
    """
    sql = """
        SELECT
            ps.id,
            ps.name,
            ps.city,
            ps.state_code,
            ps.country_code,
            ps.address,
            ps.ip_address,
            ps.lat,
            ps.long             AS lng,
            ps.verification_status,
            ps.created_by,
            u_created.name      AS created_by_name,
            ps.approval_requested_by,
            u_req.name          AS approval_requested_by_name,
            ps.rejection_reason,
            ps.verified_by,
            ps.verified_at,
            ps.authorized_by,
            ps.authorized_at,
            ps.contract_value,
            ps.hotel,
            ps.flight_details,
            ps.teams_channelid,
            ps.teams_teamid,
            ps.created_at,
            ps.updated_at,
            i.id              AS installation_id,
            i.it_lead_tech_id,
            u_tech.name       AS it_lead_tech_name,
            i.project_owner,
            u_own.name        AS project_owner_name,
            it.name           AS installation_type,
            i.Total_cameras   AS total_cameras,
            i.starting_date,
            i.limit_date
        FROM project_sites ps
        LEFT JOIN (
            SELECT site_id, MAX(id) AS latest_id
            FROM installations WHERE deleted_at IS NULL GROUP BY site_id
        ) li ON li.site_id = ps.id
        LEFT JOIN installations i        ON i.id = li.latest_id
        LEFT JOIN users u_tech           ON u_tech.id = i.it_lead_tech_id
        LEFT JOIN users u_own            ON u_own.id  = i.project_owner
        LEFT JOIN users u_created        ON u_created.id = ps.created_by
        LEFT JOIN users u_req            ON u_req.id     = ps.approval_requested_by
        LEFT JOIN installation_types it  ON it.id     = i.installation_type_id
        WHERE (ps.id = %s OR ps.site_id = %s) AND ps.deleted_at IS NULL
        ORDER BY ps.id DESC
        LIMIT 1
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id, site_id])
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        if not row:
            return None
        result = dict(zip(cols, row))
    # Merge overlay fields from default DB (SiteProjectInfo)
    overlay = get_site_project_info_overlay(site_id)
    result["check_in"] = overlay.check_in if overlay else None
    result["check_out"] = overlay.check_out if overlay else None
    result["paylocity_code"] = overlay.paylocity_code if overlay else None
    result["extra_notes"] = overlay.extra_notes if overlay else None
    return result


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

    Cacheado (TTL corto) — el SSE empuja cambios en vivo y las escrituras invalidan.
    """
    return cu.cached("inst:sites_dashboard", _compute_sites_dashboard, cu.TTL_DASHBOARD)


def _compute_sites_dashboard() -> list[dict]:
    main_sql = """
        SELECT
            s.id,
            s.name,
            s.address,
            s.city,
            s.state_code,
            s.customer_group_id,
            ist.name            AS status,
            ss.status_name      AS site_status,
            u.name              AS responsable,
            it_u.name           AS it_manager,
            i.id                AS installation_id,
            i.Total_cameras     AS total_cameras,
            i.Total_views       AS total_views,
            i.starting_date,
            i.limit_date
        FROM sites s
        LEFT JOIN site_statuses ss  ON ss.id            = s.site_status_id
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
    site_ids_list = [r["id"] for r in rows]

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
                    "type": "note",
                })

    # Device activity logs per site (SiteDeviceLog — default DB)
    activity_by_site: dict[int, list[dict]] = defaultdict(list)
    if site_ids_list:
        from apps.installations.models import SiteDeviceLog
        logs = (
            SiteDeviceLog.objects
            .filter(site_id__in=site_ids_list)
            .order_by("created_at")
            .values("site_id", "device_id", "action", "created_at", "user_id", "notes")
        )
        for lg in logs:
            ts = lg["created_at"]
            activity_by_site[lg["site_id"]].append({
                "date":   ts.isoformat() if ts else None,
                "action": lg["action"],
                "device": lg["device_id"],
                "user":   lg["user_id"],
                "notes":  lg["notes"] or None,
                "type":   "activity",
            })

    result = []
    for row in rows:
        inst_id = row["installation_id"]
        site_id = row["id"]
        note_entries    = notes_by_inst.get(inst_id, [])
        activity_entries = activity_by_site.get(site_id, [])
        # Merge and sort by date oldest→newest
        log_entries = sorted(
            note_entries + activity_entries,
            key=lambda e: e["date"] or "",
        )
        location = ", ".join(filter(None, [row.get("city"), row.get("state_code")])) or None
        latest_note = note_entries[-1]["action"] if note_entries else None
        site_status_str = row.get("site_status") or ""
        if site_status_str:
            is_operational = site_status_str.lower() in ("live", "live testing")
        else:
            # Fallback heuristic when site_status_id is not set
            s = (row["status"] or "").lower()
            is_operational = any(kw in s for kw in ("finalizad", "complet", "done", "finish", "closed", "activ", "live"))

        logs_categorized = {
            "installation": [e for e in log_entries if "install" in (e.get("action") or "").lower()],
            "inventory":    [e for e in log_entries if "install" not in (e.get("action") or "").lower()],
        }
        result.append({
            "id": row["id"],
            "name": row["name"],
            "status": row["status"] or None,
            "site_status": row.get("site_status") or None,
            "is_operational": is_operational,
            "address": row["address"] or None,
            "location": location,
            "responsable": row["responsable"] or None,
            "it_manager": row["it_manager"] or None,
            "notes": latest_note,
            "log": log_entries,
            "log_count": len(log_entries),
            "logs_categorized": logs_categorized,
            "customer_group_id": row["customer_group_id"],
            "total_cameras": row.get("total_cameras"),
            "total_views": row.get("total_views"),
            "starting_date": row.get("starting_date"),
            "limit_date": row.get("limit_date"),
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


def get_site_detail(site_id: int) -> dict | None:
    """
    Editable core fields for a single site (sigtools_beta.sites).
    Returns None when the site does not exist or is soft-deleted.
    Shape matches SiteDetailSerializer.
    """
    site = get_site_or_404(site_id)
    if site is None:
        return None
    # Site lifecycle status (site_statuses: Created/Installing/Live Testing/Live/
    # Staging) via sites.site_status_id. Exposed as `status` so the Project Info
    # editor can read and write it. This is the SITE lifecycle, distinct from the
    # installation work status (inst_statuses) shown elsewhere.
    site_status_id = None
    site_status = None
    with connections[_DB].cursor() as cur:
        cur.execute(
            "SELECT s.site_status_id, ss.status_name "
            "FROM sites s LEFT JOIN site_statuses ss ON ss.id = s.site_status_id "
            "WHERE s.id = %s",
            [site_id],
        )
        row = cur.fetchone()
        if row:
            site_status_id, site_status = row[0], row[1]

    # Personnel from the latest installation of this site. The Project Info editor
    # reads project_owner / it_lead_tech_id from the site detail; they actually
    # live on the installation, so surface them here (with resolved names).
    project_owner = it_lead_tech_id = None
    project_owner_name = it_lead_tech_name = None
    with connections[_DB].cursor() as cur:
        cur.execute(
            """
            SELECT i.project_owner, uo.name, i.it_lead_tech_id, ut.name
            FROM installations i
            LEFT JOIN users uo ON uo.id = i.project_owner
            LEFT JOIN users ut ON ut.id = i.it_lead_tech_id
            WHERE i.site_id = %s AND i.deleted_at IS NULL
            ORDER BY i.id DESC LIMIT 1
            """,
            [site_id],
        )
        row = cur.fetchone()
        if row:
            project_owner, project_owner_name, it_lead_tech_id, it_lead_tech_name = row
    return {
        "id":                    site.id,
        "name":                  site.name,
        "ip_address":            site.ip_address,
        "city":                  site.city,
        "state_code":            site.state_code,
        "country_code":          site.country_code,
        "address":               site.address,
        "timezone":              site.timezone,
        "monitored":             site.monitored,
        "maintenance":           site.maintenance,
        "receive_notifications": site.receive_notifications,
        "installation_date":     site.installation_date,
        "updated_at":            site.updated_at,
        "status":                site_status,
        "site_status":           site_status,
        "site_status_id":        site_status_id,
        "project_owner":         project_owner,
        "project_owner_name":    project_owner_name,
        "it_lead_tech_id":       it_lead_tech_id,
        "it_lead_tech_name":     it_lead_tech_name,
    }


def get_camera_model_catalog() -> list[dict]:
    """
    Flat list of every camera model registered in the company catalog.
    NOT tied to any site or physical unit — used when building a new
    installation and selecting which models to assign.

    Shape is identical to get_site_camera_models so the frontend can
    reuse the same TypeScript interface. serial and ip are always None
    because these are model definitions, not physical units.
    """
    return cu.cached("inst:catalog:camera_model_catalog:v3", _compute_camera_model_catalog, cu.TTL_CATALOG)


def _compute_camera_model_catalog() -> list[dict]:
    sql = """
        SELECT
            cm.id               AS model_id,
            cm.name             AS name,
            cb.Name             AS brand,
            ct.name             AS subtype,
            ct.description      AS type_desc,
            cm.rango_lente_mm   AS rango_lente_mm,
            cm.rango_fov_grados AS rango_fov_grados,
            cm.lens_type        AS lens_type,
            cm.poe_watts        AS poe_watts,
            cm.bandwidth_mbps   AS bandwidth_mbps
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
        enrich_camera_item({
            "id": f"cam-{row['model_id']}",
            "name": row["name"],
            "brand": row["brand"] or "",
            "serial": None,
            "ip": None,
            "resolution": None,
            "type": row["type_desc"],
            "category": "camera",
            "subtype": (row["subtype"] or "").lower(),
            "isExistingInventory": False,
            "rango_lente_mm": _parse_json_range(row["rango_lente_mm"]),
            "rango_fov_grados": _parse_json_range(row["rango_fov_grados"]),
            "lens_type": row["lens_type"],
            "poe_watts": row["poe_watts"],
            "bandwidth_mbps": row["bandwidth_mbps"],
        })
        for row in rows
    ]


def get_site_camera_models(site_id: int) -> list[dict]:
    """
    Returns one entry per individual camera installed at a given site.
    Each camera is identified by its own DB id and serial number.
    Lens/FOV/PoE/bandwidth come from camera_models' factory spec columns
    (see docs/db/camera_models_schema.md); null until populated for that
    model, in which case enrich_camera_item falls back to DEFAULT_CAM_SPECS.
    """
    return cu.cached(
        f"inst:catalog:site_camera_models:{int(site_id)}",
        lambda: _compute_site_camera_models(site_id),
        cu.TTL_CATALOG,
    )


def _compute_site_camera_models(site_id: int) -> list[dict]:
    sql = """
        SELECT
            c.id                AS camera_id,
            c.serial            AS serial,
            cm.name             AS name,
            cb.Name             AS brand,
            ct.name             AS subtype,
            ct.description      AS type_desc,
            d.address           AS ip,
            cm.rango_lente_mm   AS rango_lente_mm,
            cm.rango_fov_grados AS rango_fov_grados,
            cm.lens_type        AS lens_type,
            cm.poe_watts        AS poe_watts,
            cm.bandwidth_mbps   AS bandwidth_mbps
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
        enrich_camera_item({
            "id": f"cam-{row['camera_id']}",
            "name": row["name"],
            "brand": (row["brand"] or "").upper(),
            "serial": row["serial"],
            "ip": row["ip"] or None,
            "resolution": None,
            "type": row["type_desc"],
            "category": "camera",
            "subtype": (row["subtype"] or "").lower(),
            "lensType": row["lens_type"],
            "rango_lente_mm": _parse_json_range(row["rango_lente_mm"]),
            "rango_fov_grados": _parse_json_range(row["rango_fov_grados"]),
            "poe_watts": row["poe_watts"],
            "bandwidth_mbps": row["bandwidth_mbps"],
            "isExistingInventory": True,
        })
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


def get_site_bom(site_id: int) -> dict:
    """
    Bill of Materials for a site — device counts grouped by catalog entry,
    computed with SQL GROUP BY (cameras + other_devices). Returns the
    aggregated rows so the frontend never iterates per-unit records in memory
    to build the hardware table.
    """
    items: list[dict] = []
    total_cameras = 0
    total_other = 0

    with connections[_DB].cursor() as cur:
        # Cameras grouped by model / brand / type
        cur.execute(
            """
            SELECT cm.name AS name, cb.Name AS brand, ct.name AS subtype, COUNT(*) AS qty
            FROM cameras c
            JOIN camera_models cm ON c.camera_model_id = cm.id
            JOIN camera_brands  cb ON cm.camera_brand_id = cb.id
            JOIN camera_types   ct ON cm.camera_type_id  = ct.id
            JOIN installations  i  ON c.installation_id   = i.id
            WHERE i.site_id = %s AND i.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY cm.name, cb.Name, ct.name
            ORDER BY qty DESC, ct.name, cb.Name, cm.name
            """,
            [int(site_id)],
        )
        for name, brand, subtype, qty in cur.fetchall():
            total_cameras += qty
            items.append({
                "category": "camera",
                "subtype": (subtype or "").lower(),
                "brand": (brand or "").upper(),
                "name": name,
                "qty": qty,
                "is_camera": True,
            })

        # Other devices grouped by device_type / brand / model
        cur.execute(
            """
            SELECT dt.model AS name, dt.brand AS brand, dt.device_type AS device_type, COUNT(*) AS qty
            FROM other_devices od
            JOIN device_types dt ON od.device_type_id = dt.id
            JOIN installations i  ON od.installation_id = i.id
            WHERE i.site_id = %s AND i.deleted_at IS NULL AND od.deleted_at IS NULL
            GROUP BY dt.model, dt.brand, dt.device_type
            ORDER BY qty DESC, dt.device_type, dt.brand, dt.model
            """,
            [int(site_id)],
        )
        for name, brand, device_type, qty in cur.fetchall():
            mapping = _OTHER_DEVICE_MAP.get(device_type)
            category = mapping[0] if mapping else "device"
            subtype = mapping[1] if mapping else (device_type or "unknown").lower().replace(" ", "_")
            total_other += qty
            items.append({
                "category": category,
                "subtype": subtype,
                "brand": (brand or "").upper(),
                "name": name,
                "qty": qty,
                "is_camera": False,
            })

    return {
        "site_id": site_id,
        "total_cameras": total_cameras,
        "total_other_devices": total_other,
        "total_devices": total_cameras + total_other,
        "items": items,
    }


def get_bom_preview(devices: list[dict]) -> dict:
    """
    Pure BOM aggregation — port of helpers/report.ts generateBOMReport +
    OnboardingModal.tsx computeCamerasAndViews.
    Input devices: [{instanceId, numero, area, category, subtype, lensType, ...}]
    Returns:
      coverage_by_area: [{area, rows: [{area, device_type, numero, instance_id}]}]
      summary:          [{device_type, qty, is_camera}]  (cameras first, then alpha)
      total_cameras, total_views, total_devices
    """
    from apps.installations.catalog_enrichment import build_device_type_label, compute_cameras_and_views

    sorted_devices = sorted(devices, key=lambda d: d.get("numero") or 0)

    coverage_map: dict[str, list[dict]] = {}
    type_count: dict[str, dict] = {}

    for dev in sorted_devices:
        area = (dev.get("area") or "Unassigned").strip() or "Unassigned"
        device_type = build_device_type_label(dev)
        is_camera = (dev.get("category") or "").lower() == "camera"

        coverage_map.setdefault(area, []).append({
            "area": area,
            "device_type": device_type,
            "numero": dev.get("numero"),
            "instance_id": dev.get("instanceId"),
        })

        if device_type not in type_count:
            type_count[device_type] = {"qty": 0, "is_camera": is_camera}
        type_count[device_type]["qty"] += 1

    # Sort areas: alphabetical, "Unassigned" last
    sorted_areas = sorted(
        coverage_map.items(),
        key=lambda kv: ("\xff" if kv[0] == "Unassigned" else kv[0].lower()),
    )

    summary = sorted(
        [{"device_type": k, "qty": v["qty"], "is_camera": v["is_camera"]} for k, v in type_count.items()],
        key=lambda r: (0 if r["is_camera"] else 1, r["device_type"]),
    )

    cv = compute_cameras_and_views(devices)

    return {
        "coverage_by_area": [{"area": area, "rows": rows} for area, rows in sorted_areas],
        "summary": summary,
        "total_cameras": cv["cameras"],
        "total_views": cv["views"],
        "total_devices": len(devices),
    }


def get_site_device_catalog(site_id: int) -> list[dict]:
    """
    Unified device catalog for a site.

    Returns all cameras (one entry per physical unit) and all other devices
    (one entry per physical unit from other_devices) in a single flat list
    with a consistent shape, fully enriched (lens specs, PoE, dispatch overlay).

    Order: cameras first (sorted by subtype/brand/name), then other devices
    sorted by device_type/brand/model.
    """
    catalog = _get_site_cameras_for_catalog(site_id) + _get_site_other_devices_for_catalog(site_id)
    catalog = _enrich_catalog_serials(catalog)

    # Merge dispatch overlay (physical status, qty_received, installed, etc.)
    dispatch_map = {d.device_id: d for d in get_site_dispatch_all(site_id)}
    for item in catalog:
        d = dispatch_map.get(item["id"])
        item["vendor"]            = d.vendor if d else None
        item["quantity_send"]     = d.qty_sent if d else None
        item["tracking"]          = d.tracking if d else None
        item["observations"]      = d.observations if d else None
        item["dispatched_at"]     = d.dispatched_at.isoformat() if d and d.dispatched_at else None
        item["qty_received"]      = d.qty_received if d else None
        item["received_at"]       = d.received_at.isoformat() if d and d.received_at else None
        item["receipt_photo_url"] = d.receipt_photo_url if d else None
        item["installed"]         = d.installed if d else False
        item["installed_at"]      = d.installed_at.isoformat() if d and d.installed_at else None
        item["install_photo_url"] = d.install_photo_url if d else None
        item["physical_status"]   = (
            "installed" if (d and d.installed)
            else "received" if (d and d.received_at)
            else "none"
        )

    # Apply enricher: populates lensType/ranges/poe_watts from subtype defaults
    return [enrich_catalog_item(item) for item in catalog]


def _enrich_catalog_serials(catalog: list[dict]) -> list[dict]:
    """
    For any catalog item where serial is None, look up inv_articles.device_id
    (an indexed column) to find a matching article and copy its serial over.

    Uses WHERE device_id IN (...) — fully indexed, no full scan.
    """
    needs_serial = [item for item in catalog if not item.get("serial")]
    if not needs_serial:
        return catalog

    device_ids = [item["id"] for item in needs_serial]
    placeholders = ",".join(["%s"] * len(device_ids))
    with connections["default"].cursor() as cur:
        cur.execute(
            f"SELECT device_id, serial FROM inv_articles "
            f"WHERE device_id IN ({placeholders}) AND serial != '' AND device_id != ''",
            device_ids,
        )
        device_serial_map = {row[0]: row[1] for row in cur.fetchall()}

    if not device_serial_map:
        return catalog

    for item in needs_serial:
        found = device_serial_map.get(item["id"])
        if found:
            item["serial"] = found

    return catalog


def _get_site_cameras_for_catalog(site_id: int) -> list[dict]:
    sql = """
        SELECT
            c.id                AS camera_id,
            c.serial            AS serial,
            cm.name             AS name,
            cb.Name             AS brand,
            ct.name             AS subtype,
            ct.description      AS type_desc,
            d.address           AS ip,
            v.View_name         AS view_name,
            cm.rango_lente_mm   AS rango_lente_mm,
            cm.rango_fov_grados AS rango_fov_grados,
            cm.lens_type        AS lens_type,
            cm.poe_watts        AS poe_watts,
            cm.bandwidth_mbps   AS bandwidth_mbps
        FROM cameras c
        JOIN camera_models cm  ON c.camera_model_id = cm.id
        JOIN camera_brands cb  ON cm.camera_brand_id = cb.id
        JOIN camera_types  ct  ON cm.camera_type_id  = ct.id
        JOIN installations i   ON c.installation_id  = i.id
        LEFT JOIN devices  d   ON c.device_id        = d.id
        LEFT JOIN views    v   ON v.camera_id = c.id AND v.deleted_at IS NULL
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
            "lensType": row["lens_type"],
            "rango_lente_mm": _parse_json_range(row["rango_lente_mm"]),
            "rango_fov_grados": _parse_json_range(row["rango_fov_grados"]),
            "poe_watts": row["poe_watts"],
            "bandwidth_mbps": row["bandwidth_mbps"],
            "poe_budget_watts": None,
            "uplink_mbps": None,
            "view_name": row["view_name"] or None,
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
            "view_name": None,
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
        except (TypeError, ValueError) as exc:
            logger.warning("get_installation_design: visual_metadata JSON inválido para inst=%s: %s", inst_id, exc)
            return {}
    except Exception as exc:
        logger.warning("get_installation_design falló para inst=%s: %s", inst_id, exc)
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
    except Exception as exc:
        logger.warning("get_device_positions: query a installations falló: %s", exc)
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
    rows = list(
        SigProject.objects.values(
            "id",
            "name",
            "updated_at",
            "version",
            "data",
            "created_by",
            "approval_status",
            "approval_requested_by",
        )
    )
    user_ids = {
        uid
        for row in rows
        for uid in (row.get("created_by"), row.get("approval_requested_by"))
        if uid is not None
    }
    user_names = _sigtools_user_names_by_ids(user_ids)
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "version": row["version"],
            "created_by": row.get("created_by"),
            "created_by_name": user_names.get(row.get("created_by")),
            "approval_status": row.get("approval_status") or "draft",
            "approval_requested_by": row.get("approval_requested_by"),
            "approval_requested_by_name": user_names.get(row.get("approval_requested_by")),
            "data": row["data"],
        }
        for row in rows
    ]


def get_sig_project(project_id: str) -> dict | None:
    """Returns a single SigProject by UUID string, or None."""
    from apps.installations.models import SigProject
    try:
        p = SigProject.objects.get(pk=project_id)
    except SigProject.DoesNotExist:
        return None

    data = p.data or {}
    # Self-heal: if the live layout is empty (e.g. a previous blanking save) but the
    # protected `design` snapshot still holds a layout, restore the design fields
    # from it. Only the design itself is recovered — current metadata (sitios,
    # type, linked_installation_id) is left as-is. The next save persists the
    # recovered layout back into `data`, so the project heals on open.
    if not (data.get("devices") or data.get("drawings") or data.get("floorPlans")):
        try:
            with connections["default"].cursor() as cur:
                cur.execute("SELECT design FROM sig_projects WHERE id = %s", [str(project_id)])
                row = cur.fetchone()
            if row and row[0]:
                saved = json.loads(row[0])
                if isinstance(saved, dict) and (
                    saved.get("devices") or saved.get("drawings") or saved.get("floorPlans")
                ):
                    for key in ("devices", "drawings", "floorPlans", "enlaces"):
                        if saved.get(key):
                            data[key] = saved[key]
        except Exception:
            logging.getLogger(__name__).warning(
                "design recovery failed for project %s", project_id, exc_info=True
            )

    return {
        "id": str(p.id),
        "name": p.name,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "version": p.version,
        "created_by": p.created_by,
        "created_by_name": _sigtools_user_name_by_id(p.created_by),
        "approval_status": p.approval_status,
        "approval_requested_by": p.approval_requested_by,
        "approval_requested_by_name": _sigtools_user_name_by_id(p.approval_requested_by),
        "data": data,
    }


def _sigtools_user_names_by_ids(user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    placeholders = ",".join(["%s"] * len(user_ids))
    sql = f"SELECT id, name FROM users WHERE id IN ({placeholders})"  # noqa: S608
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql, list(user_ids))
        return {row[0]: row[1] for row in cur.fetchall()}


def _sigtools_user_name_by_id(user_id: int | None) -> str | None:
    if not user_id:
        return None
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute("SELECT name FROM users WHERE id = %s LIMIT 1", [user_id])
        row = cur.fetchone()
        return row[0] if row else None


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


def fetch_admin_role(role_id: int) -> dict | None:
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


# ---------------------------------------------------------------------------
# Dispatch / Receipt / Installation selectors (sig_dailylogs — default DB)
# ---------------------------------------------------------------------------

from django.db.models import QuerySet  # noqa: E402

from apps.installations.models import SiteDeviceDispatch, SiteDeviceLog  # noqa: E402


def get_device_dispatch(site_id: int, device_id: str) -> SiteDeviceDispatch | None:
    try:
        return SiteDeviceDispatch.objects.get(site_id=site_id, device_id=device_id)
    except SiteDeviceDispatch.DoesNotExist:
        return None


def get_site_dispatch_all(site_id: int) -> QuerySet[SiteDeviceDispatch]:
    return SiteDeviceDispatch.objects.filter(site_id=site_id)


def get_device_logs(site_id: int, device_id: str) -> QuerySet[SiteDeviceLog]:
    return SiteDeviceLog.objects.filter(site_id=site_id, device_id=device_id)


def get_site_progress(site_id: int, total_devices: int) -> dict:
    qs = SiteDeviceDispatch.objects.filter(site_id=site_id)
    dispatched = qs.filter(qty_sent__gt=0).count()
    received   = qs.filter(qty_received__gt=0).count()
    installed  = qs.filter(installed=True).count()
    denom = total_devices or 1
    return {
        "total":         total_devices,
        "dispatched":    dispatched,
        "received":      received,
        "installed":     installed,
        "pct_dispatched": round(dispatched / denom * 100, 1),
        "pct_received":   round(received   / denom * 100, 1),
        "pct_installed":  round(installed  / denom * 100, 1),
    }


def get_all_sites_dispatch_progress(site_ids: list[int] | None = None) -> list[dict]:
    """
    Batch dispatch progress for ALL active sites (or a filtered subset).

    - total_cameras / total_devices: real counts from cameras + other_devices tables
      (latest active installation per site), NOT the dispatch table count.
    - dispatched / received / installed: from SiteDeviceDispatch overlay.
    - pct_* denominators use total_devices so they reflect real inventory.

    El caso global (site_ids=None) se cachea con TTL corto; el filtrado no.
    """
    if site_ids is None:
        return cu.cached(
            "inst:dispatch_progress",
            lambda: _compute_all_sites_dispatch_progress(None),
            cu.TTL_DASHBOARD,
        )
    return _compute_all_sites_dispatch_progress(site_ids)


def _compute_all_sites_dispatch_progress(site_ids: list[int] | None = None) -> list[dict]:
    from django.db.models import Count, Q

    # 1. All active sites
    if site_ids:
        placeholders = ",".join(["%s"] * len(site_ids))
        site_sql = f"SELECT id, name FROM sites WHERE id IN ({placeholders}) AND deleted_at IS NULL"
        params = site_ids
    else:
        site_sql = "SELECT id, name FROM sites WHERE deleted_at IS NULL ORDER BY name"
        params = []

    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(site_sql, params)
        all_sites = {r[0]: r[1] for r in cur.fetchall()}

    if not all_sites:
        return []

    id_list = list(all_sites.keys())
    ph = ",".join(["%s"] * len(id_list))

    # 2. Real device counts per site — cameras + other_devices via latest installation
    device_count_sql = f"""
        SELECT
            i.site_id,
            COUNT(DISTINCT c.id)  AS camera_count,
            COUNT(DISTINCT od.id) AS other_count
        FROM (
            SELECT site_id, MAX(id) AS latest_id
            FROM installations
            WHERE site_id IN ({ph}) AND deleted_at IS NULL
            GROUP BY site_id
        ) li
        JOIN installations i ON i.id = li.latest_id
        LEFT JOIN cameras      c  ON c.installation_id  = i.id AND c.deleted_at  IS NULL
        LEFT JOIN other_devices od ON od.installation_id = i.id AND od.deleted_at IS NULL
        GROUP BY i.site_id
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(device_count_sql, id_list)
        device_counts = {
            r[0]: {"cameras": r[1], "others": r[2]}
            for r in cur.fetchall()
        }

    # 3. Dispatch overlay aggregates
    qs = (
        SiteDeviceDispatch.objects
        .filter(site_id__in=id_list)
        .values("site_id")
        .annotate(
            dispatched=Count("id", filter=Q(qty_sent__gt=0)),
            received=Count("id",   filter=Q(qty_received__gt=0)),
            installed=Count("id",  filter=Q(installed=True)),
        )
    )
    dispatch_map = {r["site_id"]: r for r in qs}

    # 4. Merge
    result = []
    for site_id, site_name in all_sites.items():
        dc   = device_counts.get(site_id, {"cameras": 0, "others": 0})
        disp = dispatch_map.get(site_id, {})
        total_cameras = dc["cameras"]
        total_devices = total_cameras + dc["others"]
        dispatched    = disp.get("dispatched", 0)
        received      = disp.get("received", 0)
        installed     = disp.get("installed", 0)
        denom         = total_devices or 1
        result.append({
            "site_id":        site_id,
            "site_name":      site_name,
            "total_cameras":  total_cameras,
            "total_devices":  total_devices,
            # keep "total" alias so frontend works with both field names
            "total":          total_devices,
            "dispatched":     dispatched,
            "received":       received,
            "installed":      installed,
            "pct_dispatched": round(dispatched / denom * 100, 1) if total_devices else 0.0,
            "pct_received":   round(received   / denom * 100, 1) if total_devices else 0.0,
            "pct_installed":  round(installed  / denom * 100, 1) if total_devices else 0.0,
        })
    result.sort(key=lambda x: x["site_id"])
    return result


# ---------------------------------------------------------------------------
# CEO dashboard (company-wide project health analytics)
# ---------------------------------------------------------------------------

# Keywords that flag a project as delayed when found in logs/notes.
# MySQL REGEXP with the default (ci) collation matches case-insensitively.
_DELAY_REGEX = r"retraso|atrasad|demora|delay|behind|problema grave"


def get_ceo_dashboard() -> dict:
    """
    Company-wide project health for the CEO dashboard.

    Per project (latest installation per active site) returns pre-computed
    metrics — install progress, schedule usage and a health semaphore — plus an
    overall summary, so the frontend never downloads every site to compute
    analytics or run keyword regexes in the browser.

    Health rule (documented):
      - behind_schedule: a delay keyword appears in logs/notes, OR the
        limit_date has passed and the project is not complete, OR the schedule
        variance (time_used% − progress%) exceeds 25 points.
      - watch: schedule variance exceeds 10 points.
      - on_track: otherwise.

    Cacheado (TTL corto) — invalidado por invalidate_dashboard() en escrituras.
    """
    return cu.cached("inst:ceo_dashboard", _compute_ceo_dashboard, cu.TTL_DASHBOARD)


def _empty_ceo_dashboard() -> dict:
    return {
        "summary": {
            "total_projects": 0, "on_track": 0, "watch": 0, "behind_schedule": 0,
            "total_devices": 0, "total_installed": 0, "overall_progress_pct": 0.0,
        },
        "projects": [],
    }


def _compute_ceo_dashboard() -> dict:
    from django.db.models import Q
    from django.utils import timezone
    from apps.installations.models import ItSiteTest, SiteDeviceLog

    # 1) Latest installation per active site + dates / status / owner / group
    main_sql = """
        SELECT
            s.id                AS site_id,
            s.name              AS site_name,
            s.customer_group_id AS customer_group_id,
            cg.name             AS customer_group,
            ist.name            AS status,
            u.name              AS project_owner,
            i.id                AS installation_id,
            i.starting_date     AS starting_date,
            i.limit_date        AS limit_date
        FROM sites s
        LEFT JOIN (
            SELECT site_id, MAX(id) AS latest_id
            FROM installations WHERE deleted_at IS NULL GROUP BY site_id
        ) li ON s.id = li.site_id
        LEFT JOIN installations  i   ON i.id = li.latest_id
        LEFT JOIN inst_statuses  ist ON i.inst_status_id  = ist.id
        LEFT JOIN users          u   ON i.project_owner   = u.id
        LEFT JOIN customer_groups cg ON cg.id = s.customer_group_id
        WHERE s.deleted_at IS NULL
        ORDER BY s.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(main_sql)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    if not rows:
        return _empty_ceo_dashboard()

    site_ids = [r["site_id"] for r in rows]
    inst_to_site = {r["installation_id"]: r["site_id"] for r in rows if r["installation_id"]}

    # 2) Install progress per site (reuse batched selector)
    progress_map = {p["site_id"]: p for p in get_all_sites_dispatch_progress(site_ids)}

    # 3) Delay alerts — batched, DB-side (never pulls full log bodies to Python)
    alert_sites: set[int] = set()
    log_hits = (
        SiteDeviceLog.objects
        .filter(site_id__in=site_ids)
        .filter(Q(notes__iregex=_DELAY_REGEX) | Q(action__iregex=_DELAY_REGEX))
        .values_list("site_id", flat=True)
        .distinct()
    )
    alert_sites.update(log_hits)

    for st in ItSiteTest.objects.filter(site_id__in=site_ids).values("site_id", "delays"):
        if st["delays"]:
            alert_sites.add(st["site_id"])

    if inst_to_site:
        ph = ",".join(["%s"] * len(inst_to_site))
        with connections[_DB].cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT installation_id FROM installation_notes "
                f"WHERE installation_id IN ({ph}) AND note REGEXP %s",
                list(inst_to_site.keys()) + [_DELAY_REGEX],
            )
            for (inst_id,) in cur.fetchall():
                site = inst_to_site.get(inst_id)
                if site is not None:
                    alert_sites.add(site)

    # 4) Build projects + health semaphore
    now = timezone.now()

    def _aware(dt):
        if dt is None:
            return None
        return timezone.make_aware(dt, timezone.utc) if timezone.is_naive(dt) else dt

    buckets = {"on_track": 0, "watch": 0, "behind_schedule": 0}
    total_installed = 0
    total_devices = 0
    projects = []

    for r in rows:
        site_id = r["site_id"]
        prog = progress_map.get(site_id, {})
        progress_pct = prog.get("pct_installed", 0.0)
        installed = prog.get("installed", 0)
        dev_total = prog.get("total_devices", 0)
        total_installed += installed
        total_devices += dev_total

        start = _aware(r.get("starting_date"))
        limit = _aware(r.get("limit_date"))
        time_used_pct = None
        overdue = False
        if start and limit and limit > start:
            span = (limit - start).total_seconds()
            elapsed = (now - start).total_seconds()
            time_used_pct = round(max(0.0, elapsed / span) * 100, 1)
            overdue = now > limit and progress_pct < 100.0

        has_alerts = site_id in alert_sites
        variance = (time_used_pct - progress_pct) if time_used_pct is not None else None
        if has_alerts or overdue or (variance is not None and variance > 25):
            health = "behind_schedule"
        elif variance is not None and variance > 10:
            health = "watch"
        else:
            health = "on_track"
        buckets[health] += 1

        projects.append({
            "site_id":           site_id,
            "site_name":         r["site_name"],
            "customer_group_id": r.get("customer_group_id"),
            "customer_group":    r.get("customer_group"),
            "status":            r.get("status"),
            "project_owner":     r.get("project_owner"),
            "starting_date":     start,
            "limit_date":        limit,
            "total_devices":     dev_total,
            "installed":         installed,
            "progress_pct":      progress_pct,
            "time_used_pct":     time_used_pct,
            "has_delay_alerts":  has_alerts,
            "health":            health,
        })

    overall_pct = round(total_installed / (total_devices or 1) * 100, 1) if total_devices else 0.0
    summary = {
        "total_projects":       len(projects),
        "on_track":             buckets["on_track"],
        "watch":                buckets["watch"],
        "behind_schedule":      buckets["behind_schedule"],
        "total_devices":        total_devices,
        "total_installed":      total_installed,
        "overall_progress_pct": overall_pct,
    }
    return {"summary": summary, "projects": projects}


def list_indoor_maps(site_id: int) -> list:
    """All indoor floor-plan maps for a site (newest first)."""
    from apps.installations.models import SiteIndoorMap
    return list(SiteIndoorMap.objects.filter(site_id=site_id))


def get_indoor_map(site_id: int, map_id: int):
    """A single indoor map scoped to its site, or None."""
    from apps.installations.models import SiteIndoorMap
    return SiteIndoorMap.objects.filter(site_id=site_id, pk=map_id).first()


def get_user_app_permissions(user_id: int) -> list[str]:
    """Return flat list of permission keys for a user via sigtools_beta raw SQL."""
    sql = """
        SELECT DISTINCT p.key
        FROM user_app_roles uar
        JOIN role_permissions rp ON rp.role_id = uar.role_id
        JOIN permissions p       ON p.id = rp.permission_id
        WHERE uar.user_id = %s
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql, [user_id])
        return [row[0] for row in cur.fetchall()]


def get_user_app_roles(user_id: int) -> list[str]:
    """Return list of role names assigned to a user via sigtools_beta raw SQL."""
    sql = """
        SELECT ar.name
        FROM user_app_roles uar
        JOIN app_roles ar ON ar.id = uar.role_id
        WHERE uar.user_id = %s
    """
    with connections[_SIGTOOLS].cursor() as cur:
        cur.execute(sql, [user_id])
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# IT Test
# ---------------------------------------------------------------------------

def get_it_test_for_site(site_id: int):
    """Returns the ItSiteTest for the given site or None."""
    from apps.installations.models import ItSiteTest
    return ItSiteTest.objects.filter(site_id=site_id).first()


def get_site_tech_info(site_id: int) -> dict | None:
    """Returns ip_address, timezone, and location for a site from sigtools_beta."""
    sql = """
        SELECT id, name, ip_address, timezone, city, state_code, country_code, address
        FROM sites
        WHERE id = %s AND deleted_at IS NULL
        LIMIT 1
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id])
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
    if not row:
        return None
    data = dict(zip(cols, row))
    parts = [p for p in [data.get("city"), data.get("state_code"), data.get("country_code")] if p]
    data["location"] = ", ".join(parts) if parts else data.get("address")
    return data


def get_site_project_info_overlay(site_id: int):
    """Returns the SiteProjectInfo overlay row or None."""
    from apps.installations.models import SiteProjectInfo
    return SiteProjectInfo.objects.filter(site_id=site_id).first()


# ---------------------------------------------------------------------------
# Dashboard init — unified first-load payload
# ---------------------------------------------------------------------------

def get_dashboard_init() -> dict:
    """
    Returns the three data sets needed for the first dashboard render in a
    single call, eliminating 2 round-trips over high-latency LAN connections.

    Keys:
      sites             — list_sites_dashboard()
      project_sites     — list_project_sites()
      dispatch_progress — get_all_sites_dispatch_progress()
    """
    return {
        "sites":             list_sites_dashboard(),
        "project_sites":     list_project_sites(),
        "dispatch_progress": get_all_sites_dispatch_progress(),
    }


# ── In-app notifications ──────────────────────────────────────────────────────

def list_notifications(recipient_id: int, unread_only: bool = False) -> list[dict]:
    """Return notifications for a user ordered by most recent first."""
    from apps.installations.models import Notification

    qs = Notification.objects.filter(recipient_id=recipient_id)
    if unread_only:
        qs = qs.filter(is_read=False)
    return [
        {
            "id":                 n.id,
            "title":              n.title,
            "message":            n.message,
            "type":               n.type,
            "is_read":            n.is_read,
            "related_project_id": str(n.related_project_id) if n.related_project_id else None,
            "created_at":         n.created_at.isoformat(),
        }
        for n in qs
    ]


def count_unread_notifications(recipient_id: int) -> int:
    from apps.installations.models import Notification

    return Notification.objects.filter(recipient_id=recipient_id, is_read=False).count()
