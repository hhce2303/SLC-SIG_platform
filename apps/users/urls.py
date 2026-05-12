from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import AvailableStationsView, LoginView, LogoutView, MeView, StatusView, UsernamesView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/status/", StatusView.as_view(), name="auth-me-status"),
    path("stations/available/", AvailableStationsView.as_view(), name="auth-stations-available"),
    path("usernames/", UsernamesView.as_view(), name="auth-usernames"),
]
