"""
Services — business logic for the Installations API.
Write operations use raw SQL directly on 'sigtools' connection
to avoid model field mapping issues with unmanaged tables.
"""
from __future__ import annotations

import json
import logging
import re
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
    # Admin membership lives in the app-level RBAC tables (user_app_roles / app_roles),
    # which is what /me and the admin panel use — NOT the legacy user_roles/roles.
    sql = """
        SELECT DISTINCT u.email
        FROM users u
        JOIN user_app_roles uar ON uar.user_id = u.id
        JOIN app_roles ar ON ar.id = uar.role_id
        WHERE u.deleted_at IS NULL
          AND u.email IS NOT NULL
          AND u.email <> ''
          AND ar.name = 'Admin'
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def _sigtools_admin_user_ids() -> list[int]:
    """Return user IDs of all Admin-role sigtools users (for in-app notifications)."""
    # Must match the RBAC source used by auth (user_app_roles / app_roles); querying
    # the legacy user_roles/roles returned no admins, so approval notifications were
    # never created.
    sql = """
        SELECT DISTINCT u.id
        FROM users u
        JOIN user_app_roles uar ON uar.user_id = u.id
        JOIN app_roles ar ON ar.id = uar.role_id
        WHERE u.deleted_at IS NULL
          AND ar.name = 'Admin'
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
        # Realtime ping (no polling): every connected client refetches ITS OWN
        # notifications. We broadcast no content per channel, so nothing leaks
        # between users — the FE filters by the authenticated recipient.
        _rt_publish(CH_INSTALLATIONS, "notifications_changed", {})
        _rt_publish(CH_INVENTORY, "notifications_changed", {})
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


