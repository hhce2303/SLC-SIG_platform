"""
Isolation tests for the multi-tenant scoping layer (T1).

These are the SECURITY GATE for tenancy. The DB is MySQL — there is NO RLS
backstop, so this app-layer logic is the ONLY thing standing between tenant A
and tenant B's rows. Tenant = customer_group. These tests are P1: they must
pass before any customer auth (T4) or customer portal (M2) ships.

No DB needed: the sigtools_beta models are `managed = False`, so the test runner
never creates their tables. We assert the SCOPING LOGIC instead — fail-closed
behavior, the manager contract, the compiled SQL WHERE clause, and contextvar
hygiene — which is deterministic and does not touch the external database.

Inventory scoping design (why Article is DERIVED, not DIRECT):
  ArticleGroup (groups): customer-level categories → DIRECT, customer_group_id.
  Article: unique physical asset tracked per site → DERIVED, site__customer_group_id.
  ActivityLog: follows the article's site → DERIVED, article__site__customer_group_id.
"""
from __future__ import annotations

from django.db import models as dj_models
from django.test import SimpleTestCase

from apps.sigtools import tenancy
from apps.sigtools.models import ActivityLog, Article, ArticleGroup, Device, Site
from apps.sigtools.tenancy import (
    TenantManager,
    TenantScopeError,
    clear_current_tenant,
    get_current_tenant,
    set_current_tenant,
    tenant_scope,
)


class TenantContextVarTests(SimpleTestCase):
    def tearDown(self):
        clear_current_tenant()  # never leak state between tests

    def test_default_is_no_tenant(self):
        self.assertIsNone(get_current_tenant())

    def test_tenant_scope_activates_and_resets(self):
        self.assertIsNone(get_current_tenant())
        with tenant_scope(42):
            self.assertEqual(get_current_tenant(), 42)
        # contextvar restored after the block — no leakage
        self.assertIsNone(get_current_tenant())

    def test_nested_scopes_restore_outer(self):
        with tenant_scope(1):
            self.assertEqual(get_current_tenant(), 1)
            with tenant_scope(2):
                self.assertEqual(get_current_tenant(), 2)
            self.assertEqual(get_current_tenant(), 1)
        self.assertIsNone(get_current_tenant())

    def test_set_then_clear(self):
        token = set_current_tenant(7)
        self.assertEqual(get_current_tenant(), 7)
        clear_current_tenant(token)
        self.assertIsNone(get_current_tenant())


class TenantManagerContractTests(SimpleTestCase):
    def tearDown(self):
        clear_current_tenant()

    def test_objects_is_plain_unfiltered_manager(self):
        # The default manager must stay unfiltered for staff/management/migrations.
        self.assertIsInstance(ArticleGroup.objects, dj_models.Manager)
        self.assertNotIsInstance(ArticleGroup.objects, TenantManager)

    def test_tenant_objects_is_tenant_manager(self):
        self.assertIsInstance(ArticleGroup.tenant_objects, TenantManager)
        self.assertIsInstance(Site.tenant_objects, TenantManager)
        self.assertIsInstance(Article.tenant_objects, TenantManager)
        self.assertIsInstance(ActivityLog.tenant_objects, TenantManager)

    def test_tenant_objects_fail_closed_without_tenant(self):
        # FAIL-CLOSED: with no active tenant, scoped access must RAISE, never
        # return every tenant's rows (the MySQL no-RLS default).
        with self.assertRaises(TenantScopeError):
            list(ArticleGroup.tenant_objects.all())
        with self.assertRaises(TenantScopeError):
            Site.tenant_objects.all()  # raised eagerly in get_queryset
        with self.assertRaises(TenantScopeError):
            Article.tenant_objects.all()

    def test_fail_closed_message_names_the_model(self):
        with self.assertRaises(TenantScopeError) as ctx:
            ArticleGroup.tenant_objects.all()
        self.assertIn("ArticleGroup", str(ctx.exception))

    def test_direct_model_scopes_sql_by_own_column(self):
        # DIRECT model (ArticleGroup has its own customer_group_id): filter is on
        # the table's own column, no join needed.
        with tenant_scope(99):
            sql = str(ArticleGroup.tenant_objects.all().query)
        self.assertIn("customer_group_id", sql)
        self.assertIn("99", sql)

    def test_article_is_derived_via_site(self):
        # Article is a physical asset tracked per site — DERIVED, not DIRECT.
        # The compiled SQL must JOIN sites and filter sites.customer_group_id,
        # proving that articles carry site_id (not a redundant customer_group_id).
        self.assertEqual(Article.tenant_path, "site__customer_group_id")
        with tenant_scope(99):
            sql = str(Article.tenant_objects.all().query).lower()
        self.assertIn("customer_group_id", sql)
        self.assertIn("99", sql)
        self.assertIn("sites", sql)  # the join target

    def test_activity_log_is_derived_via_article_site(self):
        # ActivityLog derives tenant 3 levels deep: article -> site -> customer_group.
        # No column added to activity_logs — pure join, no redundancy.
        self.assertEqual(ActivityLog.tenant_path, "article__site__customer_group_id")
        with tenant_scope(99):
            sql = str(ActivityLog.tenant_objects.all().query).lower()
        self.assertIn("customer_group_id", sql)
        self.assertIn("99", sql)
        self.assertIn("sites", sql)

    def test_derived_model_scopes_sql_via_join(self):
        # DERIVED model (Device derives tenant via site_id -> sites): the compiled
        # SQL must JOIN sites and filter sites.customer_group_id — proving the
        # normalized path works without a redundant column on devices.
        self.assertEqual(Device.tenant_path, "site__customer_group_id")
        with tenant_scope(99):
            sql = str(Device.tenant_objects.all().query).lower()
        self.assertIn("customer_group_id", sql)
        self.assertIn("99", sql)
        self.assertIn("sites", sql)  # the join target

    def test_objects_sql_has_no_tenant_filter(self):
        # The unfiltered manager must NOT inject a customer_group predicate.
        sql = str(ArticleGroup.objects.all().query).lower()
        self.assertNotIn("customer_group_id =", sql)

    def test_tenant_path_sanity(self):
        # Verify tenant_path declarations for every inventory and physical model.
        self.assertEqual(Site.tenant_path, "customer_group_id")
        self.assertEqual(ArticleGroup.tenant_path, "customer_group_id")
        self.assertEqual(Article.tenant_path, "site__customer_group_id")
        self.assertEqual(ActivityLog.tenant_path, "article__site__customer_group_id")
        self.assertEqual(Device.tenant_path, "site__customer_group_id")


class TenantResetMiddlewareTests(SimpleTestCase):
    def tearDown(self):
        clear_current_tenant()

    def test_middleware_clears_tenant_around_request(self):
        seen = {}

        def fake_view(request):
            # simulate a handler that activated a tenant mid-request
            set_current_tenant(123)
            seen["during"] = get_current_tenant()
            return "response"

        mw = tenancy.TenantResetMiddleware(fake_view)
        # tenant set before the request must be wiped on entry
        set_current_tenant(555)
        result = mw(request=object())

        self.assertEqual(result, "response")
        self.assertEqual(seen["during"], 123)
        # and cleared again on the way out — no leak into the next request
        self.assertIsNone(get_current_tenant())
