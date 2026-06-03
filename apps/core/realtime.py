"""
Pub/sub helper para tiempo real via Redis.

Uso (desde services.py o cualquier código sync):
    from apps.core.realtime import publish, CH_INSTALLATIONS, CH_PROJECTS, CH_INVENTORY
    publish(CH_INSTALLATIONS, "dispatch_updated", [{"site_id": 1, ...}])

Si Redis no está disponible, la escritura NO falla — se registra una advertencia.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis

from django.conf import settings

logger = logging.getLogger(__name__)

# Nombres de canales
CH_INSTALLATIONS = "rt:installations"
CH_PROJECTS = "rt:projects"
CH_INVENTORY = "rt:inventory"

_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=10,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _pool


def publish(channel: str, event: str, data) -> None:
    """
    Publica un evento en el canal Redis especificado.
    Best-effort: si Redis no está disponible no lanza excepción.
    """
    message = json.dumps({
        "event": event,
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    try:
        client = redis.Redis(connection_pool=_get_pool())
        client.publish(channel, message)
    except Exception as exc:
        logger.warning("realtime.publish failed (channel=%s, event=%s): %s", channel, event, exc)