def _notify_project_approval_cancelled(
    *,
    project: dict,
    requester_id: int | None,
    canceller_name: str | None,
    note: str,
) -> None:
    # The cancellation notice goes to the user who ORIGINALLY requested approval
    # (so they learn it was cancelled) — NOT to the admins.
    if not requester_id:
        return

    requester = _sigtools_users_by_ids({requester_id}).get(requester_id, {})
    requester_email = requester.get("email")

    safe_name = escape(project.get("name") or "(sin nombre)")
    safe_canceller = escape(canceller_name or "Un administrador")
    safe_note = escape(note or "")

    if requester_email:
        html = (
            f"<p>Tu solicitud de aprobación para el proyecto GIS <b>{safe_name}</b> fue cancelada.</p>"
            f"<p>Cancelada por: <b>{safe_canceller}</b></p>"
        )
        if safe_note:
            html += f"<p>Nota: {safe_note}</p>"
        _send_graph_mail_safe(
            to_emails=[requester_email],
            subject=f"[Installations] Tu solicitud de aprobación fue cancelada: {project.get('name')}",
            html_content=html,
        )

    _create_notifications_bulk(
        recipient_ids=[requester_id],
        title=f"Solicitud cancelada: {project.get('name', '')}",
        message=(
            f"Tu solicitud de aprobación para el proyecto '{project.get('name', '')}' fue cancelada"
            f"{(' por ' + canceller_name) if canceller_name else ''}."
            f"{(' Nota: ' + note) if note else ''}"
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
# Recipient resolvers (by app_role) + technician assignment
# ---------------------------------------------------------------------------

def _role_user_ids(role_names: list[str]) -> list[int]:
    """User IDs for any of the given app_role names (collation = case-insensitive)."""
    if not role_names:
        return []
    placeholders = ",".join(["%s"] * len(role_names))
    sql = f"""
        SELECT DISTINCT u.id
        FROM users u
        JOIN user_app_roles uar ON uar.user_id = u.id
        JOIN app_roles ar ON ar.id = uar.role_id
        WHERE u.deleted_at IS NULL AND ar.name IN ({placeholders})
    """  # noqa: S608
    with connections[_DB].cursor() as cur:
        cur.execute(sql, role_names)
        return [row[0] for row in cur.fetchall()]


def _inventory_operator_user_ids() -> list[int]:
    """Admins + Inventory Operators — recipients of inventory-intake notices."""
    return _role_user_ids(["admin", "inventory_op"])


def _emails_for_user_ids(user_ids) -> list[str]:
    user_map = _sigtools_users_by_ids({int(u) for u in user_ids if u})
    return sorted({u["email"] for u in user_map.values() if u.get("email")})


def _latest_installation_id(site_id: int) -> int | None:
    sql = "SELECT id FROM installations WHERE site_id = %s AND deleted_at IS NULL ORDER BY id DESC LIMIT 1"
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [site_id])
        row = cur.fetchone()
    return row[0] if row else None


def get_site_technicians(*, site_id: int) -> list[dict]:
    """Technicians assigned to a site's latest installation (it_installation_responsibles)."""
    inst_id = _latest_installation_id(site_id)
    if not inst_id:
        return []
    sql = """
        SELECT u.id, u.username, u.name, u.email
        FROM it_installation_responsibles itr
        JOIN users u ON u.id = itr.user_id
        WHERE itr.installation_id = %s AND u.deleted_at IS NULL
        ORDER BY u.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [inst_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def set_site_technicians(*, site_id: int, user_ids: list[int], assigned_by_id: int | None = None) -> list[dict] | None:
    """
    Replace the technicians assigned to a site's latest installation (reuses the
    existing it_installation_responsibles table — no schema change). Notifies the
    newly assigned technicians (in-app + email) and emits a realtime event so the
    Inventory mobile app updates the technician's site list. Returns the new
    technician list, or None if the site has no installation.
    """
    from apps.core import cache_utils as cu

    inst_id = _latest_installation_id(site_id)
    if not inst_id:
        return None

    existing = {t["id"] for t in get_site_technicians(site_id=site_id)}
    clean_ids = sorted({int(u) for u in user_ids if u})

    with transaction.atomic(using=_DB):
        with connections[_DB].cursor() as cur:
            cur.execute("DELETE FROM it_installation_responsibles WHERE installation_id = %s", [inst_id])
            for uid in clean_ids:
                cur.execute(
                    "INSERT INTO it_installation_responsibles (user_id, installation_id, created_at, updated_at) "
                    "VALUES (%s, %s, NOW(), NOW())",
                    [uid, inst_id],
                )

    # The dashboard's it_manager column derives from this table — refresh cache.
    cu.invalidate("inst:sites_dashboard")
    _rt_publish(CH_INSTALLATIONS, "site_technicians_changed", {"site_id": site_id, "user_ids": clean_ids})
    _rt_publish(CH_INVENTORY, "site_technicians_changed", {"site_id": site_id, "user_ids": clean_ids})

    # Only notify the technicians newly added (not those who were already assigned).
    newly_assigned = [uid for uid in clean_ids if uid not in existing]
    if newly_assigned:
        _notify_technicians_assigned(site_id=site_id, technician_ids=newly_assigned, assigned_by_id=assigned_by_id)

    return get_site_technicians(site_id=site_id)


def list_assigned_sites(*, user_id: int) -> list[dict]:
    """Sites where the user is an installation responsible or the lead tech."""
    sql = """
        SELECT DISTINCT s.id, s.name
        FROM sites s
        JOIN installations i ON i.site_id = s.id AND i.deleted_at IS NULL
        LEFT JOIN it_installation_responsibles itr ON itr.installation_id = i.id
        WHERE s.deleted_at IS NULL
          AND (itr.user_id = %s OR i.it_lead_tech_id = %s)
        ORDER BY s.name
    """
    with connections[_DB].cursor() as cur:
        cur.execute(sql, [user_id, user_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _notify_technicians_assigned(*, site_id: int, technician_ids: list[int], assigned_by_id: int | None) -> None:
    """In-app + email notice to technicians newly assigned to a site."""
    if not technician_ids:
        return
    with connections[_DB].cursor() as cur:
        cur.execute("SELECT name FROM sites WHERE id = %s", [site_id])
        row = cur.fetchone()
    site_name = row[0] if row else f"site {site_id}"

    lookup = set(technician_ids) | ({assigned_by_id} if assigned_by_id else set())
    user_map = _sigtools_users_by_ids(lookup)
    assigned_by_name = user_map.get(assigned_by_id, {}).get("name") or "Un administrador"

    _create_notifications_bulk(
        recipient_ids=technician_ids,
        title=f"Asignado a instalación: {site_name}",
        message=(
            f"Fuiste asignado para instalar/dar servicio al sitio '{site_name}' "
            f"por {assigned_by_name}. Revisa tus sitios en Inventory móvil."
        ),
        notif_type="technician_assigned",
    )

    emails = sorted({
        user_map[uid]["email"]
        for uid in technician_ids
        if uid in user_map and user_map[uid].get("email")
    })
    if emails:
        html = (
            f"<p>Fuiste asignado para instalar / dar servicio al sitio <b>{escape(str(site_name))}</b>.</p>"
            f"<p>Asignado por: <b>{escape(str(assigned_by_name))}</b></p>"
            f"<p>Abre <b>Inventory móvil</b> para ver tus tareas asignadas.</p>"
        )
        _send_graph_mail_safe(
            to_emails=emails,
            subject=f"[SIG] Asignado a instalación: {site_name}",
            html_content=html,
        )


def _notify_site_to_inventory(*, site_id, site_name: str, actor_user_id: int | None) -> None:
    """In-app + email notice to Admins + Inventory Operators that a new site
    landed in the system and needs equipment prepared/dispatched."""
    recipients = _inventory_operator_user_ids()
    if not recipients:
        return
    actor_name = "Un usuario"
    if actor_user_id:
        actor_name = _sigtools_users_by_ids({int(actor_user_id)}).get(int(actor_user_id), {}).get("name") or actor_name

    _create_notifications_bulk(
        recipient_ids=recipients,
        title=f"Nuevo sitio en inventario: {site_name}",
        message=(
            f"El sitio '{site_name}' (id {site_id}) fue enviado a instalaciones/inventario "
            f"por {actor_name}. Prepara y despacha el equipo correspondiente."
        ),
        notif_type="inventory_intake",
    )

    emails = _emails_for_user_ids(recipients)
    if emails:
        html = (
            f"<p>El sitio <b>{escape(str(site_name))}</b> (id {site_id}) fue enviado a "
            f"instalaciones / inventario por <b>{escape(str(actor_name))}</b>.</p>"
            f"<p>Prepara y despacha el equipo correspondiente desde Inventory.</p>"
        )
        _send_graph_mail_safe(
            to_emails=emails,
            subject=f"[SIG] Nuevo sitio en inventario: {site_name}",
            html_content=html,
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
        # 1. Resolve Pending status ID
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Pending' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Pending status not found in inst_statuses")
            active_status_id: int = row[0]

        # 2. Insert site
        # Site enters the installation phase on creation → lifecycle = Installing.
        site_sql = """
            INSERT INTO sites
                (name, customer_group_id, ip_address, teams_channelid, teams_teamid,
                 address, city, state_code, country_code,
                 site_status_id,
                 monitored, maintenance, receive_notifications,
                 cameras_count, total_devices, devices_down,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    (SELECT id FROM site_statuses WHERE LOWER(status_name) = 'installing' LIMIT 1),
                    1, 1, 1, 0, 0, 0, NOW(), NOW())
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
            result = dict(zip(cols, record))

    # Post-commit: a new site is now in the system → notify inventory operators
    # so they can prepare/dispatch equipment. Best-effort (never blocks creation).
    try:
        _notify_site_to_inventory(
            site_id=result.get("site_id"),
            site_name=result.get("site_name") or f"site {result.get('site_id')}",
            actor_user_id=data.get("created_by") or data.get("project_owner"),
        )
    except Exception:
        logger.exception("notify_site_to_inventory failed for site %s", result.get("site_id"))
    return result


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
        # 1. Resolve Pending status ID
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Pending' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Pending status not found in inst_statuses")
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

            # Entering the installation phase → site lifecycle status = Installing.
            # Resolved by name so it survives id reordering in site_statuses.
            cur.execute(
                "SELECT id FROM site_statuses WHERE LOWER(status_name) = 'installing' LIMIT 1"
            )
            _ss = cur.fetchone()
            installing_status_id = _ss[0] if _ss else (ps["site_status_id"] or 1)

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
                    installing_status_id,
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

    with transaction.atomic(using=_DB):
        # 1. Resolve Pending status ID
        with connections[_DB].cursor() as cur:
            cur.execute("SELECT id FROM inst_statuses WHERE name = 'Pending' LIMIT 1")
            row = cur.fetchone()
            if row is None:
                raise ValueError("Pending status not found in inst_statuses")
            active_status_id: int = row[0]

        # Resolve the SITE lifecycle status for the shadow site. The client sends
        # a status NAME (defaults to "Installing" — a site sent to installation
        # enters that phase). We resolve it against site_statuses by name; if the
        # name is unknown we fall back to Installing, then to id 1.
        requested_status = (data.get("status") or "Installing").strip()
        with connections[_DB].cursor() as cur:
            cur.execute(
                "SELECT id FROM site_statuses WHERE LOWER(status_name) = LOWER(%s) LIMIT 1",
                [requested_status],
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "SELECT id FROM site_statuses WHERE LOWER(status_name) = 'installing' LIMIT 1"
                )
                row = cur.fetchone()
            site_status_id: int = row[0] if row else 1

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
                    site_status_id,
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


