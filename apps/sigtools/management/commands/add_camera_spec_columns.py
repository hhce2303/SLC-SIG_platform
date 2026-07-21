"""
Management command: adds factory spec columns to camera_models in sigtools_beta.

sigtools_beta is legacy/read-only for Django (SigtoolsRouter.allow_migrate always
returns False for this app/db — see config/db_router.py), so these columns cannot
be added through a normal Django migration. This follows the same raw-DDL pattern
already used by apps/installations/management/commands/create_project_sites_table.py.

Usage:
    python manage.py add_camera_spec_columns           # dry-run: prints the DDL only
    python manage.py add_camera_spec_columns --yes      # actually applies it

Columns added (see docs/db/camera_models_schema.md for full reference):
    rango_lente_mm     JSON NULL   — [min, max] mm de distancia focal
    rango_fov_grados   JSON NULL   — [min, max] grados de FOV
    lens_type          VARCHAR(20) NULL — fixed | varifocal | hybrid
    poe_watts          FLOAT NULL
    bandwidth_mbps     FLOAT NULL
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connections

_DB = "sigtools"

_ALTER_SQLS = [
    "ALTER TABLE camera_models ADD COLUMN IF NOT EXISTS rango_lente_mm   JSON        NULL DEFAULT NULL;",
    "ALTER TABLE camera_models ADD COLUMN IF NOT EXISTS rango_fov_grados JSON        NULL DEFAULT NULL;",
    "ALTER TABLE camera_models ADD COLUMN IF NOT EXISTS lens_type        VARCHAR(20) NULL DEFAULT NULL;",
    "ALTER TABLE camera_models ADD COLUMN IF NOT EXISTS poe_watts        FLOAT       NULL DEFAULT NULL;",
    "ALTER TABLE camera_models ADD COLUMN IF NOT EXISTS bandwidth_mbps   FLOAT       NULL DEFAULT NULL;",
]


class Command(BaseCommand):
    help = "Adds factory lens/FOV/PoE/bandwidth spec columns to camera_models (sigtools_beta)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Actually run the ALTER TABLE statements. Without this flag, only prints the DDL.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stdout.write(self.style.WARNING(
                "Dry-run — no changes applied. Re-run with --yes to execute:\n"
            ))
            for sql in _ALTER_SQLS:
                self.stdout.write(f"  {sql}")
            return

        with connections[_DB].cursor() as cur:
            for sql in _ALTER_SQLS:
                cur.execute(sql)
                self.stdout.write(f"  OK: {sql[:90]}")

        self.stdout.write(self.style.SUCCESS("camera_models spec columns are ready."))
