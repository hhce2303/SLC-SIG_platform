"""
Migration: Replace UUID/CHAR(36) PKs with INT AUTO_INCREMENT
Tables: app_roles, permissions, role_permissions, user_app_roles
Run: docker exec -i <container> python manage.py shell < migrate_int_pks.py
"""
from django.db import connections

DB = "sigtools"
conn = connections[DB]
conn.ensure_connection()
conn.set_autocommit(True)

with conn.cursor() as cur:
    # ── 1. Read current data ─────────────────────────────────────────────────
    cur.execute(
        "SELECT id, name, label, description, color, is_system, created_at "
        "FROM app_roles ORDER BY name"
    )
    old_roles = cur.fetchall()

    cur.execute(
        "SELECT id, `key`, label, description, app, category "
        "FROM permissions ORDER BY `key`"
    )
    old_perms = cur.fetchall()

    cur.execute("SELECT role_id, permission_id FROM role_permissions")
    old_rp = cur.fetchall()

    cur.execute("SELECT user_id, role_id, granted_at FROM user_app_roles")
    old_uar = cur.fetchall()

    role_map = {row[0]: i for i, row in enumerate(old_roles, 1)}
    perm_map = {row[0]: i for i, row in enumerate(old_perms, 1)}

    print(f"Snapshot: {len(old_roles)} roles, {len(old_perms)} perms, "
          f"{len(old_rp)} role_perms, {len(old_uar)} user_roles")
    for i, row in enumerate(old_roles, 1):
        print(f"  role {i}: {row[1]} ({row[0]})")

    # ── 2. Drop (FK-safe order) ───────────────────────────────────────────────
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in ("user_app_roles", "role_permissions", "app_roles", "permissions"):
        cur.execute(f"DROP TABLE IF EXISTS `{t}`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    print("Dropped old tables.")

    # ── 3. Create with INT PKs ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE app_roles (
            id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
            name        VARCHAR(100)  NOT NULL,
            label       VARCHAR(100)  NOT NULL DEFAULT '',
            description TEXT          NOT NULL,
            color       VARCHAR(50)   NOT NULL DEFAULT '',
            is_system   TINYINT(1)    NOT NULL DEFAULT 0,
            created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cur.execute("""
        CREATE TABLE permissions (
            id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
            `key`       VARCHAR(100)  NOT NULL,
            label       VARCHAR(255)  NOT NULL DEFAULT '',
            description TEXT          NOT NULL,
            app         VARCHAR(50)   NOT NULL DEFAULT '',
            category    VARCHAR(50)   NOT NULL DEFAULT '',
            PRIMARY KEY (id),
            UNIQUE KEY uk_key (`key`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cur.execute("""
        CREATE TABLE role_permissions (
            role_id       INT UNSIGNED NOT NULL,
            permission_id INT UNSIGNED NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            CONSTRAINT fk_rp_role FOREIGN KEY (role_id)
                REFERENCES app_roles(id) ON DELETE CASCADE,
            CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id)
                REFERENCES permissions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    cur.execute("""
        CREATE TABLE user_app_roles (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id    BIGINT       NOT NULL,
            role_id    INT UNSIGNED NOT NULL,
            granted_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_user_role (user_id, role_id),
            CONSTRAINT fk_uar_role FOREIGN KEY (role_id)
                REFERENCES app_roles(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("Created new tables.")

    # ── 4. Reseed app_roles ───────────────────────────────────────────────────
    for i, row in enumerate(old_roles, 1):
        cur.execute(
            "INSERT INTO app_roles "
            "(id, name, label, description, color, is_system, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [i, row[1], row[2] or '', row[3] or '', row[4] or '', row[5], row[6]],
        )
    print(f"Seeded {len(old_roles)} roles.")

    # ── 5. Reseed permissions ─────────────────────────────────────────────────
    for i, row in enumerate(old_perms, 1):
        cur.execute(
            "INSERT INTO permissions "
            "(id, `key`, label, description, app, category) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [i, row[1], row[2] or '', row[3] or '', row[4] or '', row[5] or ''],
        )
    print(f"Seeded {len(old_perms)} permissions.")

    # ── 6. Reseed role_permissions ────────────────────────────────────────────
    ok = 0
    for role_uuid, perm_uuid in old_rp:
        r = role_map.get(role_uuid)
        p = perm_map.get(perm_uuid)
        if r and p:
            cur.execute(
                "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
                [r, p],
            )
            ok += 1
        else:
            print(f"  WARN rp not mapped: role={role_uuid} perm={perm_uuid}")
    print(f"Seeded {ok} role_permissions.")

    # ── 7. Reseed user_app_roles ──────────────────────────────────────────────
    ok = 0
    for user_id, role_uuid, granted_at in old_uar:
        r = role_map.get(role_uuid)
        if r:
            cur.execute(
                "INSERT INTO user_app_roles (user_id, role_id, granted_at) VALUES (%s, %s, %s)",
                [user_id, r, granted_at],
            )
            ok += 1
        else:
            print(f"  WARN uar not mapped: user={user_id} role={role_uuid}")
    print(f"Seeded {ok} user_app_roles.")

print("Migration complete!")
