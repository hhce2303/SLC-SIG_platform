"""
Multi-tenant scoping layer for sigtools_beta (T1 — multi-tenant foundation).

TENANT ROOT = `customer_groups`
-------------------------------
The tenant is `customer_groups` (apps.sigtools.models.CustomerGroup) — 24 real
clients that ALREADY own the physical assets: `sites.customer_group_id` is a hard
NOT NULL FK.

DIRECT vs DERIVED SCOPING
-------------------------
Every tenant-owned model declares a ``tenant_path`` — the ORM lookup from that
model to ``customer_groups.id``:

  * DIRECT  (own customer_group_id column):
            Site         -> "customer_group_id"  (hard FK already in DB)
            ArticleGroup -> "customer_group_id"  (customer-level categories)

  * DERIVED (reached via a FK chain, NO redundant column):
            Article      -> "site__customer_group_id"
            ActivityLog  -> "article__site__customer_group_id"
            Device       -> "site__customer_group_id"
            Installation -> "site__customer_group_id"
            Server       -> "site__customer_group_id"
            Camera       -> "device__site__customer_group_id"
            Event        -> "device__site__customer_group_id"
            OtherDevice  -> "installation__site__customer_group_id"

WHY Article is DERIVED (not DIRECT):
  An Article is a unique physical asset tracked per site (asset tracking with
  stock), not a shared catalog entry. It carries a ``site_id`` FK (added via
  scripts/add_customer_group_id_tenant_tables.sql) and derives its tenant through
  site -> customer_group — exactly like the physical chain. ArticleGroup (groups)
  are customer-level categories shared across sites, so they remain DIRECT.
  ActivityLog follows the article's site with a 3-level join — no column added.

WHY APP-LAYER ONLY
------------------
The DB is MySQL — there is NO PostgreSQL Row-Level Security. Tenant isolation is
enforced ENTIRELY here. There is no database backstop, so ``tenant_objects`` is
FAIL-CLOSED (raises when no tenant is active) and the isolation tests are a hard
P1 gate. A model with no ``tenant_path`` also fails closed.

THE TWO-MANAGER CONTRACT
------------------------
  * ``objects``        — UNFILTERED. Staff, management commands, migrations.
  * ``tenant_objects`` — SCOPED to the active customer_group, FAIL-CLOSED.

ACTIVATING / CROSS-REQUEST SAFETY
---------------------------------
A request activates its customer_group via ``tenant_scope(cg_id)`` /
``set_current_tenant(cg_id)`` (customer auth, T4, will do this). Nothing sets it
yet, so ``tenant_objects`` raises by design. ``TenantResetMiddleware`` resets the
contextvar on the way in AND out of every request so a tenant never leaks across
requests on a reused worker.
"""
from __future__ import annotations

import contextlib
import contextvars
from typing import Iterator, Optional

from django.db import models


class TenantScopeError(RuntimeError):
    """Raised when tenant-scoped data is accessed with no active tenant (or a
    model is missing tenant_path). FAIL-CLOSED: refuse rather than leak rows."""


_current_tenant_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "sigtools_current_customer_group_id", default=None
)


def set_current_tenant(customer_group_id: Optional[int]) -> contextvars.Token:
    return _current_tenant_id.set(customer_group_id)


def get_current_tenant() -> Optional[int]:
    return _current_tenant_id.get()


def clear_current_tenant(token: Optional[contextvars.Token] = None) -> None:
    if token is not None:
        _current_tenant_id.reset(token)
    else:
        _current_tenant_id.set(None)


@contextlib.contextmanager
def tenant_scope(customer_group_id: int) -> Iterator[None]:
    """Run a block scoped to ``customer_group_id`` (direct or derived path)."""
    token = set_current_tenant(customer_group_id)
    try:
        yield
    finally:
        clear_current_tenant(token)


class TenantManager(models.Manager):
    """Manager scoped to the active customer_group via the model's tenant_path.

    FAIL-CLOSED twice over: raises if no tenant is active, AND raises if the
    model declares no tenant_path (so a new tenant-owned model can't silently
    skip scoping).
    """

    def get_queryset(self) -> models.QuerySet:
        cg_id = get_current_tenant()
        if cg_id is None:
            raise TenantScopeError(
                f"{self.model.__name__}.tenant_objects used with no active tenant. "
                "Activate one with tenant_scope()/set_current_tenant() (customer "
                "auth does this), or use .objects for an intentional unscoped query."
            )
        path = getattr(self.model, "tenant_path", None)
        if not path:
            raise TenantScopeError(
                f"{self.model.__name__} is tenant-scoped but defines no tenant_path."
            )
        return super().get_queryset().filter(**{path: cg_id})


class TenantScopedModel(models.Model):
    """Abstract base for tenant-owned models reached via a FK chain (DERIVED).

    Subclasses MUST set ``tenant_path`` (e.g. "site__customer_group_id"). Adds
    NO column — the tenant is resolved through existing relations.
    """

    tenant_path: str = ""  # subclasses override; empty => fail-closed

    objects = models.Manager()        # UNFILTERED — staff/management/migrations
    tenant_objects = TenantManager()  # SCOPED, fail-closed — customer paths

    class Meta:
        abstract = True


class TenantDirectModel(TenantScopedModel):
    """Abstract base for tenant-owned models that carry their OWN
    customer_group_id column (DIRECT): sites + the inventory tables."""

    tenant_path = "customer_group_id"

    customer_group = models.ForeignKey(
        "sigtools.CustomerGroup",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        db_column="customer_group_id",
        related_name="+",
        null=True,   # nullable until Phase C of the SQL migration lands
        blank=True,
    )

    class Meta:
        abstract = True


class TenantResetMiddleware:
    """Reset the tenant contextvar in and out of every request so a tenant
    activated in one request never leaks into the next on a reused worker.
    Does NOT resolve the tenant (customer auth / T4 does that)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        clear_current_tenant()
        try:
            return self.get_response(request)
        finally:
            clear_current_tenant()
