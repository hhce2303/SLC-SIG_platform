"""
Services — business logic for the Installations API.
Write operations use raw SQL directly on 'sigtools' connection
to avoid model field mapping issues with unmanaged tables.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import connections, transaction
from django.utils.html import escape

from apps.core.exceptions import ConflictError
from apps.core.realtime import CH_INSTALLATIONS, CH_INVENTORY, CH_PROJECTS, publish as _rt_publish
from apps.core import cache_utils as cu
from apps.installations.graph_mail import GraphMailConfigError, is_graph_mail_configured, send_graph_mail

logger = logging.getLogger(__name__)

_DB = "sigtools"

# Mapping from category string to table name — both for soft-delete and sync
_TABLE_MAP: dict[str, str] = {
    "camera": "cameras",
    "other": "other_devices",
    "core_device": "devices",
    "server": "servers",
}


def _sigtools_users_by_ids(user_ids: set[int]) -> dict[int, dict[str, Any]]:
    if not user_ids:
        return {}
    placeholders = ",".join(["%s"] * len(user_ids))
    sql = f"SELECT id, name, email FROM users WHERE id IN ({placeholders})"  # noqa: S608
    with connections[_DB].cursor() as cur:
        cur.execute(sql, list(user_ids))
        rows = cur.fetchall()
    return {row[0]: {"id": row[0], "name": row[1], "email": row[2]} for row in rows}


def _sigtools_admin_emails() -> list[str]:
    sql = """
        SELECT DISTINCT u.email
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.deleted_at IS NULL
          AND u.email IS NOT NULL
          AND u.email <> ''
          AND r.name = 'Admin'
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def _sigtools_admin_user_ids() -> list[int]:
    """Return user IDs of all Admin-role sigtools users (for in-app notifications)."""
    sql = """
        SELECT DISTINCT u.id
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.deleted_at IS NULL
          AND r.name = 'Admin'
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def _create_notifications_bulk(
    *,
    recipient_ids: list[int],
    title: str,
    message: str,
    notif_type: str,
    related_project_id=None,
) -> None:
    """Bulk-insert Notification rows — best effort, never raises."""
    if not recipient_ids:
        return
    from apps.installations.models import Notification

    import uuid as _uuid
    proj_uuid = None
    if related_project_id:
        try:
            proj_uuid = _uuid.UUID(str(related_project_id))
        except (ValueError, AttributeError):
            proj_uuid = None
    try:
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_id=rid,
                    title=title[:255],
                    message=message,
                    type=notif_type,
                    related_project_id=proj_uuid,
                )
                for rid in recipient_ids
            ],
            ignore_conflicts=True,
        )
    except Exception:
        logger.exception("Failed to bulk-create notifications")


def _send_graph_mail_safe(*, to_emails: list[str], subject: str, html_content: str) -> None:
    if not to_emails:
        return
    if not is_graph_mail_configured():
        logger.warning("Graph mail is not configured; skipping email '%s'", subject)
        return
    try:
        send_graph_mail(to_emails=to_emails, subject=subject, html_content=html_content)
    except GraphMailConfigError as exc:
        logger.warning("Graph mail config error: %s", exc)
    except Exception:
        logger.exception("Failed to send Graph mail '%s'", subject)


def _notify_project_approval_requested(*, project: dict, requester_name: str | None, note: str) -> None:
    admin_emails = _sigtools_admin_emails()
    admin_user_ids = _sigtools_admin_user_ids()

    if admin_emails:
        safe_name = escape(project.get("name") or "(sin nombre)")
        safe_requester = escape(requester_name or "Usuario")
        safe_note = escape(note or "")
        html = (
            f"<p>Se solicitó aprobación para el proyecto GIS <b>{safe_name}</b>.</p>"
            f"<p>Solicitado por: <b>{safe_requester}</b></p>"
        )
        if safe_note:
            html += f"<p>Nota: {safe_note}</p>"
        _send_graph_mail_safe(
            to_emails=admin_emails,
            subject=f"[Installations] Approval requested: {project.get('name')}",
            html_content=html,
        )

    if admin_user_ids:
        _create_notifications_bulk(
            recipient_ids=admin_user_ids,
            title=f"Aprobación solicitada: {project.get('name', '')}",
            message=(
                f"{requester_name or 'Un usuario'} solicitó aprobación para el proyecto "
                f"'{project.get('name', '')}'. {('Nota: ' + note) if note else ''}"
            ).strip(),
            notif_type="approval_request",
            related_project_id=project.get("id"),
        )


def _notify_project_approval_cancelled(*, project: dict, requester_name: str | None, note: str) -> None:
    admin_emails = _sigtools_admin_emails()
    admin_user_ids = _sigtools_admin_user_ids()

    if admin_emails:
        safe_name = escape(project.get("name") or "(sin nombre)")
        safe_requester = escape(requester_name or "Usuario")
        safe_note = escape(note or "")
        html = (
            f"<p>Se canceló la solicitud de aprobación para el proyecto GIS <b>{safe_name}</b>.</p>"
            f"<p>Cancelado por: <b>{safe_requester}</b></p>"
        )
        if safe_note:
            html += f"<p>Nota: {safe_note}</p>"
        _send_graph_mail_safe(
            to_emails=admin_emails,
            subject=f"[Installations] Approval request cancelled: {project.get('name')}",
            html_content=html,
        )

    if admin_user_ids:
        _create_notifications_bulk(
            recipient_ids=admin_user_ids,
            title=f"Aprobación cancelada: {project.get('name', '')}",
            message=(
                f"{requester_name or 'Un usuario'} canceló la solicitud de aprobación para el proyecto "
                f"'{project.get('name', '')}'. {('Nota: ' + note) if note else ''}"
            ).strip(),
            notif_type="approval_cancelled",
            related_project_id=project.get("id"),
        )


def _notify_project_promoted_to_onboarding(
    *,
    site_id: int,
    project_site_id: int,
    requester_id: int | None,
    project_owner_id: int | None,
    lead_tech_id: int | None,
) -> None:
    user_map = _sigtools_users_by_ids({uid for uid in [requester_id, project_owner_id, lead_tech_id] if uid})
    recipient_emails = sorted(
        {
            user_map[uid]["email"]
            for uid in [requester_id, project_owner_id, lead_tech_id]
            if uid and uid in user_map and user_map[uid].get("email")
        }
    )
    if not recipient_emails:
        return

    requester_name = user_map.get(requester_id, {}).get("name", "N/A")
    project_owner_name = user_map.get(project_owner_id, {}).get("name", "N/A")
    lead_tech_name = user_map.get(lead_tech_id, {}).get("name", "N/A")
    html = (
        f"<p>El proyecto con staging id <b>{project_site_id}</b> fue aprobado y enviado a onboarding.</p>"
        f"<p>site_id: <b>{site_id}</b></p>"
        f"<p>Lead Tech: <b>{escape(str(lead_tech_name))}</b><br/>"
        f"Project Owner: <b>{escape(str(project_owner_name))}</b><br/>"
        f"Solicitante: <b>{escape(str(requester_name))}</b></p>"
    )
    _send_graph_mail_safe(
        to_emails=recipient_emails,
        subject=f"[Installations] Proyecto enviado a onboarding (site {site_id})",
        html_content=html,
    )

    notif_recipients = [uid for uid in [requester_id, project_owner_id, lead_tech_id] if uid]
    if notif_recipients:
        _create_notifications_bulk(
            recipient_ids=notif_recipients,
            title=f"Proyecto enviado a onboarding (site {site_id})",
            message=(
                f"El staging id {project_site_id} fue aprobado y enviado a onboarding. "
                f"Lead Tech: {lead_tech_name}. Project Owner: {project_owner_name}."
            ),
            notif_type="onboarding",
        )


def _notify_dispatch_created(*, site_id: int, device_id: str, qty_sent: int | None, actor_user_id: int | None) -> None:
    if not qty_sent or qty_sent <= 0:
        return
    sql = """
        SELECT i.project_owner, i.it_lead_tech_id, ps.approval_requested_by
        FROM installations i
        LEFT JOIN project_sites ps ON ps.site_id = i.site_id AND ps.deleted_at IS NULL
        WHERE i.site_id = %s AND i.deleted_at IS NULL
        ORDER BY i.id DESC
        LIMIT 1
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id])
        row = cur.fetchone()
    if not row:
        return

    project_owner_id, lead_tech_id, requester_id = row
    user_ids = {uid for uid in [project_owner_id, lead_tech_id, requester_id, actor_user_id] if uid}
    user_map = _sigtools_users_by_ids(user_ids)
    recipient_emails = sorted(
        {
            user_map[uid]["email"]
            for uid in [project_owner_id, lead_tech_id, requester_id]
            if uid and uid in user_map and user_map[uid].get("email")
        }
    )
    if not recipient_emails:
        return

    actor_name = user_map.get(actor_user_id, {}).get("name", "N/A")
    html = (
        f"<p>Se despacharon artículos para site <b>{site_id}</b>.</p>"
        f"<p>Dispositivo: <b>{escape(device_id)}</b><br/>"
        f"Cantidad enviada: <b>{qty_sent}</b><br/>"
        f"Registrado por: <b>{escape(str(actor_name))}</b></p>"
    )
    _send_graph_mail_safe(
        to_emails=recipient_emails,
        subject=f"[Installations] Dispatch registrado (site {site_id})",
        html_content=html,
    )

    notif_recipients = [uid for uid in [project_owner_id, lead_tech_id, requester_id] if uid]
    if notif_recipients:
        _create_notifications_bulk(
            recipient_ids=notif_recipients,
            title=f"Despacho registrado (site {site_id})",
            message=(
                f"Se despacharon {qty_sent} unidad(es) del dispositivo '{device_id}' "
                f"para site {site_id}. Registrado por: {actor_name}."
            ),
            notif_type="inventory_dispatch",
        )

# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

def create_site(data: dict) -> int:
    """Inserts a new site. Returns the new site_id."""
    sql = """
        INSERT INTO sites
            (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
             monitored, maintenance, receive_notifications,
             cameras_count, total_devices, devices_down,
             created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 1, 1, 1, 0, 0, 0, NOW(), NOW())
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [
            data["name"],
            data["customer_group_id"],
            data["ip_address"],
            data.get("teams_channelid", ""),
            data.get("teams_teamid", ""),
        ])
        return cur.lastrowid


def create_site_with_installation(data: dict) -> dict:
    """
    Atomically creates a site and its first installation.

    Steps:
    1. Look up the 'Active' inst_status_id dynamically from inst_statuses.
    2. Insert the site row; capture site_id.
    3. Insert the installation row using site_id + active status.
       project_owner is hardcoded to user_id 48 unless provided.
    4. Return the full installation record joined with site and status names.

    Raises ValueError if Active status is not found in inst_statuses.
    Both inserts are wrapped in transaction.atomic(using=_DB) — either both
    succeed or neither is committed.
    """
    _PROJECT_OWNER_DEFAULT = None

    with transaction.atomic(using=_DB):
        # 1. Resolve Active status ID
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Active' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Active status not found in inst_statuses")
            active_status_id: int = row[0]

        # 2. Insert site
        site_sql = """
            INSERT INTO sites
                (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
                 address, city, state_code, country_code,
                 monitored, maintenance, receive_notifications,
                 cameras_count, total_devices, devices_down,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 1, 0, 0, 0, NOW(), NOW())
        """
        with connections[_DB].cursor() as cur:
            cur.execute(site_sql, [
                data["name"],
                data["customer_group_id"],
                data.get("ip_address", "0.0.0.0"),
                data.get("teams_channelid", ""),
                data.get("teams_teamid", ""),
                data.get("address") or None,
                data.get("city") or None,
                data.get("state_code") or None,
                data.get("country_code") or None,
            ])
            site_id: int = cur.lastrowid

        # 3. Insert installation
        inst_sql = """
            INSERT INTO installations
                (site_id, inst_status_id, it_lead_tech_id, installation_type_id,
                 project_owner, Total_cameras, Total_views,
                 starting_date, limit_date,
                 total_hours, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.0, NOW(), NOW())
        """
        with connections[_DB].cursor() as cur:
            cur.execute(inst_sql, [
                site_id,
                active_status_id,
                data["it_lead_tech_id"],
                data["installation_type_id"],
                data.get("project_owner") or _PROJECT_OWNER_DEFAULT,
                data.get("total_cameras", 0),
                data.get("total_views", 0),
                data.get("starting_date") or None,
                data.get("limit_date") or None,
            ])
            installation_id: int = cur.lastrowid

        # 4. Fetch and return the full installation record
        fetch_sql = """
            SELECT
                i.id                AS installation_id,
                i.site_id,
                s.name              AS site_name,
                ist.name            AS status,
                i.project_owner,
                u_owner.name        AS project_owner_name,
                i.it_lead_tech_id,
                u_tech.name         AS it_lead_tech_name,
                i.installation_type_id,
                it.name             AS installation_type,
                i.Total_cameras     AS total_cameras,
                i.Total_views       AS total_views,
                i.starting_date,
                i.limit_date,
                i.total_hours,
                i.created_at
            FROM installations i
            JOIN sites s               ON s.id   = i.site_id
            JOIN inst_statuses ist     ON ist.id  = i.inst_status_id
            LEFT JOIN users u_owner    ON u_owner.id = i.project_owner
            LEFT JOIN users u_tech     ON u_tech.id  = i.it_lead_tech_id
            LEFT JOIN installation_types it ON it.id = i.installation_type_id
            WHERE i.id = %s
        """
        with connections[_DB].cursor() as cur:
            cur.execute(fetch_sql, [installation_id])
            cols = [c[0] for c in cur.description]
            record = cur.fetchone()
            return dict(zip(cols, record))


def update_project_site_info(site_id: int, data: dict) -> dict | None:
    """
    Upsert editable fields on a project_site record.

    Lookup order:
      1. project_sites.id = site_id
      2. project_sites.site_id = site_id  (promoted legacy sites)
      3. If neither exists but sites.id = site_id → seed a new project_sites
         record from the sites table, then apply the update.
    Returns the full updated record, or None if the site doesn't exist anywhere.
    """
    from apps.installations import selectors

    site_fields = {
        "name":            data.get("name"),
        "city":            data.get("city"),
        "state_code":      data.get("state_code"),
        "country_code":    data.get("country_code"),
        "address":         data.get("address"),
        "ip_address":      data.get("ip_address"),
        "contract_value":  data.get("contract_value"),
        "hotel":           data.get("hotel"),
        "flight_details":  data.get("flight_details"),
    }
    site_set = {k: v for k, v in site_fields.items() if v is not None}

    inst_fields = {
        "it_lead_tech_id":       data.get("it_lead_tech_id"),
        "project_owner":         data.get("project_owner"),
        "installation_type_id":  data.get("installation_type_id"),
        "starting_date":         data.get("starting_date"),
        "limit_date":            data.get("limit_date"),
        "Total_cameras":         data.get("total_cameras"),
    }
    inst_set = {k: v for k, v in inst_fields.items() if v is not None}

    with connections[_DB].cursor() as cur:
        # Resolve the actual project_sites.id to update
        cur.execute(
            """SELECT id FROM project_sites
               WHERE (id = %s OR site_id = %s) AND deleted_at IS NULL
               ORDER BY id DESC LIMIT 1""",
            [site_id, site_id],
        )
        row = cur.fetchone()

        if row:
            ps_id = row[0]
        else:
            # Seed from sites table for legacy sites that never went through staging
            cur.execute(
                """SELECT id, name, city, state_code, country_code,
                          ip_address, address, customer_group_id
                   FROM sites WHERE id = %s AND deleted_at IS NULL""",
                [site_id],
            )
            site_row = cur.fetchone()
            if not site_row:
                return None
            (_, s_name, s_city, s_state, s_country,
             s_ip, s_address, s_cg_id) = site_row
            cur.execute(
                """INSERT INTO project_sites
                       (name, city, state_code, country_code, ip_address,
                        address, customer_group_id, site_id,
                        verification_status, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'verified', NOW(), NOW())""",
                [s_name, s_city, s_state, s_country,
                 s_ip, s_address, s_cg_id, site_id],
            )
            ps_id = cur.lastrowid

        if site_set:
            clauses = ", ".join(f"{k} = %s" for k in site_set)
            params = list(site_set.values()) + [ps_id]
            cur.execute(
                f"UPDATE project_sites SET {clauses}, updated_at = NOW() WHERE id = %s",  # noqa: S608
                params,
            )

        if inst_set:
            clauses = ", ".join(f"{k} = %s" for k in inst_set)
            params = list(inst_set.values()) + [ps_id]
            cur.execute(
                f"""UPDATE installations SET {clauses}, updated_at = NOW()
                    WHERE site_id = %s AND deleted_at IS NULL
                    ORDER BY id DESC LIMIT 1""",  # noqa: S608
                params,
            )

    # Handle SiteProjectInfo overlay fields (stored in default DB)
    overlay_fields = {k: v for k, v in {
        "check_in":       data.get("check_in"),
        "check_out":      data.get("check_out"),
        "paylocity_code": data.get("paylocity_code"),
        "extra_notes":    data.get("extra_notes"),
    }.items() if v is not None}
    if overlay_fields:
        from apps.installations.models import SiteProjectInfo
        SiteProjectInfo.objects.update_or_create(site_id=site_id, defaults=overlay_fields)

    return selectors.get_project_site_info(site_id)


def create_project_site_with_installation(data: dict) -> dict:
    """
    Atomically creates a project_site (pre-verification staging) and its first
    installation. Writes to project_sites instead of sites, keeping the same
    response contract so the frontend is unaffected.

    Raises ValueError if Active status is not found in inst_statuses.
    """
    _PROJECT_OWNER_DEFAULT = None

    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Active' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Active status not found in inst_statuses")
            active_status_id: int = row[0]

        project_site_sql = """
            INSERT INTO project_sites
                (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
                 address, city, state_code, country_code,
                 monitored, maintenance, cameras_count,
                 verification_status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 0, 'pending', NOW(), NOW())
        """
        with connections[_DB].cursor() as cur:
            cur.execute(project_site_sql, [
                data["name"],
                data["customer_group_id"],
                data.get("ip_address", "0.0.0.0"),
                data.get("teams_channelid", ""),
                data.get("teams_teamid", ""),
                data.get("address") or None,
                data.get("city") or None,
                data.get("state_code") or None,
                data.get("country_code") or None,
            ])
            project_site_id: int = cur.lastrowid

        inst_sql = """
            INSERT INTO installations
                (site_id, inst_status_id, it_lead_tech_id, installation_type_id,
                 project_owner, Total_cameras, Total_views,
                 starting_date, limit_date,
                 total_hours, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.0, NOW(), NOW())
        """
        with connections[_DB].cursor() as cur:
            cur.execute(inst_sql, [
                project_site_id,
                active_status_id,
                data["it_lead_tech_id"],
                data["installation_type_id"],
                data.get("project_owner") or _PROJECT_OWNER_DEFAULT,
                data.get("total_cameras", 0),
                data.get("total_views", 0),
                data.get("starting_date") or None,
                data.get("limit_date") or None,
            ])
            installation_id: int = cur.lastrowid

        fetch_sql = """
            SELECT
                i.id                AS installation_id,
                i.site_id,
                ps.name             AS site_name,
                ist.name            AS status,
                i.project_owner,
                u_owner.name        AS project_owner_name,
                i.it_lead_tech_id,
                u_tech.name         AS it_lead_tech_name,
                i.installation_type_id,
                it.name             AS installation_type,
                i.Total_cameras     AS total_cameras,
                i.Total_views       AS total_views,
                i.starting_date,
                i.limit_date,
                i.total_hours,
                i.created_at
            FROM installations i
            JOIN project_sites ps        ON ps.id  = i.site_id
            JOIN inst_statuses ist       ON ist.id = i.inst_status_id
            LEFT JOIN users u_owner      ON u_owner.id = i.project_owner
            LEFT JOIN users u_tech       ON u_tech.id  = i.it_lead_tech_id
            LEFT JOIN installation_types it ON it.id   = i.installation_type_id
            WHERE i.id = %s
        """
        with connections[_DB].cursor() as cur:
            cur.execute(fetch_sql, [installation_id])
            cols = [c[0] for c in cur.description]
            record = cur.fetchone()
            return dict(zip(cols, record))


def promote_project_site(project_site_id: int, authorized_by: int) -> int:
    """
    Promotes a project_site to the real sites table.

    Steps:
    1. Load the project_site record (must exist, not deleted, not already promoted).
    2. INSERT into sites using all available columns from project_sites.
    3. UPDATE installations.site_id to the new real site_id.
    4. Mark project_site verification_status = 'verified', set authorized_by/at.

    Returns the new site_id.
    Raises ValueError if project_site not found or already promoted.
    """
    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                SELECT id, name, customer_group_id, ip_address,
                       teams_channelid, teams_teamid,
                       address, city, state_code, country_code,
                       dealership_info, lat, `long`, timezone,
                       cameras_count, preowned_cameras_count, exterior_cameras_count,
                       site_status_id, monitored, maintenance, rental,
                       installation_date, verified_by, verified_at,
                       verification_status
                FROM project_sites
                WHERE id = %s AND deleted_at IS NULL
                """,
                [project_site_id],
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"project_site {project_site_id} not found or deleted.")
            cols = [c[0] for c in cur.description]
            ps = dict(zip(cols, row))

            if ps["verification_status"] == "verified":
                raise ValueError(f"project_site {project_site_id} has already been promoted.")

            cur.execute(
                """
                INSERT INTO sites
                    (name, customer_group_id, ip_address,
                     teams_channelid, teams_teamid,
                     address, city, state_code, country_code,
                     dealership_info, lat, `long`, timezone,
                     cameras_count, preowned_cameras_count, exterior_cameras_count,
                     site_status_id, monitored, maintenance, rental,
                     installation_date,
                     receive_notifications, total_devices, devices_down,
                     created_at, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                     %s, %s, %s, %s, %s, %s, %s, %s, 1, 0, 0, NOW(), NOW())
                """,
                [
                    ps["name"],
                    ps["customer_group_id"],
                    ps["ip_address"] or "0.0.0.0",
                    ps["teams_channelid"] or "",
                    ps["teams_teamid"] or "",
                    ps["address"],
                    ps["city"],
                    ps["state_code"],
                    ps["country_code"],
                    ps["dealership_info"],
                    ps["lat"],
                    ps["long"],
                    ps["timezone"],
                    ps["cameras_count"] or 0,
                    ps["preowned_cameras_count"] or 0,
                    ps["exterior_cameras_count"] or 0,
                    ps["site_status_id"] or 1,
                    ps["monitored"] if ps["monitored"] is not None else 1,
                    ps["maintenance"] if ps["maintenance"] is not None else 1,
                    ps["rental"] if ps["rental"] is not None else 1,
                    ps["installation_date"],
                ],
            )
            site_id: int = cur.lastrowid

            cur.execute(
                "UPDATE installations SET site_id = %s, updated_at = NOW() WHERE site_id = %s AND deleted_at IS NULL",
                [site_id, project_site_id],
            )

            cur.execute(
                """
                UPDATE project_sites
                SET verification_status = 'verified',
                    authorized_by       = %s,
                    authorized_at       = NOW(),
                    updated_at          = NOW()
                WHERE id = %s
                """,
                [authorized_by, project_site_id],
            )

    return site_id


