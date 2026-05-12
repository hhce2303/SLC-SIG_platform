"""
Services — business logic for the Installations API.
Write operations use raw SQL directly on 'sigtools' connection
to avoid model field mapping issues with unmanaged tables.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import connections, transaction

from apps.core.exceptions import ConflictError

_DB = "sigtools"

# Mapping from category string to table name — both for soft-delete and sync
_TABLE_MAP: dict[str, str] = {
    "camera": "cameras",
    "other": "other_devices",
    "core_device": "devices",
    "server": "servers",
}

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
    """
    with connections[_DB].cursor() as cur:
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
            except Exception:
                # Column may not exist in this schema version — skip silently
                pass

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
    return {
        "id": str(p.id),
        "name": p.name,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "version": p.version,
        "data": p.data,
    }


@transaction.atomic
def create_sig_project(project_id: str | None, name: str, data: dict) -> dict:
    """
    Creates a SigProject. Frontend may supply its own UUID.
    Raises ConflictError if the UUID already exists.
    """
    from apps.installations.models import SigProject

    pk = project_id or str(uuid.uuid4())
    if SigProject.objects.filter(pk=pk).exists():
        raise ConflictError("A project with this ID already exists.")
    p = SigProject.objects.create(id=pk, name=name, data=data, version=1)
    return _project_to_dict(p)


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
    return _project_to_dict(p), None


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
    return _project_to_dict(p)


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
                    INSERT INTO user_app_roles (user_id, role_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    """,
                    [user_id, rid],
                )

    return selectors.fetch_admin_user(user_id)


def update_admin_user(
    user_id: int,
    full_name: str | None,
    role_names: list[str] | None,
) -> dict | None:
    """
    Updates user profile and/or replaces role assignments.
    Returns None if user not found.
    """
    from apps.installations import selectors

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE id = %s AND deleted_at IS NULL",
                [user_id],
            )
            if not cur.fetchone():
                return None

            if full_name is not None:
                cur.execute(
                    "UPDATE users SET name = %s, updated_at = NOW() WHERE id = %s",
                    [full_name, user_id],
                )

            if role_names is not None:
                cur.execute(
                    "DELETE FROM user_app_roles WHERE user_id = %s",
                    [user_id],
                )
                role_ids = _resolve_role_ids(cur, role_names)
                for rid in role_ids:
                    cur.execute(
                        """
                        INSERT INTO user_app_roles (user_id, role_id, created_at, updated_at)
                        VALUES (%s, %s, NOW(), NOW())
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

    role_id = str(uuid.uuid4())

    with transaction.atomic(using=_ADMIN_DB):
        with connections[_ADMIN_DB].cursor() as cur:
            cur.execute("SELECT id FROM app_roles WHERE name = %s", [name])
            if cur.fetchone():
                raise ConflictError("A role with this name already exists.")

            cur.execute(
                """
                INSERT INTO app_roles (id, name, label, description, color, is_system, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 0, NOW(), NOW())
                """,
                [role_id, name, label, description, color],
            )

            perm_ids = _resolve_permission_ids(cur, permission_keys)
            for pid in perm_ids:
                cur.execute(
                    """
                    INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    """,
                    [role_id, pid],
                )

    return selectors.fetch_admin_role(role_id)


def update_admin_role(
    role_id: str,
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
            if not cur.fetchone():
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
                set_clauses.append("updated_at = NOW()")
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
                        INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
                        VALUES (%s, %s, NOW(), NOW())
                        """,
                        [role_id, pid],
                    )

    return selectors.fetch_admin_role(role_id)


def delete_admin_role(role_id: str) -> bool | str:
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
