"""
Multi-database admin sites.

DailyLogAdminSite   — default admin, index shows the DB dashboard.
InventoryAdminSite  — dedicated admin for the inventory database.
SchedulesAdminSite  — dedicated admin for the schedules database.
SigtoolsAdminSite   — dedicated admin for the sigtools_beta database.
"""

from __future__ import annotations

from django.contrib.admin import AdminSite
from django.db import connections
from django.template.response import TemplateResponse


def _probe_db(alias: str, label: str, admin_url: str) -> dict:
    """Return connection status dict for a given database alias."""
    db_settings = connections[alias].settings_dict
    status = "offline"
    error = ""
    try:
        connections[alias].ensure_connection()
        status = "online"
    except Exception as exc:
        error = str(exc)
    return {
        "alias": alias,
        "label": label,
        "host": db_settings.get("HOST", ""),
        "name": db_settings.get("NAME", ""),
        "status": status,
        "error": error,
        "admin_url": admin_url,
    }


class DailyLogAdminSite(AdminSite):
    site_header = "Daily Logs Administration"
    site_title = "Daily Logs Admin"
    index_title = "Selecciona la base de datos"

    # --- index: show DB dashboard instead of app list -------------------

    def index(self, request, extra_context=None):
        # SIG Tools is the parent platform database
        sigtools = _probe_db("sigtools", "SIG Tools", "/admin/sigtools/")

        # Child product databases that live under SIG Tools
        sigtools["children"] = [
            _probe_db("default",   "Daily Logs",    "/admin/app-list/"),
            _probe_db("inventory", "Inventory",     "/admin/inventory/"),
            _probe_db("schedules", "Schedules",     "/admin/schedules/"),
            _probe_db("default",   "Installations", "/admin/installations/"),
        ]

        # Only show auth app (Users/Groups) in the sidebar on the dashboard
        all_apps = self.get_app_list(request)
        auth_apps = [a for a in all_apps if a["app_label"] == "auth"]

        ctx = {
            **self.each_context(request),
            "title": "Bases de Datos",
            "sigtools": sigtools,
            "available_apps": auth_apps,
        }
        if extra_context:
            ctx.update(extra_context)
        return TemplateResponse(request, "admin/db_dashboard.html", ctx)

    # --- app-list: the original model list page -------------------------

    def get_urls(self):
        from django.urls import path
        custom = [
            path(
                "app-list/",
                self.admin_view(self._app_list_view),
                name="app-list",
            ),
        ]
        return custom + super().get_urls()

    def _app_list_view(self, request, extra_context=None):
        """Render the standard Django admin index (model app list)."""
        return super().index(request, extra_context)


class InventoryAdminSite(AdminSite):
    site_header = "Inventory Administration"
    site_title = "Inventory Admin"
    index_title = "Inventory — Panel de Administración"

    def each_context(self, request):
        ctx = super().each_context(request)
        ctx["db_name"] = "inventory"
        return ctx


class SchedulesAdminSite(AdminSite):
    site_header = "Schedules Administration"
    site_title = "Schedules Admin"
    index_title = "Schedules — Panel de Administración"

    def each_context(self, request):
        ctx = super().each_context(request)
        ctx["db_name"] = "schedules"
        return ctx


class SigtoolsAdminSite(AdminSite):
    site_header = "SIG Tools Administration"
    site_title = "SIG Tools Admin"
    index_title = "SIG Tools — Panel de Administración"

    def each_context(self, request):
        ctx = super().each_context(request)
        ctx["db_name"] = "sigtools"
        return ctx


class InstallationsAdminSite(AdminSite):
    site_header = "Installations Administration"
    site_title = "Installations Admin"
    index_title = "Installations — Panel de Administración"

    def each_context(self, request):
        ctx = super().each_context(request)
        ctx["db_name"] = "default"
        return ctx


inventory_admin      = InventoryAdminSite(name="inventory_admin")
schedules_admin      = SchedulesAdminSite(name="schedules_admin")
sigtools_admin       = SigtoolsAdminSite(name="sigtools_admin")
installations_admin  = InstallationsAdminSite(name="installations_admin")