def _assign_canonical_numbering(
    all_devices: list[dict],
    installation_id: int,
    cur,
) -> tuple[dict[str, dict], list[str]]:
    """
    For camera devices in the payload, determine a collision-free CAM NN view_name
    against the existing views already in the DB for this installation.
    Cameras that collide with existing rows (by a different canvas_instance_id)
    get the next free sequential number.

    Returns:
      numbering  — {instanceId: {numero: int, view_name: str}} for every camera
      renumbered — [instanceId, ...] for cameras whose number actually changed
    """
    camera_devices = [d for d in all_devices if d.get("category") == "camera"]
    if not camera_devices:
        return {}, []

    canvas_ids = [d.get("instanceId") or d.get("id") for d in camera_devices]
    placeholders = ",".join(["%s"] * len(canvas_ids))
    # Fetch existing View_name values that will NOT be overwritten by this export
    cur.execute(
        f"SELECT v.View_name FROM views v "
        f"JOIN cameras c ON c.id = v.camera_id AND c.deleted_at IS NULL "
        f"WHERE c.installation_id = %s "
        f"  AND (c.canvas_instance_id IS NULL OR c.canvas_instance_id NOT IN ({placeholders})) "
        f"  AND v.deleted_at IS NULL",
        [installation_id, *canvas_ids],
    )
    taken: set[int] = set()
    for (vn,) in cur.fetchall():
        m = re.search(r"\d+", vn or "")
        if m:
            taken.add(int(m.group()))

    sorted_cams = sorted(camera_devices, key=lambda d: int(d.get("numero") or 0))
    numbering: dict[str, dict] = {}
    renumbered: list[str] = []
    used: set[int] = set()
    _next = [1]

    def next_free() -> int:
        while _next[0] in taken or _next[0] in used:
            _next[0] += 1
        n = _next[0]
        _next[0] += 1
        return n

    for dev in sorted_cams:
        iid = dev.get("instanceId") or dev.get("id")
        requested = int(dev.get("numero") or 0)
        orig_m = re.search(r"\d+", dev.get("view_name") or "")
        orig_n = int(orig_m.group()) if orig_m else 0

        if requested > 0 and requested not in taken and requested not in used:
            final_n = requested
        else:
            final_n = next_free()

        used.add(final_n)
        canonical_vn = f"CAM {final_n:02d}"
        numbering[iid] = {"numero": final_n, "view_name": canonical_vn}
        if orig_n != final_n:
            renumbered.append(iid)

    return numbering, renumbered


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

            design_mode = bool(payload.get("design_mode", True))
            all_devices = [*payload.get("devices", []), *payload.get("indoorDevices", [])]
            # Derive view_name server-side for simplified payloads that omit it
            for dev in all_devices:
                if not dev.get("view_name"):
                    prefix = "cam" if dev.get("category") == "camera" else "dev"
                    num = dev.get("numero") or 0
                    label = dev.get("displayLabel") or dev.get("display_label")
                    dev["view_name"] = (
                        f"{prefix} {num}" if design_mode or not label else label
                    )
            numbering, renumbered = _assign_canonical_numbering(all_devices, installation_id, cur)
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
                view_name = numbering.get(instance_id, {}).get("view_name") or dev.get("view_name")
                
                if inventory_id is not None:
                    # UPDATE existing physical device — only claim the canvas link
                    # (canvas_instance_id). Do NOT touch device_id here: it points
                    # to the network host that holds the IP, and the IP pass below
                    # manages it. The cameras table has no network_device_id column.
                    if category == "camera":
                        camera_update_params.append([instance_id, inventory_id, installation_id])
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

            # NOTE: we intentionally do NOT delete rows with canvas_instance_id IS
            # NULL here. That cleanup used to run on every export to purge legacy
            # "pre-fix" duplicate rows, but it cannot tell a legacy duplicate apart
            # from a legitimate physical device that exists in Inventory and simply
            # has no canvas link yet (e.g. created by the Inventory team, or loaded
            # from /sites/<id>/catalog/). As a result it hard-deleted real site
            # inventory on export, leaving the site catalog empty.
            #
            # New duplicates can no longer accumulate: canvas-originated devices are
            # inserted with a non-null canvas_instance_id and de-duplicated by the
            # unique key via ON DUPLICATE KEY UPDATE, and existing physical devices
            # are claimed via the inventory_id UPDATE path below. Any historical
            # NULL-canvas_instance_id duplicates must be cleaned by a one-time
            # migration, never by a blanket per-export DELETE.

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

            # ── Persist device IPs ─────────────────────────────────────────
            # A camera/other_device's IP lives on its linked network-host row
            # (devices.address), reached via {cameras|other_devices}.device_id —
            # the cameras/other_devices tables have no IP column of their own.
            # The canvas only carries the IP, so here we upsert that host row:
            # update the linked device's address, or create one (code='Other',
            # a valid value of the devices.code enum) and link it when the
            # device has no host yet. Without this the IP entered on the map
            # never reaches Inventory (the catalog reads devices.address).
            for dev in all_devices:
                ip = (dev.get("ip") or "").strip()
                if not ip:
                    continue
                instance_id = dev.get("instanceId") or dev.get("id")
                if not instance_id:
                    continue
                table = "cameras" if dev.get("category") == "camera" else "other_devices"
                cur.execute(
                    f"SELECT id, device_id FROM {table} "
                    f"WHERE installation_id = %s AND canvas_instance_id = %s AND deleted_at IS NULL "
                    f"ORDER BY id DESC LIMIT 1",
                    [installation_id, instance_id],
                )
                row = cur.fetchone()
                if row is None:
                    continue
                row_id, device_id = row
                if device_id:
                    cur.execute(
                        "UPDATE devices SET address = %s, updated_at = NOW() WHERE id = %s",
                        [ip, device_id],
                    )
                else:
                    host_name = (dev.get("view_name") or dev.get("name")
                                 or f"{table[:-1]}-{instance_id}")
                    cur.execute(
                        "INSERT INTO devices (name, code, address, site_id, created_at, updated_at) "
                        "VALUES (%s, 'Other', %s, %s, NOW(), NOW())",
                        [str(host_name)[:255], ip, site_id],
                    )
                    new_device_id = cur.lastrowid
                    cur.execute(
                        f"UPDATE {table} SET device_id = %s, updated_at = NOW() WHERE id = %s",
                        [new_device_id, row_id],
                    )

    # Fetch created devices and emit SSE events for real-time sync.
    # Also build id_remap: {canvas instanceId -> new "cam-<id>"/"device-<id>"} via
    # canvas_instance_id, so the frontend can repoint each design device's
    # catalogoId to the row that now backs it at this site. Without this the
    # design keeps referencing the source catalog IDs and won't render once
    # reopened with the destination site's catalog.
    created_device_ids = []
    id_remap: dict[str, str] = {}
    all_instance_ids = [
        (d.get("instanceId") or d.get("id")) for d in all_devices
        if (d.get("instanceId") or d.get("id"))
    ]
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

            if all_instance_ids:
                ph = ",".join(["%s"] * len(all_instance_ids))
                cur.execute(
                    f"SELECT canvas_instance_id, id FROM cameras "
                    f"WHERE installation_id = %s AND canvas_instance_id IN ({ph}) AND deleted_at IS NULL",
                    [installation_id, *all_instance_ids],
                )
                for canvas_iid, cam_id in cur.fetchall():
                    if canvas_iid:
                        id_remap[canvas_iid] = f"cam-{cam_id}"
                cur.execute(
                    f"SELECT canvas_instance_id, id FROM other_devices "
                    f"WHERE installation_id = %s AND canvas_instance_id IN ({ph}) AND deleted_at IS NULL",
                    [installation_id, *all_instance_ids],
                )
                for canvas_iid, dev_id in cur.fetchall():
                    if canvas_iid:
                        id_remap[canvas_iid] = f"device-{dev_id}"
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
        "numbering": numbering,
        "renumbered": renumbered,
        "id_remap": id_remap,
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

    # Site lifecycle status: the client sends a status NAME (e.g. "Installing",
    # "Live Testing") under `status`/`site_status`. Resolve it to the FK id in
    # site_statuses and write sites.site_status_id. We never invent rows — an
    # unknown name is rejected so the column only ever holds valid statuses.
    status_name = data.get("site_status") or data.get("status")
    if status_name:
        with connections[_DB].cursor() as cur:
            cur.execute(
                "SELECT id FROM site_statuses WHERE LOWER(status_name) = LOWER(%s) LIMIT 1",
                [status_name.strip()],
            )
            row = cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown site status: {status_name!r}")
        updates["site_status_id"] = row[0]

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


