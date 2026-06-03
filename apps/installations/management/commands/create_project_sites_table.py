"""
Management command: creates / alters the project_sites table in sigtools_beta.

Usage:
    python manage.py create_project_sites_table           # CREATE IF NOT EXISTS
    python manage.py create_project_sites_table --drop    # DROP + recreate
    python manage.py create_project_sites_table --migrate # ALTER to add new columns only

project_sites is a pre-verification staging table that mirrors the relevant
columns of sites. Records are promoted to sites after passing verification
and authorization checks.

Verification/authorization lifecycle columns:
    verification_status  — pending | verified | rejected
    verified_by          — user_id (sigtools users) who verified
    verified_at          — timestamp of verification
    authorized_by        — user_id who gave final authorization
    authorized_at        — timestamp of authorization
    rejection_reason     — free-text reason when status = rejected
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connections

_DB = "sigtools"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS project_sites (
    id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_group_id       BIGINT UNSIGNED NOT NULL,
    it_backup_id            BIGINT UNSIGNED NULL DEFAULT NULL,
    it_responsible_id       BIGINT UNSIGNED NULL DEFAULT NULL,
    name                    VARCHAR(255) NOT NULL,
    ip_address              VARCHAR(250) NULL DEFAULT '0.0.0.0',
    state_code              VARCHAR(2)   NULL DEFAULT 'FL',
    country_code            VARCHAR(2)   NULL DEFAULT 'US',
    city                    VARCHAR(255) NULL DEFAULT NULL,
    address                 TEXT         NULL DEFAULT NULL,
    dealership_info         TEXT         NULL DEFAULT NULL,
    map_path                TEXT         NULL DEFAULT NULL,
    lat                     DOUBLE(11,8) NULL DEFAULT NULL,
    `long`                  DOUBLE(11,8) NULL DEFAULT NULL,
    circuit_is_https        INT(11)      NULL DEFAULT 0,
    circuit_status          INT(11)      NULL DEFAULT 3,
    site_subdomain          VARCHAR(255) NULL DEFAULT NULL,
    site_subdomain_status   ENUM('none','ok','error') NOT NULL DEFAULT 'none',
    monitored               TINYINT(1)   NOT NULL DEFAULT 1,
    maintenance             TINYINT(1)   NOT NULL DEFAULT 1,
    rental                  TINYINT(1)   NOT NULL DEFAULT 1,
    installation_date       DATE         NULL DEFAULT NULL,
    site_status_id          BIGINT UNSIGNED NULL DEFAULT 1,
    site_id                 BIGINT UNSIGNED NULL DEFAULT NULL,
    cameras_count           INT(11)      NOT NULL DEFAULT 0,
    preowned_cameras_count  INT(11)      NOT NULL DEFAULT 0,
    exterior_cameras_count  INT(11)      NOT NULL DEFAULT 0,
    teams_channelid         VARCHAR(255) NOT NULL DEFAULT '',
    teams_teamid            VARCHAR(255) NOT NULL DEFAULT '',
    timezone                VARCHAR(50)  NULL DEFAULT 'America/New_York',
    -- Lifecycle
    verification_status     ENUM('pending','verified','rejected') NOT NULL DEFAULT 'pending',
    created_by              BIGINT UNSIGNED NULL DEFAULT NULL,
    approval_requested_by   BIGINT UNSIGNED NULL DEFAULT NULL,
    verified_by             BIGINT UNSIGNED NULL DEFAULT NULL,
    verified_at             TIMESTAMP    NULL DEFAULT NULL,
    authorized_by           BIGINT UNSIGNED NULL DEFAULT NULL,
    authorized_at           TIMESTAMP    NULL DEFAULT NULL,
    rejection_reason        TEXT         NULL DEFAULT NULL,
    -- Timestamps
    created_at              TIMESTAMP    NULL DEFAULT NULL,
    updated_at              TIMESTAMP    NULL DEFAULT NULL,
    deleted_at              TIMESTAMP    NULL DEFAULT NULL,

    PRIMARY KEY (id),
    INDEX idx_ps_customer_group   (customer_group_id),
    INDEX idx_ps_it_backup        (it_backup_id),
    INDEX idx_ps_it_responsible   (it_responsible_id),
    INDEX idx_ps_site_status      (site_status_id),
    INDEX idx_ps_state_code       (state_code),
    INDEX idx_ps_timezone         (timezone),
    INDEX idx_ps_verification     (verification_status),
    INDEX idx_ps_created_by       (created_by),
    INDEX idx_ps_approval_req_by  (approval_requested_by),
    INDEX idx_ps_verified_by      (verified_by),
    INDEX idx_ps_authorized_by    (authorized_by),
    INDEX idx_ps_name             (name),
    INDEX idx_ps_deleted_at       (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

_DROP_SQL = "DROP TABLE IF EXISTS project_sites;"

# Idempotent ALTER — adds the new columns if missing (safe to re-run)
_MIGRATE_SQLS = [
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS site_id          BIGINT UNSIGNED NULL DEFAULT NULL AFTER site_status_id;",
    "ALTER TABLE project_sites ADD INDEX  IF NOT EXISTS idx_ps_site_id   (site_id);",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS created_by            BIGINT UNSIGNED NULL DEFAULT NULL AFTER verification_status;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS approval_requested_by BIGINT UNSIGNED NULL DEFAULT NULL AFTER created_by;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS verified_by     BIGINT UNSIGNED NULL DEFAULT NULL AFTER approval_requested_by;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS verified_at     TIMESTAMP       NULL DEFAULT NULL AFTER verified_by;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS authorized_by   BIGINT UNSIGNED NULL DEFAULT NULL AFTER verified_at;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS authorized_at   TIMESTAMP       NULL DEFAULT NULL AFTER authorized_by;",
    "ALTER TABLE project_sites ADD COLUMN IF NOT EXISTS rejection_reason TEXT            NULL DEFAULT NULL AFTER authorized_at;",
    "ALTER TABLE project_sites ADD INDEX IF NOT EXISTS idx_ps_created_by      (created_by);",
    "ALTER TABLE project_sites ADD INDEX IF NOT EXISTS idx_ps_approval_req_by (approval_requested_by);",
    "ALTER TABLE project_sites ADD INDEX IF NOT EXISTS idx_ps_verified_by   (verified_by);",
    "ALTER TABLE project_sites ADD INDEX IF NOT EXISTS idx_ps_authorized_by (authorized_by);",
]


class Command(BaseCommand):
    help = "Creates or migrates the project_sites staging table in sigtools_beta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop",
            action="store_true",
            help="Drop the table before recreating it (DESTROYS ALL DATA).",
        )
        parser.add_argument(
            "--migrate",
            action="store_true",
            help="Run ALTER statements only — add new columns to an existing table.",
        )

    def handle(self, *args, **options):
        with connections[_DB].cursor() as cur:
            if options["migrate"]:
                for sql in _MIGRATE_SQLS:
                    try:
                        cur.execute(sql)
                        self.stdout.write(f"  OK: {sql[:80]}…")
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(f"  SKIP: {exc}"))
                self.stdout.write(self.style.SUCCESS("project_sites migration complete."))
                return

            if options["drop"]:
                self.stdout.write(self.style.WARNING("Dropping project_sites…"))
                cur.execute(_DROP_SQL)

            cur.execute(_CREATE_SQL)

        self.stdout.write(self.style.SUCCESS("project_sites table is ready."))
