"""
Admin dashboard view — database switcher.

Shows connection status for each configured database and links to their
respective admin panels.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.db import connections
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse


@staff_member_required
def db_dashboard(request: HttpRequest) -> HttpResponse:
    databases = []
    for alias in ("default", "inventory"):
        db_settings = connections[alias].settings_dict
        status = "offline"
        error = ""
        try:
            conn = connections[alias]
            conn.ensure_connection()
            status = "online"
        except Exception as exc:
            error = str(exc)

        databases.append({
            "alias": alias,
            "label": "Daily Logs" if alias == "default" else "Inventory",
            "host": db_settings.get("HOST", ""),
            "name": db_settings.get("NAME", ""),
            "status": status,
            "error": error,
            "admin_url": "/admin/" if alias == "default" else "/admin/inventory/",
        })

    return TemplateResponse(request, "admin/db_dashboard.html", {
        "title": "Database Dashboard",
        "databases": databases,
    })