def analyze_topology(devices, connections, check: dict | None = None) -> dict:
    """
    Full topology analysis: validate + build_tree + cascade + optional connection check.
    check = {source: str, target: str} to validate a proposed new connection.
    """
    from apps.installations import topology

    return topology.analyze(list(devices), list(connections), check)


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

    # Protect the canvas layout: mirror it into the `design` column, but ONLY when
    # the incoming payload actually carries a design (devices/drawings/floorPlans).
    # A blanking save (empty layout — e.g. a failed load followed by an auto-save)
    # therefore leaves the last good `design` snapshot untouched, so the layout is
    # never lost and get_sig_project() can recover it. Raw SQL because `design`
    # lives only in the DB (kept out of the model to avoid migration drift).
    if data.get("devices") or data.get("drawings") or data.get("floorPlans"):
        with connections["default"].cursor() as cur:
            cur.execute(
                "UPDATE sig_projects SET design = %s WHERE id = %s",
                [json.dumps(data), str(project_id)],
            )

    result = _project_to_dict(p)
    transaction.on_commit(lambda: _publish_project(result))
    return result, None


def delete_sig_project(project_id: str) -> bool:
    """Hard-deletes a SigProject. Returns False if not found."""
    from apps.installations.models import SigProject

    deleted_count, _ = SigProject.objects.filter(pk=project_id).delete()
    if deleted_count > 0:
        # Realtime: let other tabs drop it from their project list.
        _rt_publish(CH_PROJECTS, "project_deleted", {"id": str(project_id)})
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

    # Capture the original requester BEFORE clearing it — they receive the
    # cancellation notice. `requested_by` is whoever performed the cancel (admin).
    original_requester_id = project.approval_requested_by

    project.approval_status = "draft"
    project.approval_requested_by = None
    project.save(update_fields=["approval_status", "approval_requested_by", "updated_at"])

    result = _project_to_dict(project)
    canceller_name = _sigtools_users_by_ids({requested_by}).get(requested_by, {}).get("name") if requested_by else None

    transaction.on_commit(
        lambda: _notify_project_approval_cancelled(
            project=result,
            requester_id=original_requester_id,
            canceller_name=canceller_name,
            note=note,
        ),
    )
    transaction.on_commit(lambda: _publish_project(result))
    return result