def create_project_site_with_installation(data: dict) -> dict:
    """
    Atomically creates a project_site (staging review record), a shadow site
    in `sites` with status_id=5 (Staging) to satisfy the FK constraint on
    installations.site_id, and the first installation pointing to that shadow site.

    Flow:
    1. Insert project_site  → project_site_id (staging form for review)
    2. Insert sites (Staging status=5) → site_id (satisfies FK)
    3. UPDATE project_sites.site_id = site_id  (links the two records)
    4. Insert installation with site_id
    5. Fetch and return full installation record (same contract as before)

    Raises ValueError if Active inst_status is not found.
    """
    _PROJECT_OWNER_DEFAULT = None
    _STAGING_SITE_STATUS = 5

    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Active' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Active status not found in inst_statuses")
            active_status_id: int = row[0]

        # 1. Insert staging review record
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_sites
                    (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
                     address, city, state_code, country_code, lat, `long`,
                     monitored, maintenance, cameras_count,
                     verification_status, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 0, 'pending', %s, NOW(), NOW())
                """,
                [
                    data["name"],
                    data["customer_group_id"],
                    data.get("ip_address", "0.0.0.0"),
                    data.get("teams_channelid", ""),
                    data.get("teams_teamid", ""),
                    data.get("address") or None,
                    data.get("city") or None,
                    data.get("state_code") or None,
                    data.get("country_code") or None,
                    data.get("lat") or None,
                    data.get("lng") or None,
                    data.get("created_by") or None,
                ],
            )
            project_site_id: int = cur.lastrowid

        # 2. Insert shadow site in sites (Staging status) — satisfies FK
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                INSERT INTO sites
                    (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
                     address, city, state_code, country_code, lat, `long`,
                     site_status_id, monitored, maintenance, receive_notifications,
                     cameras_count, total_devices, devices_down,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 1, 0, 0, 0, NOW(), NOW())
                """,
                [
                    data["name"],
                    data["customer_group_id"],
                    data.get("ip_address", "0.0.0.0"),
                    data.get("teams_channelid", ""),
                    data.get("teams_teamid", ""),
                    data.get("address") or None,
                    data.get("city") or None,
                    data.get("state_code") or None,
                    data.get("country_code") or None,
                    data.get("lat") or None,
                    data.get("lng") or None,
                    _STAGING_SITE_STATUS,
                ],
            )
            site_id: int = cur.lastrowid

        # 3. Link project_site → shadow site
        with connections[_DB].cursor() as cur:
            cur.execute(
                "UPDATE project_sites SET site_id = %s, updated_at = NOW() WHERE id = %s",
                [site_id, project_site_id],
            )

        # 4. total_devices_planned overrides total_cameras when provided
        total_cameras = data.get("total_devices_planned") or data.get("total_cameras", 0) or 0

        # 5. Insert installation pointing to the shadow site (FK satisfied)
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                INSERT INTO installations
                    (site_id, inst_status_id, it_lead_tech_id, installation_type_id,
                     project_owner, Total_cameras, Total_views,
                     starting_date, limit_date,
                     total_hours, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.0, NOW(), NOW())
                """,
                [
                    site_id,
                    active_status_id,
                    data["it_lead_tech_id"],
                    data["installation_type_id"],
                    data.get("project_owner") or _PROJECT_OWNER_DEFAULT,
                    total_cameras,
                    data.get("total_views", 0),
                    data.get("starting_date") or None,
                    data.get("limit_date") or None,
                ],
            )
            installation_id: int = cur.lastrowid

        # 6. Fetch full record — JOIN sites (not project_sites) since that's where site_id points
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                SELECT
                    i.id                AS installation_id,
                    i.site_id,
                    s.name              AS site_name,
                    ist.name            AS status,
                    i.project_owner,
                    u_owner.name        AS project_owner_name,
                    i.it_lead_tech_id,
                    u_tech.name         AS it_lead_tech_name,
                    i.installation_type_id,
                    it.name             AS installation_type,
                    i.Total_cameras     AS total_cameras,
                    i.Total_views       AS total_views,
                    i.starting_date,
                    i.limit_date,
                    i.total_hours,
                    i.created_at
                FROM installations i
                JOIN sites s                ON s.id   = i.site_id
                JOIN inst_statuses ist      ON ist.id = i.inst_status_id
                LEFT JOIN users u_owner     ON u_owner.id = i.project_owner
                LEFT JOIN users u_tech      ON u_tech.id  = i.it_lead_tech_id
                LEFT JOIN installation_types it ON it.id  = i.installation_type_id
                WHERE i.id = %s
                """,
                [installation_id],
            )
            cols = [c[0] for c in cur.description]
            record = cur.fetchone()
            return dict(zip(cols, record))


