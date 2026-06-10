from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config.admin_sites import installations_admin, inventory_admin, schedules_admin, sigtools_admin

# Vistas de OpenAPI sin restricción de auth para que funcionen en local y producción
_SCHEMA_VIEW = SpectacularAPIView.as_view(permission_classes=[])
_SWAGGER_VIEW = SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[])
_REDOC_VIEW = SpectacularRedocView.as_view(url_name="schema", permission_classes=[])


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
    path("sigtools/", include("apps.sigtools.urls")),
    path("layers/", include("apps.layers.urls")),
    path("chatbot/", include("apps.chatbot.urls")),
    path("codegen/", include("apps.codegen.urls")),
    path("test/", include("apps.test.urls")),
]

urlpatterns = [
    path("admin/inventory/",     inventory_admin.urls),
    path("admin/schedules/",     schedules_admin.urls),
    path("admin/sigtools/",      sigtools_admin.urls),
    path("admin/installations/", installations_admin.urls),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    # OpenAPI — accesibles sin autenticación tanto en local como en producción
    path("api/schema/", _SCHEMA_VIEW, name="schema"),
    path("api/docs/", _SWAGGER_VIEW, name="swagger-ui"),
    path("api/redoc/", _REDOC_VIEW, name="redoc"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