# ===========================================================================
# Client presentation "guest link" — public read-only share of a SigProject
# ===========================================================================

# Fields of a device exposed to the (untrusted) client view. Anything not here
# is stripped — keep it to what's needed to RENDER the design, never internals.
_PRESENTATION_DEVICE_FIELDS = (
    "instanceId", "catalogoId", "numero", "displayLabel", "lat", "lng",
    "rotacionBase", "area", "varifocal_mm", "ptz_orientacion", "ptz_zoom",
    "alcance_metros", "sensorOverrides", "sitioId",
    # Optional per-unit price for the client proposal/BOM. Absent today (the
    # designer UI does not set it); the client view falls back to an estimate.
    "price",
)
_PRESENTATION_SITIO_FIELDS = ("id", "nombre", "lat", "lng", "zoom")
_PRESENTATION_DRAWING_FIELDS = (
    "id", "type", "coordinates", "color", "label", "sitioId", "layer", "radius", "text",
)


def _pick(d: dict, fields) -> dict:
    return {k: d[k] for k in fields if isinstance(d, dict) and k in d}


def _sanitize_pricing(pricing) -> dict | None:
    """Coerce a client {catalogoId: price} map into a clean {str: float} dict."""
    if not isinstance(pricing, dict):
        return None
    clean: dict[str, float] = {}
    for key, val in pricing.items():
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if num < 0:
            continue
        clean[str(key)[:64]] = round(num, 2)
    return clean or None


