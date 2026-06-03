"""
Poller central de tiempo real para tablas de sigtools_beta (BD externa).

Corre como proceso separado (un solo container/proceso). Cada N segundos
hace polling a las tablas de sigtools que NO controlamos (no pasan por
services.py) y publica diffs en Redis pub/sub.

Las tablas locales Django son publicadas por push desde services.py al
momento de la escritura — este poller no las toca.

Uso:
    python manage.py run_realtime_poller
    REALTIME_POLL_INTERVAL=10 python manage.py run_realtime_poller
"""

from __future__ import annotations

import os
import time
import logging

from django.core.management.base import BaseCommand
from django.db import connections

from apps.core.realtime import CH_INSTALLATIONS, CH_PROJECTS, publish

logger = logging.getLogger(__name__)


# Tablas de sigtools que emiten a rt:installations
_INSTALLATIONS_POLLS = [
    ("site_updated",          "sites",          "updated_at"),
    ("site_updated",          "project_sites",  "updated_at"),
    ("device_status_changed", "cameras",        "updated_at"),
    ("device_status_changed", "other_devices",  "updated_at"),
    ("article_updated",       "articles",       "last_mod"),
]

# Tablas de sigtools que emiten a rt:projects
_PROJECTS_POLLS = [
    ("installation_updated",  "installations",  "updated_at"),
    ("project_site_updated",  "project_sites",  "updated_at"),
]


class Command(BaseCommand):
    help = "Poller de tiempo real: vigila sigtools y publica diffs en Redis."

    def handle(self, *args, **options):
        interval = int(os.environ.get("REALTIME_POLL_INTERVAL", "5"))
        self.stdout.write(f"[poller] arrancando — intervalo={interval}s")
        logger.info("run_realtime_poller start, interval=%ss", interval)

        last_check_ts = _now_ts()

        while True:
            time.sleep(interval)
            now_ts = _now_ts()

            try:
                self._poll_installations(last_check_ts)
                self._poll_projects(last_check_ts)
            except Exception as exc:
                logger.warning("[poller] error en ciclo: %s", exc)

            last_check_ts = now_ts

    # ------------------------------------------------------------------
    def _poll_installations(self, since: str) -> None:
        emitted: dict[str, list] = {}
        try:
            with connections["sigtools"].cursor() as cur:
                for event_name, table, ts_col in _INSTALLATIONS_POLLS:
                    cur.execute(
                        f"SELECT COUNT(*) FROM `{table}` WHERE `{ts_col}` > %s",
                        [since],
                    )
                    count = cur.fetchone()[0]
                    if count:
                        emitted.setdefault(event_name, []).append(
                            {"table": table, "changed": count}
                        )
        except Exception as exc:
            logger.warning("[poller] sigtools installations poll error: %s", exc)
            return

        for event_name, entries in emitted.items():
            publish(CH_INSTALLATIONS, event_name, entries)

    def _poll_projects(self, since: str) -> None:
        try:
            with connections["sigtools"].cursor() as cur:
                for event_name, table, ts_col in _PROJECTS_POLLS:
                    cur.execute(
                        f"SELECT COUNT(*) FROM `{table}` WHERE `{ts_col}` > %s"
                        " AND deleted_at IS NULL",
                        [since],
                    )
                    count = cur.fetchone()[0]
                    if count:
                        publish(CH_PROJECTS, event_name, {})
        except Exception as exc:
            logger.warning("[poller] sigtools projects poll error: %s", exc)


def _now_ts() -> str:
    from django.utils import timezone
    return timezone.now().strftime("%Y-%m-%d %H:%M:%S")
