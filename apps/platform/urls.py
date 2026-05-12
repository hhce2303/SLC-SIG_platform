from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.platform.views import PlatformLoginView, PlatformToolsView, StationConfigView

urlpatterns = [
    path("auth/login/", PlatformLoginView.as_view(), name="platform-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="platform-token-refresh"),
    path("station-config/", StationConfigView.as_view(), name="platform-station-config"),
    path("tools/", PlatformToolsView.as_view(), name="platform-tools"),
]
