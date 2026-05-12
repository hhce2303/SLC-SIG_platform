from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from config.admin_sites import installations_admin, inventory_admin, schedules_admin, sigtools_admin


def health_check(request):
    return JsonResponse({"status": "ok"})


api_v1 = [
    path("health/", health_check, name="health-check"),
    path("auth/", include("apps.users.urls")),
    path("catalogs/", include("apps.core.urls")),
    path("events/", include("apps.logs.urls")),
    path("", include("apps.notifications.urls")),
    path("audit/", include("apps.audit.urls")),
    path("reports/", include("apps.reports.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("schedules/", include("apps.schedules.urls")),
    path("platform/", include("apps.platform.urls")),
    path("installations/", include("apps.installations.urls")),
    path("web-auth/", include("apps.sigtools_auth.urls")),
    path("chatbot/", include("apps.chatbot.urls")),
]

urlpatterns = [
    path("admin/inventory/",     inventory_admin.urls),
    path("admin/schedules/",     schedules_admin.urls),
    path("admin/sigtools/",      sigtools_admin.urls),
    path("admin/installations/", installations_admin.urls),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