def set_sig_project_presentation_token(*, project_id: str, pricing=None) -> str | None:
    """
    Generate (or return the existing) guest-link token for a project. Optionally
    store per-model unit prices ({catalogoId: price}) that drive the client
    proposal/BOM. Pricing is refreshed on every call that supplies it.
    """
    from apps.installations.models import SigProject
    import uuid as _uuid

    try:
        project = SigProject.objects.get(pk=project_id)
    except SigProject.DoesNotExist:
        return None

    update_fields = ["updated_at"]
    if not project.presentation_token:
        project.presentation_token = _uuid.uuid4()
        update_fields.append("presentation_token")

    clean_pricing = _sanitize_pricing(pricing)
    if clean_pricing is not None:
        project.presentation_pricing = clean_pricing
        update_fields.append("presentation_pricing")

    project.save(update_fields=update_fields)
    return str(project.presentation_token)


def revoke_sig_project_presentation_token(*, project_id: str) -> bool:
    """Revoke the guest link (token → NULL). Returns False if not found."""
    from apps.installations.models import SigProject

    try:
        project = SigProject.objects.get(pk=project_id)
    except SigProject.DoesNotExist:
        return False

    project.presentation_token = None
    project.save(update_fields=["presentation_token", "updated_at"])
    return True


def get_sig_project_presentation(*, token: str) -> dict | None:
    """
    Resolve a project by its guest-link token and return a SANITIZED read-only
    payload (only what a client needs to view the design — no prices, no other
    projects, no internal metadata). Returns None if the token is invalid or
    revoked.
    """
    from apps.installations.models import SigProject
    import uuid as _uuid

    try:
        token_uuid = _uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        return None

    project = SigProject.objects.filter(presentation_token=token_uuid).first()
    if project is None:
        return None

    data = project.data or {}
    sitios = [_pick(s, _PRESENTATION_SITIO_FIELDS) for s in (data.get("sitios") or []) if isinstance(s, dict)]
    devices = [_pick(d, _PRESENTATION_DEVICE_FIELDS) for d in (data.get("devices") or []) if isinstance(d, dict)]
    drawings = [_pick(dr, _PRESENTATION_DRAWING_FIELDS) for dr in (data.get("drawings") or []) if isinstance(dr, dict)]

    # Attach the admin-set unit price (per catalogoId) so the client BOM shows
    # real prices. Pricing entered at link time is the source of truth.
    pricing = project.presentation_pricing or {}
    if isinstance(pricing, dict):
        for dev in devices:
            price = pricing.get(str(dev.get("catalogoId")))
            if price is not None:
                dev["price"] = price

    return {
        "id": str(project.id),
        "name": project.name,
        "sitios": sitios,
        "devices": devices,
        "drawings": drawings,
    }


# Max length of the base64 signature image we accept (~350 KB data URL). Guards
# against an oversized/abusive payload on this public, unauthenticated endpoint.
_SIGNATURE_DATAURL_MAX = 350_000


def save_sig_project_presentation_signature(
    *, token: str, signature: dict, ip: str | None = None, user_agent: str | None = None
) -> bool:
    """
    Record a client's electronic signature (ESIGN/UETA) against the project
    resolved by its guest-link token. Public/unauthenticated — the token is the
    authorization. Returns False if the token is invalid/revoked or the payload
    fails validation. Stores a sanitized record (whitelisted keys only).
    """
    from apps.installations.models import SigProject
    from django.utils import timezone
    import uuid as _uuid

    try:
        token_uuid = _uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        return False

    if not isinstance(signature, dict):
        return False

    signer = str(signature.get("signerName", "")).strip()[:200]
    data_url = signature.get("signatureDataUrl", "")
    if not signer or not isinstance(data_url, str):
        return False
    if not data_url.startswith("data:image/") or len(data_url) > _SIGNATURE_DATAURL_MAX:
        return False

    project = SigProject.objects.filter(presentation_token=token_uuid).first()
    if project is None:
        return False

    # Whitelisted, server-stamped record — never trust client-supplied metadata.
    record = {
        "signerName": signer,
        "signatureDataUrl": data_url,
        "signedAt": timezone.now().isoformat(),
        "total": signature.get("total"),
        "currency": str(signature.get("currency", "USD"))[:8],
        "governingState": str(signature.get("governingState", ""))[:80],
        "ip": ip,
        "userAgent": (user_agent or "")[:400],
    }
    project.presentation_signature = record
    project.save(update_fields=["presentation_signature", "updated_at"])
    return True


