"""
Helpers de caché sobre Redis (django.core.cache).

El backend de caché está configurado con IGNORE_EXCEPTIONS=True, así que si
Redis no está disponible `cache.get_or_set` simplemente ejecuta la función y
devuelve el valor sin cachear — nunca rompe la request.

Uso:
    from apps.core import cache_utils as cu

    data = cu.cached("inst:sites_dashboard", _compute_sites, cu.TTL_DASHBOARD)
    cu.invalidate("inst:sites_dashboard", "inst:project_sites")
"""

from __future__ import annotations

from typing import Callable

from django.core.cache import cache

# TTLs (segundos)
TTL_DASHBOARD = 25   # lecturas dinámicas del dashboard (sigtools)
TTL_CATALOG = 600    # catálogos estáticos (modelos, tipos, grupos)


def cached(key: str, fn: Callable[[], object], ttl: int):
    """
    Devuelve el valor cacheado bajo `key`, o lo computa con `fn()` y lo cachea
    durante `ttl` segundos. Best-effort: si Redis falla, ejecuta `fn()` directo.
    """
    return cache.get_or_set(key, fn, ttl)


def invalidate(*keys: str) -> None:
    """Elimina las claves indicadas del caché (no falla si no existen)."""
    if not keys:
        return
    try:
        cache.delete_many(list(keys))
    except Exception:
        pass


# Claves del dashboard de installations (centralizadas para invalidación)
DASHBOARD_KEYS = (
    "inst:sites_dashboard",
    "inst:project_sites",
    "inst:dispatch_progress",
    "inst:ceo_dashboard",
)


def invalidate_dashboard() -> None:
    """Invalida las lecturas cacheadas del dashboard de installations."""
    invalidate(*DASHBOARD_KEYS)