def promote_project_site(project_site_id: int, authorized_by: int) -> int:
    """
    Promotes a project_site to an official site by updating the existing shadow
    site record (site_status_id=5 → 1/Created) with full data from project_sites.

    Since the installation already points to that sites.id (shadow), no update
    to installations is needed — the site simply becomes official in place.

    Steps:
    1. Load project_site (must exist, not deleted, not already verified).
    2. UPDATE sites SET full data + site_status_id=1 WHERE id = project_site.site_id.
    3. Mark project_site as verified with authorized_by/at.

    Returns the promoted site_id.
    Raises ValueError if project_site not found, deleted, or already promoted.
    """
    notify_payload: dict[str, int | None] = {}

    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            cur.execute(
                """
                SELECT id, name, customer_group_id, ip_address,
                       teams_channelid, teams_teamid,
                       address, city, state_code, country_code,
                       dealership_info, lat, `long`, timezone,
                       cameras_count, preowned_cameras_count, exterior_cameras_count,
                       monitored, maintenance, rental, installation_date,
                       verification_status, site_id, approval_requested_by
                FROM project_sites
                WHERE id = %s AND deleted_at IS NULL
                """,
                [project_site_id],
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"project_site {project_site_id} not found or deleted.")
            cols = [c[0] for c in cur.description]
            ps = dict(zip(cols, row))

            if ps["verification_status"] == "verified":
                raise ValueError(f"project_site {project_site_id} has already been promoted.")

            site_id: int = ps["site_id"]

            # UPDATE shadow site → official (status 1 = Created)
            cur.execute(
                """
                UPDATE sites SET
                    name                   = %s,
                    customer_group_id      = %s,
                    ip_address             = %s,
                    teams_channelid        = %s,
                    teams_teamid           = %s,
                    address                = %s,
                    city                   = %s,
                    state_code             = %s,
                    country_code           = %s,
                    dealership_info        = %s,
                    lat                    = %s,
                    `long`                 = %s,
                    timezone               = %s,
                    cameras_count          = %s,
                    preowned_cameras_count = %s,
                    exterior_cameras_count = %s,
                    monitored              = %s,
                    maintenance            = %s,
                    rental                 = %s,
                    installation_date      = %s,
                    site_status_id         = 1,
                    updated_at             = NOW()
                WHERE id = %s
                """,
                [
                    ps["name"],
                    ps["customer_group_id"],
                    ps["ip_address"] or "0.0.0.0",
                    ps["teams_channelid"] or "",
                    ps["teams_teamid"] or "",
                    ps["address"],
                    ps["city"],
                    ps["state_code"],
                    ps["country_code"],
                    ps["dealership_info"],
                    ps["lat"],
                    ps["long"],
                    ps["timezone"],
                    ps["cameras_count"] or 0,
                    ps["preowned_cameras_count"] or 0,
                    ps["exterior_cameras_count"] or 0,
                    ps["monitored"] if ps["monitored"] is not None else 1,
                    ps["maintenance"] if ps["maintenance"] is not None else 1,
                    ps["rental"] if ps["rental"] is not None else 1,
                    ps["installation_date"],
                    site_id,
                ],
            )

            cur.execute(
                """
                UPDATE project_sites
                SET verification_status = 'verified',
                    authorized_by       = %s,
                    authorized_at       = NOW(),
                    updated_at          = NOW()
                WHERE id = %s
                """,
                [authorized_by, project_site_id],
            )

            cur.execute(
                """
                SELECT project_owner, it_lead_tech_id
                FROM installations
                WHERE site_id = %s AND deleted_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                [site_id],
            )
            inst_row = cur.fetchone() or (None, None)
            notify_payload = {
                "site_id": site_id,
                "project_site_id": project_site_id,
                "requester_id": ps.get("approval_requested_by"),
                "project_owner_id": inst_row[0],
                "lead_tech_id": inst_row[1],
            }

    transaction.on_commit(
        lambda: _notify_project_promoted_to_onboarding(
            site_id=notify_payload["site_id"],
            project_site_id=notify_payload["project_site_id"],
            requester_id=notify_payload["requester_id"],
            project_owner_id=notify_payload["project_owner_id"],
            lead_tech_id=notify_payload["lead_tech_id"],
        ),
        using=_DB,
    )

    return site_id


_EXPORT_CAMERA_SQL = """
    INSERT INTO cameras
        (installation_id, camera_model_id, device_id,
         canvas_instance_id, serial, user, password, hours,
         created_at, updated_at)
    VALUES (%s, %s, %s, %s, 'PENDING', 'admin', 'admin', 0, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
        camera_model_id    = VALUES(camera_model_id),
        device_id          = VALUES(device_id),
        updated_at         = NOW()
"""

_EXPORT_OTHER_SQL = """
    INSERT INTO other_devices
        (installation_id, device_type_id, device_id,
         canvas_instance_id, serial, user, password, hours,
         created_at, updated_at)
    VALUES (%s, %s, %s, %s, 'PENDING', 'admin', 'admin', 0, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
        device_type_id = VALUES(device_type_id),
        device_id      = VALUES(device_id),
        updated_at     = NOW()
"""

_EXPORT_CAMERA_UPDATE_SQL = """
    UPDATE cameras
    SET canvas_instance_id = %s,
        network_device_id = %s,
        updated_at = NOW()
    WHERE id = %s AND installation_id = %s
"""

_EXPORT_OTHER_UPDATE_SQL = """
    UPDATE other_devices
    SET canvas_instance_id = %s,
        updated_at = NOW()
    WHERE id = %s AND installation_id = %s
"""

_EXPORT_CAMERA_VIEW_UPDATE_SQL = """
    UPDATE views v
    JOIN cameras c
      ON c.id = v.camera_id
     AND c.deleted_at IS NULL
    SET v.View_name = %s,
        v.updated_at = NOW()
    WHERE c.installation_id = %s
      AND c.canvas_instance_id = %s
      AND v.installation_id = %s
      AND v.deleted_at IS NULL
"""

_EXPORT_CAMERA_VIEW_INSERT_SQL = """
    INSERT INTO views
        (camera_id, approved_user_id, installation_id, View_name, created_at, updated_at)
    SELECT
        c.id,
        COALESCE(i.it_lead_tech_id, i.project_owner),
        i.id,
        %s,
        NOW(),
        NOW()
    FROM cameras c
    JOIN installations i
      ON i.id = c.installation_id
     AND i.deleted_at IS NULL
    WHERE c.installation_id = %s
      AND c.canvas_instance_id = %s
      AND c.deleted_at IS NULL
      AND COALESCE(i.it_lead_tech_id, i.project_owner) IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM users u
          WHERE u.id = COALESCE(i.it_lead_tech_id, i.project_owner)
      )
      AND NOT EXISTS (
          SELECT 1
          FROM views v
          WHERE v.camera_id = c.id
            AND v.installation_id = i.id
            AND v.deleted_at IS NULL
      )
"""


def export_inventory_from_canvas(payload: dict, installation_id: int | None = None, site_id: int | None = None) -> dict:
    """
    Takes the full canvas snapshot and creates cameras / other_devices for the
    installation.

    Atómico (transaction.atomic) — un fallo no deja devices a medias.
    Los INSERT se ejecutan en lote (executemany): 2 round-trips en vez de N.

    Returns: { success, site_id, installation_id, created_cameras, created_other_devices, skipped }
    """
    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            if site_id and not installation_id:
                cur.execute(
                    "SELECT id FROM installations WHERE site_id = %s AND deleted_at IS NULL ORDER BY id DESC LIMIT 1",
                    [site_id],
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"No active installation found for site {site_id}.")
                installation_id = row[0]
            elif not installation_id:
                raise ValueError("Either installation_id or site_id is required.")

            cur.execute(
                "SELECT site_id FROM installations WHERE id = %s AND deleted_at IS NULL",
                [installation_id],
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Installation {installation_id} not found.")
            site_id = row[0]

            all_devices = [*payload.get("devices", []), *payload.get("indoorDevices", [])]
            camera_params: list[list] = []
            camera_update_params: list[list] = []
            camera_view_params: list[list] = []
            other_params: list[list] = []
            other_update_params: list[list] = []
            skipped: list[dict] = []

            # Validación por-item en Python (sin tocar la BD) — acumula skipped.
            for dev in all_devices:
                instance_id = dev.get("instanceId") or dev.get("id")
                if not instance_id:
                    skipped.append({"reason": "missing instanceId", "dev": dict(dev)})
                    continue

                catalog_raw = dev.get("catalogoId")
                inventory_id = dev.get("inventory_id")
                
                if not catalog_raw and not inventory_id:
                    skipped.append({"reason": "missing catalogoId or inventory_id", "instanceId": instance_id})
                    continue
                
                catalog_id = None
                if catalog_raw is not None:
                    try:
                        catalog_id = int(catalog_raw)
                    except (ValueError, TypeError):
                        skipped.append({"reason": f"catalogoId not int: {catalog_raw!r}", "instanceId": instance_id})
                        continue

                category = dev.get("category", "other")
                network_device_id = dev.get("networkDeviceId") or None
                view_name = dev.get("view_name")
                
                if inventory_id is not None:
                    # UPDATE existing physical device
                    if category == "camera":
                        camera_update_params.append([instance_id, network_device_id, inventory_id, installation_id])
                        if view_name:
                            camera_view_params.append([view_name, installation_id, instance_id, installation_id])
                    else:
                        other_update_params.append([instance_id, inventory_id, installation_id])
                else:
                    # INSERT new generic device
                    params = [installation_id, catalog_id, network_device_id, instance_id]
                    if category == "camera":
                        camera_params.append(params)
                        if view_name:
                            camera_view_params.append([view_name, installation_id, instance_id, installation_id])
                    else:
                        other_params.append(params)

            # Remove orphan rows that have no canvas_instance_id (pre-fix records)
            # so they don't accumulate alongside the properly-keyed UPSERT rows.
            cur.execute(
                "DELETE FROM cameras WHERE installation_id = %s AND canvas_instance_id IS NULL",
                [installation_id],
            )
            cur.execute(
                "DELETE FROM other_devices WHERE installation_id = %s AND canvas_instance_id IS NULL",
                [installation_id],
            )

            logger.warning(
                "[export] installation=%s site=%s cameras(ins=%s upd=%s) others(ins=%s upd=%s) skipped=%s",
                installation_id, site_id, len(camera_params), len(camera_update_params), len(other_params), len(other_update_params), len(skipped),
            )

            try:
                if camera_params:
                    cur.executemany(_EXPORT_CAMERA_SQL, camera_params)
                if camera_update_params:
                    cur.executemany(_EXPORT_CAMERA_UPDATE_SQL, camera_update_params)
                if camera_view_params:
                    cur.executemany(_EXPORT_CAMERA_VIEW_UPDATE_SQL, camera_view_params)
                    cur.executemany(
                        _EXPORT_CAMERA_VIEW_INSERT_SQL,
                        [[view_name, inst_id, canvas_instance] for view_name, inst_id, canvas_instance, _ in camera_view_params],
                    )
                if other_params:
                    cur.executemany(_EXPORT_OTHER_SQL, other_params)
                if other_update_params:
                    cur.executemany(_EXPORT_OTHER_UPDATE_SQL, other_update_params)
            except Exception as exc:
                # El atomic hace rollback automático al propagar — sin estado parcial.
                logger.exception("[export] batch INSERT falló (installation=%s)", installation_id)
                raise ValueError(f"No se pudieron exportar los dispositivos: {exc}") from exc

    # Fetch created devices and emit SSE events for real-time sync
    created_device_ids = []
    try:
        with connections[_DB].cursor() as cur:
            if camera_params:
                cur.execute(
                    "SELECT id FROM cameras WHERE installation_id = %s AND updated_at >= NOW() - INTERVAL 10 SECOND",
                    [installation_id],
                )
                for row in cur.fetchall():
                    created_device_ids.append(f"cam-{row[0]}")
            if other_params:
                cur.execute(
                    "SELECT id FROM other_devices WHERE installation_id = %s AND updated_at >= NOW() - INTERVAL 10 SECOND",
                    [installation_id],
                )
                for row in cur.fetchall():
                    created_device_ids.append(f"device-{row[0]}")
    except Exception as exc:
        logger.warning("[export] failed to fetch created devices for SSE: %s", exc)

    # Emit SSE events for all created/updated devices
    for device_id in created_device_ids:
        _publish_device_event("site_device_updated", site_id, device_id)

    return {
        "success": True,
        "site_id": site_id,
        "installation_id": installation_id,
        "created_cameras": len(camera_params),
        "created_other_devices": len(other_params),
        "skipped": skipped,
    }


def _serial_in_use(serial: str, exclude_prefix: str, exclude_pk: int) -> bool:
    """
    True if `serial` is already assigned to another *active* device
    (cameras or other_devices), excluding the device being updated.

    sigtools_beta is a shared legacy DB with soft-deletes, so uniqueness is
    enforced in the app (→ 409) rather than with a hard UNIQUE constraint that
    could clash with historical / soft-deleted rows. All values parameterized.
    """
    with connections[_DB].cursor() as cur:
        if exclude_prefix == "cam":
            cur.execute(
                "SELECT 1 FROM cameras WHERE serial = %s AND deleted_at IS NULL AND id <> %s LIMIT 1",
                [serial, exclude_pk],
            )
        else:
            cur.execute(
                "SELECT 1 FROM cameras WHERE serial = %s AND deleted_at IS NULL LIMIT 1",
                [serial],
            )
        if cur.fetchone():
            return True

        if exclude_prefix != "cam":
            cur.execute(
                "SELECT 1 FROM other_devices WHERE serial = %s AND deleted_at IS NULL AND id <> %s LIMIT 1",
                [serial, exclude_pk],
            )
        else:
            cur.execute(
                "SELECT 1 FROM other_devices WHERE serial = %s AND deleted_at IS NULL LIMIT 1",
                [serial],
            )
        return cur.fetchone() is not None


def update_device_serial(site_id: int, device_id: str, serial: str) -> None:
    """
    Update serial on a catalog device identified by the string device_id
    (e.g. 'cam-12', 'switch-5').

    Raises:
        ValueError    — device_id malformed or device not found for the site.
        ConflictError — serial already assigned to another active device (409).
    """
    prefix, _, raw_id = device_id.partition("-")
    try:
        pk = int(raw_id)
    except ValueError:
        raise ValueError(f"Invalid device_id format: {device_id!r}")

    # Serial uniqueness (app-level → 409). Skip the check for empty serials
    # (clearing a serial is allowed and many devices legitimately have none).
    if serial and serial.strip() and _serial_in_use(serial, prefix, pk):
        raise ConflictError(f"Serial '{serial}' is already assigned to another device.")

    with connections[_DB].cursor() as cur:
        if prefix == "cam":
            cur.execute(
                """
                UPDATE cameras c
                JOIN installations i ON c.installation_id = i.id
                SET c.serial = %s, c.updated_at = NOW()
                WHERE c.id = %s AND i.site_id = %s AND c.deleted_at IS NULL
                """,
                [serial, pk, site_id],
            )
        else:
            cur.execute(
                """
                UPDATE other_devices od
                JOIN installations i ON od.installation_id = i.id
                SET od.serial = %s, od.updated_at = NOW()
                WHERE od.id = %s AND i.site_id = %s AND od.deleted_at IS NULL
                """,
                [serial, pk, site_id],
            )
        if cur.rowcount == 0:
            raise ValueError(f"Device {device_id!r} not found for site {site_id}")

    _publish_device_event("site_device_updated", site_id, device_id, serial=serial)


# Columns on sigtools_beta.sites the API is allowed to edit. Used as an
# allowlist so column names are never taken from user input (values stay
# parameterized).
_SITE_EDITABLE_COLUMNS = (
    "name", "ip_address", "city", "state_code", "country_code",
    "address", "timezone", "monitored", "maintenance",
    "receive_notifications", "installation_date",
)


def update_site(site_id: int, data: dict) -> dict | None:
    """
    Update editable core fields on a sigtools_beta.sites row (raw SQL — the
    Site model is unmanaged/read-only). Only fields present in `data` and
    whitelisted in _SITE_EDITABLE_COLUMNS are written.

    Returns the updated site dict (SiteDetailSerializer shape), or None when
    the site does not exist / is soft-deleted.
    """
    from apps.installations import selectors

    # Existence check up front: MySQL UPDATE rowcount reflects *changed* rows,
    # so a no-op update (identical values) returns 0 even though the row exists.
    if selectors.get_site_or_404(site_id) is None:
        return None

    updates = {col: data[col] for col in _SITE_EDITABLE_COLUMNS if col in data}
    if updates:
        set_clause = ", ".join(f"{col} = %s" for col in updates)
        params = list(updates.values()) + [site_id]
        with connections[_DB].cursor() as cur:
            cur.execute(
                f"UPDATE sites SET {set_clause}, updated_at = NOW() "
                "WHERE id = %s AND deleted_at IS NULL",
                params,
            )
        cu.invalidate_dashboard()
        _rt_publish(CH_INSTALLATIONS, "site_updated", {"site_id": site_id, **updates})

    return selectors.get_site_detail(site_id)


def validate_topology(devices, connections) -> dict:
    """
    Validate a canvas network topology: loop detection + PoE budget + uplink
    bandwidth + port counts. Pure computation (no DB) — see
    apps.installations.topology for the algorithm and request contract.
    """
    from apps.installations import topology

    return topology.validate(list(devices), list(connections))


def create_indoor_map(site_id: int, image_file, label: str = "", uploaded_by: int | None = None):
    """
    Store an uploaded indoor floor-plan on MEDIA_ROOT and return the created
    SiteIndoorMap row. The FileField writes the file natively (no base64).
    """
    from apps.installations.models import SiteIndoorMap

    return SiteIndoorMap.objects.create(
        site_id=site_id,
        label=label or "",
        image=image_file,
        content_type=getattr(image_file, "content_type", "") or "",
        size_bytes=getattr(image_file, "size", 0) or 0,
        uploaded_by=uploaded_by,
    )


def delete_indoor_map(site_id: int, map_id: int) -> bool:
    """Delete an indoor map (row + file on disk). False if not found."""
    from apps.installations.models import SiteIndoorMap

    obj = SiteIndoorMap.objects.filter(site_id=site_id, pk=map_id).first()
    if obj is None:
        return False
    try:
        obj.image.delete(save=False)  # remove the file from MEDIA_ROOT
    except Exception as exc:
        logger.warning("[indoor-map] file delete failed for %s: %s", map_id, exc)
    obj.delete()
    return True


def delete_site(site_id: int) -> bool:
    """
    Soft-deletes a site and cascades to all its active installations.
    Returns False if the site was not found.
    """
    with connections[_DB].cursor() as cur:
        cur.execute(
            "UPDATE sites SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            [site_id],
        )
        if cur.rowcount == 0:
            return False
        cur.execute(
            "UPDATE installations SET deleted_at = NOW() WHERE site_id = %s AND deleted_at IS NULL",
            [site_id],
        )
    return True


# ---------------------------------------------------------------------------
# Installations / Projects
# ---------------------------------------------------------------------------

def create_installation(data: dict) -> int:
    """Creates a new installation container. Returns installation_id."""
    sql = """
        INSERT INTO installations
            (site_id, it_lead_tech_id, installation_type_id,
             inst_status_id, total_hours, created_at, updated_at)
        VALUES (%s, %s, %s, 1, 0.0, NOW(), NOW())
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [
            data["site_id"],
            data["it_lead_tech_id"],
            data["installation_type_id"],
        ])
        return cur.lastrowid


def delete_installation(inst_id: int) -> bool:
    """Soft-deletes an installation. Returns False if not found."""
    with connections[_DB].cursor() as cur:
        cur.execute(
            "UPDATE installations SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            [inst_id],
        )
        return cur.rowcount > 0


def sync_installation(inst_id: int, payload: dict) -> dict[str, int]:
    """
    Processes physical_changes for an installation:
    - Inserts added hardware (camera / core_device / other / server)
    - Soft-deletes removed hardware
    - Attempts to update visual_metadata (skips if column absent)

    Returns id_mapping: { temp_id → real_db_id }

    Atómico: si cualquier alta/baja falla, se revierte todo (sin estado parcial).
    """
    with transaction.atomic(using=_DB), connections[_DB].cursor() as cur:
        # Validate installation exists
        cur.execute(
            "SELECT site_id FROM installations WHERE id = %s AND deleted_at IS NULL",
            [inst_id],
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Installation not found")
        site_id: int = row[0]

        id_mapping: dict[str, int] = {}

        # --- 1. Process Added ---
        for item in payload.get("physical_changes", {}).get("added", []):
            new_id: int | None = None
            category = item.get("category")

            if category == "camera":
                model_id = item.get("model_id")
                device_id = item.get("network_device_id")
                if not model_id or not device_id:
                    raise ValueError("model_id and network_device_id required for camera")
                cur.execute(
                    """
                    INSERT INTO cameras
                        (installation_id, camera_model_id, device_id,
                         serial, user, password, hours, created_at, updated_at)
                    VALUES (%s, %s, %s, 'PENDING', 'admin', 'admin', 0, NOW(), NOW())
                    """,
                    [inst_id, model_id, device_id],
                )
                new_id = cur.lastrowid

            elif category == "other":
                type_id = item.get("type_id")
                device_id = item.get("network_device_id")
                if not type_id or not device_id:
                    raise ValueError("type_id and network_device_id required for other")
                cur.execute(
                    """
                    INSERT INTO other_devices
                        (installation_id, device_type_id, device_id,
                         serial, user, password, hours, created_at, updated_at)
                    VALUES (%s, %s, %s, 'PENDING', 'admin', 'admin', 0, NOW(), NOW())
                    """,
                    [inst_id, type_id, device_id],
                )
                new_id = cur.lastrowid

            elif category == "core_device":
                type_id = item.get("type_id")
                if not type_id:
                    raise ValueError("type_id required for core_device")
                cur.execute(
                    "SELECT device_type, brand, model FROM device_types WHERE id = %s",
                    [type_id],
                )
                dt_row = cur.fetchone()
                if not dt_row:
                    raise ValueError(f"device_type {type_id} not found")
                full_name = f"{dt_row[1]} {dt_row[2]}"
                valid_codes = {"Router", "PDU", "InterMapper", "Other"}
                enum_code = dt_row[0] if dt_row[0] in valid_codes else "Other"
                cur.execute(
                    """
                    INSERT INTO devices
                        (name, code, address, site_id, status, created_at, updated_at)
                    VALUES (%s, %s, '0.0.0.0', %s, 0, NOW(), NOW())
                    """,
                    [full_name, enum_code, site_id],
                )
                new_id = cur.lastrowid

            elif category == "server":
                vms_name = str(item.get("type_id", ""))
                if not vms_name:
                    raise ValueError("type_id (vms_name) required for server")
                valid_sys = {"Arteco", "ICRealtime", "Other"}
                enum_sys = vms_name if vms_name in valid_sys else "Other"
                cur.execute(
                    """
                    INSERT INTO servers
                        (name, `system`, vms_name, site_id, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 0, NOW(), NOW())
                    """,
                    [f"Server {vms_name}", enum_sys, vms_name, site_id],
                )
                new_id = cur.lastrowid

            if new_id and item.get("temp_id"):
                id_mapping[item["temp_id"]] = new_id

        # --- 2. Process Removed ---
        for removed in payload.get("physical_changes", {}).get("removed", []):
            table = _TABLE_MAP.get(removed.get("category"))
            if not table:
                raise ValueError(f"Invalid category: {removed.get('category')}")
            # Table name comes from an internal dict — safe from SQL injection
            cur.execute(
                f"UPDATE `{table}` SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                [removed["id"]],
            )

        # --- 3. Update visual_metadata if column exists ---
        v_meta = payload.get("visual_metadata", {})
        if v_meta and id_mapping:
            try:
                json_str = json.dumps(v_meta)
                for temp_id, real_id in id_mapping.items():
                    json_str = json_str.replace(f'"{temp_id}"', f'"{real_id}"')
                cur.execute(
                    "UPDATE installations SET visual_metadata = %s, updated_at = NOW() WHERE id = %s",
                    [json_str, inst_id],
                )
            except Exception as exc:
                # Column may not exist in this schema version — degradar sin romper,
                # pero dejar rastro para diagnóstico.
                logger.warning("sync_installation: no se pudo actualizar visual_metadata (inst=%s): %s", inst_id, exc)

    return id_mapping


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------

def delete_device(item_id: int, category: str) -> bool:
    """Soft-deletes a device by category. Returns False if not found."""
    table = _TABLE_MAP.get(category)
    if not table:
        raise ValueError(f"Invalid category: {category}")
    with connections[_DB].cursor() as cur:
        cur.execute(
            f"UPDATE `{table}` SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            [item_id],
        )
        return cur.rowcount > 0


def set_device_parent(device_id: int, parent_id: int | None) -> bool:
    """Sets or clears parent_id for a core_device. Returns False if not found."""
    with connections[_DB].cursor() as cur:
        cur.execute(
            "UPDATE devices SET parent_id = %s, updated_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            [parent_id, device_id],
        )
        return cur.rowcount > 0


def bulk_set_device_parent(inst_id: int, assignments: list[dict]) -> dict:
    """
    Assigns or clears parent_id for a batch of devices in one transaction.
    Returns { updated: int, skipped: [str] }.
    """
    updated = 0
    skipped: list[str] = []

    with connections[_DB].cursor() as cur:
        # Validate installation
        cur.execute(
            "SELECT site_id FROM installations WHERE id = %s AND deleted_at IS NULL",
            [inst_id],
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Installation not found")
        site_id: int = row[0]

        # Load core_devices for the site (valid parents + children)
        cur.execute(
            "SELECT id, code FROM devices WHERE site_id = %s AND deleted_at IS NULL",
            [site_id],
        )
        site_devices: dict[int, str] = {r[0]: r[1] for r in cur.fetchall()}

        # Load cameras and other_devices for this installation
        cur.execute(
            "SELECT id FROM cameras WHERE installation_id = %s AND deleted_at IS NULL",
            [inst_id],
        )
        inst_cameras: set[int] = {r[0] for r in cur.fetchall()}

        cur.execute(
            "SELECT id FROM other_devices WHERE installation_id = %s AND deleted_at IS NULL",
            [inst_id],
        )
        inst_others: set[int] = {r[0] for r in cur.fetchall()}

        for item in assignments:
            dev_id = item["device_id"]
            cat = item["category"]
            parent_id = item.get("parent_id")

            # Parent must be a core_device of the same site
            if parent_id is not None and parent_id not in site_devices:
                skipped.append(
                    f"{cat} {dev_id}: parent_id {parent_id} is not a core_device of site {site_id}"
                )
                continue

            if cat == "camera":
                if dev_id not in inst_cameras:
                    skipped.append(f"camera {dev_id}: not part of installation {inst_id}")
                    continue
                if parent_id is None:
                    skipped.append(f"camera {dev_id}: parent_id cannot be null for cameras")
                    continue
                cur.execute(
                    "UPDATE cameras SET device_id = %s, updated_at = NOW() WHERE id = %s",
                    [parent_id, dev_id],
                )
                updated += 1

            elif cat == "other":
                if dev_id not in inst_others:
                    skipped.append(f"other {dev_id}: not part of installation {inst_id}")
                    continue
                if parent_id is None:
                    skipped.append(f"other {dev_id}: parent_id cannot be null for other_devices")
                    continue
                cur.execute(
                    "UPDATE other_devices SET device_id = %s, updated_at = NOW() WHERE id = %s",
                    [parent_id, dev_id],
                )
                updated += 1

            elif cat == "core_device":
                if dev_id not in site_devices:
                    skipped.append(f"core_device {dev_id}: not part of site {site_id}")
                    continue
                if dev_id == parent_id:
                    skipped.append(f"core_device {dev_id}: cannot be its own parent")
                    continue
                # Try to update parent_id (column may not exist in this schema version)
                try:
                    cur.execute(
                        "UPDATE devices SET parent_id = %s, updated_at = NOW() WHERE id = %s",
                        [parent_id, dev_id],
                    )
                    updated += 1
                except Exception:
                    skipped.append(f"core_device {dev_id}: parent_id column not available")
            else:
                skipped.append(f"device {dev_id}: unknown category '{cat}'")

    return {"updated": updated, "skipped": skipped}


# ===========================================================================
# sig_projects (default DB — Django ORM)
# ===========================================================================

def _project_to_dict(p) -> dict:
    user_map = _sigtools_users_by_ids(
        {uid for uid in [getattr(p, "created_by", None), getattr(p, "approval_requested_by", None)] if uid is not None}
    )
    return {
        "id": str(p.id),
        "name": p.name,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "version": p.version,
        "created_by": p.created_by,
        "created_by_name": user_map.get(p.created_by, {}).get("name"),
        "approval_status": getattr(p, "approval_status", "draft"),
        "approval_requested_by": p.approval_requested_by,
        "approval_requested_by_name": user_map.get(p.approval_requested_by, {}).get("name"),
        "data": p.data,
    }


def _publish_project(p_dict: dict) -> None:
    _rt_publish(CH_PROJECTS, "project_updated", [{
        "id":      p_dict["id"],
        "name":    p_dict["name"],
        "version": p_dict["version"],
    }])


@transaction.atomic
def create_sig_project(project_id: str | None, name: str, data: dict, created_by: int | None = None) -> dict:
    """
    Creates a SigProject. Frontend may supply its own UUID.
    Raises ConflictError if the UUID already exists.
    """
    from apps.installations.models import SigProject

    pk = project_id or str(uuid.uuid4())
    if SigProject.objects.filter(pk=pk).exists():
        raise ConflictError("A project with this ID already exists.")
    p = SigProject.objects.create(
        id=pk,
        name=name,
        data=data,
        version=1,
        created_by=created_by,
        approval_status="draft",
    )
    result = _project_to_dict(p)
    transaction.on_commit(lambda: _publish_project(result))
    return result


@transaction.atomic
def update_sig_project(
    project_id: str,
    name: str,
    data: dict,
    expected_version: int,
) -> tuple[dict | None, dict | None]:
    """
    Optimistic-concurrency update.
    Returns (updated_project, None) on success.
    Returns (None, conflict_project)  on version mismatch.
    Returns (None, None)              if not found.
    """
    from apps.installations.models import SigProject

    try:
        p = SigProject.objects.select_for_update().get(pk=project_id)
    except SigProject.DoesNotExist:
        return None, None

    if p.version != expected_version:
        return None, _project_to_dict(p)

    p.name = name
    p.data = data
    p.version = p.version + 1
    p.save()
    result = _project_to_dict(p)
    transaction.on_commit(lambda: _publish_project(result))
    return result, None


def delete_sig_project(project_id: str) -> bool:
    """Hard-deletes a SigProject. Returns False if not found."""
    from apps.installations.models import SigProject

    deleted_count, _ = SigProject.objects.filter(pk=project_id).delete()
    return deleted_count > 0


def rename_sig_project(project_id: str, name: str) -> dict | None:
    """
    Updates only the name field — does NOT bump version.
    Returns the updated project dict, or None if not found.
    """
    from apps.installations.models import SigProject

    rows_updated = SigProject.objects.filter(pk=project_id).update(name=name)
    if not rows_updated:
        return None
    try:
        p = SigProject.objects.get(pk=project_id)
    except SigProject.DoesNotExist:
        return None
    result = _project_to_dict(p)
    _publish_project(result)
    return result


@transaction.atomic
def request_sig_project_approval(
    *,
    project_id: str,
    requested_by: int | None,
    note: str = "",
) -> dict | None:
    from apps.installations.models import SigProject

    try:
        project = SigProject.objects.select_for_update().get(pk=project_id)
    except SigProject.DoesNotExist:
        return None

    project.approval_status = "pending_approval"
    project.approval_requested_by = requested_by
    project.save(update_fields=["approval_status", "approval_requested_by", "updated_at"])

    result = _project_to_dict(project)
    requester_name = _sigtools_users_by_ids({requested_by}).get(requested_by, {}).get("name") if requested_by else None

    transaction.on_commit(
        lambda: _notify_project_approval_requested(project=result, requester_name=requester_name, note=note),
    )
    transaction.on_commit(lambda: _publish_project(result))
    return result


@transaction.atomic
def cancel_sig_project_approval(
    *,
    project_id: str,
    requested_by: int | None,
    note: str = "",
) -> dict | None:
    from apps.installations.models import SigProject

    try:
        project = SigProject.objects.select_for_update().get(pk=project_id)
    except SigProject.DoesNotExist:
        return None

    project.approval_status = "draft"
    project.approval_requested_by = None
    project.save(update_fields=["approval_status", "approval_requested_by", "updated_at"])

    result = _project_to_dict(project)
    requester_name = _sigtools_users_by_ids({requested_by}).get(requested_by, {}).get("name") if requested_by else None

    transaction.on_commit(
        lambda: _notify_project_approval_cancelled(project=result, requester_name=requester_name, note=note),
    )
    transaction.on_commit(lambda: _publish_project(result))
    return result


# ===========================================================================
# Admin — sigtools_beta (users, app_roles, permissions)
# ===========================================================================

_ADMIN_DB = "sigtools"


def _resolve_role_ids(cursor, role_names: list[str]) -> list[str]:
    """Returns list of role IDs for given role names."""
    if not role_names:
        return []
    placeholders = ",".join(["%s"] * len(role_names))
    cursor.execute(
        f"SELECT id FROM app_roles WHERE name IN ({placeholders})",  # noqa: S608
        role_names,
    )
    return [row[0] for row in cursor.fetchall()]


def _resolve_permission_ids(cursor, permission_keys: list[str]) -> list[str]:
    """Returns list of permission IDs for given permission keys."""
    if not permission_keys:
        return []
    placeholders = ",".join(["%s"] * len(permission_keys))
    cursor.execute(
        f"SELECT id FROM permissions WHERE `key` IN ({placeholders})",  # noqa: S608
        permission_keys,
    )
    return [row[0] for row in cursor.fetchall()]


def create_admin_user(
    username: str,
    password: str,
    full_name: str,
    role_names: list[str],
) -> dict:
    """
    Inserts a user into sigtools_beta.users and assigns roles.
    Raises ConflictError if username already exists.
    """
    from apps.installations import selectors

    email = f"{username}@sig.systems"
    hashed_pw = make_password(password)

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE username = %s AND deleted_at IS NULL",
                [username],
            )
            if cur.fetchone():
                raise ConflictError("A user with this username already exists.")

            cur.execute(
                """
                INSERT INTO users (name, email, username, password, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                """,
                [full_name, email, username, hashed_pw],
            )
            user_id = cur.lastrowid

            role_ids = _resolve_role_ids(cur, role_names)
            for rid in role_ids:
                cur.execute(
                    """
                    INSERT INTO user_app_roles (user_id, role_id, granted_at)
                    VALUES (%s, %s, NOW())
                    """,
                    [user_id, rid],
                )

    return selectors.fetch_admin_user(user_id)


def update_admin_user(
    user_id: int,
    full_name: str | None,
    role_names: list[str] | None,
    is_active: bool | None = None,
) -> dict | None:
    """
    Updates user profile and/or replaces role assignments.
    is_active=False soft-deletes; is_active=True restores.
    Returns None if user not found.
    """
    from apps.installations import selectors

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id = %s", [user_id])
            if not cur.fetchone():
                return None

            if full_name is not None:
                cur.execute(
                    "UPDATE users SET name = %s, updated_at = NOW() WHERE id = %s",
                    [full_name, user_id],
                )

            if is_active is False:
                cur.execute(
                    "UPDATE users SET deleted_at = NOW(), updated_at = NOW() WHERE id = %s AND deleted_at IS NULL",
                    [user_id],
                )
            elif is_active is True:
                cur.execute(
                    "UPDATE users SET deleted_at = NULL, updated_at = NOW() WHERE id = %s",
                    [user_id],
                )

            if role_names is not None:
                cur.execute("DELETE FROM user_app_roles WHERE user_id = %s", [user_id])
                role_ids = _resolve_role_ids(cur, role_names)
                for rid in role_ids:
                    cur.execute(
                        """
                        INSERT INTO user_app_roles (user_id, role_id, granted_at)
                        VALUES (%s, %s, NOW())
                        """,
                        [user_id, rid],
                    )

    return selectors.fetch_admin_user(user_id)


def deactivate_admin_user(user_id: int) -> bool:
    """Soft-deletes a user (sets deleted_at). Returns False if not found or already inactive."""
    with connections[_ADMIN_DB].cursor() as cur:
        cur.execute(
            "UPDATE users SET deleted_at = NOW(), updated_at = NOW() WHERE id = %s AND deleted_at IS NULL",
            [user_id],
        )
        return cur.rowcount > 0


def create_admin_role(
    name: str,
    label: str,
    description: str,
    color: str,
    permission_keys: list[str],
) -> dict:
    """
    Inserts a role into sigtools_beta.app_roles and assigns permissions.
    Raises ConflictError if name already exists.
    """
    from apps.installations import selectors

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute("SELECT id FROM app_roles WHERE name = %s", [name])
            if cur.fetchone():
                raise ConflictError("A role with this name already exists.")

            cur.execute(
                """
                INSERT INTO app_roles (name, label, description, color, is_system, created_at)
                VALUES (%s, %s, %s, %s, 0, NOW())
                """,
                [name, label, description, color],
            )
            role_id = cur.lastrowid

            perm_ids = _resolve_permission_ids(cur, permission_keys)
            for pid in perm_ids:
                cur.execute(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (%s, %s)
                    """,
                    [role_id, pid],
                )

    return selectors.fetch_admin_role(role_id)


def update_admin_role(
    role_id: int,
    label: str | None,
    description: str | None,
    color: str | None,
    permission_keys: list[str] | None,
) -> dict | None:
    """
    Updates role metadata and/or replaces permission assignments.
    Returns None if not found.
    """
    from apps.installations import selectors

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute("SELECT id FROM app_roles WHERE id = %s", [role_id])
            row = cur.fetchone()
            if not row:
                return None

            set_clauses: list[str] = []
            params: list = []
            if label is not None:
                set_clauses.append("label = %s")
                params.append(label)
            if description is not None:
                set_clauses.append("description = %s")
                params.append(description)
            if color is not None:
                set_clauses.append("color = %s")
                params.append(color)

            if set_clauses:
                params.append(role_id)
                cur.execute(
                    f"UPDATE app_roles SET {', '.join(set_clauses)} WHERE id = %s",  # noqa: S608
                    params,
                )

            if permission_keys is not None:
                cur.execute("DELETE FROM role_permissions WHERE role_id = %s", [role_id])
                perm_ids = _resolve_permission_ids(cur, permission_keys)
                for pid in perm_ids:
                    cur.execute(
                        """
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (%s, %s)
                        """,
                        [role_id, pid],
                    )

    return selectors.fetch_admin_role(role_id)


def delete_admin_role(role_id: int) -> bool | str:
    """
    Deletes a role and its assignments.
    Returns 'system' if the role is protected (is_system=true).
    Returns False if not found.
    Returns True on success.
    """
    with connections[_ADMIN_DB].cursor() as cur:
        cur.execute("SELECT id, is_system FROM app_roles WHERE id = %s", [role_id])
        row = cur.fetchone()
        if not row:
            return False
        if row[1]:  # is_system flag
            return "system"

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute("DELETE FROM role_permissions WHERE role_id = %s", [role_id])
            cur.execute("DELETE FROM user_app_roles WHERE role_id = %s", [role_id])
            cur.execute("DELETE FROM app_roles WHERE id = %s", [role_id])

    return True


# ---------------------------------------------------------------------------
# Dispatch / Receipt / Installation services (sig_dailylogs — default DB)
# ---------------------------------------------------------------------------

from django.utils import timezone as _tz  # noqa: E402

from apps.installations.models import SiteDeviceDispatch, SiteDeviceLog  # noqa: E402


def _publish_dispatch(dispatch: "SiteDeviceDispatch") -> None:
    _rt_publish(CH_INSTALLATIONS, "dispatch_updated", [{
        "site_id":      dispatch.site_id,
        "device_id":    dispatch.device_id,
        "installed":    dispatch.installed,
        "qty_received": dispatch.qty_received,
        "qty_sent":     dispatch.qty_sent,
    }])


def _publish_device_event(event: str, site_id: int, device_id: str, **extra) -> None:
    """
    Evento nombrado de dispositivo (device_received / device_installed /
    site_device_updated). El frontend lo reenvía a un window-event y refresca.

    Se publica en AMBOS canales (inventory e installations) para que llegue
    sin importar a cuál stream esté suscrito el syncBus del front. Es barato
    (~1ms por canal) y el front hace debounce de duplicados.

    Lleva el ESTADO COMPLETO del dispositivo (no solo un "ping"), y
    `{site_id, device_id}` siempre presentes para clientes que solo usan eso.
    """
    payload = {"site_id": site_id, "device_id": device_id, **extra}
    _rt_publish(CH_INVENTORY, event, payload)
    _rt_publish(CH_INSTALLATIONS, event, payload)


def _dispatch_state(d: "SiteDeviceDispatch") -> dict:
    """Snapshot serializable del estado de despacho/recepción/instalación."""
    return {
        "qty_sent":          d.qty_sent,
        "vendor":            d.vendor,
        "tracking":          d.tracking,
        "observations":      d.observations,
        "dispatched_at":     d.dispatched_at.isoformat() if d.dispatched_at else None,
        "qty_received":      d.qty_received,
        "received_at":       d.received_at.isoformat() if d.received_at else None,
        "receipt_photo_url": d.receipt_photo_url,
        "installed":         d.installed,
        "installed_at":      d.installed_at.isoformat() if d.installed_at else None,
        "install_photo_url": d.install_photo_url,
    }


def upsert_device_dispatch(
    site_id: int, device_id: str, actor_user_id: int | None = None, **fields
) -> SiteDeviceDispatch:
    qty_sent = fields.get("qty_sent")
    dispatch, _ = SiteDeviceDispatch.objects.update_or_create(
        site_id=site_id,
        device_id=device_id,
        defaults=fields,
    )
    _publish_dispatch(dispatch)
    _publish_device_event("site_device_updated", site_id, device_id, **_dispatch_state(dispatch))
    cu.invalidate_dashboard()
    _notify_dispatch_created(
        site_id=site_id,
        device_id=device_id,
        qty_sent=qty_sent,
        actor_user_id=actor_user_id,
    )
    return dispatch


def confirm_device_receipt(
    site_id: int,
    device_id: str,
    qty_received: int,
    receipt_notes: str,
    receipt_photo_url: str,
) -> SiteDeviceDispatch:
    dispatch, _ = SiteDeviceDispatch.objects.update_or_create(
        site_id=site_id,
        device_id=device_id,
        defaults={
            "qty_received":      qty_received,
            "received_at":       _tz.now(),
            "receipt_notes":     receipt_notes,
            "receipt_photo_url": receipt_photo_url,
        },
    )
    _publish_dispatch(dispatch)
    _publish_device_event("device_received", site_id, device_id, **_dispatch_state(dispatch))
    cu.invalidate_dashboard()
    return dispatch


def mark_device_installed(
    site_id: int,
    device_id: str,
    install_notes: str,
    install_photo_url: str,
) -> SiteDeviceDispatch:
    dispatch, _ = SiteDeviceDispatch.objects.update_or_create(
        site_id=site_id,
        device_id=device_id,
        defaults={
            "installed":         True,
            "installed_at":      _tz.now(),
            "install_notes":     install_notes,
            "install_photo_url": install_photo_url,
        },
    )
    _publish_dispatch(dispatch)
    _publish_device_event("device_installed", site_id, device_id, **_dispatch_state(dispatch))
    cu.invalidate_dashboard()
    return dispatch


def log_device_activity(
    site_id: int,
    device_id: str,
    action: str,
    user_id: int | None,
    notes: str = "",
) -> SiteDeviceLog:
    log = SiteDeviceLog.objects.create(
        site_id=site_id,
        device_id=device_id,
        action=action,
        user_id=user_id,
        notes=notes,
    )
    _rt_publish(CH_INSTALLATIONS, "activity_logged", [
        {"site_id": log.site_id, "device_id": log.device_id, "action": log.action}
    ])
    return log


# ---------------------------------------------------------------------------
# IT Test (sig_dailylogs — default DB)
# ---------------------------------------------------------------------------

def upsert_it_test(site_id: int, data: dict):
    """Create or update the ItSiteTest record for a site."""
    from apps.installations.models import ItSiteTest
    allowed_fields = {
        "references", "camera_flags", "checklist", "grade",
        "summary", "delays", "attachments", "date",
        "start_time", "end_time", "technicians", "it_personnel",
    }
    defaults = {k: v for k, v in data.items() if k in allowed_fields}
    obj, _ = ItSiteTest.objects.update_or_create(site_id=site_id, defaults=defaults)
    return obj


# ---------------------------------------------------------------------------
# Notifications (in-app)
# ---------------------------------------------------------------------------

def mark_notification_read(*, notification_id: int, recipient_id: int) -> bool:
    """Mark a single notification as read. Returns False if not found / not owner."""
    from apps.installations.models import Notification

    updated = Notification.objects.filter(id=notification_id, recipient_id=recipient_id).update(is_read=True)
    return updated > 0


def mark_all_notifications_read(*, recipient_id: int) -> int:
    """Mark all unread notifications for a user as read. Returns count updated."""
    from apps.installations.models import Notification

    return Notification.objects.filter(recipient_id=recipient_id, is_read=False).update(is_read=True)
