"""
Read-only queries for catalog data.

Selectors never mutate state — they only return optimized querysets or dicts.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Min

from apps.core.models import Activity
from apps.sigtools.models import Site as SigtoolsSite


def get_all_sites() -> list[dict[str, Any]]:
    """
    Return all sites from sigtools_beta DB with ID concatenated to the name.

    Format: "ID - name"  (e.g. "5 - AS Koons Test")
    """
    return [
        {
            "id": site.pk,
            "site_name": f"{site.pk} - {site.name}",
        }
        for site in (
            SigtoolsSite.objects
            .filter(deleted_at__isnull=True)
            .only("id", "name")
            .order_by("name")
        )
    ]


def get_all_activities() -> list[dict[str, Any]]:
    """Return unique activities ordered by name (one canonical ID per name)."""
    return list(
        Activity.objects
        .values("act_name")
        .annotate(id=Min("id"))
        .order_by("act_name")
        .values("id", "act_name")
    )