# Accepted upload types and size cap for a manually-signed agreement copy.
_UPLOAD_ALLOWED_CT = {"application/pdf", "image/png", "image/jpeg"}
_UPLOAD_EXT = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}
_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def save_sig_project_presentation_uploaded_doc(
    *, token: str, file, signer_name: str = "", ip: str | None = None, user_agent: str | None = None
) -> str | None:
    """
    Store a manually-signed copy of the agreement (PDF/image) on MEDIA_ROOT and
    record it on the project resolved by its guest-link token. Returns the file
    URL, or None if the token/payload is invalid. Public/unauthenticated — the
    token is the authorization.
    """
    from apps.installations.models import SigProject
    from django.core.files.storage import default_storage
    from django.utils import timezone
    import uuid as _uuid

    try:
        token_uuid = _uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        return None

    if file is None:
        return None
    content_type = getattr(file, "content_type", "") or ""
    if content_type not in _UPLOAD_ALLOWED_CT:
        return None
    if getattr(file, "size", 0) > _UPLOAD_MAX_BYTES:
        return None

    project = SigProject.objects.filter(presentation_token=token_uuid).first()
    if project is None:
        return None

    ext = _UPLOAD_EXT.get(content_type, "bin")
    name = f"presentation-signatures/{token_uuid}/{_uuid.uuid4().hex}.{ext}"
    saved_path = default_storage.save(name, file)
    url = default_storage.url(saved_path)

    project.presentation_signature = {
        "signerName": str(signer_name).strip()[:200],
        "signedAt": timezone.now().isoformat(),
        "method": "uploaded",
        "uploadedDocUrl": url,
        "ip": ip,
        "userAgent": (user_agent or "")[:400],
    }
    project.save(update_fields=["presentation_signature", "updated_at"])
    return url


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
    # Push the site's freshly-recomputed aggregate progress INSIDE the event so
    # the front-end updates its dashboard from the stream alone — no follow-up
    # HTTP fetch (the old SSE→refetch behaved like polling under load).
    progress = None
    try:
        from apps.installations.selectors import get_all_sites_dispatch_progress
        rows = get_all_sites_dispatch_progress([dispatch.site_id])
        progress = rows[0] if rows else None
    except Exception:
        progress = None
    _rt_publish(CH_INSTALLATIONS, "dispatch_updated", [{
        "site_id":      dispatch.site_id,
        "device_id":    dispatch.device_id,
        "installed":    dispatch.installed,
        "qty_received": dispatch.qty_received,
        "qty_sent":     dispatch.qty_sent,
        "progress":     progress,
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


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

_NOMINATIM_UA = "SIGInstallations/1.0 (juan.riascos@sig.systems)"
_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"


def geocode_site(site_id: int) -> dict | None:
    """
    Returns {lat, lng, source} for a site or None if not resolvable.
    Cascade:
      1. DB lat/lon already stored
      2. Nominatim structured query (street+city+state+country — most precise)
      3. Nominatim free-form full address
      4. Nominatim free-form address only
      5. Nominatim city+state fallback
      6. US Census Geocoder (only when country=us/blank and Nominatim failed)
    Saves resolved coordinates back to project_sites. Cache key v2 so stale
    None results from the old logic are retried with the improved cascade.
    """
    import re as _re
    import httpx
    from apps.installations.models import ProjectSite

    cache_key = f"inst:geocode:site:v4:{site_id}"

    def _strip_unit(addr: str) -> str:
        """Remove apartment/suite/unit suffixes that confuse Nominatim."""
        return _re.sub(
            r",?\s*(suite|ste\.?|unit|apt\.?|#)\s*[\w-]+\s*$",
            "",
            addr,
            flags=_re.IGNORECASE,
        ).strip().rstrip(",").strip()

    def _extract_street(addr: str, city: str) -> str:
        """
        When address already contains city/state/ZIP (e.g. '4429 US-1, Fort Pierce, FL 34982'),
        extract only the street number+name for use in structured Nominatim queries.
        Looks for ', CITY' pattern (after a comma) to avoid matching city names that are
        part of the street name itself (e.g. '3281 Manor Way, Dallas, TX').
        """
        if not addr:
            return addr
        # Match ', CITY' after a comma separator (city appears as a distinct segment)
        if city:
            m_city = _re.search(r",\s*" + _re.escape(city) + r"\b", addr, flags=_re.IGNORECASE)
            if m_city:
                return addr[:m_city.start()].strip()
        # Fallback: truncate at ', STATE ZIP' or ', STATE, ZIP' pattern
        m = _re.search(r",\s*[A-Za-z]{2}\s+\d{5}(?:-\d{4})?\s*$", addr)
        if m:
            return addr[:m.start()].strip(", ").strip()
        # Fallback: truncate at standalone trailing ZIP
        m = _re.search(r",\s*\d{5}(?:-\d{4})?\s*$", addr)
        if m:
            trimmed = addr[:m.start()]
            m2 = _re.search(r",\s*[A-Za-z]{2}\s*$", trimmed)
            if m2:
                trimmed = trimmed[:m2.start()]
            return trimmed.strip(", ").strip()
        return addr

    def _nominatim_structured(address: str, city: str, state: str, country: str) -> tuple[float, float] | None:
        params = {
            "format": "json", "limit": 1,
            "street": address,
            "city": city,
            "state": state,
            "country": country or "us",
        }
        # Remove empty fields — Nominatim handles partial structured better than empty strings
        params = {k: v for k, v in params.items() if v}
        try:
            resp = httpx.get(
                f"{_NOMINATIM_BASE}/search",
                params=params,
                headers={"User-Agent": _NOMINATIM_UA},
                timeout=6.0,
            )
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as exc:
            logger.warning("[geocode] nominatim structured failed site=%s params=%s err=%s", site_id, params, exc)
        return None

    def _nominatim_free(query: str, country: str) -> tuple[float, float] | None:
        if not query:
            return None
        params: dict = {"format": "json", "limit": 1, "q": query}
        if country:
            params["countrycodes"] = country
        try:
            resp = httpx.get(
                f"{_NOMINATIM_BASE}/search",
                params=params,
                headers={"User-Agent": _NOMINATIM_UA},
                timeout=6.0,
            )
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as exc:
            logger.warning("[geocode] nominatim free failed site=%s q=%r err=%s", site_id, query, exc)
        return None

    def _census_geocode(address: str, city: str, state: str) -> tuple[float, float] | None:
        """US Census Bureau geocoder — free, no key, high precision for US street addresses."""
        query_str = ", ".join(filter(None, [address, city, state]))
        if not query_str:
            return None
        try:
            resp = httpx.get(
                "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                params={
                    "address": query_str,
                    "benchmark": "Public_AR_Current",
                    "format": "json",
                },
                timeout=8.0,
            )
            matches = resp.json().get("result", {}).get("addressMatches", [])
            if matches:
                coords = matches[0]["coordinates"]
                return float(coords["y"]), float(coords["x"])  # y=lat, x=lng
        except Exception as exc:
            logger.warning("[geocode] census geocoder failed site=%s q=%r err=%s", site_id, query_str, exc)
        return None

    def _compute():
        from apps.sigtools.models import Site as _SigtoolsSite

        # Check ProjectSite (linked via site_id FK) for already-stored coordinates.
        ps_row = (
            ProjectSite.objects.using(_DB)
            .filter(site_id=site_id, deleted_at__isnull=True)
            .values("id", "lat", "lon")
            .first()
        )
        if ps_row and ps_row["lat"] and ps_row["lon"]:
            return {"lat": float(ps_row["lat"]), "lng": float(ps_row["lon"]), "source": "db"}

        # Read address/city/state from the operational sites table.
        row = (
            _SigtoolsSite.objects.using(_DB)
            .filter(pk=site_id, deleted_at__isnull=True)
            .values("address", "city", "state_code", "country_code")
            .first()
        )
        if row is None:
            return None

        raw_address = (row.get("address") or "").strip()
        address = _strip_unit(raw_address)
        city    = (row.get("city") or "").strip()
        state   = (row.get("state_code") or "").strip()
        country = (row.get("country_code") or "us").strip().lower()

        # Detect if the address field already contains a full address (city/ZIP embedded).
        # When true, extract just the street portion for the structured query, and use
        # the address as-is for free-form queries (no need to append city/state again).
        is_full_address = bool(
            (city and city.lower() in address.lower())
            or _re.search(r"\b\d{5}\b", address)
        )
        street_only = _extract_street(address, city) if is_full_address else address

        result: tuple[float, float] | None = None
        source = "nominatim"

        # 1. Nominatim structured with clean street portion (most precise)
        if street_only and city:
            result = _nominatim_structured(street_only, city, state, country)

        # 2. Nominatim free-form — use address as-is if it's already a full address,
        #    otherwise assemble from fields.
        if not result:
            if is_full_address:
                full_q = address
            else:
                full_q = ", ".join(filter(None, [address, city, state, "USA" if country == "us" else country.upper()]))
            result = _nominatim_free(full_q, country)

        # 3. Nominatim free-form address only (handles edge cases where full_q failed)
        if not result and is_full_address and address != full_q:
            result = _nominatim_free(address, country)
        elif not result and not is_full_address and address:
            result = _nominatim_free(address, country)

        # 4. Nominatim city+state fallback
        if not result:
            city_state = ", ".join(filter(None, [city, state]))
            result = _nominatim_free(city_state, country)

        # 5. US Census Geocoder (US sites only, when all Nominatim attempts failed)
        if not result and country in ("us", "usa", ""):
            result = _census_geocode(address, city, state)
            if result:
                source = "census"

        if result:
            lat, lng = result
            if ps_row:
                ProjectSite.objects.using(_DB).filter(site_id=site_id).update(lat=lat, lon=lng)
            # Always persist on the operational sites row so the dashboard list
            # returns it and the map never has to geocode this site again.
            try:
                with connections[_DB].cursor() as cur:
                    cur.execute(
                        "UPDATE sites SET lat=%s, `long`=%s WHERE id=%s",
                        [lat, lng, site_id],
                    )
            except Exception as exc:
                logger.warning("[geocode] could not persist coords to sites %s: %s", site_id, exc)
            return {"lat": lat, "lng": lng, "source": source}

        logger.warning(
            "[geocode] site %s not resolved — address=%r city=%r state=%r country=%r",
            site_id, raw_address, city, state, country,
        )
        return None

    return cu.cached(cache_key, _compute, 86400)


def geocode_search(query: str, limit: int = 5) -> list[dict]:
    """
    Nominatim search proxy with Redis caching (TTL 1 h).
    Returns list of {lat, lon, display_name} matching the raw Nominatim shape.
    """
    import hashlib
    import httpx

    key_hash = hashlib.md5(f"{query.lower()}:{limit}".encode()).hexdigest()
    cache_key = f"inst:geocode:search:{key_hash}"

    def _compute():
        try:
            resp = httpx.get(
                f"{_NOMINATIM_BASE}/search",
                params={
                    "format": "json",
                    "limit": limit,
                    "q": query,
                    "countrycodes": "co,mx,pe,cl,ar,ec,ve,pa,us,es",
                    "addressdetails": 0,
                },
                headers={"User-Agent": _NOMINATIM_UA},
                timeout=5.0,
            )
            data = resp.json()
            return [
                {
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "display_name": r.get("display_name", ""),
                }
                for r in (data or [])
            ]
        except Exception:
            return []

    return cu.cached(cache_key, _compute, 3600)
