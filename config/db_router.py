"""
Database routers.

InventoryRouter  — apps.inventory  → 'inventory' database.
SchedulesRouter  — apps.schedules  → 'schedules' database.
SigtoolsRouter   — apps.sigtools   → 'sigtools' database.
Everything else uses 'default'.
"""

from __future__ import annotations

INVENTORY_APP = "inventory"
SCHEDULES_APP = "schedules"


class SchedulesRouter:

    def db_for_read(self, model, **hints):
        if model._meta.app_label == SCHEDULES_APP:
            return "schedules"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == SCHEDULES_APP:
            return "schedules"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if SCHEDULES_APP in labels:
            return labels == {SCHEDULES_APP}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == SCHEDULES_APP:
            return db == "schedules"
        if db == "schedules":
            return False
        return None


class InventoryRouter:

    def db_for_read(self, model, **hints):
        if model._meta.app_label == INVENTORY_APP:
            return "inventory"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == INVENTORY_APP:
            return "inventory"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        db1 = "inventory" if obj1._meta.app_label == INVENTORY_APP else "default"
        db2 = "inventory" if obj2._meta.app_label == INVENTORY_APP else "default"
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == INVENTORY_APP:
            return db == "inventory"
        if db == "inventory":
            return False
        return None


SIGTOOLS_APP = "sigtools"


class SigtoolsRouter:

    def db_for_read(self, model, **hints):
        if model._meta.app_label == SIGTOOLS_APP:
            return "sigtools"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == SIGTOOLS_APP:
            return "sigtools"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if SIGTOOLS_APP in labels:
            return labels == {SIGTOOLS_APP}
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == SIGTOOLS_APP:
            return False  # read-only, never migrate
        if db == "sigtools":
            return False
        return None
